"""
External API service layer with resilience patterns
"""
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from circuitbreaker import circuit
from logging_config import get_logger
from exceptions import ExternalAPIException, ValidationException
from config import get_settings
from cache import cached

logger = get_logger(__name__)
settings = get_settings()


class BaseAPIClient:
    """Base class for API clients with common patterns"""
    
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self.client = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
            
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.RequestError)
    )
    @circuit(failure_threshold=5, recovery_timeout=60)
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Make HTTP request with retry and circuit breaker"""
        if not self.client:
            raise RuntimeError("Client not initialized. Use async context manager.")
            
        try:
            response = await self.client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise ExternalAPIException(
                self.__class__.__name__,
                f"HTTP {e.response.status_code}",
                e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise ExternalAPIException(
                self.__class__.__name__,
                str(e),
                503
            )


class OpenCurbClient(BaseAPIClient):
    """OpenCurb API client with caching"""
    
    def __init__(self):
        super().__init__(
            base_url=settings.opencurb_base_url,
            timeout=settings.opencurb_timeout
        )
        
    @cached(prefix="opencurb_data", ttl=300)
    async def get_parking_data(self, lat: float, lon: float, radius: int) -> List[Dict[str, Any]]:
        """Fetch parking data with caching"""
        
        # Validate coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            raise ValidationException("coordinates", "Invalid latitude or longitude")
            
        if not (50 <= radius <= 2000):
            raise ValidationException("radius", "Radius must be between 50 and 2000 meters")
            
        params = {
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "radius": radius
        }
        
        try:
            response = await self._make_request("GET", "/regulations", params=params)
            data = response.json()
            
            # Validate response structure
            if not isinstance(data, dict) or 'features' not in data:
                logger.warning("Unexpected OpenCurb response structure")
                return []
                
            features = data.get('features', [])
            logger.info(f"Retrieved {len(features)} parking segments from OpenCurb")
            
            return features
            
        except Exception as e:
            logger.error(f"OpenCurb API error: {e}")
            # Return empty list instead of failing completely
            return []


class NYCOpenDataClient(BaseAPIClient):
    """NYC Open Data API client"""
    
    def __init__(self):
        super().__init__(
            base_url="https://data.cityofnewyork.us",
            timeout=settings.nyc_opendata_timeout
        )
        
    @cached(prefix="nyc_signs", ttl=3600)
    async def get_parking_signs(self, bounds: Dict[str, float], limit: int = 1000) -> List[Dict]:
        """Fetch parking signs within bounds"""
        
        # Build SoQL query
        where_clause = (
            f"latitude >= {bounds['min_lat']} AND "
            f"latitude <= {bounds['max_lat']} AND "
            f"longitude >= {bounds['min_lon']} AND "
            f"longitude <= {bounds['max_lon']}"
        )
        
        params = {
            "$where": where_clause,
            "$limit": limit,
            "$order": "objectid"
        }
        
        try:
            response = await self._make_request(
                "GET", 
                "/resource/xswq-wnv9.json",
                params=params
            )
            
            signs = response.json()
            logger.info(f"Retrieved {len(signs)} parking signs from NYC Open Data")
            
            return signs
            
        except Exception as e:
            logger.error(f"NYC Open Data API error: {e}")
            return []


# Singleton instances
opencurb_client = OpenCurbClient()
nyc_opendata_client = NYCOpenDataClient()