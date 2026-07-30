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
- bounds request bodies without loading them into the gateway process;
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

Candidates receive evidence and a confidence explanation. More than one
equally plausible candidate fails closed. `CIAL_LAN_BIND_INTERFACE` or
`CIAL_LAN_BIND_IP` can resolve an operator-reviewed ambiguity. No interface
name, index, address, or subnet is hardcoded. IPv4 plus prefix is converted
with the standard IP network operation, including `/16`, `/20`, and `/24`.

The manager revalidates before binding and periodically thereafter. If the
hotspot is absent, local CIAL remains available and LAN status says:

> CIAL is running on this device. LAN access is waiting for Windows Mobile Hotspot.

An address change stops admission, unregisters discovery, rebinds the owned
gateway, updates owned firewall rules, republishes discovery, and refreshes
the health projection and QR URL.

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
Windows. Internal service ports are never opened.

Inspect/dry-run prints the proposed commands without mutation. Disable and
uninstall remove only the stable CIAL-owned rule names. A manager does not
report `firewall_state=ready` until effective rule address, protocol, port,
program, and remote scope match.

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

A file lock prevents duplicate managers. PID metadata includes ownership
tokens, so shutdown never kills an unrelated Caddy. `SetThreadExecutionState`
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
non-critical `lan_access` object: `enabled`, `mode`, `gateway_ready`,
`discovery_ready`, `hostname`, `scheme`, `port`, `hotspot_detected`,
`bind_address_available`, `ip_fallback_available`, `tls_state`,
`firewall_state`, `keep_awake`, `checked_at`, and `safe_detail`.

The backend reads only the sanitized manager health file. LAN failure never
changes `chat_available` for localhost use. The projection excludes SSID,
password, MAC/GUID, client identities or history, cookies, secrets, and
absolute repository/executable/workspace paths.

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

## Limitations and enterprise path

Consumer `.local` behavior and Windows Mobile Hotspot implementation details
vary. HTTP is unencrypted. Caddy internal-CA HTTPS needs per-client trust
onboarding. The future enterprise deployment path is managed DNS plus a
managed certificate/private PKI and policy-controlled firewall distribution;
it does not require changing FastAPI, indexing, retrieval, or storage.
