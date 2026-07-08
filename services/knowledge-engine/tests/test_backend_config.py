from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.app.core.config import settings
from backend.app.core.paths import REPO_ROOT
from backend.app.services.knowledge_engine_service import (
    _server_collection_requires_rebuild,
)


class BackendSettingsTests(unittest.TestCase):
    def test_backend_defaults_match_integrated_local_stack(self) -> None:
        self.assertEqual(settings.qdrant_mode, "server")
        self.assertEqual(settings.qdrant_url, "http://localhost:6335")
        self.assertEqual(settings.data_files_path, REPO_ROOT / "data" / "files")
        self.assertEqual(settings.repo_path, REPO_ROOT)

    @staticmethod
    def _config(root: Path, manifest_path: Path) -> SimpleNamespace:
        return SimpleNamespace(
            qdrant_mode="server",
            force_rebuild_index=False,
            incremental_indexing_enabled=True,
            document_manifest_path=manifest_path,
            knowledge_root=root,
            qdrant_collection_name="cial_phase4",
            qdrant_url="http://localhost:6335",
            qdrant_api_key=None,
        )

    @staticmethod
    def _write_manifest(root: Path, manifest_path: Path) -> None:
        payload = {
            "version": 1,
            "corpus_root": str(root.resolve()),
            "collection_name": "cial_phase4",
            "documents": [
                {
                    "relative_path": "manual.txt",
                    "sha256": "0" * 64,
                    "size_bytes": 12,
                    "modified_time": 1.0,
                    "document_type": "txt",
                    "category": None,
                    "collection": None,
                    "chunk_count": 1,
                }
            ],
        }
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    @patch("qdrant_client.QdrantClient")
    def test_missing_server_collection_with_manifest_forces_rebuild(
        self,
        client_class: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "data" / "files"
            manifest_path = Path(directory) / "data" / "indexes" / "document_manifest.json"
            root.mkdir(parents=True)
            self._write_manifest(root, manifest_path)
            client_class.return_value.collection_exists.return_value = False

            self.assertTrue(
                _server_collection_requires_rebuild(
                    self._config(root, manifest_path)
                )
            )

        client_class.return_value.close.assert_called_once_with()

    @patch("qdrant_client.QdrantClient")
    def test_nonempty_server_collection_with_manifest_reuses_index(
        self,
        client_class: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "data" / "files"
            manifest_path = Path(directory) / "data" / "indexes" / "document_manifest.json"
            root.mkdir(parents=True)
            self._write_manifest(root, manifest_path)
            client_class.return_value.collection_exists.return_value = True
            client_class.return_value.get_collection.return_value = SimpleNamespace(
                points_count=3
            )

            self.assertFalse(
                _server_collection_requires_rebuild(
                    self._config(root, manifest_path)
                )
            )

        client_class.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
