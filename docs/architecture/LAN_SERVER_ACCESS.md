# Laptop LAN Server Access

Status: optional Windows hotspot edge mode. Disabled by default.

## Purpose

Laptop LAN Server Mode makes one Windows laptop the complete CIAL server while
phones, tablets, and other laptops on its Windows Mobile Hotspot remain
browser-only clients. The preferred URL is
`http://cial-knowledge-os.local`; the detected hotspot IPv4 URL is always
shown as a fallback.

This mode does not change the query or indexing architecture. FastAPI remains
query-only, the standalone indexer remains the only continuous indexing
worker, PostgreSQL remains the metadata/control plane, Qdrant remains the
vector store, Ollama remains the local generator, and React/Vite remains the
browser application.

## Threat model

Hotspot membership is connectivity, not authorization. Every client must
authenticate with the existing backend-issued HttpOnly session cookie and
every workspace, document, preview, download, chat, source, and admin request
is reauthorized by the existing backend policy.

HTTP hotspot mode is intentionally labelled unencrypted and is suitable only
for a controlled local hotspot. It does not protect credentials or content
from another party able to observe that LAN. Managed HTTPS is a separate
explicit mode and is not considered trusted until the client trusts and
validates the Caddy local CA. The launcher never installs a client root
certificate or suppresses a browser warning.

## Topology and port boundary

```text
hotspot browser
  -> detected-hotspot-ip:80 (Caddy, the only TCP LAN listener)
       -> / and assets: frontend/dist/public
       -> /api/*: 127.0.0.1:8000

127.0.0.1:8000   FastAPI query/auth API
127.0.0.1:5432   PostgreSQL
127.0.0.1:6335   Qdrant
127.0.0.1:11434  Ollama
no listener      standalone indexer
UDP 5353         mDNS publisher, hotspot interface only when supported
```

Vite development and preview servers are never part of LAN mode. Caddy serves
the compiled production files directly. Docker port publications for
PostgreSQL and Qdrant must use explicit `127.0.0.1` host bindings.

## One-origin gateway

The browser uses one origin. Frontend production builds use an empty
`VITE_API_BASE_URL`, so `/api/*`, PDF.js assets, uploads, downloads, NDJSON
chat, summary streams, and admin SSE all traverse Caddy. The generated
Caddyfile:

- binds only the selected hotspot address and configured HTTP/HTTPS port;
- rejects unexpected `Host` values;
- serves the SPA with `index.html` fallback and no directory listing;
- proxies `/api/*` to the loopback backend with forwarded headers;
- disables proxy response buffering and flushes streaming responses;
- bounds `/api/*` request bodies at 512 MB without loading them into the
  gateway process; oversized requests receive an edge-level rejection;
- applies compatible security headers and no HSTS in HTTP mode;
- uses bounded rotating access/error logs with query strings, request/response
  headers, cookies, and bodies excluded.

FastAPI accepts only configured loopback and LAN hosts. Forwarded headers are
interpreted only because Uvicorn is launched with the loopback Caddy address
as its proxy allowlist; a LAN client cannot connect directly to FastAPI.

## Hotspot detection

The Windows detector consumes safe projections of `Get-NetAdapter`,
`Get-NetIPAddress`, `Get-NetIPConfiguration`, `Get-NetConnectionProfile`, and
available ICS/NAT evidence. It requires an Up interface with a private,
non-link-local IPv4 address and prefix. Loopback, VPN, tunnel, Bluetooth,
Docker, Hyper-V, WSL, and other virtualization adapters are excluded unless
an explicit override selects them.

Explicit binding is evaluated before hotspot scoring. An interface override is
case-insensitive, an IP override is exact, and a combined override must match
the same probe record. Interface-only and IP-only modes must each resolve one
Up record with one safe private IPv4. Loopback, link-local, multicast, and
unspecified addresses are rejected. A missing, down, mismatched, or ambiguous
explicit binding raises an actionable safe error and never becomes the generic
waiting-for-hotspot state. Explicit selection does not require ICS, NAT, or
Wi-Fi Direct evidence.

Automatic candidates receive evidence and a confidence explanation. In
addition to ICS/NAT/Wi-Fi Direct evidence, scoring recognizes the common
Windows Mobile Hotspot `192.168.137.1/24` shape, a secondary Up wireless
gateway-like address, and a separate public wireless uplink. The observed
address on this workstation is `192.168.137.1`; it is a common default, not a
universal constant. WSL, generic Hyper-V, Docker, VPN, Bluetooth, tunnel, and
disconnected adapters are excluded. More than one equally plausible candidate
fails closed. No single interface alias is hardcoded. IPv4 plus prefix is
converted with the standard IP network operation, including `/16`, `/20`, and
`/24`.

The manager revalidates before binding and periodically thereafter. If the
hotspot is absent, local CIAL remains available and LAN status says:

> CIAL is running on this device. LAN access is waiting for Windows Mobile Hotspot.

An address change stops admission, unregisters discovery, rebinds the owned
gateway, updates owned firewall rules, republishes discovery, and refreshes
the health projection and QR URL.

The periodic Windows adapter probe is external to the gateway process. A
PowerShell/WMI timeout or malformed transient response is logged as
`adapter_probe_timeout`/`adapter_probe_failed` with `gateway_retained` when the
owned Caddy process and bound HTTP listener remain healthy. It does not reset
active client streams. Three consecutive failed probes (configurable with
`CIAL_LAN_ADAPTER_PROBE_FAILURE_LIMIT`) or one failed gateway health check
causes fail-closed reconfiguration. A successful probe resets the failure
counter, and a completed probe that proves the selected address was lost or
changed follows the same reconfiguration path.

## Discovery and IP fallback

The isolated publisher uses the Python `zeroconf` package. It advertises:

- host `cial-knowledge-os.local` (or the validated configured domain);
- service `_http._tcp.local`;
- the current LAN port and detected hotspot IPv4;
- TXT keys limited to product, version, and scheme.

Registration is limited to the selected interface when the library supports
it. A naming conflict is reported and retries deterministically with
`cial-knowledge-os-2.local`. Registration is removed during shutdown. An mDNS
failure never removes IP access. `.local` client support varies, so the
launcher and admin projection always show the IP fallback and must not claim
universal zero-configuration discovery without physical-device UAT.

## Firewall

Firewall management is opt-in through
`CIAL_LAN_FIREWALL_MANAGED=true` and requires an elevated PowerShell session.
Rules are idempotent, grouped as `CIAL Knowledge OS LAN`, and named with the
`CIAL-LAN-` prefix. TCP is limited to the configured gateway port, hotspot
local address, and hotspot subnet. UDP 5353 is added only for enabled mDNS and
is scoped to the discovery program/interface capabilities supported by
Windows. Rules use all Windows network profiles because hotspot interfaces may
be unclassified or Public, but the local address, remote subnet, interface,
protocol, and port constraints remain mandatory and are verified after
creation. Internal service ports are never opened.

Inspect reports `absent`, `partial`, `mismatched`, or `ready` without mutation.
It normalizes PowerShell scalars/arrays, numeric or named protocols, and the
CIDR or dotted-netmask forms returned by Windows before comparing the effective
filters. Apply reconciles the two stable CIAL-owned names and rolls both back
if creation or verification fails; Remove is idempotent and never selects
unrelated rules. A manager does not report `firewall_state=ready` until the
effective rule address, interface, profile, protocol, port, program, and remote
scope match. Firewall failure is fail-closed: Caddy is stopped and mDNS is not
started.

PowerShell variable names are case-insensitive. In particular, a typed
`[int]$HttpPort` parameter must not be reused as `$httpPort` for a CIM port
filter; use distinct names such as `$httpPortFilter`. Launching the script from
`cmd.exe` does not change this PowerShell binding rule.

## Authentication, cookies, and hosts

The session cookie remains host-only (`Domain` is omitted), `Path=/`,
`HttpOnly`, and `SameSite=Lax` unless a stricter compatible value is
configured. `Secure=false` is allowed only for explicit HTTP LAN mode;
`Secure=true` is required in HTTPS mode. Login, refresh, and logout use the
same attributes.

HTTPS state uses the configured app-owned Caddy data/config directory. Before
Caddy can start in HTTPS mode, the manager replaces and verifies the DACL on
that tree: inheritance is disabled and only the current server user, SYSTEM,
and built-in Administrators receive Full Control. Any inherited rule, broad
principal, missing approved principal, ACL application error, or verification
error fails HTTPS closed with a path-free actionable error. HTTP and local-only
CIAL remain available. Existing certificate state is permission-hardened in
place; startup and cleanup do not delete or regenerate it.

Allowed hosts are loopback names/addresses, the configured `.local` domain,
the currently detected hotspot address, and an explicitly reported conflict
hostname. Wildcard authenticated CORS is prohibited. Same-origin LAN traffic
needs no CORS permission. Development loopback origins remain available.

## Process lifecycle

The optional manager owns only hotspot detection, generated Caddy
configuration/process, mDNS registration, the process-scoped Windows
execution-state lease, CIAL-owned firewall state, rotating LAN logs, and a
sanitized health file. It never imports retrieval/indexing models, reads the
corpus, or opens Qdrant collections.

A readable JSON owner file plus a separate OS byte lock prevents duplicate
managers. The owner PID is checked against the LAN-manager module before start
or forced stop. An unlocked record whose PID is absent or no longer a LAN
manager is recovered as stale; a live lock is never deleted. The start script
invokes only `<repo>\.venv\Scripts\python.exe` and repeated start is
idempotent. Caddy PID metadata includes its manager owner and the stop path
also verifies the generated Caddy configuration before terminating it, so
shutdown never kills an unrelated Python or Caddy process. `SetThreadExecutionState`
prevents system sleep without changing a power plan or forcing the display on;
the lease is released in `finally`. Closing the lid may still suspend the
laptop according to Windows policy.

Startup:

1. validate settings, frontend build, and staged Caddy;
2. detect/revalidate the hotspot;
3. acquire the process-scoped keep-awake lease;
4. verify the app-owned HTTPS state ACL when HTTPS is enabled;
5. start Caddy on the detected address;
6. apply and verify optional firewall rules;
7. publish mDNS;
8. verify IP/domain frontend, auth route, and streaming route behavior;
9. display security state, exact URLs, and an offline-generated QR code.

Shutdown stops the owned Caddy first, then unregisters mDNS, releases
keep-awake, and removes only ephemeral CIAL-owned firewall rules and process
markers. Certificate state is preserved. Core service lifecycle remains owned
by the normal launcher.

## Configuration

| Variable | Default |
| --- | --- |
| `CIAL_LAN_ACCESS_ENABLED` | `false` |
| `CIAL_LAN_MODE` | `hotspot` |
| `CIAL_LAN_HOSTNAME` | `cial-knowledge-os` |
| `CIAL_LAN_DOMAIN` | `cial-knowledge-os.local` |
| `CIAL_LAN_BIND_INTERFACE` | `auto` |
| `CIAL_LAN_BIND_IP` | `auto` |
| `CIAL_LAN_HTTP_PORT` | `80` |
| `CIAL_LAN_HTTPS_ENABLED` | `false` |
| `CIAL_LAN_HTTPS_PORT` | `443` |
| `CIAL_LAN_ALLOW_IP_FALLBACK` | `true` |
| `CIAL_LAN_MDNS_ENABLED` | `true` |
| `CIAL_LAN_GATEWAY` | `caddy` |
| `CIAL_CADDY_PATH` | empty; operator/installer staged |
| `CIAL_LAN_GATEWAY_DATA_DIR` | `outputs/lan-server/caddy` |
| `CIAL_LAN_FIREWALL_MANAGED` | `true` |
| `CIAL_LAN_FIREWALL_REMOTE_SCOPE` | `hotspot_subnet` |
| `CIAL_LAN_QR_ENABLED` | `true` |
| `CIAL_LAN_KEEP_AWAKE` | `true` |
| `CIAL_LAN_ADAPTER_RECHECK_SECONDS` | `5` |
| `CIAL_LAN_STARTUP_TIMEOUT_SECONDS` | `30` |
| `CIAL_LAN_SHUTDOWN_TIMEOUT_SECONDS` | `10` |

Host labels, `.local` domain, port ranges, mode combinations, interface/IP
overrides, and app-owned paths are validated before mutation.

## Status contract

Authenticated `/api/system/status` and the authorized admin monitor add a
non-critical `lan_access` object: `state`, `enabled`, `mode`, `gateway_ready`,
`discovery_ready`, `hostname`, `scheme`, `port`, `hotspot_detected`,
`bind_address_available`, `ip_fallback_available`, `tls_state`,
`firewall_state`, `keep_awake`, `checked_at`, and `safe_detail`.

The backend reads only the sanitized manager health file. LAN failure never
changes `chat_available` for localhost use. The projection excludes SSID,
password, MAC/GUID, client identities or history, cookies, secrets, and
absolute repository/executable/workspace paths.

`state` is one of `disabled`, `waiting_for_hotspot`,
`explicit_binding_invalid`, `adapter_detected`, `caddy_validating`,
`ready`, `firewall_failed`, `mdns_failed`, `reconfiguring`, or `stopped`
for the corresponding lifecycle point. mDNS failure may coexist with
`gateway_ready=true` and a working IP fallback. Explicit-binding failures use
messages such as “Configured LAN interface is unavailable” or “Configured LAN
IP is not assigned to the selected interface”; they are not misreported as a
missing hotspot.

## Failure behavior

- Missing hotspot: local runtime continues; LAN waits.
- Ambiguous adapters: fail closed with interface/IP override guidance.
- Missing/invalid Caddy or port conflict: LAN unavailable; no unrelated
  process is killed.
- mDNS failure: IP URL remains usable.
- Firewall failure: external readiness is not claimed.
- Missing/stale frontend build: explicit rebuild or controlled failure.
- FastAPI failure: gateway returns a controlled 503 response.
- Indexer failure with a valid generation: chat remains available and indexing
  is degraded under the existing health semantics.
- Address loss/change: pause, re-detect, and reconfigure owned edge state.

## Testing and UAT

Unit tests cover settings, adapter selection/subnets/overrides, Caddy
generation, host boundaries, health sanitization, mDNS lifecycle, firewall
plans, process ownership, keep-awake release, address changes, and disabled
local mode. PowerShell tests cover parsing, elevation/dry-run, path resolution,
rerunnability, spaces, waiting-for-hotspot, and alternate ports.

Automated browser validation uses a real production build behind real Caddy.
Host-resolver mapping on the server is automation evidence only, not mDNS UAT.
Artifacts belong under `outputs/playwright/lan-server-mode/`.

Physical-device UAT must record only device family/browser/OS and verify
domain, IP fallback, login, chat, citation preview, theme/mobile layout, and
reconnect. Until performed, domain interoperability and trusted HTTPS remain
explicitly pending.

### Current-machine UAT (2026-08-01)

The live Windows probe observed `Wi-Fi 3`, interface index 11,
`192.168.137.1/24`, Up, on the MediaTek adapter, with all ICS/NAT/Wi-Fi Direct
flags false and a separate Public Wi-Fi uplink. Both explicit and automatic
dry runs selected it and real Caddy validation produced `bind 192.168.137.1`.
Host UAT then measured:

- exactly one lock-owning manager launched through the repository `.venv`;
  Windows' venv redirector also retains one waiting parent launcher process;
- one Caddy child owned by that manager and one listener at
  `192.168.137.1:80`;
- HTTP 200 for the SPA by IP and by `cial-knowledge-os.local`, and HTTP 200 for
  `/api/health` through both names;
- live mDNS registration resolving `cial-knowledge-os.local` to
  `192.168.137.1` after updating the installed zeroconf API usage to
  `IPVersion.V4Only`;
- hotspot Off removed Caddy/listener and reported
  `explicit_binding_invalid`; hotspot On restored the same waiting manager,
  listener, mDNS, and IP fallback;
- repeated start preserved the owner PID; two repeated stops returned success
  and left no listener, manager owner, Caddy process, PID file, or lock.

The validation shell was not an Administrator. Firewall Inspect confirmed the
requested local address `192.168.137.1`, remote subnet `192.168.137.0/24`, port
80, and interface `Wi-Fi 3`, but Apply could not be executed. No CIAL-owned
rules were present. Therefore administrator firewall Apply/Remove and physical
second-device login/session/chat/document/citation checks remain pending and
browser automation was intentionally not opened.

### Current-server release validation (2026-08-08)

The production server used the explicitly validated `Wi-Fi` binding at
`192.168.1.111/24` (remote subnet `192.168.1.0/24`). Operator-installed Caddy
served the canonical `frontend/dist/public` build and was the only LAN TCP
listener at `192.168.1.111:80`; FastAPI 8000, PostgreSQL 5432, Qdrant 6335,
Ollama 11434, and the optional Vite preview 5173 remained loopback-only. Both
`http://192.168.1.111/login` and `http://cial-knowledge-os.local/login`
returned 200, and mDNS status was ready.

Real Playwright navigation through the IP fallback completed signup and
reached the authenticated dashboard. Real streamed chat through Caddy returned
grounded PDF citations before and after controlled Qdrant, Ollama, API, and
gateway restarts. During the restart exercise, an adapter probe exceeded its
15-second timeout and exposed that the manager previously treated a transient
probe stall as fatal; the manager now retains the healthy gateway, with a
regression test covering timeout followed by a later real address change.

Firewall Inspect was non-mutating and reported `state=mismatched` for existing
CIAL-owned HTTP and mDNS rules because they do not match the current Wi-Fi
address/subnet/interface. Apply was intentionally not attempted without an
Administrator token. From an elevated PowerShell at the repository root, the
exact reconciliation and verification commands are:

```powershell
.\scripts\lan_firewall.ps1 -Mode Apply -LocalAddress 192.168.1.111 -RemoteSubnet 192.168.1.0/24 -HttpPort 80 -InterfaceAlias 'Wi-Fi' -DiscoveryProgram .\.venv\Scripts\python.exe
.\scripts\lan_firewall.ps1 -Mode Inspect -LocalAddress 192.168.1.111 -RemoteSubnet 192.168.1.0/24 -HttpPort 80 -InterfaceAlias 'Wi-Fi' -DiscoveryProgram .\.venv\Scripts\python.exe
```

Require `state=ready`, `verified=true`, `http_valid=true`, and
`mdns_valid=true` before physical-device UAT. PostgreSQL service restart also
requires an Administrator token on this host; use
`Restart-Service -Name postgresql-x64-18 -Force`, then require port 5432 and
`database_ready=true`. These two elevation-only checks and physical second-
device/browser interoperability remain outside host automation.

## Operations and troubleshooting

From the repository root:

```powershell
.\scripts\get_lan_adapter.ps1
.\scripts\start_lan_gateway.ps1 -BackendPort 8000
Get-Content .\outputs\lan-server\manager.lock
Get-Content .\outputs\lan-server\status.json
Get-NetTCPConnection -State Listen | Where-Object LocalPort -In 80,443,8000,6335,5432,11434
Get-NetFirewallRule -Group "CIAL Knowledge OS LAN"
.\scripts\stop_lan_gateway.ps1
```

For direct elevated firewall diagnosis, use the exact detected scope. These
commands are safe to repeat:

```powershell
.\scripts\lan_firewall.ps1 -Mode Apply -LocalAddress 192.168.137.1 -RemoteSubnet 192.168.137.0/24 -HttpPort 80 -InterfaceAlias 'Wi-Fi 3' -DiscoveryProgram .\.venv\Scripts\python.exe
.\scripts\lan_firewall.ps1 -Mode Inspect -LocalAddress 192.168.137.1 -RemoteSubnet 192.168.137.0/24 -HttpPort 80 -InterfaceAlias 'Wi-Fi 3' -DiscoveryProgram .\.venv\Scripts\python.exe
.\scripts\lan_firewall.ps1 -Mode Remove
```

Apply and Remove require an Administrator token. Inspect does not. Consume the
JSON result and require `state=ready` plus `verified=true` before treating
Apply as successful; `rolled_back`, `permission_denied`, and malformed output
are failures.

Exactly one process command line may contain `backend.app.lan.manager`; its
owner PID must equal `manager.lock.pid`. Port 80/443 must listen on only the
selected hotspot address. Ports 8000, 6335, 5432, and 11434 must remain on
loopback. If status says `explicit_binding_invalid`, compare the configured
alias/IP with the current probe rather than deleting the lock or weakening
detection. If `mdns_failed`, use `ip_fallback_url`; IP access is intentionally
independent from `.local` support.

## Limitations and enterprise path

Consumer `.local` behavior and Windows Mobile Hotspot implementation details
vary. HTTP is unencrypted. Caddy internal-CA HTTPS needs per-client trust
onboarding. The future enterprise deployment path is managed DNS plus a
managed certificate/private PKI and policy-controlled firewall distribution;
it does not require changing FastAPI, indexing, retrieval, or storage.
