"""
Normalizer Registry — Provides a clean interface for the Faust worker
to obtain the correct normalizer function for each source type.

Usage:
    from ...normalizers import get_normalizer
    normalizer = get_normalizer("auth_log")
    ecs_event = normalizer(raw_line)
"""

from typing import Callable, Union

from ...models import NormalizedEvent

from .auth_log_normalizer import normalize_auth_log
from .cicids_normalizer import normalize_cicids
from .cloudtrail_normalizer import normalize_cloudtrail
from .syslog_normalizer import normalize_syslog

# Type alias for normalizer functions
NormalizerFn = Callable[[Union[str, dict]], NormalizedEvent]

_REGISTRY: dict[str, NormalizerFn] = {
    "syslog": normalize_syslog,
    "cloudtrail": normalize_cloudtrail,
    "auth_log": normalize_auth_log,
    "auth": normalize_auth_log,  # alias
    "cicids": normalize_cicids,
}


def get_normalizer(source_type: str) -> NormalizerFn:
    """
    Return the normalizer function for the given source type.

    Raises:
        ValueError: if source_type is not registered.
    """
    normalizer = _REGISTRY.get(source_type.lower())
    if normalizer is None:
        raise ValueError(
            f"Unknown source type: '{source_type}'. "
            f"Available: {list(_REGISTRY.keys())}"
        )
    return normalizer


def list_source_types() -> list[str]:
    """Return all registered source types."""
    return list(_REGISTRY.keys())


__all__ = [
    "get_normalizer",
    "list_source_types",
    "normalize_syslog",
    "normalize_cloudtrail",
    "normalize_auth_log",
    "normalize_cicids",
]

