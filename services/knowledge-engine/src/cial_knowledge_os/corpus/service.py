"""Dedicated Corpus service facade."""

from __future__ import annotations

from pathlib import Path
import uuid

from sqlalchemy.orm import sessionmaker

from backend.app.db.base import import_models

from .explorer import CorpusExplorer
from .models import CorpusSyncSummary
from .scanner import FilesystemCorpusScanner
from .synchronizer import CorpusSynchronizer
from .tree_builder import CorpusTreeBuilder


class CorpusServiceUnavailable(RuntimeError):
    """Raised when the metadata database is not configured."""


class CorpusService:
    """Owns Corpus discovery, metadata synchronization, and Corpus API reads."""

    def __init__(
        self,
        *,
        root: Path,
        session_factory: sessionmaker | None,
        hash_algorithm: str = "sha256",
        batch_size: int = 500,
    ) -> None:
        self.root = root
        self.session_factory = session_factory
        self.hash_algorithm = hash_algorithm
        self.batch_size = batch_size
        self.scanner = FilesystemCorpusScanner(root, hash_algorithm=hash_algorithm)
        self.tree_builder = CorpusTreeBuilder()
        self.synchronizer = CorpusSynchronizer(batch_size=batch_size)

    def sync(self) -> CorpusSyncSummary:
        if self.session_factory is None:
            return CorpusSyncSummary(message="DATABASE_URL is not configured; Corpus sync skipped.")
        import_models()
        scan_result = self.scanner.scan()
        tree = self.tree_builder.build(scan_result)
        with self.session_factory() as session:
            with session.begin():
                summary = self.synchronizer.synchronize(tree, session)
        return summary

    def get_tree(self) -> dict[str, object]:
        if self.session_factory is None:
            raise CorpusServiceUnavailable("Metadata database is not configured.")
        import_models()
        with self.session_factory() as session:
            return CorpusExplorer(session).tree()

    def get_folder(self, relative_path: str) -> dict[str, object] | None:
        if self.session_factory is None:
            raise CorpusServiceUnavailable("Metadata database is not configured.")
        import_models()
        with self.session_factory() as session:
            return CorpusExplorer(session).folder_contents(relative_path)

    def get_document(self, document_id: uuid.UUID) -> dict[str, object] | None:
        if self.session_factory is None:
            raise CorpusServiceUnavailable("Metadata database is not configured.")
        import_models()
        with self.session_factory() as session:
            return CorpusExplorer(session).document(document_id)
