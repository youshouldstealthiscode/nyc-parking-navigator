# NYC Parking Navigator Backend Service - Refactored

from fastapi import FastAPI, HTTPException, Query, Depends, Request, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, time
import httpx
from geopy.distance import geodesic
import json
import re

# Import our modules
from config import get_settings, Settings
from logging_config import setup_logging, get_logger
from exceptions import (
    ParkingNavigatorException, ExternalAPIException,
    DataNotFoundException, ValidationException,
    exception_handler, generic_exception_handler
)
from cache import cache, cached
from services import opencurb_client, nyc_opendata_client

# Initialize
settings = get_settings()
setup_logging(settings.log_level, settings.log_format)
logger = get_logger(__name__)


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    logger.info("Starting NYC Parking Navigator API")
    
    # Startup tasks
    yield
    
    # Shutdown tasks
    logger.info("Shutting down NYC Parking Navigator API")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json"
)

# Add exception handlers
app.add_exception_handler(ParkingNavigatorException, exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

if settings.enable_compression:
    app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID for tracing"""
    import uuid
    request_id = str(uuid.uuid4())
    
    # Add to logger context
    logger.info(
        f"Request started: {request.method} {request.url.path}",
        extra={"request_id": request_id}
    )
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    logger.info(
        f"Request completed: {response.status_code}",
        extra={"request_id": request_id}
    )
    
    return response
# Enhanced Data models with validation
class Location(BaseModel):
    """Geographic location with validation"""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    
    @validator('latitude', 'longitude')
    def validate_coordinates(cls, v, field):
        """Ensure coordinates are valid"""
        if v is None:
            raise ValueError(f"{field.name} cannot be None")
        return round(v, 6)  # Limit precision

class ParkingSegment(BaseModel):
    """Parking segment with detailed information"""
    segment_id: str = Field(..., min_length=1)
    coordinates: List[List[float]]
    street_name: str
    side: str = Field(..., pattern="^(north|south|east|west|left|right|unknown)$")
    regulations: List[Dict[str, Any]]
    current_status: str
    status_color: str = Field(..., pattern="^(green|red|blue|yellow|gray)$")
    next_change: Optional[datetime] = None
    confidence_score: float = Field(default=1.0, ge=0, le=1)
    distance: Optional[float] = Field(default=None, description="Distance in meters from query location")

class ParkingQuery(BaseModel):
    """Query parameters for parking search"""
    location: Location
    radius_meters: int = Field(default=500, ge=50, le=2000, description="Search radius in meters")
    query_time: Optional[datetime] = Field(default_factory=datetime.now)
    
    @validator('query_time', pre=True, always=True)
    def set_query_time(cls, v):
        """Default to current time if not provided"""
        return v or datetime.now()

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    cache_status: str
    
# Parking rule parser - Refactored into a service
class ParkingRuleParser:
    """Advanced parking rule parser with caching"""
    
    def __init__(self):
        self.days_map = {
            'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 
            'FRI': 4, 'SAT': 5, 'SUN': 6,
            'MONDAY': 0, 'TUESDAY': 1, 'WEDNESDAY': 2, 
            'THURSDAY': 3, 'FRIDAY': 4, 'SATURDAY': 5, 'SUNDAY': 6
        }
        
        # Compiled regex patterns for performance
        self.time_pattern = re.compile(r'(\d{1,2}):?(\d{2})?\s*(AM|PM)')
        self.day_pattern = re.compile(
            r'(MON|TUE|WED|THU|FRI|SAT|SUN|MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)'
        )
        
    def parse_time_range(self, time_str: str) -> Optional[tuple]:
        """Parse time range with better error handling"""
        try:
            time_str = time_str.upper().strip()
            matches = self.time_pattern.findall(time_str)
            
            if len(matches) >= 2:
                start_time = self._parse_time_match(matches[0])
                end_time = self._parse_time_match(matches[1])
                return (start_time, end_time)
                
        except Exception as e:
            logger.warning(f"Failed to parse time range '{time_str}': {e}")
        
        return None
    
    def _parse_time_match(self, match: tuple) -> time:
        """Parse individual time from regex match"""
        hour = int(match[0])
        minute = int(match[1]) if match[1] else 0
        period = match[2]
        
        # Convert to 24-hour format
        if period == 'PM' and hour != 12:
            hour += 12
        elif period == 'AM' and hour == 12:
            hour = 0
            
        return time(hour, minute)    
    def parse_days(self, day_str: str) -> List[int]:
        """Parse day strings with improved logic"""
        days = []
        day_str = day_str.upper().strip()
        
        # Handle day ranges
        if any(word in day_str for word in ['THRU', 'THROUGH', '-']):
            parts = re.split(r'THRU|THROUGH|-', day_str)
            if len(parts) == 2:
                start_day = parts[0].strip()
                end_day = parts[1].strip()
                if start_day in self.days_map and end_day in self.days_map:
                    start_idx = self.days_map[start_day]
                    end_idx = self.days_map[end_day]
                    
                    # Handle week wraparound
                    if start_idx <= end_idx:
                        days = list(range(start_idx, end_idx + 1))
                    else:
                        days = list(range(start_idx, 7)) + list(range(0, end_idx + 1))
                        
        # Handle multiple days
        elif any(sep in day_str for sep in ['&', ',', 'AND']):
            day_parts = re.split(r'&|,|AND', day_str)
            for day in day_parts:
                day = day.strip()
                if day in self.days_map:
                    days.append(self.days_map[day])
                    
        # Single day
        else:
            matches = self.day_pattern.findall(day_str)
            for match in matches:
                if match in self.days_map:
                    days.append(self.days_map[match])
                    
        return sorted(list(set(days)))  # Remove duplicates and sort
    
    @cached(prefix="parking_rule", ttl=3600)
    async def parse_rule(self, rule_text: str) -> Dict[str, Any]:
        """Parse parking rule with caching"""
        if not rule_text:
            return {'original_text': '', 'type': 'UNKNOWN', 'parsed': False}
            
        rule_text = rule_text.upper().strip()
        
        # Determine rule type with priority
        rule_type = 'UNKNOWN'
        if 'NO STOPPING' in rule_text:
            rule_type = 'NO_STOPPING'
        elif 'NO STANDING' in rule_text:
            rule_type = 'NO_STANDING'
        elif 'NO PARKING' in rule_text:
            rule_type = 'NO_PARKING'
        elif 'STREET CLEANING' in rule_text:
            rule_type = 'STREET_CLEANING'
        elif re.search(r'\d+\s*HOUR\s*PARKING', rule_text):
            rule_type = 'METERED'
            match = re.search(r'(\d+)\s*HOUR', rule_text)
            hours_limit = int(match.group(1)) if match else None
        else:
            hours_limit = None
            
        # Extract time range
        time_pattern = r'(\d{1,2}:?\d{0,2}\s*[AP]M)\s*[-TO]+\s*(\d{1,2}:?\d{0,2}\s*[AP]M)'
        time_match = re.search(time_pattern, rule_text)
        time_range = self.parse_time_range(time_match.group()) if time_match else None
        
        # Extract days
        days = self.parse_days(rule_text)
        
        # Check for exceptions
        exceptions = []
        if 'EXCEPT' in rule_text:
            except_part = rule_text.split('EXCEPT')[1]
            exceptions = self.parse_days(except_part)
            
        return {
            'original_text': rule_text,
            'type': rule_type,
            'days': days,
            'time_range': time_range,
            'exceptions': exceptions,
            'hours_limit': hours_limit if rule_type == 'METERED' else None,
            'parsed': True,
            'confidence': 0.9 if rule_type != 'UNKNOWN' else 0.5
        }
# Initialize parser
parser = ParkingRuleParser()

# Parking business logic
class ParkingService:
    """Service layer for parking operations"""
    
    def __init__(self):
        self.parser = parser
        
    async def check_parking_availability(
        self, 
        regulations: List[Dict], 
        check_time: datetime
    ) -> tuple[bool, Optional[str], float]:
        """
        Check if parking is allowed at given time
        Returns: (allowed, restriction_type, confidence_score)
        """
        current_day = check_time.weekday()
        current_time = check_time.time()
        
        # Start with assumption that parking is allowed
        allowed = True
        restriction_type = None
        confidence_scores = []
        
        for rule in regulations:
            # Parse the rule if not already parsed
            if isinstance(rule, dict) and 'description' in rule:
                parsed = await self.parser.parse_rule(rule.get('description', ''))
            else:
                parsed = rule
                
            confidence_scores.append(parsed.get('confidence', 0.5))
            
            # Skip if rule doesn't apply to current day
            if parsed.get('days') and current_day not in parsed['days']:
                continue
                
            # Check exceptions (days when rule doesn't apply)
            if current_day in parsed.get('exceptions', []):
                continue
                
            # Check if rule applies to current time
            if parsed.get('time_range'):
                start_time, end_time = parsed['time_range']
                
                # Handle time ranges that cross midnight
                if start_time <= end_time:
                    time_applies = start_time <= current_time <= end_time
                else:
                    time_applies = current_time >= start_time or current_time <= end_time
                    
                if time_applies:
                    # Rule is active
                    rule_type = parsed.get('type')
                    if rule_type in ['NO_PARKING', 'NO_STANDING', 'NO_STOPPING', 'STREET_CLEANING']:
                        allowed = False
                        restriction_type = rule_type
                    elif rule_type == 'METERED':
                        restriction_type = 'METERED'
                        
        # Calculate average confidence
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
        
        return allowed, restriction_type, avg_confidence
    
    def get_next_status_change(
        self, 
        regulations: List[Dict], 
        current_time: datetime
    ) -> Optional[datetime]:
        """Calculate when parking status will change next"""
        # TODO: Implement logic to find next status change
        # This would analyze all rules and find the next time boundary
        return None
    
    def calculate_parking_segments(
        self,
        features: List[Dict],
        query_time: datetime,
        user_location: Optional[Location] = None
    ) -> List[ParkingSegment]:
        """Process raw parking data into segments"""
        segments = []
        
        for feature in features:
            if feature.get('type') != 'Feature':
                continue
                
            geometry = feature.get('geometry', {})
            properties = feature.get('properties', {})
            
            # Skip invalid geometries
            if not geometry.get('coordinates'):
                continue
                
            # Check parking availability
            regulations = properties.get('regulations', [])
            allowed, restriction_type, confidence = asyncio.run(
                self.check_parking_availability(regulations, query_time)
            )
            
            # Determine status and color
            if not allowed:
                status_color = 'red'
                current_status = restriction_type or 'NO_PARKING'
            elif restriction_type == 'METERED':
                status_color = 'blue'
                current_status = 'METERED'
            else:
                status_color = 'green'
                current_status = 'AVAILABLE'
                
            # Calculate distance if user location provided
            if user_location and geometry.get('coordinates'):
                coords = geometry['coordinates'][0]  # First point of line
                distance = geodesic(
                    (user_location.latitude, user_location.longitude),
                    (coords[1], coords[0])
                ).meters
            else:
                distance = None
                
            segment = ParkingSegment(
                segment_id=properties.get('id', f"seg_{hash(str(geometry))}"),
                coordinates=geometry.get('coordinates', []),
                street_name=properties.get('street_name', 'Unknown'),
                side=properties.get('side', 'unknown').lower(),
                regulations=regulations,
                current_status=current_status,
                status_color=status_color,
                next_change=self.get_next_status_change(regulations, query_time),
                confidence_score=confidence,
                distance=distance
            )
            
            segments.append(segment)
            
        # Sort by distance if available
        if user_location:
            segments.sort(key=lambda s: s.distance or float('inf'))
            
        return segments


# Initialize service
parking_service = ParkingService()
# Dependency injection
async def get_settings_dep() -> Settings:
    """Dependency for settings"""
    return settings

# API Endpoints
@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "message": "NYC Parking Navigator API",
        "version": settings.api_version,
        "docs": f"{settings.api_prefix}/docs"
    }

@app.get(
    f"{settings.api_prefix}/health",
    response_model=HealthResponse,
    tags=["General"]
)
async def health_check():
    """Health check endpoint with detailed status"""
    
    # Check cache status
    try:
        cache.set("health_check", "ok", ttl=5)
        cache_status = "healthy" if cache.get("health_check") == "ok" else "degraded"
    except:
        cache_status = "unavailable"
        
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version=settings.api_version,
        cache_status=cache_status
    )

@app.post(
    f"{settings.api_prefix}/parking/query",
    response_model=List[ParkingSegment],
    tags=["Parking"],
    summary="Query parking availability",
    description="Get parking segments for a location with real-time availability"
)
async def query_parking(
    query: ParkingQuery,
    settings: Settings = Depends(get_settings_dep)
) -> List[ParkingSegment]:
    """Query parking availability with caching and error handling"""
    
    logger.info(
        f"Parking query for location: {query.location.latitude}, {query.location.longitude}",
        extra={"radius": query.radius_meters, "time": query.query_time}
    )
    
    # Create cache key
    cache_key = f"parking_query:{query.location.latitude}:{query.location.longitude}:{query.radius_meters}:{query.query_time.hour}"
    
    # Try cache first
    cached_result = cache.get(cache_key)
    if cached_result:
        logger.info("Returning cached parking data")
        return cached_result
        
    try:
        # Fetch from OpenCurb
        async with opencurb_client as client:
            features = await client.get_parking_data(
                query.location.latitude,
                query.location.longitude,
                query.radius_meters
            )
            
        # Process segments
        segments = parking_service.calculate_parking_segments(
            features,
            query.query_time,
            query.location
        )
        
        # Cache results
        if segments:
            cache.set(cache_key, segments, ttl=300)
            
        logger.info(f"Processed {len(segments)} parking segments")
        
        return segments
        
    except ExternalAPIException as e:
        # Log but don't fail - try alternative sources
        logger.error(f"OpenCurb API failed: {e}")
        
        # TODO: Fallback to NYC Open Data
        return []
        
    except Exception as e:
        logger.exception("Unexpected error in parking query")
        raise ParkingNavigatorException(
            "Failed to process parking query",
            500,
            {"error": str(e)}
        )

@app.get(
    f"{settings.api_prefix}/parking/location/{{lat}}/{{lon}}",
    response_model=List[ParkingSegment],
    tags=["Parking"],
    summary="Get parking at specific location"
)
async def get_parking_at_location(
    lat: float = Path(..., ge=-90, le=90),
    lon: float = Path(..., ge=-180, le=180),
    radius: int = Query(default=200, ge=50, le=1000)
) -> List[ParkingSegment]:
    """Simplified endpoint for location-based parking query"""
    
    query = ParkingQuery(
        location=Location(latitude=lat, longitude=lon),
        radius_meters=radius
    )
    
    return await query_parking(query)

@app.get(
    f"{settings.api_prefix}/parking/rules/parse",
    tags=["Parking"],
    summary="Parse parking rule text"
)
async def parse_parking_rule(
    rule_text: str = Query(..., min_length=1, max_length=500)
) -> Dict[str, Any]:
    """Parse and analyze parking rule text"""
    
    if not rule_text.strip():
        raise ValidationException("rule_text", "Rule text cannot be empty")
        
    try:
        parsed = await parser.parse_rule(rule_text)
        return parsed
    except Exception as e:
        logger.error(f"Failed to parse rule: {e}")
        raise ParkingNavigatorException(
            "Failed to parse parking rule",
            400,
            {"rule_text": rule_text, "error": str(e)}
        )

@app.delete(
    f"{settings.api_prefix}/cache",
    tags=["Admin"],
    summary="Clear cache",
    include_in_schema=settings.debug  # Only show in debug mode
)
async def clear_cache(
    pattern: str = Query(default="*", description="Cache key pattern to clear")
) -> Dict[str, Any]:
    """Clear cached data"""
    
    deleted = cache.delete(pattern)
    logger.info(f"Cleared {deleted} cache entries with pattern: {pattern}")
    
    return {
        "status": "success",
        "deleted": deleted,
        "pattern": pattern
    }

# Error handlers for specific HTTP codes
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "message": "Resource not found",
                "path": str(request.url.path)
            }
        }
    )

@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    """Handle validation errors"""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "message": "Validation failed",
                "details": exc.errors() if hasattr(exc, 'errors') else str(exc)
            }
        }
    )

# Add startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info(f"Starting {settings.api_title} v{settings.api_version}")
    
    # Warm up cache
    cache.clear_expired()
    
    # Log configuration
    logger.info(f"Environment: {'DEBUG' if settings.debug else 'PRODUCTION'}")
    logger.info(f"Cache enabled: {settings.redis_url is not None}")
    logger.info(f"Rate limiting: {settings.rate_limit_enabled}")

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers,
        log_level=settings.log_level.lower()
    )