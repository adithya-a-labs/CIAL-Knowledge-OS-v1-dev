"""Local continuous-indexing benchmark and queue observer.

The default mode is a mutation-free batch-assembly microbenchmark. Use
``--wait-for-queue`` while an indexer is processing a deliberately prepared
test corpus to record durable end-to-end throughput.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from backend.app.services.continuous_indexer import ChunkEnvelope, CrossDocumentBatcher
from backend.app.services.indexing_queue import ACTIVE_JOB_STATUSES, DurableIndexQueue


def batcher_benchmark(documents: int, chunks_per_document: int) -> dict[str, object]:
    started = time.perf_counter()
    batcher = CrossDocumentBatcher(max_chunks=64, max_tokens=32768, max_wait_ms=75)
    batches: list[list[ChunkEnvelope]] = []
    total_chunks = documents * chunks_per_document
    for document_index in range(documents):
        asset_id = uuid.uuid5(uuid.NAMESPACE_URL, f"benchmark:{document_index}")
        for chunk_index in range(chunks_per_document):
            body = f"document {document_index} chunk {chunk_index} " + ("benchmark text " * 80)
            item = ChunkEnvelope(
                job_id=uuid.uuid5(asset_id, str(chunk_index)),
                asset_id=asset_id,
                chunk=None,
                token_count=CrossDocumentBatcher.estimate_tokens(body),
            )
            ready = batcher.add(item)
            if ready:
                batches.append(ready)
    tail = batcher.flush()
    if tail:
        batches.append(tail)
    elapsed = time.perf_counter() - started
    multi_asset_batches = sum(len({item.asset_id for item in batch}) > 1 for batch in batches)
    return {
        "mode": "batcher_only",
        "documents": documents,
        "chunks": total_chunks,
        "batches": len(batches),
        "multi_asset_batches": multi_asset_batches,
        "chunks_per_second": round(total_chunks / elapsed, 2) if elapsed else None,
        "elapsed_seconds": round(elapsed, 6),
    }


def optional_gpu_sample() -> dict[str, object] | None:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return {"rows": [line.strip() for line in result.stdout.splitlines() if line.strip()]}


def embedding_benchmark(chunks: int) -> dict[str, object]:
    """Measure the real configured local embedding model on its actual device."""

    import torch

    from backend.app.core.config import settings
    from backend.app.services.knowledge_engine_service import KnowledgeEngineService
    from cial_knowledge_os.embeddings import embed_texts, load_embedding_model

    config = KnowledgeEngineService().build_config(force_rebuild_index=False)
    config.embedding_device = settings.indexer_device
    model = load_embedding_model(config)
    actual_device = str(model.device)
    precision = settings.indexer_precision
    if precision == "auto":
        precision = "float16" if actual_device.startswith("cuda") else "float32"
    if precision == "float16":
        model.half()
    elif precision == "bfloat16":
        model.bfloat16()
    texts = [
        f"benchmark asset {index // 20} chunk {index} " + ("airport knowledge text " * 80)
        for index in range(chunks)
    ]
    embed_texts(model, texts[: min(8, len(texts))], batch_size=min(8, len(texts)))
    if actual_device.startswith("cuda"):
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    vectors = embed_texts(
        model,
        texts,
        batch_size=settings.indexer_embed_batch_size,
    )
    if actual_device.startswith("cuda"):
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    return {
        "mode": "embedding_model",
        "model": config.embedding_model_name,
        "configured_device": settings.indexer_device,
        "actual_device": actual_device,
        "precision": precision,
        "chunks": chunks,
        "dimensions": int(vectors.shape[1]),
        "elapsed_seconds": round(elapsed, 4),
        "chunks_per_second": round(chunks / elapsed, 2),
        "peak_cuda_memory_mb": (
            round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
            if actual_device.startswith("cuda")
            else None
        ),
        "gpu": optional_gpu_sample(),
    }


def create_mixed_fixtures(root: Path, documents: int) -> dict[str, object]:
    """Create non-destructive supported-format fixtures under an explicit root."""

    root.mkdir(parents=True, exist_ok=True)
    formats = ("txt", "md", "csv", "json", "html", "xml", "yaml")
    created: list[str] = []
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    for index in range(documents):
        extension = formats[index % len(formats)]
        path = root / f"continuous-index-{run_id}-{index:05d}.{extension}"
        body = f"CIAL benchmark document {index}. " + ("Local airport operations evidence. " * 120)
        if extension == "md":
            content = f"# Benchmark {index}\n\n{body}\n"
        elif extension == "csv":
            content = f"id,content\n{index},\"{body}\"\n"
        elif extension == "json":
            content = json.dumps({"id": index, "content": body})
        elif extension == "html":
            content = f"<html><body><h1>Benchmark {index}</h1><p>{body}</p></body></html>"
        elif extension == "xml":
            content = f"<document><id>{index}</id><content>{body}</content></document>"
        elif extension == "yaml":
            content = f"id: {index}\ncontent: {json.dumps(body)}\n"
        else:
            content = body
        path.write_text(content, encoding="utf-8")
        created.append(str(path))
    return {
        "root": str(root.resolve()),
        "documents_created": len(created),
        "formats": list(formats),
        "first_file": created[0] if created else None,
    }


def wait_for_queue(timeout_seconds: int) -> dict[str, object]:
    queue = DurableIndexQueue()
    before = queue.status()
    started = time.perf_counter()
    peak_active = 0
    samples = 0
    while time.perf_counter() - started < timeout_seconds:
        current = queue.status()
        counts = current.get("queue_counts", {})
        active = sum(int(counts.get(status, 0)) for status in ACTIVE_JOB_STATUSES)
        peak_active = max(peak_active, active)
        samples += 1
        if active == 0:
            break
        time.sleep(1)
    elapsed = time.perf_counter() - started
    after = queue.status()
    before_completed = int(before.get("queue_counts", {}).get("completed", 0))
    after_completed = int(after.get("queue_counts", {}).get("completed", 0))
    completed = max(0, after_completed - before_completed)
    before_throughput = before.get("throughput", {})
    after_throughput = after.get("throughput", {})
    embedded = max(
        0,
        int(after_throughput.get("chunks_embedded", 0))
        - int(before_throughput.get("chunks_embedded", 0)),
    )
    extracted = max(
        0,
        int(after_throughput.get("chunks_extracted", 0))
        - int(before_throughput.get("chunks_extracted", 0)),
    )
    point_delta = max(
        0,
        int(after.get("qdrant_point_count", 0))
        - int(before.get("qdrant_point_count", 0)),
    )
    return {
        "mode": "durable_queue",
        "elapsed_seconds": round(elapsed, 3),
        "jobs_completed": completed,
        "jobs_per_second": round(completed / elapsed, 3) if elapsed else None,
        "peak_active_jobs": peak_active,
        "chunks_extracted": extracted,
        "extraction_chunks_per_second": round(extracted / elapsed, 3) if elapsed else None,
        "chunks_embedded": embedded,
        "embedding_chunks_per_second": round(embedded / elapsed, 3) if elapsed else None,
        "qdrant_point_delta": point_delta,
        "qdrant_points_per_second": round(point_delta / elapsed, 3) if elapsed else None,
        "samples": samples,
        "before": before,
        "after": after,
        "gpu": optional_gpu_sample(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=int, default=100)
    parser.add_argument("--chunks-per-document", type=int, default=20)
    parser.add_argument("--wait-for-queue", action="store_true")
    parser.add_argument("--embedding-sample-chunks", type=int, default=0)
    parser.add_argument("--create-fixtures", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.documents <= 0 or args.chunks_per_document <= 0:
        parser.error("documents and chunks-per-document must be positive")
    fixtures = (
        create_mixed_fixtures(args.create_fixtures, args.documents)
        if args.create_fixtures
        else None
    )
    if args.embedding_sample_chunks < 0:
        parser.error("embedding-sample-chunks must be non-negative")
    if args.wait_for_queue:
        report = wait_for_queue(args.timeout_seconds)
    elif args.embedding_sample_chunks:
        report = embedding_benchmark(args.embedding_sample_chunks)
    else:
        report = batcher_benchmark(args.documents, args.chunks_per_document)
    if fixtures is not None:
        report["fixtures"] = fixtures
    report["recorded_at"] = datetime.now(timezone.utc).isoformat()
    rendered = json.dumps(report, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(rendered + "\n", encoding="utf-8")
        temporary.replace(args.output)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
