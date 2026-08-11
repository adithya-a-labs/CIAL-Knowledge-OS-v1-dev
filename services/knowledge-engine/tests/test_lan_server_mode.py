from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import re
import subprocess
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
    FirewallOperationError,
    InstanceLock,
    LanManager,
    needs_reconfigure,
    prepare_caddy_state,
    restrict_secret_tree,
)
from backend.app.lan.network import (
    HotspotAdapter,
    HotspotSelectionError,
    select_hotspot_adapter,
    subnet_for,
)
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


def _run_firewall_contract(expression: str) -> str:
    script = settings.repo_path / "scripts" / "lan_firewall.ps1"
    escaped = str(script).replace("'", "''")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f". '{escaped}'; {expression}",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return completed.stdout.strip()


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
    with pytest.raises(RuntimeError, match="ambiguous"):
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


def test_explicit_interface_and_ip_bypass_missing_probe_flags():
    selected = select_hotspot_adapter(
        [_record(
            interface_alias="Wi-Fi 3",
            interface_index=11,
            description="MediaTek Wi-Fi 7 MT7925 Wireless LAN Card",
            address="192.168.137.1",
            nat=False,
            ics=False,
            wifi_direct=False,
        )],
        interface_override="wi-fi 3",
        ip_override="192.168.137.1",
    )
    assert selected.category == "explicit_hotspot_binding"
    assert selected.confidence == "explicit"
    assert selected.reason == "matched configured LAN interface and IP"


def test_explicit_interface_mismatch_is_actionable():
    with pytest.raises(HotspotSelectionError, match="interface is unavailable"):
        select_hotspot_adapter([_record()], interface_override="Wi-Fi 99")


def test_explicit_interface_and_ip_must_own_same_record():
    with pytest.raises(HotspotSelectionError, match="not assigned to the selected"):
        select_hotspot_adapter(
            [_record(interface_alias="Wi-Fi 3", address="192.168.137.1")],
            interface_override="Wi-Fi 3",
            ip_override="192.168.50.1",
        )


def test_explicit_interface_only_resolves_one_safe_address():
    selected = select_hotspot_adapter(
        [_record(interface_alias="Wi-Fi 3", address="192.168.137.1", ics=False, wifi_direct=False)],
        interface_override="WI-FI 3",
    )
    assert selected.address == "192.168.137.1"


def test_explicit_ip_only_resolves_owning_adapter():
    selected = select_hotspot_adapter(
        [_record(interface_alias="Wi-Fi 3", address="192.168.137.1", ics=False, wifi_direct=False)],
        ip_override="192.168.137.1",
    )
    assert selected.interface_alias == "Wi-Fi 3"


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.10.1"])
def test_explicit_binding_rejects_unsafe_ipv4(address):
    with pytest.raises(HotspotSelectionError, match="safe private IPv4"):
        select_hotspot_adapter([_record(address=address)], ip_override=address)


def test_explicit_binding_rejects_ambiguous_records():
    duplicate = _record(interface_alias="Wi-Fi 3", address="192.168.137.1")
    with pytest.raises(HotspotSelectionError, match="multiple adapter records"):
        select_hotspot_adapter(
            [duplicate, dict(duplicate)],
            interface_override="Wi-Fi 3",
            ip_override="192.168.137.1",
        )


def test_automatic_detection_supports_secondary_mediatek_hotspot_shape():
    selected = select_hotspot_adapter([
        _record(
            interface_alias="Wi-Fi",
            interface_index=17,
            description="MediaTek Wi-Fi 7 MT7925 Wireless LAN Card",
            address="172.20.10.6",
            prefix_length=28,
            profile_category="Public",
            nat=False,
            ics=False,
            wifi_direct=False,
        ),
        _record(
            interface_alias="Wi-Fi 3",
            interface_index=11,
            description="MediaTek Wi-Fi 7 MT7925 Wireless LAN Card",
            address="192.168.137.1",
            profile_category="",
            nat=False,
            ics=False,
            wifi_direct=False,
        ),
    ])
    assert selected is not None
    assert selected.interface_alias == "Wi-Fi 3"
    assert selected.address == "192.168.137.1"


def test_automatic_detection_excludes_wsl_bluetooth_and_disconnected():
    assert select_hotspot_adapter([
        _record(interface_alias="vEthernet (WSL)", description="Hyper-V WSL", address="192.168.137.1"),
        _record(interface_alias="Bluetooth Network", description="Bluetooth PAN", address="192.168.137.1"),
        _record(interface_alias="Wi-Fi 3", status="Disconnected", address="192.168.137.1"),
    ]) is None


def test_automatic_hotspot_default_tie_fails_closed():
    with pytest.raises(HotspotSelectionError, match="Automatic hotspot detection is ambiguous"):
        select_hotspot_adapter([
            _record(interface_alias="Wireless A", interface_index=2, address="192.168.137.1", ics=False, wifi_direct=False),
            _record(interface_alias="Wireless B", interface_index=3, address="192.168.137.1", ics=False, wifi_direct=False),
        ])


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
    assert "bind 0.0.0.0" not in rendered
    assert "reverse_proxy 127.0.0.1:8000" in rendered
    assert "request_body" in rendered
    assert "max_size 110MB" in rendered
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


def test_status_projection_redacts_paths_and_secret_values():
    clean = sanitize_status({
        "safe_detail": r"Failed at C:\Users\operator\private token=top-secret",
    })
    assert r"C:\Users" not in clean["safe_detail"]
    assert "top-secret" not in clean["safe_detail"]


def test_mdns_failure_status_preserves_ip_fallback(monkeypatch, tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    monkeypatch.setattr(lan_manager, "settings", SimpleNamespace(
        repo_path=tmp_path,
        lan_domain="cial-knowledge-os.local",
        lan_https_enabled=False,
        lan_http_port=80,
        lan_https_port=443,
        lan_allow_ip_fallback=True,
        lan_mode="hotspot",
        lan_qr_enabled=False,
    ))
    manager = LanManager(backend_port=8000, frontend_root=frontend)
    manager.adapter = HotspotAdapter(
        interface_alias="Wi-Fi 3",
        interface_index=11,
        address="192.168.137.1",
        prefix_length=24,
        subnet="192.168.137.0/24",
        category="explicit_hotspot_binding",
        confidence="explicit",
        reason="matched configured LAN interface and IP",
    )
    manager.status(
        detail="LAN gateway is ready; mDNS is unavailable, so use the IP fallback.",
        state="mdns_failed",
        gateway_ready=True,
        discovery_ready=False,
        firewall_state="ready",
    )
    status = read_status(manager.status_path)
    assert status["state"] == "mdns_failed"
    assert status["gateway_ready"] is True
    assert status["discovery_ready"] is False
    assert status["ip_fallback_available"] is True
    assert status["ip_fallback_url"] == "http://192.168.137.1"


def test_explicit_binding_error_has_distinct_safe_status(monkeypatch, tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    monkeypatch.setattr(lan_manager, "settings", SimpleNamespace(
        repo_path=tmp_path,
        lan_domain="cial-knowledge-os.local",
        lan_https_enabled=False,
        lan_http_port=80,
        lan_https_port=443,
        lan_allow_ip_fallback=True,
        lan_mode="hotspot",
        lan_qr_enabled=False,
        lan_keep_awake=False,
        lan_firewall_managed=False,
        lan_mdns_enabled=False,
        lan_adapter_recheck_seconds=0,
    ))
    monkeypatch.setattr(
        lan_manager,
        "_detect",
        lambda root: (_ for _ in ()).throw(HotspotSelectionError(
            "explicit_ip_not_assigned",
            "Configured LAN IP is not assigned to the selected interface.",
        )),
    )
    manager = LanManager(
        backend_port=8000,
        dry_run=True,
        frontend_root=frontend,
    )
    assert manager.run() == 1
    status = read_status(manager.status_path)
    assert status["state"] == "explicit_binding_invalid"
    assert status["safe_detail"] == "Configured LAN IP is not assigned to the selected interface."
    assert "waiting for Windows Mobile Hotspot" not in status["safe_detail"]


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


def test_firewall_script_has_no_case_insensitive_parameter_collisions():
    source = (settings.repo_path / "scripts" / "lan_firewall.ps1").read_text(
        encoding="utf-8"
    )
    variables = re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", source)
    for parameter in (
        "Mode",
        "LocalAddress",
        "RemoteSubnet",
        "HttpPort",
        "InterfaceAlias",
        "DiscoveryProgram",
    ):
        variants = {name for name in variables if name.casefold() == parameter.casefold()}
        assert variants == {parameter}
    assert "$httpPortFilter" in source
    assert "$httpAddressFilter" in source
    assert "$httpInterfaceFilter" in source
    assert "$mdnsRule" in source


def test_firewall_scope_normalization_handles_cidr_and_windows_netmask():
    output = _run_firewall_contract(
        "[pscustomobject]@{cidr=(ConvertTo-CanonicalIpv4Scope '192.168.137.0/24');"
        "netmask=(ConvertTo-CanonicalIpv4Scope '192.168.137.0/255.255.255.0')}"
        " | ConvertTo-Json -Compress"
    )
    assert json.loads(output) == {
        "cidr": "192.168.137.0/24",
        "netmask": "192.168.137.0/24",
    }


def test_firewall_contract_verifies_filters_and_rejects_each_mismatch():
    output = _run_firewall_contract(
        "$rule=[pscustomobject]@{Enabled='True';Direction='Inbound';Action='Allow';Profile=@('Any')};"
        "$port=[pscustomobject]@{Protocol=6;LocalPort=@('80')};"
        "$address=[pscustomobject]@{LocalAddress=@('192.168.137.1');RemoteAddress=@('192.168.137.0/255.255.255.0')};"
        "$interface=[pscustomobject]@{InterfaceAlias=@('Wi-Fi 3')};"
        "$application=[pscustomobject]@{Program=(Join-Path (Get-Location) '.venv\\Scripts\\python.exe')};"
        "$snapshot=[pscustomobject]@{rule=$rule;port_filter=$port;address_filter=$address;interface_filter=$interface;application_filter=$application};"
        "$expectedProgram=$application.Program;"
        "$valid=Test-CialRuleContract $snapshot 'TCP' '80' '192.168.137.1' '192.168.137.0/24' 'Wi-Fi 3';"
        "$port.LocalPort='81';$badPort=Test-CialRuleContract $snapshot 'TCP' '80' '192.168.137.1' '192.168.137.0/24' 'Wi-Fi 3';$port.LocalPort='80';"
        "$address.LocalAddress='192.168.50.1';$badLocal=Test-CialRuleContract $snapshot 'TCP' '80' '192.168.137.1' '192.168.137.0/24' 'Wi-Fi 3';$address.LocalAddress='192.168.137.1';"
        "$address.RemoteAddress='Any';$badRemote=Test-CialRuleContract $snapshot 'TCP' '80' '192.168.137.1' '192.168.137.0/24' 'Wi-Fi 3';$address.RemoteAddress='192.168.137.0/24';"
        "$interface.InterfaceAlias='Wi-Fi';$badInterface=Test-CialRuleContract $snapshot 'TCP' '80' '192.168.137.1' '192.168.137.0/24' 'Wi-Fi 3';$interface.InterfaceAlias='Wi-Fi 3';"
        "$rule.Profile='Private';$badProfile=Test-CialRuleContract $snapshot 'TCP' '80' '192.168.137.1' '192.168.137.0/24' 'Wi-Fi 3';$rule.Profile='Any';"
        "$port.Protocol=17;$badProtocol=Test-CialRuleContract $snapshot 'TCP' '80' '192.168.137.1' '192.168.137.0/24' 'Wi-Fi 3';"
        "$port.LocalPort='5353';$mdns=Test-CialRuleContract $snapshot 'UDP' '5353' '192.168.137.1' '192.168.137.0/24' 'Wi-Fi 3' $expectedProgram;"
        "[pscustomobject]@{valid=$valid;badPort=$badPort;badLocal=$badLocal;badRemote=$badRemote;badInterface=$badInterface;badProfile=$badProfile;badProtocol=$badProtocol;mdns=$mdns}|ConvertTo-Json -Compress"
    )
    result = json.loads(output)
    assert result == {
        "valid": True,
        "badPort": False,
        "badLocal": False,
        "badRemote": False,
        "badInterface": False,
        "badProfile": False,
        "badProtocol": False,
        "mdns": True,
    }


def test_firewall_contract_accepts_numeric_windows_enum_values():
    output = _run_firewall_contract(
        "$rule=[pscustomobject]@{Enabled=1;Direction=1;Action=2;Profile=0};"
        "$snapshot=[pscustomobject]@{rule=$rule;"
        "port_filter=[pscustomobject]@{Protocol=6;LocalPort='80'};"
        "address_filter=[pscustomobject]@{LocalAddress='192.168.137.1';RemoteAddress='192.168.137.0/255.255.255.0'};"
        "interface_filter=[pscustomobject]@{InterfaceAlias='Wi-Fi 3'};application_filter=$null};"
        "Test-CialRuleContract $snapshot 'TCP' '80' '192.168.137.1' '192.168.137.0/24' 'Wi-Fi 3'"
    )
    assert output == "True"


def test_firewall_inspect_state_classification_is_truthful():
    output = _run_firewall_contract(
        "[pscustomobject]@{"
        "absent=(Get-CialContractState 0 0 $true $false $false);"
        "partial=(Get-CialContractState 1 0 $true $true $false);"
        "mismatched=(Get-CialContractState 1 1 $true $false $true);"
        "duplicate=(Get-CialContractState 2 1 $true $true $true);"
        "ready=(Get-CialContractState 1 1 $true $true $true)"
        "}|ConvertTo-Json -Compress"
    )
    assert json.loads(output) == {
        "absent": "absent",
        "partial": "partial",
        "mismatched": "mismatched",
        "duplicate": "mismatched",
        "ready": "ready",
    }


def test_firewall_creation_commands_are_exactly_scoped():
    source = (settings.repo_path / "scripts" / "lan_firewall.ps1").read_text(
        encoding="utf-8"
    )
    assert source.count("New-NetFirewallRule") == 2
    assert "-Protocol TCP -LocalPort $HttpPort -LocalAddress $LocalAddress" in source
    assert "-Protocol UDP -LocalPort 5353 -LocalAddress $LocalAddress" in source
    assert source.count("-RemoteAddress $RemoteSubnet -InterfaceAlias $InterfaceAlias") == 2
    assert source.count("-Direction Inbound -Action Allow -Enabled True -Profile Any") == 2
    assert "-Program $resolvedDiscoveryProgram" in source
    assert "-LocalAddress Any" not in source
    assert "-RemoteAddress Any" not in source


def test_firewall_inspect_output_redacts_discovery_program():
    script = settings.repo_path / "scripts" / "lan_firewall.ps1"
    completed = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(script), "-Mode", "Inspect",
            "-LocalAddress", "192.168.137.1",
            "-RemoteSubnet", "192.168.137.0/24",
            "-HttpPort", "80",
            "-InterfaceAlias", "Wi-Fi 3",
            "-DiscoveryProgram", sys.executable,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    result = json.loads(completed.stdout)
    assert "program" not in json.dumps(result).casefold()
    assert str(Path(sys.executable).parent).casefold() not in completed.stdout.casefold()


def test_firewall_operations_are_owned_idempotent_and_rollback_safe():
    source = (settings.repo_path / "scripts" / "lan_firewall.ps1").read_text(
        encoding="utf-8"
    )
    inspect_block = source.split('if ($Mode -eq "Inspect") {', 1)[1].split(
        'if (-not (Test-Administrator))', 1
    )[0]
    assert "New-NetFirewallRule" not in inspect_block
    assert "Remove-CialRule" not in inspect_block
    assert 'Remove-CialRule -RuleName $HttpRuleName' in source
    assert 'Remove-CialRule -RuleName $MdnsRuleName' in source
    assert source.count('Remove-CialRule -RuleName $HttpRuleName') >= 3
    assert source.count('Remove-CialRule -RuleName $MdnsRuleName') >= 3
    assert 'state = "rolled_back"' in source
    assert 'error_code = "administrator_required"' in source
    assert "Get-NetFirewallRule -DisplayName $RuleName" in source
    assert "Where-Object { $_.Group -eq $FirewallGroupName }" in source
    assert "$HttpRuleCount -eq 1" in source
    assert "$MdnsRuleCount -eq [int]$MdnsRequired" in source
    apply_result_body = re.search(
        r'\[pscustomobject\]@\{\s*mode = "apply"(?P<body>.*?)\}\s*\| ConvertTo-Json',
        source,
        re.DOTALL,
    ).group("body")
    assert "discovery_program =" not in apply_result_body.casefold()
    assert "program =" not in apply_result_body.casefold()


def test_manager_requires_verified_firewall_json(monkeypatch, tmp_path):
    adapter = HotspotAdapter(
        "Wi-Fi 3", 11, "192.168.137.1", 24, "192.168.137.0/24",
        "windows_mobile_hotspot", "high", "fixture",
    )
    monkeypatch.setattr(
        lan_manager.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"mode": "apply", "state": "ready", "verified": True}),
        ),
    )
    assert lan_manager._run_firewall(tmp_path, mode="Apply", adapter=adapter, port=80) == "ready"

    monkeypatch.setattr(
        lan_manager.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout=json.dumps({
                "mode": "apply",
                "state": "rolled_back",
                "verified": False,
                "error_code": "firewall_verification_failed",
            }),
        ),
    )
    with pytest.raises(FirewallOperationError) as captured:
        lan_manager._run_firewall(tmp_path, mode="Apply", adapter=adapter, port=80)
    assert captured.value.state == "rolled_back"
    assert "rolled back" in captured.value.safe_detail


def _manager_firewall_settings(tmp_path):
    return SimpleNamespace(
        repo_path=tmp_path,
        lan_domain="cial-knowledge-os.local",
        lan_https_enabled=False,
        lan_http_port=80,
        lan_https_port=443,
        lan_allow_ip_fallback=True,
        lan_mode="hotspot",
        lan_qr_enabled=False,
        lan_keep_awake=False,
        lan_firewall_managed=True,
        lan_mdns_enabled=False,
        lan_adapter_recheck_seconds=0,
    )


def test_manager_stops_caddy_and_skips_mdns_on_firewall_failure(monkeypatch, tmp_path):
    adapter = HotspotAdapter(
        "Wi-Fi 3", 11, "192.168.137.1", 24, "192.168.137.0/24",
        "windows_mobile_hotspot", "high", "fixture",
    )
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    monkeypatch.setattr(lan_manager, "settings", _manager_firewall_settings(tmp_path))
    monkeypatch.setattr(lan_manager, "_detect", lambda root: adapter)
    manager = LanManager(backend_port=8000, frontend_root=frontend)
    events = []
    monkeypatch.setattr(manager, "_start_gateway", lambda selected: events.append("caddy_started"))
    monkeypatch.setattr(manager, "_stop_gateway", lambda: events.append("caddy_stopped"))
    monkeypatch.setattr(manager.mdns, "register", lambda **kwargs: events.append("mdns_started"))
    monkeypatch.setattr(manager.mdns, "unregister", lambda: events.append("mdns_stopped"))
    monkeypatch.setattr(manager.keep_awake, "release", lambda: events.append("awake_released"))

    def firewall(root, *, mode, adapter, port):
        if mode == "Apply":
            raise FirewallOperationError(
                state="rolled_back",
                error_code="firewall_verification_failed",
                safe_detail="CIAL firewall verification failed and owned rules were rolled back.",
            )
        return "absent"

    monkeypatch.setattr(lan_manager, "_run_firewall", firewall)
    assert manager.run() == 1
    assert "caddy_started" not in events
    assert "caddy_stopped" in events
    assert "mdns_started" not in events
    status = read_status(manager.status_path)
    assert status["state"] == "firewall_failed"
    assert status["firewall_state"] == "rolled_back"
    assert status["gateway_ready"] is False


def test_manager_marks_ready_only_after_firewall_success(monkeypatch, tmp_path):
    adapter = HotspotAdapter(
        "Wi-Fi 3", 11, "192.168.137.1", 24, "192.168.137.0/24",
        "windows_mobile_hotspot", "high", "fixture",
    )
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    monkeypatch.setattr(lan_manager, "settings", _manager_firewall_settings(tmp_path))
    monkeypatch.setattr(lan_manager, "_detect", lambda root: adapter)
    monkeypatch.setattr(
        lan_manager,
        "_run_firewall",
        lambda root, *, mode, adapter, port: "ready" if mode == "Apply" else "absent",
    )
    manager = LanManager(backend_port=8000, frontend_root=frontend)
    monkeypatch.setattr(manager, "_start_gateway", lambda selected: None)
    monkeypatch.setattr(manager, "_stop_gateway", lambda: None)
    observed = []
    original_status = manager.status

    def capture_status(**kwargs):
        observed.append(kwargs)
        original_status(**kwargs)
        if kwargs.get("gateway_ready"):
            manager.stop_path.write_text("stop", encoding="ascii")

    monkeypatch.setattr(manager, "status", capture_status)
    monkeypatch.setattr(lan_manager.time, "sleep", lambda seconds: None)
    assert manager.run() == 0
    ready = next(item for item in observed if item.get("gateway_ready"))
    assert ready["state"] == "ready"
    assert ready["firewall_state"] == "ready"


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
        IPVersion=SimpleNamespace(V4Only="v4"),
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


def test_instance_lock_recovers_stale_owner_record(tmp_path, monkeypatch):
    lock_path = tmp_path / "manager.lock"
    lock_path.write_text(json.dumps({"version": 1, "pid": 999999}), encoding="ascii")
    monkeypatch.setattr(lan_manager, "_pid_is_lan_manager", lambda pid: False)
    with InstanceLock(lock_path):
        metadata = json.loads(lock_path.read_text(encoding="ascii"))
        assert metadata["pid"] > 0
        assert metadata["kind"] == "cial_lan_manager"
    assert not lock_path.exists()


def test_live_stale_owner_record_fails_closed(tmp_path, monkeypatch):
    lock_path = tmp_path / "manager.lock"
    lock_path.write_text(json.dumps({"version": 1, "pid": 4242}), encoding="ascii")
    monkeypatch.setattr(lan_manager, "_pid_is_lan_manager", lambda pid: pid == 4242)
    with pytest.raises(RuntimeError, match="already running"):
        with InstanceLock(lock_path):
            pass


def test_hotspot_loss_and_address_changes_require_cleanup():
    original = HotspotAdapter(
        "Wi-Fi 3", 11, "192.168.137.1", 24, "192.168.137.0/24",
        "windows_mobile_hotspot", "high", "fixture",
    )
    changed = HotspotAdapter(
        "Wi-Fi 3", 11, "192.168.50.1", 24, "192.168.50.0/24",
        "windows_mobile_hotspot", "high", "fixture",
    )
    assert needs_reconfigure(original, None) is True
    assert needs_reconfigure(original, changed) is True
    assert needs_reconfigure(original, original) is False


@pytest.mark.parametrize("replacement", [None, "changed"])
def test_runtime_hotspot_change_runs_owned_cleanup(monkeypatch, tmp_path, replacement):
    original = HotspotAdapter(
        "Wi-Fi 3", 11, "192.168.137.1", 24, "192.168.137.0/24",
        "windows_mobile_hotspot", "high", "fixture",
    )
    changed = HotspotAdapter(
        "Wi-Fi 3", 11, "192.168.50.1", 24, "192.168.50.0/24",
        "windows_mobile_hotspot", "high", "fixture",
    )
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    fake_settings = SimpleNamespace(
        repo_path=tmp_path,
        lan_domain="cial-knowledge-os.local",
        lan_https_enabled=False,
        lan_http_port=80,
        lan_https_port=443,
        lan_allow_ip_fallback=True,
        lan_mode="hotspot",
        lan_qr_enabled=False,
        lan_keep_awake=False,
        lan_firewall_managed=False,
        lan_mdns_enabled=False,
        lan_adapter_recheck_seconds=0,
    )
    monkeypatch.setattr(lan_manager, "settings", fake_settings)
    detections = iter([original, changed if replacement == "changed" else None])
    monkeypatch.setattr(lan_manager, "_detect", lambda root: next(detections))
    monkeypatch.setattr(lan_manager.time, "sleep", lambda seconds: None)
    manager = LanManager(backend_port=8000, frontend_root=frontend)
    events = []
    monkeypatch.setattr(manager, "_start_gateway", lambda adapter: events.append("start"))
    monkeypatch.setattr(manager, "_gateway_is_healthy", lambda adapter: True)
    monkeypatch.setattr(manager, "_stop_gateway", lambda: events.append("stop"))
    monkeypatch.setattr(manager.mdns, "unregister", lambda: events.append("mdns_unregistered"))
    monkeypatch.setattr(manager.keep_awake, "release", lambda: events.append("awake_released"))
    assert manager.run() == 75
    assert events == ["start", "stop", "mdns_unregistered", "awake_released"]
    assert read_status(manager.status_path)["state"] == "reconfiguring"


@pytest.mark.parametrize(
    ("detections", "gateway_healthy", "expected_probe_calls"),
    [
        (
            [
                subprocess.TimeoutExpired("get_lan_adapter.ps1", 15),
                subprocess.SubprocessError("probe failed"),
                OSError("probe unavailable"),
            ],
            True,
            3,
        ),
        ([subprocess.TimeoutExpired("get_lan_adapter.ps1", 15)], False, 1),
    ],
)
def test_runtime_adapter_probe_failures_eventually_reconfigure(
    monkeypatch,
    tmp_path,
    detections,
    gateway_healthy,
    expected_probe_calls,
):
    original = HotspotAdapter(
        "Wi-Fi", 7, "192.168.1.111", 24, "192.168.1.0/24",
        "explicit_hotspot_binding", "explicit", "operator binding",
    )
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    fake_settings = SimpleNamespace(
        repo_path=tmp_path,
        lan_domain="cial-knowledge-os.local",
        lan_https_enabled=False,
        lan_http_port=80,
        lan_https_port=443,
        lan_allow_ip_fallback=True,
        lan_mode="hotspot",
        lan_qr_enabled=False,
        lan_keep_awake=False,
        lan_firewall_managed=False,
        lan_mdns_enabled=False,
        lan_adapter_recheck_seconds=0,
        lan_adapter_probe_failure_limit=3,
    )
    outcomes = iter([original, *detections])
    probe_calls = []

    def detect(_root):
        probe_calls.append(True)
        result = next(outcomes)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(lan_manager, "settings", fake_settings)
    monkeypatch.setattr(lan_manager, "_detect", detect)
    monkeypatch.setattr(lan_manager.time, "sleep", lambda seconds: None)
    manager = LanManager(backend_port=8000, frontend_root=frontend)
    monkeypatch.setattr(manager, "_start_gateway", lambda adapter: None)
    monkeypatch.setattr(manager, "_gateway_is_healthy", lambda adapter: gateway_healthy)
    monkeypatch.setattr(manager, "_stop_gateway", lambda: None)
    monkeypatch.setattr(manager.mdns, "unregister", lambda: None)
    monkeypatch.setattr(manager.keep_awake, "release", lambda: None)

    assert manager.run() == 75
    assert len(probe_calls) == expected_probe_calls + 1
    assert read_status(manager.status_path)["state"] == "reconfiguring"


def test_successful_adapter_probe_resets_transient_failure_counter(monkeypatch, tmp_path):
    original = HotspotAdapter(
        "Wi-Fi", 7, "192.168.1.111", 24, "192.168.1.0/24",
        "explicit_hotspot_binding", "explicit", "operator binding",
    )
    changed = replace(original, address="192.168.1.112")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    timeout = lambda: subprocess.TimeoutExpired("get_lan_adapter.ps1", 15)
    outcomes = iter([original, timeout(), timeout(), original, timeout(), timeout(), changed])
    fake_settings = SimpleNamespace(
        repo_path=tmp_path,
        lan_domain="cial-knowledge-os.local",
        lan_https_enabled=False,
        lan_http_port=80,
        lan_https_port=443,
        lan_allow_ip_fallback=True,
        lan_mode="hotspot",
        lan_qr_enabled=False,
        lan_keep_awake=False,
        lan_firewall_managed=False,
        lan_mdns_enabled=False,
        lan_adapter_recheck_seconds=0,
        lan_adapter_probe_failure_limit=3,
    )

    def detect(_root):
        result = next(outcomes)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(lan_manager, "settings", fake_settings)
    monkeypatch.setattr(lan_manager, "_detect", detect)
    monkeypatch.setattr(lan_manager.time, "sleep", lambda seconds: None)
    manager = LanManager(backend_port=8000, frontend_root=frontend)
    monkeypatch.setattr(manager, "_start_gateway", lambda adapter: None)
    monkeypatch.setattr(manager, "_gateway_is_healthy", lambda adapter: True)
    monkeypatch.setattr(manager, "_stop_gateway", lambda: None)
    monkeypatch.setattr(manager.mdns, "unregister", lambda: None)
    monkeypatch.setattr(manager.keep_awake, "release", lambda: None)

    assert manager.run() == 75
    assert read_status(manager.status_path)["state"] == "reconfiguring"


def test_runtime_adapter_probe_timeout_retains_healthy_gateway(monkeypatch, tmp_path):
    original = HotspotAdapter(
        "Wi-Fi", 7, "192.168.1.111", 24, "192.168.1.0/24",
        "explicit_hotspot_binding", "explicit", "operator binding",
    )
    changed = replace(original, address="192.168.1.112")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    fake_settings = SimpleNamespace(
        repo_path=tmp_path,
        lan_domain="cial-knowledge-os.local",
        lan_https_enabled=False,
        lan_http_port=80,
        lan_https_port=443,
        lan_allow_ip_fallback=True,
        lan_mode="hotspot",
        lan_qr_enabled=False,
        lan_keep_awake=False,
        lan_firewall_managed=False,
        lan_mdns_enabled=False,
        lan_adapter_recheck_seconds=0,
    )
    detections = iter(
        [
            original,
            subprocess.TimeoutExpired("get_lan_adapter.ps1", 15),
            changed,
        ]
    )

    def detect(_root):
        result = next(detections)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(lan_manager, "settings", fake_settings)
    monkeypatch.setattr(lan_manager, "_detect", detect)
    monkeypatch.setattr(lan_manager.time, "sleep", lambda seconds: None)
    manager = LanManager(backend_port=8000, frontend_root=frontend)
    events = []
    monkeypatch.setattr(manager, "_start_gateway", lambda adapter: events.append("start"))
    monkeypatch.setattr(manager, "_stop_gateway", lambda: events.append("stop"))
    monkeypatch.setattr(manager.mdns, "unregister", lambda: events.append("mdns_unregistered"))
    monkeypatch.setattr(manager.keep_awake, "release", lambda: events.append("awake_released"))

    assert manager.run() == 75
    assert events == ["start", "stop", "mdns_unregistered", "awake_released"]
    assert read_status(manager.status_path)["state"] == "reconfiguring"


def test_launch_scripts_are_repo_venv_only_and_idempotent():
    start = (settings.repo_path / "scripts" / "start_lan_gateway.ps1").read_text(encoding="utf-8")
    production_launcher = (settings.repo_path / "Launch-CIAL-Knowledge-OS.ps1").read_text(encoding="utf-8")
    assert 'Join-Path $RepoRoot ".venv\\Scripts\\python.exe"' in start
    assert "Get-Command python" not in start
    assert "Test-CialManagerProcess" in start
    assert "already running" in start
    assert "[switch]$Lan" in production_launcher
    assert '[Alias("lan")]' not in production_launcher


def test_stop_script_targets_only_recorded_owned_processes_and_is_idempotent():
    stop = (settings.repo_path / "scripts" / "stop_lan_gateway.ps1").read_text(encoding="utf-8")
    assert "Get-RecordedPid -Path $LockPath" in stop
    assert "backend\\.app\\.lan\\.manager" in stop
    assert "GeneratedCaddyfile" in stop
    assert "Get-Process |" not in stop
    assert "Write-StoppedStatus" in stop


def test_firewall_script_scopes_rules_to_selected_hotspot_only():
    source = (settings.repo_path / "scripts" / "lan_firewall.ps1").read_text(encoding="utf-8")
    assert "-LocalAddress $LocalAddress" in source
    assert "-RemoteAddress $RemoteSubnet" in source
    assert "-InterfaceAlias $InterfaceAlias" in source
    assert "-LocalPort $HttpPort" in source
    assert "-Profile Any" in source
    assert "Get-NetFirewallApplicationFilter" in source


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
