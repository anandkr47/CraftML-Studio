"""
Worker event protocol (stdlib only: shared by the app and the remote worker bundle).

The worker prints one line per event::

    @@craftml {"v": 1, "type": "progress", ...}

Lines without the prefix are ordinary output and are treated as log text.
JSON is ASCII-escaped so no console code page (notably on Windows) can corrupt it.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

PROTOCOL_VERSION = 1
EVENT_PREFIX = "@@craftml "
EVENT_TYPES = ("log", "status", "progress", "metric", "telemetry", "artifact")


def encode(event_type: str, **fields: Any) -> str:
    """One event line (no trailing newline)."""
    payload = {"v": PROTOCOL_VERSION, "type": event_type}
    payload.update({k: v for k, v in fields.items() if v is not None})
    return EVENT_PREFIX + json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def decode(line: str) -> Optional[Dict[str, Any]]:
    """Parse an event line; None for plain output, malformed JSON or unknown protocol versions."""
    line = line.rstrip("\r\n")
    if not line.startswith(EVENT_PREFIX):
        return None
    try:
        payload = json.loads(line[len(EVENT_PREFIX):])
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("v") != PROTOCOL_VERSION or payload.get("type") not in EVENT_TYPES:
        return None
    return payload
