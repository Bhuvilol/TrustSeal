"""
Structured Logging Utilities

Provides consistent structured logging across the application with:
- Correlation IDs for request tracing
- State transition logging
- Metric logging
- Error context
"""

import logging
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

# Context variable for correlation ID (thread-safe)
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set correlation ID for current context.
    
    Args:
        correlation_id: Optional correlation ID. If None, generates a new UUID.
        
    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get correlation ID from current context."""
    return correlation_id_var.get()


def clear_correlation_id() -> None:
    """Clear correlation ID from current context."""
    correlation_id_var.set(None)


class StructuredLogger:
    """Wrapper for standard logger that adds structured context."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _add_context(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add correlation ID and other context to log record."""
        context = extra or {}
        
        correlation_id = get_correlation_id()
        if correlation_id:
            context["correlation_id"] = correlation_id
            
        return context

    def debug(self, msg: str, **kwargs):
        """Log debug message with structured context."""
        extra = self._add_context(kwargs.pop("extra", None))
        self.logger.debug(msg, extra=extra, **kwargs)

    def info(self, msg: str, **kwargs):
        """Log info message with structured context."""
        extra = self._add_context(kwargs.pop("extra", None))
        self.logger.info(msg, extra=extra, **kwargs)

    def warning(self, msg: str, **kwargs):
        """Log warning message with structured context."""
        extra = self._add_context(kwargs.pop("extra", None))
        self.logger.warning(msg, extra=extra, **kwargs)

    def error(self, msg: str, **kwargs):
        """Log error message with structured context."""
        extra = self._add_context(kwargs.pop("extra", None))
        self.logger.error(msg, extra=extra, **kwargs)

    def exception(self, msg: str, **kwargs):
        """Log exception with structured context."""
        extra = self._add_context(kwargs.pop("extra", None))
        self.logger.exception(msg, extra=extra, **kwargs)

    def log_state_transition(
        self,
        entity_type: str,
        entity_id: str,
        from_state: str,
        to_state: str,
        **extra_context,
    ):
        """
        Log a state transition with structured context.
        
        Args:
            entity_type: Type of entity (e.g., "batch", "anchor", "telemetry_event")
            entity_id: ID of the entity
            from_state: Previous state
            to_state: New state
            **extra_context: Additional context fields
        """
        context = {
            "event_type": "state_transition",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "from_state": from_state,
            "to_state": to_state,
            **extra_context,
        }
        extra = self._add_context(context)
        self.logger.info(
            f"{entity_type} {entity_id}: {from_state} → {to_state}",
            extra=extra,
        )

    def log_metric(
        self,
        metric_name: str,
        value: float,
        unit: Optional[str] = None,
        **tags,
    ):
        """
        Log a metric with structured context.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Optional unit (e.g., "ms", "count", "bytes")
            **tags: Additional tags for the metric
        """
        context = {
            "event_type": "metric",
            "metric_name": metric_name,
            "metric_value": value,
            **tags,
        }
        if unit:
            context["metric_unit"] = unit
            
        extra = self._add_context(context)
        self.logger.info(
            f"Metric: {metric_name}={value}{unit or ''}",
            extra=extra,
        )

    def log_api_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        **extra_context,
    ):
        """
        Log an API request with structured context.
        
        Args:
            method: HTTP method
            path: Request path
            status_code: Response status code
            duration_ms: Request duration in milliseconds
            **extra_context: Additional context fields
        """
        context = {
            "event_type": "api_request",
            "http_method": method,
            "http_path": path,
            "http_status": status_code,
            "duration_ms": duration_ms,
            **extra_context,
        }
        extra = self._add_context(context)
        self.logger.info(
            f"{method} {path} {status_code} {duration_ms:.2f}ms",
            extra=extra,
        )


def get_structured_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger for the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(logging.getLogger(name))
