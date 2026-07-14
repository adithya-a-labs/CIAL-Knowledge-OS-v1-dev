"""Scan corpus ingestion decisions without modifying Qdrant or PostgreSQL."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cial_knowledge_os.file_formats import inspect_ingestion_candidate  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-only", action="store_true", help="Required acknowledgement: this command never writes state.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON.")
    parser.add_argument("--corpus-root", type=Path, default=PROJECT_ROOT.parent.parent / "data" / "files")
    parser.add_argument("--ocr-engine", default="tesseract")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.scan_only:
        raise SystemExit("Pass --scan-only; this diagnostic intentionally has no indexing mode.")
    root = args.corpus_root.expanduser().resolve()
    rows = [
        inspect_ingestion_candidate(path, corpus_root=root, ocr_engine=args.ocr_engine)
        for path in sorted(root.rglob("*")) if path.is_file()
    ] if root.exists() else []
    skipped = [row for row in rows if not row["eligible"]]
    payload = {
        "corpus_root": str(root),
        "scan_only": True,
        "total_files_discovered": len(rows),
        "supported_files": sum(bool(row["validation"]["valid_for_ingestion"]) and row["eligible"] for row in rows),
        "unsupported_files": sum(row["skip_reason"] == "unsupported_extension" for row in rows),
        "temporary_or_hidden_files": sum(row["skip_reason"] in {"temporary_office_file", "hidden_or_system_file"} for row in rows),
        "ocr_candidates": sum(row["validation"]["requires_ocr"] for row in rows),
        "ocr_ready_files": sum(row["validation"]["requires_ocr"] and row["eligible"] for row in rows),
        "files_that_would_be_skipped": len(skipped),
        "counts_by_extension": dict(sorted(Counter(row["extension"] or "[none]" for row in rows).items())),
        "counts_by_skip_reason": dict(sorted(Counter(row["skip_reason"] for row in skipped).items())),
        "skipped_files": [{key: row[key] for key in ("filename", "relative_path", "extension", "detected_mime_type", "skip_reason")} for row in skipped],
        "selected_loaders": [{key: row[key] for key in ("filename", "relative_path", "extension", "loader_selected")} for row in rows if row["eligible"]],
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for key in ("total_files_discovered", "supported_files", "unsupported_files", "temporary_or_hidden_files", "ocr_candidates", "ocr_ready_files", "files_that_would_be_skipped"):
            print(f"{key}: {payload[key]}")
        print(f"counts_by_extension: {payload['counts_by_extension']}")
        print(f"counts_by_skip_reason: {payload['counts_by_skip_reason']}")
        for row in payload["skipped_files"]:
            print(f"SKIP {row['relative_path']}: {row['skip_reason']}")
        for row in payload["selected_loaders"]:
            print(f"LOAD {row['relative_path']}: {row['loader_selected']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
