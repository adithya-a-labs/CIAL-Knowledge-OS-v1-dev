from __future__ import annotations

import threading
import time

import pytest

from backend.app.core.config import settings
from backend.app.services.chat_concurrency import (
    BoundedEventChannel,
    ChatCapacityError,
    ChatConcurrencyController,
)


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    *,
    workers: int = 3,
    active_global: int = 3,
    active_per_user: int = 2,
    queued_global: int = 8,
    queued_per_user: int = 4,
) -> None:
    monkeypatch.setattr(settings, "chat_executor_workers", workers)
    monkeypatch.setattr(settings, "chat_multi_request_enabled", True)
    monkeypatch.setattr(settings, "chat_fair_scheduling", True)
    monkeypatch.setattr(settings, "chat_max_active_global", active_global)
    monkeypatch.setattr(settings, "chat_max_active_per_user", active_per_user)
    monkeypatch.setattr(settings, "chat_max_queued_global", queued_global)
    monkeypatch.setattr(settings, "chat_max_queued_per_user", queued_per_user)
    monkeypatch.setattr(settings, "chat_query_embedding_concurrency", 1)
    monkeypatch.setattr(settings, "chat_retrieval_concurrency", 2)
    monkeypatch.setattr(settings, "chat_rerank_concurrency", 1)
    monkeypatch.setattr(settings, "chat_generation_concurrency", 1)
    monkeypatch.setattr(settings, "chat_request_timeout_seconds", 10.0)
    monkeypatch.setattr(settings, "chat_queue_wait_timeout_seconds", 10.0)
    monkeypatch.setattr(settings, "chat_event_queue_size", 8)
    monkeypatch.setattr(settings, "chat_token_flush_chars", 64)
    monkeypatch.setattr(settings, "chat_token_flush_ms", 40)


def test_same_user_runs_two_requests_and_third_queues_without_blocking_another_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    controller = ChatConcurrencyController()
    controller.start()
    started = {name: threading.Event() for name in ("a1", "a2", "a3", "b1")}
    release = {name: threading.Event() for name in started}

    def work(name: str):
        def execute(_record):
            started[name].set()
            assert release[name].wait(5)

        return execute

    try:
        controller.submit(user_key="a", work=work("a1"))
        controller.submit(user_key="a", work=work("a2"))
        assert started["a1"].wait(2)
        assert started["a2"].wait(2)
        controller.submit(user_key="a", work=work("a3"))
        assert controller.snapshot()["queued_chat_request_count"] == 1

        controller.submit(user_key="b", work=work("b1"))
        assert started["b1"].wait(2)
        assert not started["a3"].is_set()
    finally:
        for event in release.values():
            event.set()
        controller.close()


def test_round_robin_dispatches_waiting_user_before_same_users_backlog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        workers=1,
        active_global=1,
        active_per_user=1,
    )
    controller = ChatConcurrencyController()
    controller.start()
    first_started = threading.Event()
    release_first = threading.Event()
    next_started: list[str] = []
    next_started_event = threading.Event()

    def first(_record):
        first_started.set()
        assert release_first.wait(5)

    def queued(name: str):
        def execute(_record):
            next_started.append(name)
            next_started_event.set()

        return execute

    try:
        controller.submit(user_key="a", work=first)
        assert first_started.wait(2)
        controller.submit(user_key="a", work=queued("a2"))
        controller.submit(user_key="b", work=queued("b1"))
        release_first.set()
        assert next_started_event.wait(2)
        assert next_started[0] == "b1"
    finally:
        release_first.set()
        controller.close()


def test_fair_scheduling_flag_can_restore_fifo_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        workers=1,
        active_global=1,
        active_per_user=1,
    )
    monkeypatch.setattr(settings, "chat_fair_scheduling", False)
    controller = ChatConcurrencyController()
    controller.start()
    first_started = threading.Event()
    release_first = threading.Event()
    next_started = threading.Event()
    order: list[str] = []

    def first(_record):
        first_started.set()
        assert release_first.wait(5)

    def queued(name: str):
        def execute(_record):
            order.append(name)
            next_started.set()

        return execute

    try:
        controller.submit(user_key="a", work=first)
        assert first_started.wait(2)
        controller.submit(user_key="a", work=queued("a2"))
        controller.submit(user_key="b", work=queued("b1"))
        assert controller.snapshot()["fair_scheduling"] is False
        release_first.set()
        assert next_started.wait(2)
        assert order[0] == "a2"
    finally:
        release_first.set()
        controller.close()


def test_capacity_rejection_allocates_no_request_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        workers=1,
        active_global=1,
        active_per_user=1,
        queued_global=1,
        queued_per_user=1,
    )
    controller = ChatConcurrencyController()
    controller.start()
    started = threading.Event()
    release = threading.Event()

    def blocked(_record):
        started.set()
        assert release.wait(5)

    try:
        controller.submit(user_key="a", work=blocked)
        assert started.wait(2)
        controller.submit(user_key="a", work=lambda _: None)
        before = controller.snapshot()
        with pytest.raises(ChatCapacityError) as captured:
            controller.submit(user_key="b", work=lambda _: None)
        after = controller.snapshot()
        assert captured.value.detail()["code"] == "chat_capacity_reached"
        assert captured.value.scope == "global"
        assert after["queued_chat_request_count"] == before["queued_chat_request_count"]
        assert after["global_limit_rejection_count"] == 1
    finally:
        release.set()
        controller.close()


def test_cancel_queued_request_removes_only_that_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        workers=1,
        active_global=1,
        active_per_user=1,
    )
    controller = ChatConcurrencyController()
    controller.start()
    started = threading.Event()
    release = threading.Event()
    survivor_started = threading.Event()

    def blocked(_record):
        started.set()
        assert release.wait(5)

    try:
        controller.submit(user_key="a", work=blocked)
        assert started.wait(2)
        cancelled = controller.submit(user_key="a", work=lambda _: None)
        controller.submit(
            user_key="b", work=lambda _: survivor_started.set()
        )
        assert controller.cancel(cancelled.request_id)
        release.set()
        assert survivor_started.wait(2)
    finally:
        release.set()
        controller.close()


def test_slow_consumer_event_channel_stays_bounded_and_keeps_terminal_event() -> None:
    channel = BoundedEventChannel(maxsize=3, token_flush_chars=8)
    for _ in range(100):
        channel.put({"type": "token", "delta": "x"})
    channel.put({"type": "stage", "stage_id": "persisting", "status": "started"})
    channel.put({"type": "result", "payload": {"answer": "done"}})
    channel.put(None)

    values = []
    while True:
        item = channel.get(timeout=0.1)
        if item is None:
            break
        values.append(item)
    assert channel.high_water_mark <= 3
    assert any(item["type"] == "result" for item in values)


def test_slow_consumer_never_loses_token_text_when_stages_interleave() -> None:
    channel = BoundedEventChannel(
        maxsize=3,
        token_flush_chars=1,
        token_flush_ms=1,
    )
    channel.put({"type": "token", "delta": "a"})
    channel.put({"type": "stage", "stage_id": "one"})
    channel.put({"type": "stage", "stage_id": "two"})
    channel.put({"type": "token", "delta": "b"})
    channel.put({"type": "stage", "stage_id": "three"})
    channel.put({"type": "token", "delta": "c"})
    channel.put(None)

    values = []
    while True:
        item = channel.get(timeout=0.1)
        if item is None:
            break
        values.append(item)

    assert channel.high_water_mark <= 3
    assert "".join(
        str(item.get("delta") or "")
        for item in values
        if item["type"] == "token"
    ) == "abc"


def test_worker_and_dispatcher_threads_are_lifecycle_managed_not_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, workers=1, active_global=1, active_per_user=1)
    controller = ChatConcurrencyController()
    controller.start()
    observed = {}
    completed = threading.Event()

    def inspect(_record):
        observed["daemon"] = threading.current_thread().daemon
        completed.set()

    controller.submit(user_key="a", work=inspect)
    assert completed.wait(2)
    assert controller._dispatcher is not None
    assert controller._dispatcher.daemon is False
    assert observed["daemon"] is False
    controller.close()


def test_submission_sequence_is_monotonic_and_restart_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, workers=1, active_global=1, active_per_user=1)
    controller = ChatConcurrencyController()
    controller.start()
    release = threading.Event()
    started = threading.Event()

    def blocked(_record):
        started.set()
        assert release.wait(5)

    try:
        first = controller.submit(user_key="a", work=blocked)
        assert started.wait(2)
        second = controller.submit(user_key="a", work=lambda _: None)
        assert first.submission_sequence >= 1_000_000_000_000_000_000
        assert second.submission_sequence > first.submission_sequence
    finally:
        release.set()
        controller.close()


def test_ineligible_same_user_queue_expires_without_waiting_for_active_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        workers=2,
        active_global=2,
        active_per_user=1,
    )
    monkeypatch.setattr(settings, "chat_queue_wait_timeout_seconds", 0.05)
    controller = ChatConcurrencyController()
    controller.start()
    started = threading.Event()
    release = threading.Event()

    def blocked(_record):
        started.set()
        assert release.wait(5)

    try:
        controller.submit(user_key="a", work=blocked)
        assert started.wait(2)
        queued = controller.submit(user_key="a", work=lambda _: None)
        terminal = []
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            item = queued.events.get(timeout=0.5)
            if item is None:
                break
            terminal.append(item)
        assert queued.cleanup_complete is True
        assert queued.stage == "timed_out"
        assert any(
            item["type"] == "error"
            and item["payload"]["reason"] == "queue_timeout"
            for item in terminal
        )
    finally:
        release.set()
        controller.close()


def test_cancellation_while_waiting_for_generation_never_enters_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        workers=2,
        active_global=2,
        active_per_user=2,
    )
    controller = ChatConcurrencyController()
    controller.start()
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def first(record):
        with controller.gate("generation", record):
            first_entered.set()
            assert release_first.wait(5)

    def second(record):
        with controller.gate("generation", record):
            second_entered.set()

    try:
        controller.submit(user_key="a", work=first)
        assert first_entered.wait(2)
        waiting = controller.submit(user_key="a", work=second)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if controller.snapshot()["gates"]["generation"]["waiters"] == 1:
                break
            time.sleep(0.01)
        assert controller.cancel(waiting.request_id)
        release_first.set()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not waiting.cleanup_complete:
            time.sleep(0.01)
        assert waiting.cleanup_complete is True
        assert waiting.stage == "cancelled"
        assert second_entered.is_set() is False
    finally:
        release_first.set()
        controller.close()


def test_generation_gate_enforces_hard_concurrency_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        workers=4,
        active_global=4,
        active_per_user=2,
    )
    controller = ChatConcurrencyController()
    controller.start()
    state_lock = threading.Lock()
    active = 0
    peak = 0
    all_done = threading.Event()
    completed = 0

    def work(record):
        nonlocal active, peak, completed
        with controller.gate("generation", record):
            with state_lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with state_lock:
                active -= 1
                completed += 1
                if completed == 4:
                    all_done.set()

    try:
        for index in range(4):
            controller.submit(user_key=f"user-{index % 2}", work=work)
        assert all_done.wait(3)
        assert peak == 1
    finally:
        controller.close()


def test_cooperative_generation_cancellation_is_request_local_and_skips_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(
        monkeypatch,
        workers=2,
        active_global=2,
        active_per_user=2,
    )
    monkeypatch.setattr(settings, "chat_generation_concurrency", 2)
    controller = ChatConcurrencyController()
    controller.start()
    a_generation_started = threading.Event()
    b_generation_started = threading.Event()
    release_b = threading.Event()
    a_iterator_closed = threading.Event()
    a_slot_released = threading.Event()
    b_completed = threading.Event()
    a_persisted = threading.Event()
    b_persisted = threading.Event()
    produced_by_a: list[str] = []

    def request_a(record):
        try:
            with controller.gate("generation", record):
                try:
                    produced_by_a.append("first-token")
                    record.emit_token("first-token")
                    a_generation_started.set()
                    assert record.cancel_event.wait(2)
                    record.raise_if_cancelled()
                    produced_by_a.append("token-after-cancel")
                    record.emit_token("token-after-cancel")
                finally:
                    a_iterator_closed.set()
            a_persisted.set()
        finally:
            a_slot_released.set()

    def request_b(record):
        assert a_generation_started.wait(2)
        with controller.gate("generation", record):
            b_generation_started.set()
            assert release_b.wait(2)
            record.raise_if_cancelled()
            b_persisted.set()
            record.stage = "completed"
            record.emit_terminal("result", {"request": "b"})
        b_completed.set()

    try:
        a_record = controller.submit(user_key="same-user", work=request_a)
        assert a_generation_started.wait(2)
        b_record = controller.submit(user_key="same-user", work=request_b)
        assert b_generation_started.wait(2)

        assert controller.cancel(a_record.request_id)
        assert a_record.cancel_event.is_set() is True
        assert b_record.cancel_event.is_set() is False
        release_b.set()

        assert a_iterator_closed.wait(2)
        assert a_slot_released.wait(2)
        assert b_completed.wait(2)
        with controller._condition:
            assert controller._condition.wait_for(
                lambda: controller._active_count == 0
                and controller._queued_count_locked() == 0,
                timeout=2,
            )

        assert produced_by_a == ["first-token"]
        assert a_persisted.is_set() is False
        assert b_persisted.is_set() is True
        assert b_record.cancel_event.is_set() is False
        snapshot = controller.snapshot()
        assert snapshot["active_chat_request_count"] == 0
        assert snapshot["queued_chat_request_count"] == 0
        assert snapshot["gates"]["generation"]["used"] == 0
        assert snapshot["gates"]["generation"]["waiters"] == 0
        assert snapshot["cancellation_count"] == 1
        assert snapshot["completed_count"] == 1
    finally:
        release_b.set()
        controller.close()
