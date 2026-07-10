from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.app.core.config import settings
from backend.app.core.application_config import (
    configured_corpus_root,
    configured_repository_id,
    read_application_config,
    repository_identity_for_path,
    save_primary_repository_path,
    validate_repository_path,
)
from backend.app.core.paths import REPO_ROOT
from backend.app.services.knowledge_engine_service import (
    _server_collection_requires_rebuild,
)


class BackendSettingsTests(unittest.TestCase):
    def test_backend_defaults_match_integrated_local_stack(self) -> None:
        self.assertEqual(settings.qdrant_mode, "server")
        self.assertEqual(settings.qdrant_url, "http://localhost:6335")
        self.assertEqual(settings.data_files_path, settings.corpus_root_path)
        self.assertEqual(settings.repo_path, REPO_ROOT)

    def test_application_config_stores_primary_repository_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "application.json"
            repository = Path(directory) / "KnowledgeRepository"
            repository.mkdir()

            save_primary_repository_path(repository, config_path=config_path)

            payload = read_application_config(config_path)
            self.assertEqual(payload["repositories"][0]["id"], "enterprise")
            self.assertEqual(
                payload["repositories"][0]["repository_id"],
                repository_identity_for_path(repository),
            )
            self.assertEqual(payload["repositories"][0]["path"], str(repository.resolve()))
            validation = validate_repository_path(repository)
            self.assertTrue(validation.valid)

    def test_saving_primary_repository_preserves_other_repositories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "application.json"
            repository = Path(directory) / "KnowledgeRepository"
            repository.mkdir()
            config_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "repositories": [
                            {
                                "id": "department-ops",
                                "name": "Operations",
                                "type": "filesystem",
                                "path": "Z:\\Ops",
                                "enabled": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            save_primary_repository_path(repository, config_path=config_path)

            payload = read_application_config(config_path)
            self.assertEqual(
                [item["id"] for item in payload["repositories"]],
                ["enterprise", "department-ops"],
            )

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_application_config_uses_development_corpus_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            default = Path(directory) / "data" / "files"
            missing_config = Path(directory) / "missing" / "application.json"
            with patch.dict("os.environ", {"CIAL_APPLICATION_CONFIG": str(missing_config)}, clear=True):
                self.assertEqual(configured_corpus_root(default), default.resolve())

    def test_saved_application_config_precedes_deprecated_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "application.json"
            saved_repository = Path(directory) / "Saved Repository"
            legacy_repository = Path(directory) / "legacy"
            saved_repository.mkdir()
            legacy_repository.mkdir()
            save_primary_repository_path(saved_repository, config_path=config_path)

            with patch.dict(
                "os.environ",
                {
                    "CIAL_APPLICATION_CONFIG": str(config_path),
                    "CIAL_DATA_DIR": str(legacy_repository),
                },
                clear=True,
            ):
                self.assertEqual(configured_corpus_root(Path(directory) / "default"), saved_repository.resolve())
                self.assertEqual(configured_repository_id(Path(directory) / "default"), repository_identity_for_path(saved_repository))

    def test_explicit_corpus_root_precedes_saved_application_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "application.json"
            saved_repository = Path(directory) / "Saved Repository"
            explicit_repository = Path(directory) / "Explicit Repository"
            saved_repository.mkdir()
            explicit_repository.mkdir()
            save_primary_repository_path(saved_repository, config_path=config_path)

            with patch.dict(
                "os.environ",
                {
                    "CIAL_APPLICATION_CONFIG": str(config_path),
                    "CIAL_CORPUS_ROOT": str(explicit_repository),
                },
                clear=True,
            ):
                self.assertEqual(configured_corpus_root(Path(directory) / "default"), explicit_repository.resolve())
                self.assertEqual(configured_repository_id(Path(directory) / "default"), repository_identity_for_path(explicit_repository))

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
