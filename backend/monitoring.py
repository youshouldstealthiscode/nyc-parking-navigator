"""
Application monitoring and metrics
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from functools import wraps
import time
from fastapi import Request, Response
from logging_config import get_logger

logger = get_logger(__name__)

# Define metrics
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

active_requests = Gauge(
    'http_requests_active',
    'Active HTTP requests'
)

parking_queries = Counter(
    'parking_queries_total',
    'Total parking queries',
    ['status']
)

cache_hits = Counter(
    'cache_hits_total',
    'Cache hit count',
    ['cache_type']
)

cache_misses = Counter(
    'cache_misses_total',
    'Cache miss count',
    ['cache_type']
)

external_api_calls = Counter(
    'external_api_calls_total',
    'External API calls',
    ['api', 'status']
)

external_api_duration = Histogram(
    'external_api_duration_seconds',
    'External API call duration',
    ['api']
)


class MetricsMiddleware:
    """Middleware to collect metrics"""
    
    async def __call__(self, request: Request, call_next):
        # Skip metrics endpoint
        if request.url.path == "/metrics":
            return await call_next(request)
            
        # Start timing
        start_time = time.time()
        
        # Track active requests
        active_requests.inc()
        
        # Process request
        try:
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            request_count.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()
            
            request_duration.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
            
            return response
            
        finally:
            active_requests.dec()


def track_external_api(api_name: str):
    """Decorator to track external API calls"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                external_api_calls.labels(api=api_name, status='success').inc()
                return result
                
            except Exception as e:
                external_api_calls.labels(api=api_name, status='error').inc()
                raise
                
            finally:
                duration = time.time() - start_time
                external_api_duration.labels(api=api_name).observe(duration)
                
        return wrapper
    return decorator


def track_cache(cache_type: str):
    """Decorator to track cache hits/misses"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Assuming None means cache miss
            if result is None:
                cache_misses.labels(cache_type=cache_type).inc()
            else:
                cache_hits.labels(cache_type=cache_type).inc()
                
            return result
        return wrapper
    return decorator


async def metrics_endpoint(request: Request) -> Response:
    """Prometheus metrics endpoint"""
    metrics = generate_latest()
    return Response(
        content=metrics,
        media_type="text/plain; version=0.0.4"
    )