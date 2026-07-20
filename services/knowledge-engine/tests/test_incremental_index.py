from __future__ import annotations

import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from langchain_core.documents import Document

from cial_knowledge_os.config import Phase3Config
from cial_knowledge_os.incremental_index import (
    create_indexing_plan,
    write_manifest,
)
from cial_knowledge_os.loaders import _base_metadata
from cial_knowledge_os.phase3_pipeline import Phase3RAGPipeline


class _EmbeddingModel:
    def __init__(self) -> None:
        self.encoded_texts: list[str] = []

    def get_sentence_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts: list[str], **_: object) -> np.ndarray:
        self.encoded_texts.extend(texts)
        return np.asarray(
            [
                [
                    float(len(text)),
                    float(sum(map(ord, text)) % 97),
                    1.0,
                ]
                for text in texts
            ],
            dtype=np.float32,
        )


def _load_fake_pdfs(paths: list[Path], *, corpus_root: Path) -> list[Document]:
    return [
        Document(
            page_content=path.read_text(encoding="utf-8"),
            metadata=_base_metadata(
                path,
                "test",
                1,
                corpus_root=corpus_root,
            ),
        )
        for path in paths
    ]


class ManifestPlanningTests(unittest.TestCase):
    def test_additional_approved_root_joins_manifest_and_temp_files_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            enterprise = base / "files"; personal = base / "user-workspaces"
            enterprise.mkdir(); personal.mkdir()
            (enterprise / "policy.pdf").write_bytes(b"enterprise")
            private = personal / "org" / "user" / "personal_uploads" / "note.pdf"
            private.parent.mkdir(parents=True); private.write_bytes(b"personal")
            (private.parent / "partial.pdf.part").write_bytes(b"partial")
            trash = personal / ".trash" / "deleted.pdf"; trash.parent.mkdir(); trash.write_bytes(b"deleted")

            plan = create_indexing_plan(corpus_root=enterprise, additional_roots=(personal,),
                manifest_path=base / "manifest.json", collection_name="shared")

            self.assertEqual([entry.relative_path for entry in plan.new],
                ["org/user/personal_uploads/note.pdf", "policy.pdf"])
            self.assertEqual({Path(entry.source_root) for entry in plan.new},
                {enterprise.resolve(), personal.resolve()})

    def test_classifies_new_unchanged_changed_deleted_and_force_rebuild(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "files"
            manifest = Path(directory) / "indexes" / "document_manifest.json"
            root.mkdir()
            first = root / "first.pdf"
            deleted = root / "deleted.pdf"
            first.write_bytes(b"first")
            deleted.write_bytes(b"deleted")

            initial = create_indexing_plan(
                corpus_root=root,
                manifest_path=manifest,
                collection_name="test",
            )
            self.assertEqual(
                [entry.relative_path for entry in initial.new],
                ["deleted.pdf", "first.pdf"],
            )
            write_manifest(
                initial,
                collection_name="test",
                chunk_counts={"first.pdf": 2, "deleted.pdf": 1},
            )

            unchanged = create_indexing_plan(
                corpus_root=root,
                manifest_path=manifest,
                collection_name="test",
            )
            self.assertEqual(len(unchanged.unchanged), 2)

            retry_plan = create_indexing_plan(
                corpus_root=root,
                manifest_path=manifest,
                collection_name="test",
                force_reindex_paths=("first.pdf",),
            )
            self.assertEqual([entry.relative_path for entry in retry_plan.changed], ["first.pdf"])
            self.assertEqual([entry.relative_path for entry in retry_plan.unchanged], ["deleted.pdf"])

            first.write_bytes(b"changed")
            deleted.unlink()
            added = root / "new.pdf"
            added.write_bytes(b"new")
            changed = create_indexing_plan(
                corpus_root=root,
                manifest_path=manifest,
                collection_name="test",
            )
            self.assertEqual(
                [entry.relative_path for entry in changed.new],
                ["new.pdf"],
            )
            self.assertEqual(
                [entry.relative_path for entry in changed.changed],
                ["first.pdf"],
            )
            self.assertEqual(
                [entry.relative_path for entry in changed.deleted],
                ["deleted.pdf"],
            )

            forced = create_indexing_plan(
                corpus_root=root,
                manifest_path=manifest,
                collection_name="test",
                force_rebuild=True,
            )
            self.assertEqual(len(forced.new), 2)
            self.assertEqual(len(forced.unchanged), 0)

            disabled = create_indexing_plan(
                corpus_root=root,
                manifest_path=manifest,
                collection_name="test",
                incremental_enabled=False,
            )
            self.assertEqual(len(disabled.new), 2)
            self.assertFalse(disabled.incremental_enabled)


class IncrementalPipelineTests(unittest.TestCase):
    def test_enterprise_and_personal_roots_share_dense_and_bm25_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); personal = root / "personal"
            config = self._config(root, additional_knowledge_roots=(personal,))
            enterprise_file = config.knowledge_root / "enterprise.pdf"
            personal_file = personal / "org" / "user" / "personal_uploads" / "private.pdf"
            enterprise_file.parent.mkdir(parents=True); personal_file.parent.mkdir(parents=True)
            enterprise_file.write_text("enterprise runway procedure", encoding="utf-8")
            personal_file.write_text("private apron checklist", encoding="utf-8")

            pipeline = self._run_index(config)
            paths = {chunk.metadata["relative_path"] for chunk in pipeline.chunks}
            self.assertEqual(paths, {"enterprise.pdf", "org/user/personal_uploads/private.pdf"})
            self.assertEqual(len(pipeline.bm25_retriever._chunks), len(pipeline.chunks))
            pipeline.close()
    def _config(self, root: Path, **kwargs: object) -> Phase3Config:
        return Phase3Config(
            project_root=root,
            qdrant_collection_name="incremental_test",
            chunk_size=80,
            chunk_overlap=10,
            retrieval_mode="hybrid",
            **kwargs,
        )

    def _run_index(self, config: Phase3Config) -> Phase3RAGPipeline:
        return self._run_index_with_model(config, _EmbeddingModel())

    def _run_index_with_model(
        self,
        config: Phase3Config,
        embedding_model: _EmbeddingModel,
    ) -> Phase3RAGPipeline:
        pipeline = Phase3RAGPipeline(
            config,
            embedding_model=embedding_model,  # type: ignore[arg-type]
        )
        with patch(
            "cial_knowledge_os.rag_pipeline.load_pdf_paths",
            side_effect=_load_fake_pdfs,
        ), patch(
            "cial_knowledge_os.rag_pipeline.load_pdf_documents",
            side_effect=lambda current: _load_fake_pdfs(
                sorted(current.knowledge_root.rglob("*.pdf")),
                corpus_root=current.knowledge_root,
            ),
        ):
            pipeline.load()
            pipeline.chunk()
            pipeline.embed()
            pipeline.index()
        return pipeline

    def test_non_force_second_run_indexes_only_a_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._config(root, force_rebuild_index=False)
            first_source = config.knowledge_root / "first.pdf"
            first_source.parent.mkdir(parents=True)
            first_source.write_text("unchanged first document", encoding="utf-8")

            first_model = _EmbeddingModel()
            first = self._run_index_with_model(config, first_model)
            self.assertEqual(first.indexing_summary["new_files"], 1)
            self.assertTrue(first_model.encoded_texts)
            first.close()

            second_source = config.knowledge_root / "second.pdf"
            second_source.write_text("new second document", encoding="utf-8")

            second_model = _EmbeddingModel()
            second = self._run_index_with_model(config, second_model)

            self.assertEqual(second.indexing_summary["new_files"], 1)
            self.assertEqual(second.indexing_summary["unchanged_files"], 1)
            self.assertEqual(second.indexing_summary["changed_files"], 0)
            self.assertEqual(second.indexing_summary["deleted_files"], 0)
            self.assertTrue(second_model.encoded_texts)
            self.assertTrue(
                all(
                    "new second document" in text
                    for text in second_model.encoded_texts
                )
            )
            self.assertTrue(
                all(
                    "unchanged first document" not in text
                    for text in second_model.encoded_texts
                )
            )

            indexed_paths = {
                str(chunk.metadata.get("relative_path"))
                for chunk in second.chunks
            }
            self.assertEqual(indexed_paths, {"first.pdf", "second.pdf"})
            self.assertEqual(
                {
                    str(item["metadata"].get("relative_path"))
                    for item in second.bm25_retriever._chunks  # type: ignore[union-attr]
                },
                indexed_paths,
            )
            manifest = json.loads(
                config.document_manifest_path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                {
                    item["relative_path"]
                    for item in manifest["documents"]
                },
                indexed_paths,
            )
            second.close()

    def test_manual_retry_forces_only_the_failed_file_through_dense_and_bm25_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial_config = self._config(root)
            failed = initial_config.knowledge_root / "failed.pdf"
            stable = initial_config.knowledge_root / "stable.pdf"
            failed.parent.mkdir(parents=True)
            failed.write_text("unique retried runway phrase", encoding="utf-8")
            stable.write_text("unrelated stable phrase", encoding="utf-8")
            initial = self._run_index(initial_config)
            initial_count = len(initial.chunks)
            initial.close()

            retry_model = _EmbeddingModel()
            retry = self._run_index_with_model(
                self._config(root, force_reindex_paths=("failed.pdf",)), retry_model,
            )
            self.assertEqual(retry.indexing_summary["changed_files"], 1)
            self.assertEqual(retry.indexing_summary["unchanged_files"], 1)
            self.assertGreater(retry.indexing_summary["chunks_removed"], 0)
            self.assertEqual(len(retry.chunks), initial_count)
            self.assertTrue(all("unique retried runway phrase" in text for text in retry_model.encoded_texts))
            self.assertEqual(
                {item["metadata"]["relative_path"] for item in retry.bm25_retriever._chunks},
                {"failed.pdf", "stable.pdf"},
            )
            self.assertEqual(
                {chunk.metadata["relative_path"] for chunk in retry.chunks},
                {"failed.pdf", "stable.pdf"},
            )
            retry.close()

    def test_new_unchanged_changed_and_deleted_files_update_both_indexes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._config(root)
            source = config.knowledge_root / "ops" / "manuals" / "one.pdf"
            source.parent.mkdir(parents=True)
            source.write_text("alpha procedure " * 20, encoding="utf-8")

            first = self._run_index(config)
            first_count = len(first.chunks)
            self.assertGreater(first_count, 0)
            self.assertEqual(first.indexing_summary["new_files"], 1)
            self.assertTrue(first.indexing_summary["bm25_rebuilt"])
            first.close()

            second = self._run_index(config)
            self.assertEqual(second.documents, [])
            self.assertEqual(second.indexing_summary["unchanged_files"], 1)
            self.assertEqual(second.indexing_summary["chunks_added"], 0)
            self.assertEqual(second.indexing_summary["chunks_reused"], first_count)
            self.assertFalse(second.indexing_summary["vector_index_updated"])
            self.assertFalse(second.indexing_summary["bm25_rebuilt"])
            self.assertEqual(len(second.chunks), first_count)
            second.close()

            source.write_text("bravo replacement " * 8, encoding="utf-8")
            changed = self._run_index(config)
            self.assertEqual(changed.indexing_summary["changed_files"], 1)
            self.assertGreater(changed.indexing_summary["chunks_removed"], 0)
            self.assertTrue(changed.indexing_summary["bm25_rebuilt"])
            self.assertTrue(
                all(
                    "bravo replacement" in item["text"]
                    for item in changed.bm25_retriever._chunks  # type: ignore[union-attr]
                )
            )
            changed.close()

            source.unlink()
            deleted = self._run_index(config)
            self.assertEqual(deleted.indexing_summary["deleted_files"], 1)
            self.assertGreater(deleted.indexing_summary["chunks_removed"], 0)
            self.assertEqual(deleted.chunks, [])
            manifest = json.loads(
                config.document_manifest_path.read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["documents"], [])
            deleted.close()

    def test_force_rebuild_preserves_taxonomy_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial_config = self._config(root)
            source = (
                initial_config.knowledge_root
                / "aviation"
                / "icao"
                / "annex.pdf"
            )
            source.parent.mkdir(parents=True)
            source.write_text("airport safety requirement", encoding="utf-8")
            initial = self._run_index(initial_config)
            initial.close()

            forced = self._run_index(
                self._config(root, force_rebuild_index=True)
            )
            metadata = forced.chunks[0].metadata
            self.assertEqual(metadata["relative_path"], "aviation/icao/annex.pdf")
            self.assertEqual(metadata["category"], "aviation")
            self.assertEqual(metadata["collection"], "icao")
            self.assertTrue(metadata["document_id"])
            self.assertTrue(forced.indexing_summary["vector_index_updated"])
            self.assertGreater(forced.indexing_summary["chunks_removed"], 0)
            forced.close()
            del forced
            gc.collect()


if __name__ == "__main__":
    unittest.main()
