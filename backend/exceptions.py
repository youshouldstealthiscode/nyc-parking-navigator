"""
Custom exceptions and error handling
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from logging_config import get_logger

logger = get_logger(__name__)


class ParkingNavigatorException(Exception):
    """Base exception for application"""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ExternalAPIException(ParkingNavigatorException):
    """External API call failed"""
    def __init__(self, service: str, message: str, status_code: int = 503):
        super().__init__(
            f"External service error ({service}): {message}",
            status_code,
            {"service": service}
        )


class DataNotFoundException(ParkingNavigatorException):
    """Requested data not found"""
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            f"{resource} not found: {identifier}",
            404,
            {"resource": resource, "identifier": identifier}
        )


class ValidationException(ParkingNavigatorException):
    """Input validation failed"""
    def __init__(self, field: str, message: str):
        super().__init__(
            f"Validation error for {field}: {message}",
            422,
            {"field": field}
        )


class RateLimitException(ParkingNavigatorException):
    """Rate limit exceeded"""
    def __init__(self, limit: int, window: int):
        super().__init__(
            f"Rate limit exceeded: {limit} requests per {window} seconds",
            429,
            {"limit": limit, "window": window}
        )


async def exception_handler(request: Request, exc: ParkingNavigatorException) -> JSONResponse:
    """Handle custom exceptions"""
    
    # Log the exception
    logger.error(
        f"Exception occurred: {exc.message}",
        extra={
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    # Return structured error response
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "type": exc.__class__.__name__,
                "details": exc.details
            }
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions"""
    
    # Log the full exception
    logger.exception(
        "Unexpected exception occurred",
        extra={
            "path": request.url.path,
            "method": request.method
        }
    )
    
    # Return generic error response
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "An unexpected error occurred",
                "type": "InternalServerError"
            }
        }
    )