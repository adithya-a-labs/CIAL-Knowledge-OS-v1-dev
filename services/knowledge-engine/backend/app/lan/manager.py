"""Supervised optional Windows hotspot edge manager."""

from __future__ import annotations

import argparse
from contextlib import suppress
import csv
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import msvcrt
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.lan.discovery import MdnsPublisher
from backend.app.lan.gateway import GatewayConfig, render_caddyfile
from backend.app.lan.network import (
    HotspotAdapter,
    HotspotSelectionError,
    select_hotspot_adapter,
)
from backend.app.lan.power import KeepAwakeLease
from backend.app.lan.status import write_status


LOGGER = logging.getLogger("cial.lan")
_SID_PATTERN = re.compile(r"^S-\d(?:-\d+)+$")


class FirewallOperationError(RuntimeError):
    """Sanitized failure returned by the owned Windows firewall helper."""

    def __init__(self, *, state: str, error_code: str, safe_detail: str) -> None:
        super().__init__(safe_detail)
        self.state = state
        self.error_code = error_code
        self.safe_detail = safe_detail


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(name: str, **fields: Any) -> None:
    safe = {"event": name, "checked_at": _now()} | {
        key: value for key, value in fields.items() if key in {
            "mode", "port", "hostname", "state", "duration_ms", "error_code",
            "interface_category",
        }
    }
    LOGGER.info(json.dumps(safe, separators=(",", ":")))


def _probe_records(repo_root: Path) -> list[dict[str, Any]]:
    script = repo_root / "scripts" / "get_lan_adapter.ps1"
    completed = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(script),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    value = json.loads(completed.stdout or "[]")
    return value if isinstance(value, list) else [value]


def _detect(repo_root: Path) -> HotspotAdapter | None:
    return select_hotspot_adapter(
        _probe_records(repo_root),
        interface_override=settings.lan_bind_interface,
        ip_override=settings.lan_bind_ip,
    )


def _run_firewall(repo_root: Path, *, mode: str, adapter: HotspotAdapter, port: int) -> str:
    script = repo_root / "scripts" / "lan_firewall.ps1"
    arguments = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(script), "-Mode", mode,
        "-LocalAddress", adapter.address,
        "-RemoteSubnet", adapter.subnet,
        "-HttpPort", str(port),
        "-InterfaceAlias", adapter.interface_alias,
    ]
    if settings.lan_mdns_enabled:
        try:
            import psutil

            discovery_program = psutil.Process(os.getpid()).exe()
        except Exception:  # noqa: BLE001
            discovery_program = sys.executable
        arguments.extend(["-DiscoveryProgram", discovery_program])
    completed = subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    try:
        result = json.loads((completed.stdout or "").strip())
    except (TypeError, ValueError):
        result = {}
    if completed.returncode or not isinstance(result, dict):
        error_code = str(result.get("error_code") or "firewall_helper_failed")
        state = str(result.get("state") or "failed")
        details = {
            "administrator_required": "LAN firewall management requires an Administrator PowerShell session.",
            "discovery_program_unavailable": "The configured mDNS runtime is unavailable for firewall scoping.",
            "firewall_creation_failed": "CIAL firewall rule creation failed and owned partial rules were removed.",
            "firewall_verification_failed": "CIAL firewall verification failed and owned rules were rolled back.",
        }
        raise FirewallOperationError(
            state=state,
            error_code=error_code,
            safe_detail=details.get(
                error_code,
                "CIAL firewall management failed; external access was closed.",
            ),
        )
    state = str(result.get("state") or "unknown")
    verified = result.get("verified") is True
    if mode == "Apply" and (state != "ready" or not verified):
        raise FirewallOperationError(
            state=state,
            error_code="firewall_verification_failed",
            safe_detail="CIAL firewall verification failed and owned rules were rolled back.",
        )
    if mode == "Remove" and (state != "absent" or not verified):
        raise FirewallOperationError(
            state=state,
            error_code="firewall_remove_failed",
            safe_detail="CIAL-owned firewall rules could not be removed.",
        )
    return state


def restrict_secret_tree(path: Path) -> None:
    """Restrict an app-owned Caddy TLS tree before private keys are created."""
    identity = subprocess.run(
        ["whoami.exe", "/user", "/fo", "csv", "/nh"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    try:
        row = next(csv.reader([identity.stdout.strip()]))
        sid = row[1].strip()
    except (IndexError, StopIteration) as exc:
        raise RuntimeError("Unable to determine the current Windows user SID.") from exc
    if identity.returncode or not _SID_PATTERN.fullmatch(sid):
        raise RuntimeError("Unable to determine the current Windows user SID.")
    acl_script = settings.repo_path / "scripts" / "lan_caddy_acl.ps1"
    if not acl_script.is_file():
        raise RuntimeError("Caddy TLS state ACL helper is unavailable.")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(acl_script),
            "-Mode",
            "Apply",
            "-RootPath",
            str(path),
            "-CurrentUserSid",
            sid,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    try:
        result = json.loads(completed.stdout or "{}")
    except (TypeError, ValueError):
        result = {}
    if (
        completed.returncode
        or result.get("verified") is not True
        or result.get("allowed_principal_count") != 3
    ):
        raise RuntimeError("Unable to restrict the Caddy TLS state directory ACL.")


def prepare_caddy_state(
    caddy_root: Path,
    *,
    https_enabled: bool,
) -> tuple[Path, Path]:
    """Create app-owned Caddy state and fail closed before HTTPS can start."""
    caddy_data = caddy_root / "data"
    caddy_config = caddy_root / "config"
    caddy_data.mkdir(parents=True, exist_ok=True)
    caddy_config.mkdir(parents=True, exist_ok=True)
    if https_enabled:
        restrict_secret_tree(caddy_root)
    return caddy_data, caddy_config


class InstanceLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.guard_path = path.with_suffix(path.suffix + ".guard")
        self.handle: Any = None

    def __enter__(self) -> "InstanceLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        owner_pid: int | None = None
        with suppress(OSError, ValueError, TypeError, json.JSONDecodeError):
            raw = self.path.read_text(encoding="utf-8").strip()
            value = json.loads(raw) if raw.startswith("{") else {"pid": int(raw)}
            owner_pid = int(value["pid"])
            if owner_pid == os.getpid() or _pid_is_lan_manager(owner_pid):
                raise RuntimeError("A CIAL LAN manager is already running.")
        self.handle = self.guard_path.open(
            "r+b" if self.guard_path.exists() else "w+b"
        )
        acquired = False
        try:
            self.handle.seek(0)
            if not self.handle.read(1):
                self.handle.write(b" ")
                self.handle.flush()
            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            acquired = True
            self.path.write_text(json.dumps({
                "version": 1,
                "kind": "cial_lan_manager",
                "pid": os.getpid(),
            }), encoding="ascii")
        except OSError as exc:
            if acquired:
                with suppress(OSError):
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            with suppress(OSError):
                self.handle.close()
            raise RuntimeError("A CIAL LAN manager is already running.") from exc
        return self

    def __exit__(self, *_: object) -> None:
        if self.handle is not None:
            self.handle.seek(0)
            try:
                try:
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    # Windows releases byte-range locks when the handle closes.
                    pass
            finally:
                self.handle.close()
                with suppress(OSError):
                    self.path.unlink(missing_ok=True)
                with suppress(OSError):
                    self.guard_path.unlink(missing_ok=True)


def _pid_is_lan_manager(pid: int) -> bool:
    """Check a stale owner record without exposing its command line."""

    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        import psutil

        process = psutil.Process(pid)
        command = " ".join(process.cmdline()).casefold()
        return process.is_running() and "backend.app.lan.manager" in command
    except Exception:  # noqa: BLE001
        return False


def needs_reconfigure(
    previous: HotspotAdapter,
    detected: HotspotAdapter | None,
) -> bool:
    """Return whether owned edge resources must be torn down and rebuilt."""

    return detected is None or (
        detected.address != previous.address
        or detected.interface_index != previous.interface_index
        or detected.prefix_length != previous.prefix_length
        or detected.interface_alias.casefold() != previous.interface_alias.casefold()
    )


class LanManager:
    def __init__(
        self,
        *,
        backend_port: int,
        dry_run: bool = False,
        test_bind: str | None = None,
        frontend_root: Path | None = None,
    ) -> None:
        self.repo_root = settings.repo_path
        self.backend_port = backend_port
        self.dry_run = dry_run
        self.test_bind = test_bind
        self.frontend_root = frontend_root or (
            self.repo_root / "frontend" / "dist" / "public"
        )
        try:
            self.frontend_root.resolve().relative_to(self.repo_root.resolve())
        except ValueError as exc:
            raise ValueError("LAN frontend root must remain inside the repository.") from exc
        self.root = self.repo_root / "outputs" / "lan-server"
        self.status_path = self.root / "status.json"
        self.caddy_process: subprocess.Popen[str] | None = None
        self.caddy_pid_path = self.root / "caddy.pid.json"
        self.stop_path = self.root / "stop.request"
        self.mdns = MdnsPublisher()
        self.keep_awake = KeepAwakeLease()
        self.adapter: HotspotAdapter | None = None
        self.published_domain = settings.lan_domain
        self.lifecycle_state = "waiting_for_hotspot"

    def status(self, *, detail: str, state: str | None = None, gateway_ready: bool = False, discovery_ready: bool = False, firewall_state: str = "unmanaged") -> None:
        adapter = self.adapter
        hotspot_detected = adapter is not None and not self.test_bind
        scheme = "https" if settings.lan_https_enabled else "http"
        port = settings.lan_https_port if settings.lan_https_enabled else settings.lan_http_port
        if state is not None:
            self.lifecycle_state = state
        domain_url = f"{scheme}://{self.published_domain}" + (f":{port}" if port not in {80, 443} else "")
        ip_url = (
            f"{scheme}://{adapter.address}" + (f":{port}" if port not in {80, 443} else "")
            if adapter and settings.lan_allow_ip_fallback else None
        )
        write_status(self.status_path, {
            "state": self.lifecycle_state,
            "enabled": True,
            "mode": settings.lan_mode,
            "gateway_ready": gateway_ready,
            "discovery_ready": discovery_ready,
            "hostname": self.published_domain,
            "scheme": scheme,
            "port": port,
            "hotspot_detected": hotspot_detected,
            "bind_address_available": adapter is not None,
            "ip_fallback_available": bool(ip_url and gateway_ready),
            "tls_state": "untrusted" if settings.lan_https_enabled else "unconfigured",
            "firewall_state": firewall_state,
            "keep_awake": self.keep_awake.acquired,
            "checked_at": _now(),
            "safe_detail": detail,
            "domain_url": domain_url if gateway_ready else None,
            "ip_fallback_url": ip_url if gateway_ready else None,
        })
        if gateway_ready and settings.lan_qr_enabled:
            import qrcode

            image = qrcode.make(domain_url)
            image.save(self.frontend_root / "lan-access-qr.png")

    def _validate_caddy(self) -> Path:
        if not settings.caddy_path:
            raise RuntimeError(
                "Caddy is not staged. Set CIAL_CADDY_PATH to an operator-installed caddy.exe."
            )
        caddy = Path(settings.caddy_path).expanduser()
        if not caddy.is_file() or caddy.suffix.casefold() != ".exe":
            raise RuntimeError("CIAL_CADDY_PATH must name an existing caddy.exe.")
        completed = subprocess.run(
            [str(caddy), "version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError("Configured Caddy failed its version check.")
        return caddy

    def _start_gateway(self, adapter: HotspotAdapter) -> None:
        caddy = self._validate_caddy()
        frontend_root = self.frontend_root
        port = settings.lan_https_port if settings.lan_https_enabled else settings.lan_http_port
        caddyfile = self.root / "Caddyfile.generated"
        caddyfile.parent.mkdir(parents=True, exist_ok=True)
        caddyfile.write_text(render_caddyfile(GatewayConfig(
            bind_ip=adapter.address,
            port=port,
            domain=settings.lan_domain,
            backend_port=self.backend_port,
            frontend_root=frontend_root,
            log_path=self.root / "logs" / "caddy-access.jsonl",
            https=settings.lan_https_enabled,
        )), encoding="utf-8")
        validate = subprocess.run(
            [str(caddy), "validate", "--config", str(caddyfile), "--adapter", "caddyfile"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if validate.returncode:
            raise RuntimeError("Generated Caddy configuration failed validation.")
        if self.dry_run:
            return
        env = os.environ.copy()
        configured_caddy_root = Path(settings.lan_gateway_data_dir)
        caddy_root = (
            configured_caddy_root
            if configured_caddy_root.is_absolute()
            else self.repo_root / configured_caddy_root
        ).resolve()
        caddy_data, caddy_config = prepare_caddy_state(
            caddy_root,
            https_enabled=settings.lan_https_enabled,
        )
        env["XDG_DATA_HOME"] = str(caddy_data)
        env["XDG_CONFIG_HOME"] = str(caddy_config)
        logs = self.root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        self.caddy_process = subprocess.Popen(
            [str(caddy), "run", "--config", str(caddyfile), "--adapter", "caddyfile"],
            # Caddy's internal diagnostics can disclose absolute certificate
            # state paths. Lifecycle events and the redacted rotating access
            # log remain available through app-owned logging.
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
        )
        self.caddy_pid_path.write_text(
            json.dumps({
                "version": 1,
                "kind": "cial_owned_caddy",
                "pid": self.caddy_process.pid,
                "owner_pid": os.getpid(),
            }),
            encoding="utf-8",
        )
        deadline = time.monotonic() + settings.lan_startup_timeout_seconds
        url = f"{'https' if settings.lan_https_enabled else 'http'}://{adapter.address}:{port}/"
        while time.monotonic() < deadline:
            if self.caddy_process.poll() is not None:
                raise RuntimeError("Owned Caddy process exited during startup.")
            try:
                response = httpx.get(url, headers={"Host": settings.lan_domain}, timeout=2, verify=False)
                if response.status_code < 500:
                    _event("gateway_ready", port=port, hostname=settings.lan_domain, state="ready")
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise RuntimeError("Caddy did not become ready before the startup timeout.")

    def _stop_gateway(self) -> None:
        process = self.caddy_process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=settings.lan_shutdown_timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        self.caddy_process = None
        self.caddy_pid_path.unlink(missing_ok=True)
        _event("gateway_stopped", state="stopped")

    def run(self) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        firewall_state = "unmanaged"
        _event("lan_manager_started", mode=settings.lan_mode)
        try:
            self.stop_path.unlink(missing_ok=True)
            while self.adapter is None:
                if self.stop_path.exists():
                    return 0
                try:
                    self.adapter = (
                        HotspotAdapter(
                            interface_alias="loopback-test",
                            interface_index=1,
                            address=self.test_bind,
                            prefix_length=8,
                            subnet="127.0.0.0/8",
                            category="automated_test_loopback",
                            confidence="explicit",
                            reason="explicit host-machine automation bind",
                        )
                        if self.test_bind
                        else _detect(self.repo_root)
                    )
                except HotspotSelectionError as exc:
                    state = (
                        "explicit_binding_invalid"
                        if exc.code.startswith("explicit_")
                        else "waiting_for_hotspot"
                    )
                    self.status(detail=exc.safe_detail, state=state)
                    _event("adapter_selection_failed", state=state, error_code=exc.code)
                    if self.dry_run:
                        return 1
                    time.sleep(settings.lan_adapter_recheck_seconds)
                    continue
                if self.adapter is None:
                    self.status(
                        detail="CIAL is running on this device. LAN access is waiting for Windows Mobile Hotspot.",
                        state="waiting_for_hotspot",
                    )
                    print("CIAL is running on this device. LAN access is waiting for Windows Mobile Hotspot.")
                    if self.dry_run:
                        return 0
                    time.sleep(settings.lan_adapter_recheck_seconds)
            _event("hotspot_detected", interface_category=self.adapter.category, state="detected")
            self.status(
                detail="LAN adapter detected; validating the gateway.",
                state="adapter_detected",
                firewall_state=firewall_state,
            )
            if settings.lan_keep_awake and not self.dry_run:
                self.keep_awake.acquire()
                _event("keep_awake_acquired", state="ready" if self.keep_awake.acquired else "failed")
            self.status(
                detail="LAN adapter detected; validating Caddy configuration.",
                state="caddy_validating",
                firewall_state=firewall_state,
            )
            self._start_gateway(self.adapter)
            if settings.lan_firewall_managed and not self.test_bind:
                try:
                    firewall_state = _run_firewall(
                        self.repo_root,
                        mode="Inspect" if self.dry_run else "Apply",
                        adapter=self.adapter,
                        port=settings.lan_https_port if settings.lan_https_enabled else settings.lan_http_port,
                    )
                except FirewallOperationError as exc:
                    self.status(
                        detail=exc.safe_detail,
                        state="firewall_failed",
                        firewall_state=exc.state,
                    )
                    raise
                except Exception:
                    self.status(
                        detail="CIAL firewall helper failed; external access was closed.",
                        state="firewall_failed",
                        firewall_state="failed",
                    )
                    raise
                _event("firewall_rule_verified", state=firewall_state)
            discovery_ready = False
            mdns_failed = False
            if settings.lan_mdns_enabled and not self.dry_run and not self.test_bind:
                try:
                    domain = self.mdns.register(
                        domain=settings.lan_domain,
                        address=self.adapter.address,
                        port=settings.lan_https_port if settings.lan_https_enabled else settings.lan_http_port,
                        scheme="https" if settings.lan_https_enabled else "http",
                    )
                    self.published_domain = domain
                    discovery_ready = True
                    _event("mdns_registered", hostname=domain, state="ready")
                except Exception as exc:  # noqa: BLE001
                    mdns_failed = True
                    _event("mdns_failed", state="failed", error_code=type(exc).__name__)
            self.status(
                detail=(
                    "Loopback-only host-machine validation gateway is ready; this is not hotspot UAT."
                    if self.test_bind and not self.dry_run
                    else "LAN gateway is ready; mDNS is unavailable, so use the IP fallback."
                    if mdns_failed
                    else "LAN gateway is ready."
                    if not self.dry_run
                    else "LAN dry-run validation completed."
                ),
                state="mdns_failed" if mdns_failed else "ready",
                gateway_ready=not self.dry_run,
                discovery_ready=discovery_ready,
                firewall_state=firewall_state,
            )
            if self.dry_run:
                return 0
            while True:
                time.sleep(settings.lan_adapter_recheck_seconds)
                if self.stop_path.exists():
                    return 0
                try:
                    detected = self.adapter if self.test_bind else _detect(self.repo_root)
                except subprocess.TimeoutExpired:
                    # Adapter inspection is an external PowerShell probe. A
                    # transient WMI/network-stack stall must not tear down an
                    # otherwise healthy gateway and reset active client streams.
                    _event(
                        "adapter_probe_timeout",
                        state="gateway_retained",
                        error_code="TimeoutExpired",
                    )
                    continue
                except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as exc:
                    _event(
                        "adapter_probe_failed",
                        state="gateway_retained",
                        error_code=type(exc).__name__,
                    )
                    continue
                except HotspotSelectionError:
                    detected = None
                if needs_reconfigure(self.adapter, detected):
                    _event("hotspot_lost" if detected is None else "hotspot_address_changed", state="reconfigure")
                    self.status(
                        detail="Hotspot addressing changed; LAN access is reconfiguring.",
                        state="reconfiguring",
                        gateway_ready=False,
                        discovery_ready=False,
                        firewall_state=firewall_state,
                    )
                    return 75
        except KeyboardInterrupt:
            return 0
        except Exception as exc:  # noqa: BLE001
            if self.lifecycle_state not in {"explicit_binding_invalid", "firewall_failed"}:
                self.status(
                    detail="LAN gateway startup failed. Local CIAL remains available.",
                    state="caddy_failed",
                    firewall_state="failed" if settings.lan_firewall_managed else "unmanaged",
                )
            _event("gateway_failed", state="failed", error_code=type(exc).__name__)
            LOGGER.error("LAN manager failure: %s", type(exc).__name__)
            return 1
        finally:
            stop_requested = self.stop_path.exists()
            self._stop_gateway()
            self.mdns.unregister()
            if settings.lan_firewall_managed and self.adapter and not self.dry_run and not self.test_bind:
                try:
                    _run_firewall(
                        self.repo_root,
                        mode="Remove",
                        adapter=self.adapter,
                        port=settings.lan_https_port if settings.lan_https_enabled else settings.lan_http_port,
                    )
                except Exception:  # noqa: BLE001
                    _event("firewall_rule_failed", state="cleanup_failed")
            self.keep_awake.release()
            (self.frontend_root / "lan-access-qr.png").unlink(missing_ok=True)
            if stop_requested:
                self.status(
                    detail="LAN access is stopped. Local CIAL remains available.",
                    state="stopped",
                    gateway_ready=False,
                    discovery_ready=False,
                    firewall_state="unmanaged",
                )
            self.stop_path.unlink(missing_ok=True)
            _event("keep_awake_released", state="released")
            _event("lan_manager_stopped", state="stopped")


def main() -> int:
    parser = argparse.ArgumentParser(description="CIAL Windows hotspot LAN manager")
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--test-bind",
        choices=("127.0.0.1",),
        help="Loopback-only host-machine automation; never publishes mDNS or firewall rules.",
    )
    parser.add_argument(
        "--frontend-root",
        type=Path,
        help="Repository-contained production build root; intended for isolated validation builds.",
    )
    args = parser.parse_args()
    if not settings.lan_access_enabled and not args.dry_run:
        write_status(
            settings.repo_path / "outputs" / "lan-server" / "status.json",
            {
                "enabled": False,
                "state": "disabled",
                "safe_detail": "LAN access is disabled.",
            },
        )
        print("LAN access is disabled. Set CIAL_LAN_ACCESS_ENABLED=true or use the --lan launcher option.")
        return 2
    root = settings.repo_path / "outputs" / "lan-server"
    root.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(root / "lan-manager.jsonl", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    LOGGER.setLevel(logging.INFO)
    LOGGER.addHandler(handler)
    try:
        with InstanceLock(root / "manager.lock"):
            return LanManager(
                backend_port=args.backend_port,
                dry_run=args.dry_run,
                test_bind=args.test_bind,
                frontend_root=args.frontend_root,
            ).run()
    except RuntimeError as exc:
        if str(exc) == "A CIAL LAN manager is already running.":
            print(str(exc))
            return 0
        raise


if __name__ == "__main__":
    raise SystemExit(main())
