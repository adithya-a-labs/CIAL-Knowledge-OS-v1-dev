"""Safe firewall command planning used by the Windows wrapper and tests."""

from __future__ import annotations

from dataclasses import dataclass


GROUP = "CIAL Knowledge OS LAN"
HTTP_RULE = "CIAL-LAN-HTTP"
MDNS_RULE = "CIAL-LAN-MDNS"


@dataclass(frozen=True)
class FirewallPlan:
    local_address: str
    subnet: str
    http_port: int
    mdns_enabled: bool
    discovery_program: str

    def rule_names(self) -> tuple[str, ...]:
        return (HTTP_RULE, MDNS_RULE) if self.mdns_enabled else (HTTP_RULE,)

