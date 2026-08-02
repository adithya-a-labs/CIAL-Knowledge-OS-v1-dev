"""Interface-scoped mDNS lifecycle."""

from __future__ import annotations

import socket
from typing import Any


class MdnsPublisher:
    def __init__(self) -> None:
        self.zeroconf: Any = None
        self.info: Any = None

    def register(self, *, domain: str, address: str, port: int, scheme: str) -> str:
        from zeroconf import IPVersion, NonUniqueNameException, ServiceInfo, Zeroconf

        selected = domain
        service_type = "_https._tcp.local." if scheme == "https" else "_http._tcp.local."
        for suffix in ("", "-2"):
            candidate = domain if not suffix else f"{domain.removesuffix('.local')}{suffix}.local"
            info = ServiceInfo(
                service_type,
                f"CIAL Knowledge OS{suffix}.{service_type}",
                addresses=[socket.inet_aton(address)],
                port=port,
                server=f"{candidate}.",
                properties={"product": "cial-knowledge-os", "version": "0.1.0", "scheme": scheme},
            )
            zc = Zeroconf(interfaces=[address], ip_version=IPVersion.V4Only)
            try:
                zc.register_service(info, allow_name_change=False)
                self.zeroconf, self.info, selected = zc, info, candidate
                return selected
            except NonUniqueNameException:
                zc.close()
                continue
        raise RuntimeError("mDNS hostname conflict could not be resolved.")

    def unregister(self) -> None:
        if self.zeroconf is not None:
            try:
                if self.info is not None:
                    self.zeroconf.unregister_service(self.info)
            finally:
                self.zeroconf.close()
        self.zeroconf = None
        self.info = None
