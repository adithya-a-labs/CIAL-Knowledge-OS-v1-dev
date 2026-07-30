"""Bounded, fair, process-local orchestration for live chat requests."""

from __future__ import annotations

from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
import logging
import threading
import time
import uuid
from typing import Any, Callable, Iterator

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

TERMINAL_STAGES = {"completed", "cancelled", "timed_out", "failed"}


class ChatCapacityError(RuntimeError):
    """Safe admission failure returned before request resources are allocated."""

    def __init__(
        self,
        *,
        scope: str,
        active_count: int,
        queued_count: int,
        limit: int,
        retry_after_seconds: int = 2,
    ) -> None:
        super().__init__("The assistant is at capacity. Please retry shortly.")
        self.scope = scope
        self.active_count = active_count
        self.queued_count = queued_count
        self.limit = limit
        self.retry_after_seconds = retry_after_seconds

    def detail(self) -> dict[str, Any]:
        return {
            "code": "chat_capacity_reached",
            "message": str(self),
            "scope": self.scope,
            "retry_after_seconds": self.retry_after_seconds,
            "active_count": self.active_count,
            "queued_count": self.queued_count,
            "limit": self.limit,
        }


class ChatControllerUnavailable(RuntimeError):
    pass


class BoundedEventChannel:
    """A bounded event deque that coalesces token deltas under slow consumers."""

    def __init__(
        self,
        maxsize: int,
        token_flush_chars: int,
        token_flush_ms: int = 40,
    ) -> None:
        self.maxsize = maxsize
        self.token_flush_chars = token_flush_chars
        self.token_flush_seconds = token_flush_ms / 1000
        self._items: deque[dict[str, Any] | None] = deque()
        self._condition = threading.Condition()
        self.high_water_mark = 0
        self._closed = False
        self._last_token_at: float | None = None

    def put(self, item: dict[str, Any] | None) -> None:
        with self._condition:
            if self._closed:
                return
            if item is None:
                self._closed = True
                self._condition.notify_all()
                return
            item_type = item.get("type")
            if item_type == "token":
                token_at = time.monotonic()
                if self._coalesce_token_locked(item, token_at):
                    self._last_token_at = token_at
                    self._condition.notify()
                    return
                if (
                    len(self._items) >= self.maxsize
                    and self._coalesce_queued_token_locked(item)
                ):
                    self._last_token_at = token_at
                    self._condition.notify()
                    return
                self._last_token_at = token_at
            else:
                self._last_token_at = None
            if len(self._items) >= self.maxsize:
                if item_type in {"result", "error", "cancelled"}:
                    self._make_terminal_room_locked()
                elif not self._discard_nonterminal_event_locked():
                    # Stage/citation telemetry is best-effort under pressure;
                    # never discard answer text to enqueue it.
                    return
            self._items.append(item)
            self.high_water_mark = max(self.high_water_mark, len(self._items))
            self._condition.notify()

    def _coalesce_token_locked(
        self,
        item: dict[str, Any],
        token_at: float,
    ) -> bool:
        if not self._items:
            return False
        previous = self._items[-1]
        if not isinstance(previous, dict) or previous.get("type") != "token":
            return False
        combined = str(previous.get("delta") or "") + str(item.get("delta") or "")
        flush_due = (
            self._last_token_at is None
            or token_at - self._last_token_at >= self.token_flush_seconds
        )
        if (
            (len(combined) > self.token_flush_chars or flush_due)
            and len(self._items) < self.maxsize
        ):
            return False
        previous["delta"] = combined
        return True

    def _coalesce_queued_token_locked(self, item: dict[str, Any]) -> bool:
        for value in reversed(self._items):
            if isinstance(value, dict) and value.get("type") == "token":
                value["delta"] = (
                    str(value.get("delta") or "")
                    + str(item.get("delta") or "")
                )
                return True
        return False

    def _discard_nonterminal_event_locked(self) -> bool:
        for index, value in enumerate(self._items):
            if (
                isinstance(value, dict)
                and value.get("type") not in {
                    "token",
                    "result",
                    "error",
                    "cancelled",
                }
            ):
                del self._items[index]
                return True
        return False

    def _make_terminal_room_locked(self) -> None:
        while len(self._items) >= self.maxsize:
            if self._discard_nonterminal_event_locked():
                continue
            for index, value in enumerate(self._items):
                if isinstance(value, dict) and value.get("type") == "token":
                    del self._items[index]
                    break
            else:
                self._items.popleft()

    def get(self, timeout: float | None = None) -> dict[str, Any] | None:
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while not self._items:
                if self._closed:
                    return None
                remaining = (
                    None if deadline is None else max(0.0, deadline - time.monotonic())
                )
                if remaining == 0:
                    raise TimeoutError
                self._condition.wait(remaining)
            return self._items.popleft()


@dataclass(slots=True)
class ChatRequestRecord:
    request_id: str
    user_key: str
    work: Callable[["ChatRequestRecord"], None]
    events: BoundedEventChannel
    deadline: float
    client_request_id: str | None = None
    submission_sequence: int = 0
    cancel_event: threading.Event = field(default_factory=threading.Event)
    stage: str = "accepted"
    created_at: float = field(default_factory=time.monotonic)
    queued_at: float = field(default_factory=time.monotonic)
    started_at: float | None = None
    first_token_at: float | None = None
    completed_at: float | None = None
    safe_error_code: str | None = None
    visible_token_started: bool = False
    terminal_emitted: bool = False
    cleanup_complete: bool = False
    queue_wait_ms: float | None = None
    gate_wait_ms: dict[str, float] = field(default_factory=dict)

    def raise_if_cancelled(self) -> None:
        if time.monotonic() >= self.deadline:
            self.cancel_event.set()
            raise TimeoutError("Chat request deadline exceeded.")
        if self.cancel_event.is_set():
            raise InterruptedError("Chat request cancelled.")

    def emit(self, event: dict[str, Any]) -> None:
        event.setdefault("request_id", self.request_id)
        if self.client_request_id:
            event.setdefault("client_request_id", self.client_request_id)
        event.setdefault("elapsed_ms", int((time.monotonic() - self.created_at) * 1000))
        self.events.put(event)

    def emit_token(self, delta: str) -> None:
        if not delta:
            return
        self.raise_if_cancelled()
        if self.first_token_at is None:
            self.first_token_at = time.monotonic()
        self.visible_token_started = True
        self.emit(
            {
                "type": "token",
                "stage_id": "generation",
                "status": "started",
                "delta": delta,
            }
        )

    def emit_terminal(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        if self.terminal_emitted:
            return
        self.terminal_emitted = True
        self.emit(
            {
                "type": event_type,
                "stage_id": "complete",
                "status": "completed" if event_type == "result" else "failed",
                **({"payload": payload} if payload is not None else {}),
            }
        )


@dataclass(slots=True)
class _GateWaiter:
    record: ChatRequestRecord
    granted: threading.Event = field(default_factory=threading.Event)
    acquired: bool = False


class FairResourceGate:
    """Cancellation-aware per-user FIFO / cross-user round-robin gate."""

    def __init__(
        self,
        name: str,
        capacity: int,
        *,
        fair_scheduling: bool = True,
    ) -> None:
        self.name = name
        self.capacity = capacity
        self.fair_scheduling = fair_scheduling
        self._used = 0
        self._queues: dict[str, deque[_GateWaiter]] = {}
        self._users: deque[str] = deque()
        self._condition = threading.Condition()
        self._closed = False
        self._wait_samples: deque[float] = deque(maxlen=512)
        self._last_granted_user: str | None = None

    @contextmanager
    def acquire(self, record: ChatRequestRecord) -> Iterator[None]:
        record.raise_if_cancelled()
        waiter = _GateWaiter(record)
        started = time.monotonic()
        waiting_stage = {
            "query_embedding": "waiting_for_query_embedding",
            "retrieval": "searching",
            "reranker": "waiting_for_reranker",
            "generation": "waiting_for_generation",
        }[self.name]
        running_stage = {
            "query_embedding": "searching",
            "retrieval": "searching",
            "reranker": "reranking",
            "generation": "generating",
        }[self.name]
        record.stage = waiting_stage
        record.emit(
            {
                "type": "stage",
                "stage_id": waiting_stage,
                "status": "started",
                "metrics": {"gate": self.name},
            }
        )
        with self._condition:
            if self._closed:
                raise ChatControllerUnavailable("Chat concurrency controller is stopping.")
            queue_for_user = self._queues.setdefault(record.user_key, deque())
            queue_for_user.append(waiter)
            if record.user_key not in self._users:
                self._users.append(record.user_key)
            self._grant_locked()
        try:
            while not waiter.granted.wait(0.05):
                if record.cancel_event.is_set():
                    self._remove(waiter)
                    raise InterruptedError("Chat request cancelled.")
                if time.monotonic() >= record.deadline:
                    record.cancel_event.set()
                    self._remove(waiter)
                    raise TimeoutError(f"{self.name} gate wait timed out.")
            record.raise_if_cancelled()
            waited_ms = (time.monotonic() - started) * 1000
            record.gate_wait_ms[self.name] = waited_ms
            record.stage = running_stage
            record.emit(
                {
                    "type": "stage",
                    "stage_id": running_stage,
                    "status": "started",
                    "metrics": {
                        "gate": self.name,
                        "gate_wait_ms": round(waited_ms, 3),
                    },
                }
            )
            with self._condition:
                self._wait_samples.append(waited_ms)
            yield
        finally:
            if waiter.acquired:
                with self._condition:
                    waiter.acquired = False
                    self._used = max(0, self._used - 1)
                    self._grant_locked()
                    self._condition.notify_all()

    def _remove(self, waiter: _GateWaiter) -> None:
        with self._condition:
            queue_for_user = self._queues.get(waiter.record.user_key)
            if queue_for_user is not None:
                try:
                    queue_for_user.remove(waiter)
                except ValueError:
                    pass
                if not queue_for_user:
                    self._queues.pop(waiter.record.user_key, None)
                    self._users = deque(
                        key for key in self._users if key != waiter.record.user_key
                    )
            self._grant_locked()
            self._condition.notify_all()

    def _grant_locked(self) -> None:
        while self._used < self.capacity and self._users:
            if (
                self.fair_scheduling
                and len(self._users) > 1
                and self._users[0] == self._last_granted_user
            ):
                self._users.rotate(-1)
            user_key = self._users.popleft()
            queue_for_user = self._queues.get(user_key)
            if not queue_for_user:
                self._queues.pop(user_key, None)
                continue
            waiter = queue_for_user.popleft()
            if queue_for_user:
                self._users.append(user_key)
            else:
                self._queues.pop(user_key, None)
            if waiter.record.cancel_event.is_set():
                continue
            self._used += 1
            self._last_granted_user = user_key
            waiter.acquired = True
            waiter.granted.set()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            for queue_for_user in self._queues.values():
                for waiter in queue_for_user:
                    waiter.record.cancel_event.set()
                    waiter.granted.set()
            self._condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            samples = list(self._wait_samples)
            return {
                "used": self._used,
                "capacity": self.capacity,
                "waiters": sum(len(values) for values in self._queues.values()),
                "wait_ms_p50": _percentile(samples, 0.50),
                "wait_ms_p95": _percentile(samples, 0.95),
            }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile)))
    return round(ordered[index], 3)


class ChatConcurrencyController:
    """Lifecycle-managed bounded scheduler and content-free request registry."""

    def __init__(self) -> None:
        multi_request_enabled = settings.chat_multi_request_enabled
        self.fair_scheduling = settings.chat_fair_scheduling
        self.max_active_global = (
            settings.chat_max_active_global if multi_request_enabled else 1
        )
        self.max_active_per_user = (
            settings.chat_max_active_per_user if multi_request_enabled else 1
        )
        self.max_queued_global = settings.chat_max_queued_global
        self.max_queued_per_user = settings.chat_max_queued_per_user
        self._condition = threading.Condition()
        self._queues: dict[str, deque[ChatRequestRecord]] = {}
        self._users: deque[str] = deque()
        self._active_by_user: Counter[str] = Counter()
        self._active_count = 0
        self._last_dispatched_user: str | None = None
        self._records: dict[str, ChatRequestRecord] = {}
        self._admitting = False
        self._closed = False
        self._dispatcher: threading.Thread | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=settings.chat_executor_workers,
            thread_name_prefix="cial-chat",
        )
        self.gates = {
            "query_embedding": FairResourceGate(
                "query_embedding",
                settings.chat_query_embedding_concurrency,
                fair_scheduling=self.fair_scheduling,
            ),
            "retrieval": FairResourceGate(
                "retrieval",
                settings.chat_retrieval_concurrency,
                fair_scheduling=self.fair_scheduling,
            ),
            "reranker": FairResourceGate(
                "reranker",
                settings.chat_rerank_concurrency,
                fair_scheduling=self.fair_scheduling,
            ),
            "generation": FairResourceGate(
                "generation",
                settings.chat_generation_concurrency,
                fair_scheduling=self.fair_scheduling,
            ),
        }
        self._counts: Counter[str] = Counter()
        self._queue_wait_samples: deque[float] = deque(maxlen=512)
        self._event_queue_high_water = 0
        self._submission_sequence = 0
        self._session_guard = threading.Lock()
        self._session_locks: dict[str, tuple[threading.Lock, int]] = {}

    def start(self) -> None:
        with self._condition:
            if self._closed:
                raise ChatControllerUnavailable("Chat concurrency controller is closed.")
            if self._dispatcher is not None:
                self._admitting = True
                return
            self._admitting = True
            self._dispatcher = threading.Thread(
                target=self._dispatch_loop,
                name="cial-chat-dispatcher",
                daemon=False,
            )
            self._dispatcher.start()

    def submit(
        self,
        *,
        user_key: str,
        work: Callable[[ChatRequestRecord], None],
        client_request_id: str | None = None,
        request_id: str | None = None,
    ) -> ChatRequestRecord:
        with self._condition:
            if not self._admitting or self._closed:
                raise ChatControllerUnavailable("The assistant is stopping.")
            global_queued = self._queued_count_locked()
            user_queued = len(self._queues.get(user_key, ()))
            if global_queued >= self.max_queued_global:
                self._counts["global_limit_rejections"] += 1
                raise ChatCapacityError(
                    scope="global",
                    active_count=self._active_count,
                    queued_count=global_queued,
                    limit=self.max_queued_global,
                )
            if user_queued >= self.max_queued_per_user:
                self._counts["user_limit_rejections"] += 1
                raise ChatCapacityError(
                    scope="user",
                    active_count=self._active_by_user[user_key],
                    queued_count=user_queued,
                    limit=self.max_queued_per_user,
                )
            now = time.monotonic()
            self._submission_sequence = max(
                time.time_ns(),
                self._submission_sequence + 1,
            )
            record = ChatRequestRecord(
                request_id=request_id or str(uuid.uuid4()),
                client_request_id=client_request_id,
                user_key=user_key,
                work=work,
                events=BoundedEventChannel(
                    settings.chat_event_queue_size,
                    settings.chat_token_flush_chars,
                    settings.chat_token_flush_ms,
                ),
                deadline=now + settings.chat_request_timeout_seconds,
                submission_sequence=self._submission_sequence,
                created_at=now,
                queued_at=now,
            )
            self._records[record.request_id] = record
            queue_for_user = self._queues.setdefault(user_key, deque())
            queue_for_user.append(record)
            if user_key not in self._users:
                self._users.append(user_key)
            record.emit(
                {
                    "type": "stage",
                    "stage_id": "queued",
                    "status": "started",
                    "metrics": {
                        "active_count": self._active_count,
                        "queued_count": global_queued + 1,
                    },
                }
            )
            self._condition.notify_all()
            return record

    def cancel(self, request_id: str) -> bool:
        with self._condition:
            record = self._records.get(request_id)
            if record is None:
                return False
            record.cancel_event.set()
            if record.started_at is None:
                self._remove_queued_locked(record)
                self._finish_without_worker_locked(record, "cancelled")
            self._condition.notify_all()
            return True

    def gate(self, name: str, record: ChatRequestRecord) -> Iterator[None]:
        gate = self.gates[name]
        return gate.acquire(record)

    @contextmanager
    def external_generation(
        self,
        user_key: str = "auxiliary",
        cancel_event: threading.Event | None = None,
    ) -> Iterator[None]:
        """Share local-model capacity with summaries and message actions."""

        record = ChatRequestRecord(
            request_id=str(uuid.uuid4()),
            user_key=user_key,
            work=lambda _: None,
            events=BoundedEventChannel(
                4,
                settings.chat_token_flush_chars,
                settings.chat_token_flush_ms,
            ),
            deadline=time.monotonic() + settings.chat_request_timeout_seconds,
            cancel_event=cancel_event or threading.Event(),
        )
        with self.gates["generation"].acquire(record):
            yield

    def transition(
        self,
        record: ChatRequestRecord,
        stage: str,
        *,
        status: str = "started",
        metrics: dict[str, Any] | None = None,
    ) -> None:
        record.stage = stage
        record.emit(
            {
                "type": "stage",
                "stage_id": stage,
                "status": status,
                "metrics": dict(metrics or {}),
            }
        )

    @contextmanager
    def materialize_session(self, session_key: str) -> Iterator[None]:
        """Serialize only first-session creation, never answer execution."""

        with self._session_guard:
            lock, references = self._session_locks.get(
                session_key, (threading.Lock(), 0)
            )
            self._session_locks[session_key] = (lock, references + 1)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self._session_guard:
                current_lock, references = self._session_locks.get(
                    session_key, (lock, 1)
                )
                if references <= 1:
                    self._session_locks.pop(session_key, None)
                else:
                    self._session_locks[session_key] = (
                        current_lock,
                        references - 1,
                    )

    def _dispatch_loop(self) -> None:
        while True:
            with self._condition:
                self._expire_queued_locked()
                self._condition.wait_for(
                    lambda: self._closed
                    or self._has_eligible_locked(),
                    timeout=0.25,
                )
                self._expire_queued_locked()
                if self._closed and not self._users:
                    return
                while self._active_count < self.max_active_global:
                    record = self._next_eligible_locked()
                    if record is None:
                        break
                    now = time.monotonic()
                    if record.cancel_event.is_set():
                        self._finish_without_worker_locked(record, "cancelled")
                        continue
                    if (
                        now - record.queued_at
                        >= settings.chat_queue_wait_timeout_seconds
                    ):
                        record.cancel_event.set()
                        self._finish_without_worker_locked(record, "timed_out")
                        continue
                    record.started_at = now
                    record.queue_wait_ms = (now - record.queued_at) * 1000
                    self._queue_wait_samples.append(record.queue_wait_ms)
                    record.stage = "validating"
                    self._active_count += 1
                    self._active_by_user[record.user_key] += 1
                    self._executor.submit(self._run_record, record)

    def _next_eligible_locked(self) -> ChatRequestRecord | None:
        attempts = len(self._users)
        if (
            self.fair_scheduling
            and len(self._users) > 1
            and self._users[0] == self._last_dispatched_user
        ):
            self._users.rotate(-1)
        while attempts > 0 and self._users:
            attempts -= 1
            user_key = self._users.popleft()
            queue_for_user = self._queues.get(user_key)
            if not queue_for_user:
                self._queues.pop(user_key, None)
                continue
            if self._active_by_user[user_key] >= self.max_active_per_user:
                self._users.append(user_key)
                continue
            record = queue_for_user.popleft()
            if queue_for_user:
                self._users.append(user_key)
            else:
                self._queues.pop(user_key, None)
            self._last_dispatched_user = user_key
            return record
        return None

    def _has_eligible_locked(self) -> bool:
        return (
            self._active_count < self.max_active_global
            and any(
                self._active_by_user[user_key] < self.max_active_per_user
                and bool(self._queues.get(user_key))
                for user_key in self._users
            )
        )

    def _expire_queued_locked(self) -> None:
        now = time.monotonic()
        terminal: list[tuple[ChatRequestRecord, str]] = []
        for queue_for_user in tuple(self._queues.values()):
            for record in tuple(queue_for_user):
                if record.cancel_event.is_set():
                    terminal.append((record, "cancelled"))
                elif (
                    now - record.queued_at
                    >= settings.chat_queue_wait_timeout_seconds
                ):
                    record.cancel_event.set()
                    terminal.append((record, "timed_out"))
        for record, stage in terminal:
            self._remove_queued_locked(record)
            self._finish_without_worker_locked(record, stage)

    def _run_record(self, record: ChatRequestRecord) -> None:
        try:
            record.raise_if_cancelled()
            record.work(record)
            if not record.terminal_emitted:
                record.stage = "completed"
        except InterruptedError:
            record.stage = "cancelled"
            self._counts["cancelled"] += 1
            record.emit_terminal(
                "cancelled", {"message": "Assistant request stopped."}
            )
        except TimeoutError:
            record.stage = "timed_out"
            self._counts["timed_out"] += 1
            record.emit_terminal(
                "error",
                {
                    "message": "The assistant request timed out. Please retry.",
                    "reason": "request_timeout",
                    "timeout_state": "timed_out",
                    "retry_allowed": not record.visible_token_started,
                },
            )
        except Exception as exc:  # route work converts expected failures first
            record.stage = "failed"
            record.safe_error_code = type(exc).__name__
            self._counts["failed"] += 1
            logger.exception(
                "chat_request_worker_failed",
                extra={
                    "event": "chat_request_failed",
                    "request_id": record.request_id,
                    "stage": record.stage,
                    "error_code": record.safe_error_code,
                },
            )
            record.emit_terminal(
                "error",
                {
                    "message": "The assistant could not complete this request.",
                    "reason": "internal_error",
                    "retry_allowed": not record.visible_token_started,
                },
            )
        finally:
            record.completed_at = time.monotonic()
            if record.stage == "completed":
                self._counts["completed"] += 1
            record.events.put(None)
            with self._condition:
                self._event_queue_high_water = max(
                    self._event_queue_high_water, record.events.high_water_mark
                )
                self._active_count = max(0, self._active_count - 1)
                self._active_by_user[record.user_key] -= 1
                if self._active_by_user[record.user_key] <= 0:
                    self._active_by_user.pop(record.user_key, None)
                record.cleanup_complete = True
                self._records.pop(record.request_id, None)
                self._condition.notify_all()

    def _remove_queued_locked(self, record: ChatRequestRecord) -> None:
        queue_for_user = self._queues.get(record.user_key)
        if queue_for_user is None:
            return
        try:
            queue_for_user.remove(record)
        except ValueError:
            return
        if not queue_for_user:
            self._queues.pop(record.user_key, None)
            self._users = deque(key for key in self._users if key != record.user_key)

    def _finish_without_worker_locked(
        self, record: ChatRequestRecord, terminal_stage: str
    ) -> None:
        record.stage = terminal_stage
        record.completed_at = time.monotonic()
        self._counts[terminal_stage] += 1
        if terminal_stage == "cancelled":
            record.emit_terminal(
                "cancelled", {"message": "Assistant request stopped."}
            )
        else:
            record.emit_terminal(
                "error",
                {
                    "message": "The assistant request timed out while queued.",
                    "reason": "queue_timeout",
                    "timeout_state": "timed_out",
                    "retry_allowed": True,
                },
            )
        record.events.put(None)
        record.cleanup_complete = True
        self._records.pop(record.request_id, None)

    def _queued_count_locked(self) -> int:
        return sum(len(values) for values in self._queues.values())

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            records = tuple(self._records.values())
            queue_waits = list(self._queue_wait_samples)
            return {
                "active_chat_request_count": self._active_count,
                "queued_chat_request_count": self._queued_count_locked(),
                "counts_by_stage": dict(Counter(record.stage for record in records)),
                "gates": {
                    name: gate.snapshot() for name, gate in self.gates.items()
                },
                "global_limit_rejection_count": self._counts[
                    "global_limit_rejections"
                ],
                "per_user_limit_rejection_count": self._counts[
                    "user_limit_rejections"
                ],
                "queue_wait_ms_p50": _percentile(queue_waits, 0.50),
                "queue_wait_ms_p95": _percentile(queue_waits, 0.95),
                "cancellation_count": self._counts["cancelled"],
                "timeout_count": self._counts["timed_out"],
                "completed_count": self._counts["completed"],
                "failed_count": self._counts["failed"],
                "event_queue_high_water_mark": self._event_queue_high_water,
                "fair_scheduling": self.fair_scheduling,
                "admitting": self._admitting,
            }

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._admitting = False
            self._closed = True
            queued = [record for values in self._queues.values() for record in values]
            self._queues.clear()
            self._users.clear()
            for record in queued:
                record.cancel_event.set()
                self._finish_without_worker_locked(record, "cancelled")
            for record in self._records.values():
                record.cancel_event.set()
            self._condition.notify_all()
        for gate in self.gates.values():
            gate.close()
        if self._dispatcher is not None:
            self._dispatcher.join(timeout=5)
        shutdown_deadline = time.monotonic() + 5
        with self._condition:
            while self._active_count and time.monotonic() < shutdown_deadline:
                self._condition.wait(
                    max(0.0, shutdown_deadline - time.monotonic())
                )
            all_workers_stopped = self._active_count == 0
        self._executor.shutdown(
            wait=all_workers_stopped,
            cancel_futures=True,
        )
