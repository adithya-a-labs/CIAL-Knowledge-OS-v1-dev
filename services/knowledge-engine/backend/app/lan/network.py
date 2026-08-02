"""Fail-closed Windows hotspot adapter selection."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from typing import Any, Iterable


EXCLUDED_MARKERS = (
    "bluetooth",
    "docker",
    "hyper-v",
    "loopback",
    "openvpn",
    "tailscale",
    "tap-",
    "teredo",
    "tunnel",
    "virtualbox",
    "vmware",
    "vpn",
    "wintun",
    "wireguard",
    "wsl",
)


class HotspotSelectionError(RuntimeError):
    """Safe, actionable adapter-selection failure."""

    def __init__(self, code: str, safe_detail: str) -> None:
        super().__init__(safe_detail)
        self.code = code
        self.safe_detail = safe_detail


@dataclass(frozen=True)
class HotspotAdapter:
    interface_alias: str
    interface_index: int
    address: str
    prefix_length: int
    subnet: str
    category: str
    confidence: str
    reason: str


def subnet_for(address: str, prefix_length: int) -> str:
    return str(ipaddress.ip_network(f"{address}/{prefix_length}", strict=False))


def _text(record: dict[str, Any]) -> str:
    return " ".join(
        str(record.get(key) or "")
        for key in ("interface_alias", "name", "description", "interface_description")
    ).casefold()


def _safe_record(record: dict[str, Any], *, exclude_virtual: bool) -> bool:
    if str(record.get("status") or "").casefold() not in {"up", "connected"}:
        return False
    if exclude_virtual and any(marker in _text(record) for marker in EXCLUDED_MARKERS):
        return False
    try:
        address = ipaddress.ip_address(str(record["address"]))
        prefix = int(record["prefix_length"])
    except (KeyError, TypeError, ValueError):
        return False
    return bool(
        address.version == 4
        and address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_unspecified
        and 1 <= prefix <= 32
    )


def _adapter(record: dict[str, Any], *, category: str, confidence: str, reason: str) -> HotspotAdapter:
    address = str(record["address"])
    prefix = int(record["prefix_length"])
    return HotspotAdapter(
        interface_alias=str(record.get("interface_alias") or ""),
        interface_index=int(record.get("interface_index") or 0),
        address=address,
        prefix_length=prefix,
        subnet=subnet_for(address, prefix),
        category=category,
        confidence=confidence,
        reason=reason,
    )


def _explicit_selection(
    records: list[dict[str, Any]],
    *,
    interface_override: str,
    ip_override: str,
) -> HotspotAdapter:
    interface_explicit = interface_override.strip().casefold() != "auto"
    ip_explicit = ip_override.strip().casefold() != "auto"
    safe = [record for record in records if _safe_record(record, exclude_virtual=False)]

    interface_matches = records
    if interface_explicit:
        wanted = interface_override.strip().casefold()
        interface_matches = [
            record
            for record in records
            if wanted
            in {
                str(record.get("interface_alias") or "").strip().casefold(),
                str(record.get("interface_index") or "").strip().casefold(),
            }
        ]
        if not interface_matches:
            raise HotspotSelectionError(
                "explicit_interface_unavailable",
                "Configured LAN interface is unavailable.",
            )
        if not any(
            str(record.get("status") or "").casefold() in {"up", "connected"}
            for record in interface_matches
        ):
            raise HotspotSelectionError(
                "explicit_interface_down",
                "Configured LAN interface is not Up.",
            )

    if ip_explicit:
        try:
            wanted_ip = ipaddress.ip_address(ip_override.strip())
        except ValueError as exc:
            raise HotspotSelectionError(
                "explicit_ip_invalid", "Configured LAN IP is not a valid private IPv4 address."
            ) from exc
        if (
            wanted_ip.version != 4
            or not wanted_ip.is_private
            or wanted_ip.is_loopback
            or wanted_ip.is_link_local
            or wanted_ip.is_multicast
            or wanted_ip.is_unspecified
        ):
            raise HotspotSelectionError(
                "explicit_ip_unsafe", "Configured LAN IP is not a safe private IPv4 address."
            )

    matches = safe
    if interface_explicit:
        allowed_ids = {id(record) for record in interface_matches}
        matches = [record for record in matches if id(record) in allowed_ids]
        if not matches:
            raise HotspotSelectionError(
                "explicit_interface_no_safe_ip",
                "Configured LAN interface has no single safe private IPv4 address.",
            )
    if ip_explicit:
        matches = [record for record in matches if str(record.get("address") or "") == ip_override.strip()]
        if not matches:
            detail = (
                "Configured LAN IP is not assigned to the selected interface."
                if interface_explicit
                else "Configured LAN IP is not assigned to an available interface."
            )
            raise HotspotSelectionError("explicit_ip_not_assigned", detail)
    if len(matches) != 1:
        raise HotspotSelectionError(
            "explicit_binding_ambiguous",
            "Configured LAN binding matches multiple adapter records.",
        )
    return _adapter(
        matches[0],
        category="explicit_hotspot_binding",
        confidence="explicit",
        reason="matched configured LAN interface and IP",
    )


def _is_wireless(record: dict[str, Any]) -> bool:
    media = str(record.get("media_type") or "").casefold()
    text = _text(record)
    return media in {"native 802.11", "wireless lan"} or "wi-fi" in text or "wifi" in text


def _candidate(
    record: dict[str, Any],
    *,
    all_records: list[dict[str, Any]],
) -> tuple[int, list[str]] | None:
    if not _safe_record(record, exclude_virtual=True):
        return None
    address = ipaddress.ip_address(str(record["address"]))
    prefix = int(record["prefix_length"])
    text = _text(record)
    score = 0
    reasons: list[str] = ["up private IPv4 interface"]
    if bool(record.get("ics")):
        score += 100
        reasons.append("Windows connection-sharing evidence")
    if bool(record.get("nat")):
        score += 80
        reasons.append("matching Windows NAT prefix")
    if bool(record.get("wifi_direct")) or "wi-fi direct" in text:
        score += 60
        reasons.append("Wi-Fi Direct hotspot adapter")
    if str(address) == "192.168.137.1" and prefix == 24:
        score += 120
        reasons.append("common Windows Mobile Hotspot IPv4/prefix")
    if _is_wireless(record):
        score += 15
        reasons.append("wireless interface")
    if str(address).endswith(".1"):
        score += 20
        reasons.append("private gateway-like IPv4")
    upstream_exists = any(
        other is not record
        and _safe_record(other, exclude_virtual=True)
        and _is_wireless(other)
        and str(other.get("profile_category") or "").casefold() == "public"
        for other in all_records
    )
    if upstream_exists:
        score += 35
        reasons.append("separate public wireless uplink")
    if str(record.get("profile_category") or "").casefold() == "private":
        score += 10
        reasons.append("private network profile")
    if score < 60:
        return None
    return score, reasons


def select_hotspot_adapter(
    records: Iterable[dict[str, Any]],
    *,
    interface_override: str = "auto",
    ip_override: str = "auto",
) -> HotspotAdapter | None:
    available = list(records)
    interface_explicit = interface_override.strip().casefold() != "auto"
    ip_explicit = ip_override.strip().casefold() != "auto"
    if interface_explicit or ip_explicit:
        return _explicit_selection(
            available,
            interface_override=interface_override,
            ip_override=ip_override,
        )

    prepared: list[tuple[int, dict[str, Any], list[str]]] = []
    for record in available:
        selection = _candidate(record, all_records=available)
        if selection is not None:
            score, reasons = selection
            prepared.append((score, record, reasons))
    if not prepared:
        return None
    prepared.sort(key=lambda item: item[0], reverse=True)
    if len(prepared) > 1 and prepared[0][0] == prepared[1][0]:
        raise HotspotSelectionError(
            "automatic_detection_ambiguous",
            "Automatic hotspot detection is ambiguous. Configure a LAN interface or IP override.",
        )
    score, record, reasons = prepared[0]
    return _adapter(
        record,
        category="windows_mobile_hotspot",
        confidence="high" if score >= 80 else "medium",
        reason="; ".join(reasons),
    )
