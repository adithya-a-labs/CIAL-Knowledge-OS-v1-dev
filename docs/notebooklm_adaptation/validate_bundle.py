from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent

REQUIRED_FILES = [
    "README.md",
    "ANALYSIS_MANIFEST.md",
    "EXECUTIVE_SUMMARY.md",
    "reports/ROUTE_AND_SURFACE_INVENTORY.md",
    "reports/INFORMATION_ARCHITECTURE.md",
    "reports/USER_FLOW_MAP.md",
    "reports/UI_STATE_MACHINE.md",
    "reports/COMPONENT_INVENTORY.md",
    "reports/DESIGN_SYSTEM_ANALYSIS.md",
    "reports/RESPONSIVE_BEHAVIOUR.md",
    "reports/NETWORK_AND_RUNTIME_OBSERVATIONS.md",
    "reports/ACCESSIBILITY_AUDIT.md",
    "reports/ERROR_AND_EDGE_STATES.md",
    "reports/NOTEBOOKLM_FEATURE_MATRIX.md",
    "reports/CIAL_NOTEBOOK_ADAPTATION.md",
    "reports/PROPOSED_CIAL_COMPONENT_ARCHITECTURE.md",
    "reports/PROPOSED_CIAL_API_CONTRACTS.md",
    "reports/PLAYWRIGHT_REGRESSION_SPEC.md",
    "reports/SCREENSHOT_INDEX.md",
    "data/routes.json",
    "data/surfaces.json",
    "data/controls.json",
    "data/components.json",
    "data/user_flows.json",
    "data/state_transitions.json",
    "data/layout_measurements.json",
    "data/design_tokens.json",
    "data/responsive_observations.json",
    "data/accessibility_findings.json",
    "data/network_request_categories.json",
    "data/runtime_observations.json",
    "data/evidence_index.json",
    "data/feature_matrix.csv",
    "diagrams/information_architecture.mmd",
    "diagrams/user_flow.mmd",
    "diagrams/notebook_state_machine.mmd",
    "diagrams/component_hierarchy.mmd",
    "diagrams/proposed_cial_architecture.mmd",
]
REQUIRED_DIRS = [
    "reports",
    "data",
    "evidence/screenshots/desktop",
    "evidence/screenshots/tablet",
    "evidence/screenshots/mobile",
    "evidence/accessibility_snapshots",
    "evidence/dom_snapshots",
    "evidence/network",
    "evidence/console",
    "evidence/performance",
    "evidence/traces",
    "evidence/fixtures",
    "diagrams",
]


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


errors: list[str] = []
for item in REQUIRED_FILES:
    if not (ROOT / item).is_file():
        errors.append(f"missing file: {item}")
for item in REQUIRED_DIRS:
    if not (ROOT / item).is_dir():
        errors.append(f"missing directory: {item}")

json_files = sorted((ROOT / "data").glob("*.json"))
json_payloads: dict[str, dict] = {}
allowed_classifications = {"OBSERVED", "INFERRED", "RECOMMENDED", "UNKNOWN"}
for path in json_files:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"invalid JSON {relative(path)}: {exc}")
        continue
    json_payloads[path.name] = payload
    for key in ("schema_version", "generated_at", "dataset_id", "classification", "items"):
        if key not in payload:
            errors.append(f"{relative(path)} missing {key}")
    if payload.get("classification") not in allowed_classifications:
        errors.append(f"{relative(path)} has invalid top-level classification")
    seen: set[str] = set()
    for index, record in enumerate(payload.get("items", [])):
        if record.get("classification") not in allowed_classifications:
            errors.append(f"{relative(path)} item {index} has invalid classification")
        stable_ids = [
            str(value)
            for key, value in record.items()
            if key.endswith("_id") and isinstance(value, str)
        ]
        if not stable_ids:
            errors.append(f"{relative(path)} item {index} has no stable ID")
            continue
        primary = stable_ids[0]
        if primary in seen:
            errors.append(f"{relative(path)} duplicate ID: {primary}")
        seen.add(primary)

csv_path = ROOT / "data/feature_matrix.csv"
with csv_path.open(encoding="utf-8", newline="") as stream:
    reader = csv.reader(stream)
    rows = list(reader)
expected_header = [
    "feature_id",
    "feature",
    "surface",
    "purpose",
    "trigger",
    "result",
    "dependencies",
    "empty_state",
    "loading_state",
    "error_state",
    "desktop_behaviour",
    "tablet_behaviour",
    "mobile_behaviour",
    "classification",
    "cial_relevance",
    "evidence_paths",
]
if not rows or rows[0] != expected_header:
    errors.append("feature_matrix.csv header mismatch")
if len(rows) < 2:
    errors.append("feature_matrix.csv has no data rows")

screenshot_index = (ROOT / "reports/SCREENSHOT_INDEX.md").read_text(encoding="utf-8")
screenshot_paths = re.findall(r"`(evidence/screenshots/[^`]+)`", screenshot_index)
for item in screenshot_paths:
    if not (ROOT / item).is_file():
        errors.append(f"screenshot index missing target: {item}")

evidence_payload = json_payloads.get("evidence_index.json", {})
for record in evidence_payload.get("items", []):
    item = record.get("path", "")
    if not item or not (ROOT / item).is_file():
        errors.append(f"evidence index missing target: {item}")

for path in sorted((ROOT / "diagrams").glob("*.mmd")):
    text = path.read_text(encoding="utf-8").lstrip()
    if not (text.startswith("flowchart ") or text.startswith("stateDiagram-v2")):
        errors.append(f"invalid Mermaid graph start: {relative(path)}")

fixture_dir = ROOT / "evidence/fixtures"
fixture_names = {path.name for path in fixture_dir.iterdir() if path.is_file()}
expected_fixtures = {
    "README.md",
    "generate_test_pdf.py",
    "notebooklm_benchmark_source.pdf",
    "notebooklm_benchmark_source_render.png",
}
if not expected_fixtures.issubset(fixture_names):
    errors.append("fixture set incomplete")
if (ROOT / "evidence/test_sources").exists():
    errors.append("obsolete evidence/test_sources directory exists")

all_files = [path for path in ROOT.rglob("*") if path.is_file()]
for path in all_files:
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        errors.append(f"file escapes output root: {path}")
    if "unredacted" in path.name.lower() or path.name.lower().startswith("_tmp"):
        errors.append(f"unredacted/temp file remains: {relative(path)}")

text_extensions = {".md", ".txt", ".json", ".csv", ".mmd", ".py"}
privacy_patterns = {
    "email": re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    "uuid": re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
        r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
    ),
    "bearer_value": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."),
    "signed_query": re.compile(r"[?&](?:signature|sig|token|auth)=[^&\s]{8,}", re.I),
}
for path in all_files:
    if path.suffix.lower() not in text_extensions:
        continue
    text = path.read_text(encoding="utf-8")
    for name, pattern in privacy_patterns.items():
        if pattern.search(text):
            errors.append(f"privacy pattern {name}: {relative(path)}")

result = {
    "status": "PASS" if not errors else "FAIL",
    "errors": errors,
    "required_files": len(REQUIRED_FILES),
    "json_files_parsed": len(json_payloads),
    "feature_rows": max(0, len(rows) - 1),
    "screenshot_index_entries": len(screenshot_paths),
    "evidence_index_entries": len(evidence_payload.get("items", [])),
    "mermaid_files": len(list((ROOT / "diagrams").glob("*.mmd"))),
    "all_output_files": len(all_files),
}
print(json.dumps(result, indent=2))
raise SystemExit(0 if not errors else 1)
