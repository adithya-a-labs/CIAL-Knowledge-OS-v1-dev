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


def _candidate(record: dict[str, Any]) -> tuple[int, list[str]] | None:
    status = str(record.get("status") or "").casefold()
    if status not in {"up", "connected"}:
        return None
    text = _text(record)
    if any(marker in text for marker in EXCLUDED_MARKERS):
        return None
    try:
        address = ipaddress.ip_address(str(record["address"]))
        prefix = int(record["prefix_length"])
    except (KeyError, TypeError, ValueError):
        return None
    if (
        address.version != 4
        or not address.is_private
        or address.is_loopback
        or address.is_link_local
        or not 1 <= prefix <= 32
    ):
        return None

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
    if str(record.get("profile_category") or "").casefold() == "private":
        score += 10
        reasons.append("private network profile")
    if str(record.get("media_type") or "").casefold() in {"native 802.11", "wireless lan"}:
        score += 5
        reasons.append("wireless media")
    if score < 60:
        return None
    return score, reasons


def select_hotspot_adapter(
    records: Iterable[dict[str, Any]],
    *,
    interface_override: str = "auto",
    ip_override: str = "auto",
) -> HotspotAdapter | None:
    prepared: list[tuple[int, dict[str, Any], list[str]]] = []
    interface_override_folded = interface_override.strip().casefold()
    ip_override_folded = ip_override.strip().casefold()
    for record in records:
        selection = _candidate(record)
        if selection is None:
            continue
        if interface_override_folded != "auto":
            alias = str(record.get("interface_alias") or "")
            index = str(record.get("interface_index") or "")
            if interface_override_folded not in {alias.casefold(), index.casefold()}:
                continue
        if ip_override_folded != "auto" and str(record.get("address")) != ip_override:
            continue
        score, reasons = selection
        if interface_override_folded != "auto":
            score += 1000
            reasons.append("explicit interface override")
        if ip_override_folded != "auto":
            score += 1000
            reasons.append("explicit IP override")
        prepared.append((score, record, reasons))

    if not prepared:
        return None
    prepared.sort(key=lambda item: item[0], reverse=True)
    if len(prepared) > 1 and prepared[0][0] == prepared[1][0]:
        aliases = ", ".join(str(item[1].get("interface_alias") or "?") for item in prepared[:2])
        raise RuntimeError(
            "Ambiguous hotspot adapters detected "
            f"({aliases}). Set CIAL_LAN_BIND_INTERFACE or CIAL_LAN_BIND_IP."
        )
    score, record, reasons = prepared[0]
    address = str(record["address"])
    prefix = int(record["prefix_length"])
    return HotspotAdapter(
        interface_alias=str(record.get("interface_alias") or ""),
        interface_index=int(record.get("interface_index") or 0),
        address=address,
        prefix_length=prefix,
        subnet=subnet_for(address, prefix),
        category="windows_mobile_hotspot",
        confidence="high" if score >= 80 else "medium",
        reason="; ".join(reasons),
    )

