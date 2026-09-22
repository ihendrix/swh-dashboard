"""Small transformation helpers for the Software Heritage dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

_EXTENSION_RE_BYTES = re.compile(rb"\.([A-Za-z0-9]+)$")
_EXTENSION_RE_TEXT = re.compile(r"\.([A-Za-z0-9]+)$")


def decode_filename(value: Any) -> str | None:
    """Decode a filename value from the SWH Parquet dataset safely."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value)


def extract_extension(value: Any) -> str | None:
    """Return the final alphanumeric extension, lower-cased and without a dot.

    This mirrors the paper's deliberately lax first-pass extension heuristic:
    take the alphanumeric sequence after the last dot and filter later.
    """
    if value is None:
        return None

    if isinstance(value, (bytes, bytearray, memoryview)):
        match = _EXTENSION_RE_BYTES.search(bytes(value))
        if not match:
            return None
        return match.group(1).decode("ascii").lower()

    match = _EXTENSION_RE_TEXT.search(str(value))
    if not match:
        return None
    return match.group(1).lower()


def timestamp_to_year(value: Any) -> int | None:
    """Convert a Unix-like integer timestamp to a UTC year.

    The published aggregated table exposes the timestamp as BIGINT. This helper
    accepts seconds, milliseconds, microseconds, or nanoseconds based on
    magnitude, which keeps the demo robust across export/display conventions.
    """
    if value is None:
        return None
    try:
        raw = int(value)
    except (TypeError, ValueError, OverflowError):
        return None

    magnitude = abs(raw)
    if magnitude < 100_000_000_000:  # seconds
        seconds = raw
    elif magnitude < 100_000_000_000_000:  # milliseconds
        seconds = raw / 1_000
    elif magnitude < 100_000_000_000_000_000:  # microseconds
        seconds = raw / 1_000_000
    else:  # nanoseconds
        seconds = raw / 1_000_000_000

    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).year
    except (OverflowError, OSError, ValueError):
        return None
