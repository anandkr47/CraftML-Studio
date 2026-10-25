"""
Timeouts and bounded retries with exponential backoff + jitter.

Only idempotent operations should be wrapped. ``TransientError.retry_after``
(from a 429/503 ``Retry-After`` header) overrides the computed delay.
"""

from __future__ import annotations

import random
import time
from email.utils import parsedate_to_datetime
from typing import Callable, Mapping, Optional, Tuple, Type, TypeVar

from core.cloud.errors import TransientError

T = TypeVar("T")

CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 60.0
DEFAULT_TIMEOUT: Tuple[float, float] = (CONNECT_TIMEOUT, READ_TIMEOUT)


def backoff_delay(attempt: int, base: float = 0.5, cap: float = 20.0, rng: Callable[[], float] = random.random) -> float:
    """Full-jitter backoff: uniform in [0, min(cap, base * 2**attempt)]."""
    return rng() * min(cap, base * (2 ** attempt))


def retry_after_seconds(headers: Mapping[str, str], now: Optional[float] = None) -> Optional[float]:
    """Parse ``Retry-After`` (delta-seconds or HTTP date); None if absent or invalid."""
    value = headers.get("Retry-After") or headers.get("retry-after")
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        target = parsedate_to_datetime(value).timestamp()
    except (TypeError, ValueError):
        return None
    return max(0.0, target - (time.time() if now is None else now))


def retry_call(
    fn: Callable[[], T],
    *,
    attempts: int = 4,
    retry_on: Tuple[Type[BaseException], ...] = (TransientError,),
    max_delay: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> T:
    """Call ``fn`` up to ``attempts`` times, sleeping between retryable failures."""
    for attempt in range(attempts):
        try:
            return fn()
        except retry_on as exc:
            if attempt == attempts - 1:
                raise
            hinted = getattr(exc, "retry_after", None)
            sleep(min(max_delay, hinted if hinted is not None else backoff_delay(attempt, rng=rng)))
    raise AssertionError("unreachable")  # pragma: no cover
