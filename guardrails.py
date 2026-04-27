from __future__ import annotations

import re

from logger_config import setup_logger

logger = setup_logger("guardrails")


class ValidationError(Exception):
    """Raised when user-supplied input fails a guardrail check."""


def validate_duration(duration: int | float) -> int:
    if not isinstance(duration, (int, float)) or duration <= 0:
        logger.error("Invalid duration value: %r", duration)
        raise ValidationError(f"Duration must be a positive number (got {duration!r})")
    if duration > 480:
        logger.warning("Unusually long duration entered: %s minutes", duration)
    return int(duration)


def validate_priority(priority: int | float) -> int:
    if not isinstance(priority, (int, float)) or not (1 <= priority <= 10):
        logger.error("Invalid priority value: %r", priority)
        raise ValidationError(f"Priority must be between 1 and 10 (got {priority!r})")
    return int(priority)


def validate_time_format(time_str: str) -> str:
    if not re.fullmatch(r"\d{2}:\d{2}", time_str or ""):
        logger.error("Invalid time format: %r", time_str)
        raise ValidationError(f"Time must be HH:MM format (got {time_str!r})")
    h, m = map(int, time_str.split(":"))
    if not (0 <= h < 24 and 0 <= m < 60):
        logger.error("Time values out of range: %s", time_str)
        raise ValidationError(f"Time values out of range: {time_str}")
    return time_str


def validate_pet_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        logger.error("Empty pet name submitted")
        raise ValidationError("Pet name cannot be empty")
    if len(name) > 50:
        logger.warning("Pet name truncated from %d to 50 chars", len(name))
        name = name[:50]
    return name


def validate_time_available(minutes: int | float) -> int:
    if not isinstance(minutes, (int, float)) or minutes <= 0:
        logger.error("Invalid time_available: %r", minutes)
        raise ValidationError("Time available must be a positive number")
    if minutes > 1440:
        raise ValidationError("Time available cannot exceed 1440 minutes (24 hours)")
    return int(minutes)
