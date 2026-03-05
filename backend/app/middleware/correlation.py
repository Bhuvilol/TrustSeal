"""
Correlation ID Middleware

Adds correlation IDs to all HTTP requests for distributed tracing.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils.logging import set_correlation_id, clear_correlation_id, get_structured_logger

logger = get_structured_logger(__name__)


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation IDs to requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        correlation_id = set_correlation_id(correlation_id)

        # Add to request state for access in route handlers
        request.state.correlation_id = correlation_id

        # Track request timing
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log API request
            logger.log_api_request(
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_ip=request.client.host if request.client else None,
            )

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id

            return response

        except Exception as e:
            # Log error with correlation ID
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms,
                },
            )
            raise

        finally:
            # Clean up correlation ID from context
            clear_correlation_id()
