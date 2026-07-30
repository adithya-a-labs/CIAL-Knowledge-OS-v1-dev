"""Sanitized file-based LAN status projection."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


FIELDS = {
    "enabled",
    "mode",
    "gateway_ready",
    "discovery_ready",
    "hostname",
    "scheme",
    "port",
    "hotspot_detected",
    "bind_address_available",
    "ip_fallback_available",
    "tls_state",
    "firewall_state",
    "keep_awake",
    "checked_at",
    "safe_detail",
    "ip_fallback_url",
    "domain_url",
}


def disabled_status() -> dict[str, Any]:
    return {
        "enabled": False,
        "mode": "hotspot",
        "gateway_ready": False,
        "discovery_ready": False,
        "hostname": None,
        "scheme": "http",
        "port": None,
        "hotspot_detected": False,
        "bind_address_available": False,
        "ip_fallback_available": False,
        "tls_state": "unconfigured",
        "firewall_state": "unmanaged",
        "keep_awake": False,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "safe_detail": "LAN access is disabled.",
        "ip_fallback_url": None,
        "domain_url": None,
    }


def sanitize_status(payload: dict[str, Any]) -> dict[str, Any]:
    clean = disabled_status() | {key: payload.get(key) for key in FIELDS if key in payload}
    clean["safe_detail"] = str(clean.get("safe_detail") or "")[:300]
    for key in ("hostname", "scheme", "tls_state", "firewall_state"):
        value = clean.get(key)
        clean[key] = None if value is None else str(value)[:100]
    return clean


def read_status(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return disabled_status()
    return sanitize_status(value if isinstance(value, dict) else {})


def write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(sanitize_status(payload), indent=2), encoding="utf-8")
    temporary.replace(path)

