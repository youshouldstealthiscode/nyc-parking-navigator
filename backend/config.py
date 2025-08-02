"""
Configuration management for NYC Parking Navigator
Uses environment variables with sensible defaults
"""
from pydantic_settings import BaseSettings
from typing import Optional, List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with validation"""
    
    # API Configuration
    api_title: str = "NYC Parking Navigator API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    debug: bool = False
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # Database Configuration
    database_url: str = "postgresql://localhost/nyc_parking"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    
    # External APIs
    opencurb_base_url: str = "https://api.opencurb.nyc/v1"
    opencurb_timeout: int = 30
    nyc_opendata_timeout: int = 60
    
    # Caching
    redis_url: Optional[str] = None
    cache_ttl: int = 300  # 5 minutes
    
    # Security
    api_key_header: str = "X-API-Key"
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # 1 hour
    
    # CORS
    cors_origins: List[str] = ["*"]
    cors_credentials: bool = True
    cors_methods: List[str] = ["*"]
    cors_headers: List[str] = ["*"]
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Performance
    enable_compression: bool = True
    enable_cache_headers: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()