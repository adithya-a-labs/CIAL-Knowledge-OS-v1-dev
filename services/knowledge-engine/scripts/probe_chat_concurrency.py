"""Deterministic bounded-scheduler probe; this does not invoke Qdrant or Ollama."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import sys
import threading
import time
import tracemalloc
from typing import Any

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from backend.app.core.config import settings  # noqa: E402
from backend.app.services.chat_concurrency import (  # noqa: E402
    ChatCapacityError,
    ChatConcurrencyController,
)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return round(ordered[index], 3)


def configure_probe() -> None:
    settings.chat_multi_request_enabled = True
    settings.chat_executor_workers = 8
    settings.chat_max_active_global = 8
    settings.chat_max_active_per_user = 2
    settings.chat_max_queued_global = 64
    settings.chat_max_queued_per_user = 8
    settings.chat_query_embedding_concurrency = 1
    settings.chat_retrieval_concurrency = 4
    settings.chat_rerank_concurrency = 1
    settings.chat_generation_concurrency = 1
    settings.chat_queue_wait_timeout_seconds = 5
    settings.chat_request_timeout_seconds = 10
    settings.chat_event_queue_size = 32
    settings.chat_token_flush_ms = 10
    settings.chat_token_flush_chars = 32


def run_case(submissions: int, user_count: int) -> dict[str, Any]:
    controller = ChatConcurrencyController()
    controller.start()
    lock = threading.Lock()
    active = 0
    peak_active = 0
    active_by_user: Counter[str] = Counter()
    peak_by_user: Counter[str] = Counter()
    generation_active = 0
    peak_generation = 0
    start_order: list[str] = []
    records = []
    rejected: list[str] = []
    started_at = time.perf_counter()
    tracemalloc.start()

    def work(record) -> None:
        nonlocal active, peak_active, generation_active, peak_generation
        with lock:
            active += 1
            active_by_user[record.user_key] += 1
            peak_active = max(peak_active, active)
            peak_by_user[record.user_key] = max(
                peak_by_user[record.user_key],
                active_by_user[record.user_key],
            )
            start_order.append(record.user_key)
        with controller.gate("retrieval", record):
            time.sleep(0.002)
        with controller.gate("generation", record):
            with lock:
                generation_active += 1
                peak_generation = max(peak_generation, generation_active)
            record.emit_token("synthetic")
            time.sleep(0.005)
            with lock:
                generation_active -= 1
        record.emit_terminal("result", {"synthetic": True})
        with lock:
            active -= 1
            active_by_user[record.user_key] -= 1

    try:
        for index in range(submissions):
            user_key = f"user-{index % user_count}"
            try:
                records.append(controller.submit(user_key=user_key, work=work))
            except ChatCapacityError as exc:
                rejected.append(exc.scope)

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            snapshot = controller.snapshot()
            if (
                snapshot["active_chat_request_count"] == 0
                and snapshot["queued_chat_request_count"] == 0
            ):
                break
            time.sleep(0.005)
        else:
            raise RuntimeError("Synthetic concurrency probe did not drain.")

        elapsed = time.perf_counter() - started_at
        _, peak_memory = tracemalloc.get_traced_memory()
        queue_waits = [
            record.queue_wait_ms
            for record in records
            if record.queue_wait_ms is not None
        ]
        first_tokens = [
            (record.first_token_at - record.created_at) * 1000
            for record in records
            if record.first_token_at is not None
        ]
        total_latencies = [
            (record.completed_at - record.created_at) * 1000
            for record in records
            if record.completed_at is not None
        ]
        longest_run = 0
        current_run = 0
        prior_user = None
        for user_key in start_order:
            current_run = current_run + 1 if user_key == prior_user else 1
            longest_run = max(longest_run, current_run)
            prior_user = user_key
        final_snapshot = controller.snapshot()
        return {
            "submitted": submissions,
            "users": user_count,
            "accepted": len(records),
            "rejected": len(rejected),
            "rejection_scopes": dict(Counter(rejected)),
            "elapsed_ms": round(elapsed * 1000, 3),
            "throughput_requests_per_second": round(
                len(records) / elapsed if elapsed else 0,
                3,
            ),
            "active_peak": peak_active,
            "per_user_active_peak": max(peak_by_user.values(), default=0),
            "generation_peak": peak_generation,
            "queue_wait_ms_p50": percentile(queue_waits, 0.50),
            "queue_wait_ms_p95": percentile(queue_waits, 0.95),
            "first_token_ms_p50": percentile(first_tokens, 0.50),
            "first_token_ms_p95": percentile(first_tokens, 0.95),
            "total_latency_ms_p50": percentile(total_latencies, 0.50),
            "total_latency_ms_p95": percentile(total_latencies, 0.95),
            "start_order_longest_same_user_run": longest_run,
            "event_queue_high_water_mark": final_snapshot[
                "event_queue_high_water_mark"
            ],
            "tracemalloc_peak_bytes": peak_memory,
            "database_connections": None,
        }
    finally:
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        controller.close()


def cancellation_probe() -> dict[str, Any]:
    controller = ChatConcurrencyController()
    controller.start()
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def first(record) -> None:
        with controller.gate("generation", record):
            first_entered.set()
            release_first.wait(2)

    def second(record) -> None:
        with controller.gate("generation", record):
            second_entered.set()

    try:
        controller.submit(user_key="user-a", work=first)
        if not first_entered.wait(2):
            raise RuntimeError("Cancellation probe failed to acquire first gate.")
        waiting = controller.submit(user_key="user-b", work=second)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if controller.snapshot()["gates"]["generation"]["waiters"] == 1:
                break
            time.sleep(0.005)
        cancelled = controller.cancel(waiting.request_id)
        release_first.set()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not waiting.cleanup_complete:
            time.sleep(0.005)
        return {
            "cancel_signal_accepted": cancelled,
            "cancelled_record_cleaned": waiting.cleanup_complete,
            "cancelled_record_stage": waiting.stage,
            "cancelled_waiter_entered_generation": second_entered.is_set(),
        }
    finally:
        release_first.set()
        controller.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    configure_probe()
    cases = [
        run_case(submissions, users)
        for submissions in (1, 2, 4, 8, 16)
        for users in (1, 2, 4, 8)
        if users <= submissions
    ]
    payload = {
        "kind": "synthetic_controller_probe",
        "real_qdrant_exercised": False,
        "real_ollama_exercised": False,
        "note": (
            "Measures process-local scheduler mechanics only; model, retrieval, "
            "database pool, and end-to-end browser latency are intentionally excluded."
        ),
        "configuration": {
            "workers": settings.chat_executor_workers,
            "active_global": settings.chat_max_active_global,
            "active_per_user": settings.chat_max_active_per_user,
            "queued_global": settings.chat_max_queued_global,
            "queued_per_user": settings.chat_max_queued_per_user,
            "retrieval_gate": settings.chat_retrieval_concurrency,
            "generation_gate": settings.chat_generation_concurrency,
        },
        "cases": cases,
        "cancellation": cancellation_probe(),
        "case_throughput_median": round(
            statistics.median(
                case["throughput_requests_per_second"] for case in cases
            ),
            3,
        ),
    }
    rendered = json.dumps(payload, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
