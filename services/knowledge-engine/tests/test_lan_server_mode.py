from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest

from backend.app.core.config import settings
from backend.app.lan.firewall import FirewallPlan, HTTP_RULE, MDNS_RULE
from backend.app.lan.discovery import MdnsPublisher
from backend.app.lan.gateway import GatewayConfig, render_caddyfile
from backend.app.lan import manager as lan_manager
from backend.app.lan.manager import (
    InstanceLock,
    prepare_caddy_state,
    restrict_secret_tree,
)
from backend.app.lan.network import select_hotspot_adapter, subnet_for
from backend.app.lan.power import KeepAwakeLease
from backend.app.lan.status import read_status, sanitize_status, write_status
from backend.app.security import host_boundary, session_tokens
from backend.app.security.host_boundary import LanHostBoundaryMiddleware


def _record(**overrides):
    value = {
        "interface_alias": "Hotspot Adapter",
        "interface_index": 17,
        "description": "Microsoft Wi-Fi Direct Virtual Adapter",
        "status": "Up",
        "media_type": "Native 802.11",
        "address": "192.168.45.1",
        "prefix_length": 24,
        "profile_category": "Private",
        "nat": False,
        "ics": True,
        "wifi_direct": True,
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    ("address", "prefix", "expected"),
    [
        ("192.168.137.1", 24, "192.168.137.0/24"),
        ("172.20.31.1", 20, "172.20.16.0/20"),
        ("10.8.1.1", 16, "10.8.0.0/16"),
    ],
)
def test_subnet_derivation(address, prefix, expected):
    assert subnet_for(address, prefix) == expected


def test_hotspot_detector_accepts_ics_evidence():
    selected = select_hotspot_adapter([_record()])
    assert selected is not None
    assert selected.address == "192.168.45.1"
    assert selected.subnet == "192.168.45.0/24"
    assert selected.confidence == "high"


@pytest.mark.parametrize("description", ["WireGuard VPN", "WSL Adapter", "DockerNAT", "Bluetooth PAN"])
def test_hotspot_detector_excludes_non_hotspot_adapters(description):
    assert select_hotspot_adapter([_record(description=description, ics=True)]) is None


def test_hotspot_detector_excludes_down_adapter():
    assert select_hotspot_adapter([_record(status="Down")]) is None


def test_hotspot_detector_fails_closed_when_ambiguous():
    with pytest.raises(RuntimeError, match="Ambiguous"):
        select_hotspot_adapter([
            _record(interface_alias="Candidate A", interface_index=1),
            _record(interface_alias="Candidate B", interface_index=2, address="192.168.46.1"),
        ])


def test_hotspot_detector_honors_interface_and_ip_override():
    selected = select_hotspot_adapter(
        [
            _record(interface_alias="Candidate A", interface_index=1),
            _record(interface_alias="Candidate B", interface_index=2, address="192.168.46.1"),
        ],
        interface_override="Candidate B",
        ip_override="192.168.46.1",
    )
    assert selected is not None
    assert selected.interface_index == 2


def test_caddyfile_is_interface_bound_same_origin_and_streaming_safe(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("ok", encoding="utf-8")
    rendered = render_caddyfile(GatewayConfig(
        bind_ip="192.168.45.1",
        port=80,
        domain="cial-knowledge-os.local",
        backend_port=8000,
        frontend_root=dist,
        log_path=tmp_path / "access.jsonl",
    ))
    assert "bind 192.168.45.1" in rendered
    assert "reverse_proxy 127.0.0.1:8000" in rendered
    assert "flush_interval -1" in rendered
    assert "try_files {path} /index.html" in rendered
    assert "Unexpected Host" in rendered
    assert 'X-Frame-Options "SAMEORIGIN"' in rendered
    assert "frame-ancestors 'self'" in rendered
    assert "Strict-Transport-Security" not in rendered
    assert "request>headers delete" in rendered
    assert "request>uri delete" in rendered
    assert "6335" not in rendered and "11434" not in rendered


def test_caddyfile_https_uses_internal_tls_and_hsts(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("ok", encoding="utf-8")
    rendered = render_caddyfile(GatewayConfig(
        bind_ip="192.168.45.1",
        port=443,
        domain="cial-knowledge-os.local",
        backend_port=8000,
        frontend_root=dist,
        log_path=tmp_path / "access.jsonl",
        https=True,
    ))
    assert "https://:443" in rendered
    assert "tls internal" in rendered
    assert "auto_https off" not in rendered
    assert "Strict-Transport-Security" in rendered
    assert "header_up X-Forwarded-Proto https" in rendered


def test_caddyfile_rejects_missing_frontend(tmp_path):
    with pytest.raises(ValueError, match="index.html"):
        render_caddyfile(GatewayConfig(
            bind_ip="192.168.45.1", port=80, domain="cial-knowledge-os.local",
            backend_port=8000, frontend_root=tmp_path, log_path=tmp_path / "log",
        ))


def test_status_projection_discards_secrets_and_paths(tmp_path):
    path = tmp_path / "status.json"
    write_status(path, {
        "enabled": True,
        "safe_detail": "ready",
        "hotspot_password": "secret",
        "adapter_mac": "00:11:22:33:44:55",
        "repository_path": r"C:\private",
    })
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["enabled"] is True
    assert "hotspot_password" not in raw
    assert "adapter_mac" not in raw
    assert "repository_path" not in raw
    assert read_status(path)["safe_detail"] == "ready"


def test_status_projection_handles_invalid_file(tmp_path):
    path = tmp_path / "status.json"
    path.write_text("{broken", encoding="utf-8")
    assert read_status(path)["enabled"] is False


def test_firewall_plan_uses_only_stable_owned_names():
    plan = FirewallPlan(
        local_address="192.168.45.1",
        subnet="192.168.45.0/24",
        http_port=80,
        mdns_enabled=True,
        discovery_program="python.exe",
    )
    assert plan.rule_names() == (HTTP_RULE, MDNS_RULE)
    assert all(name.startswith("CIAL-LAN-") for name in plan.rule_names())


def test_mdns_conflict_falls_back_and_unregisters(monkeypatch):
    class Conflict(Exception):
        pass

    instances = []

    class FakeZeroconf:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.closed = False
            self.unregistered = None
            instances.append(self)

        def register_service(self, info, **kwargs):
            if len(instances) == 1:
                raise Conflict
            self.info = info

        def unregister_service(self, info):
            self.unregistered = info

        def close(self):
            self.closed = True

    def service_info(service_type, name, **kwargs):
        return SimpleNamespace(service_type=service_type, name=name, **kwargs)

    monkeypatch.setitem(sys.modules, "zeroconf", SimpleNamespace(
        IPVersion=SimpleNamespace(V4="v4"),
        NonUniqueNameException=Conflict,
        ServiceInfo=service_info,
        Zeroconf=FakeZeroconf,
    ))
    publisher = MdnsPublisher()
    selected = publisher.register(
        domain="cial-knowledge-os.local",
        address="192.168.45.1",
        port=443,
        scheme="https",
    )
    assert selected == "cial-knowledge-os-2.local"
    assert instances[0].closed is True
    assert publisher.info.service_type == "_https._tcp.local."
    assert publisher.info.name == "CIAL Knowledge OS-2._https._tcp.local."
    assert publisher.info.server == "cial-knowledge-os-2.local."
    publisher.unregister()
    assert instances[1].unregistered is not None
    assert instances[1].closed is True


def test_host_boundary_rejects_unexpected_host():
    app = FastAPI()
    app.add_middleware(LanHostBoundaryMiddleware)

    @app.get("/")
    def root():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/", headers={"Host": "random.example"}).status_code == 400
    assert client.get("/", headers={"Host": "localhost"}).status_code == 200


def test_allowed_hosts_adds_only_sanitized_lan_addresses(monkeypatch, tmp_path):
    status = tmp_path / "status.json"
    write_status(status, {
        "enabled": True,
        "domain_url": "http://cial-knowledge-os.local",
        "ip_fallback_url": "http://192.168.45.1",
    })
    monkeypatch.setattr(
        host_boundary,
        "settings",
        SimpleNamespace(
            lan_access_enabled=True,
            lan_domain="cial-knowledge-os.local",
            outputs_path=tmp_path,
        ),
    )
    allowed = host_boundary.allowed_hosts(status)
    assert {"cial-knowledge-os.local", "192.168.45.1"} <= allowed
    assert "random.example" not in allowed


def test_non_loopback_forwarded_headers_are_removed():
    app = FastAPI()
    app.add_middleware(LanHostBoundaryMiddleware)

    @app.get("/")
    def root(request: Request):
        return {"forwarded": request.headers.get("x-forwarded-for")}

    client = TestClient(app, client=("192.168.45.20", 50000))
    response = client.get("/", headers={"Host": "localhost", "X-Forwarded-For": "203.0.113.5"})
    assert response.status_code == 200
    assert response.json()["forwarded"] is None


@pytest.mark.parametrize(("secure", "expected"), [(False, False), (True, True)])
def test_auth_cookie_http_https_flags(monkeypatch, secure, expected):
    monkeypatch.setattr(session_tokens, "settings", replace(
        settings,
        auth_secret_key="lan-cookie-test",
        auth_cookie_secure=secure,
        auth_cookie_samesite="lax",
    ))
    cookie = session_tokens.session_cookie_settings()
    assert cookie["secure"] is expected
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "lax"
    assert "domain" not in cookie


def test_keep_awake_release_is_idempotent():
    lease = KeepAwakeLease()
    lease.release()
    assert lease.acquired is False


def test_instance_lock_rejects_duplicate_manager(tmp_path):
    lock_path = tmp_path / "manager.lock"
    with InstanceLock(lock_path):
        with pytest.raises(RuntimeError, match="already running"):
            with InstanceLock(lock_path):
                pass


def test_https_secret_tree_acl_is_sid_scoped(monkeypatch, tmp_path):
    calls = []
    responses = iter([
        SimpleNamespace(
            returncode=0,
            stdout='"WORKSTATION\\\\operator","S-1-5-21-1-2-3-1001"\n',
        ),
        SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "verified": True,
                "item_count": 3,
                "allowed_principal_count": 3,
            }),
        ),
    ])

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        return next(responses)

    monkeypatch.setattr(lan_manager.subprocess, "run", fake_run)
    path_with_spaces = tmp_path / "Caddy state with spaces"
    path_with_spaces.mkdir()
    restrict_secret_tree(path_with_spaces)
    assert calls[0][:2] == ["whoami.exe", "/user"]
    assert calls[1][0] == "powershell.exe"
    assert calls[1][calls[1].index("-RootPath") + 1] == str(path_with_spaces)
    assert calls[1][calls[1].index("-CurrentUserSid") + 1] == "S-1-5-21-1-2-3-1001"


def test_acl_helper_defines_exact_non_inherited_principals():
    source = (settings.repo_path / "scripts" / "lan_caddy_acl.ps1").read_text(
        encoding="utf-8"
    )
    assert '"S-1-5-18"' in source
    assert '"S-1-5-32-544"' in source
    assert "$CurrentUserSid" in source
    assert "SetAccessRuleProtection($true, $false)" in source
    assert "RemoveAccessRuleSpecific" in source
    assert "-not $allowedSidSet.Contains($sid)" in source
    assert "$rule.IsInherited" in source


def test_acl_verification_failure_is_generic_and_fail_closed(monkeypatch, tmp_path):
    responses = iter([
        SimpleNamespace(
            returncode=0,
            stdout='"WORKSTATION\\\\operator","S-1-5-21-1-2-3-1001"\n',
        ),
        SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "verified": False,
                "item_count": 1,
                "allowed_principal_count": 4,
            }),
        ),
    ])
    monkeypatch.setattr(
        lan_manager.subprocess,
        "run",
        lambda *args, **kwargs: next(responses),
    )
    state_path = tmp_path / "sensitive state"
    state_path.mkdir()
    with pytest.raises(RuntimeError) as captured:
        restrict_secret_tree(state_path)
    assert str(state_path) not in str(captured.value)
    assert "ACL" in str(captured.value)


def test_https_acl_failure_prevents_ready_state_without_deleting_state(
    monkeypatch,
    tmp_path,
):
    state_root = tmp_path / "Caddy state"
    existing_state = state_root / "data" / "existing-state.bin"
    existing_state.parent.mkdir(parents=True)
    existing_state.write_bytes(b"preserve")

    def fail_acl(path):
        raise RuntimeError("Unable to restrict the Caddy TLS state directory ACL.")

    monkeypatch.setattr(lan_manager, "restrict_secret_tree", fail_acl)
    with pytest.raises(RuntimeError, match="ACL"):
        prepare_caddy_state(state_root, https_enabled=True)
    assert existing_state.read_bytes() == b"preserve"


def test_http_caddy_state_does_not_require_acl(monkeypatch, tmp_path):
    state_root = tmp_path / "HTTP Caddy state"
    existing_state = state_root / "data" / "existing-state.bin"
    existing_state.parent.mkdir(parents=True)
    existing_state.write_bytes(b"preserve")
    called = False

    def unexpected_acl(path):
        nonlocal called
        called = True

    monkeypatch.setattr(lan_manager, "restrict_secret_tree", unexpected_acl)
    data_path, config_path = prepare_caddy_state(
        state_root,
        https_enabled=False,
    )
    assert called is False
    assert data_path.is_dir() and config_path.is_dir()
    assert existing_state.read_bytes() == b"preserve"


def test_caddy_internal_diagnostics_do_not_log_secret_paths():
    source = (
        settings.repo_path
        / "services"
        / "knowledge-engine"
        / "backend"
        / "app"
        / "lan"
        / "manager.py"
    ).read_text(encoding="utf-8")
    assert "stdout=subprocess.DEVNULL" in source
    assert "stderr=subprocess.DEVNULL" in source
    assert "caddy.err.log" not in source
