"""Print non-sensitive citation metadata for PDF chunks in Qdrant.

Example:
    python scripts/inspect_pdf_citation_metadata.py --filename "CISG-2025-01-Cyber Security Guidelines for Smart City Infrastructure.pdf"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cial_knowledge_os.config import KnowledgeOSConfig  # noqa: E402
from cial_knowledge_os.vectorstore import create_qdrant_client  # noqa: E402


SAFE_KEYS = (
    "document_id",
    "document_version_id",
    "file_name",
    "relative_path",
    "mime_type",
    "file_type",
    "page_number",
    "page_index",
    "page_start",
    "page_end",
    "chunk_id",
    "chunk_index",
    "citation_metadata_version",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filename", required=True, help="Exact indexed PDF filename.")
    parser.add_argument("--limit", type=int, default=5, help="Maximum matching chunks to print.")
    parser.add_argument("--qdrant-mode", choices=("embedded", "server"), default="embedded")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--collection", default="cial_basic_rag")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT.parent.parent / "data")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = KnowledgeOSConfig(
        project_root=PROJECT_ROOT.parent.parent,
        data_dir=args.data_dir,
        qdrant_mode=args.qdrant_mode,
        qdrant_url=args.qdrant_url,
        qdrant_collection_name=args.collection,
    )
    client = create_qdrant_client(config)
    try:
        offset = None
        matches = 0
        while matches < args.limit:
            points, offset = client.scroll(
                collection_name=config.qdrant_collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                metadata = dict((point.payload or {}).get("metadata") or {})
                if metadata.get("file_name") != args.filename:
                    continue
                matches += 1
                print(f"point_id: {point.id}")
                for key in SAFE_KEYS:
                    print(f"{key}: {metadata.get(key)}")
                print()
                if matches >= args.limit:
                    break
            if offset is None:
                break
        if not matches:
            print("No matching PDF chunks found.")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
