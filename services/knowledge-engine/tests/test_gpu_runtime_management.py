from __future__ import annotations

from threading import Event
import time
from types import SimpleNamespace

from backend.app.services.continuous_indexer import ContinuousIndexer
from backend.app.services.gpu_resource_coordinator import GpuResourceCoordinator
from backend.app.services.gpu_resource_coordinator import inspect_ollama_runtime
from backend.app.services.gpu_resource_coordinator import inspect_gpu_runtime
from backend.app.services.gpu_resource_coordinator import release_ollama_runtime
from backend.app.services.knowledge_engine_service import KnowledgeEngineService


def test_gpu_priority_marker_is_visible_across_coordinators(tmp_path):
    marker = tmp_path / "chat-priority.json"
    writer = GpuResourceCoordinator(marker)
    reader = GpuResourceCoordinator(marker)

    assert reader.chat_active() is False
    with writer.chat_priority("request-1"):
        assert reader.chat_active() is True
    assert reader.chat_active() is False


def test_indexer_yields_and_releases_gpu_for_active_chat():
    released: list[bool] = []
    indexer = ContinuousIndexer.__new__(ContinuousIndexer)
    indexer.engine = SimpleNamespace(
        release_indexer_gpu=lambda: released.append(True) or True
    )
    indexer.stop_event = Event()
    indexer._metrics = {
        "gpu_state": "embedding",
        "chat_priority_active": False,
        "chat_priority_wait_seconds": 0.0,
        "embedding_model_gpu_resident": True,
    }
    indexer._gpu_coordinator = SimpleNamespace(
        chat_active=lambda: True,
        wait_for_chat=lambda stop_event: 0.25,
    )

    indexer._yield_to_chat_if_needed()

    assert released == [True]
    assert indexer._metrics["gpu_state"] == "warming"
    assert indexer._metrics["chat_priority_active"] is False
    assert indexer._metrics["embedding_model_gpu_resident"] is False
    assert indexer._metrics["chat_priority_wait_seconds"] == 0.25


def test_idle_indexer_releases_embedding_model(monkeypatch):
    released: list[bool] = []
    indexer = ContinuousIndexer.__new__(ContinuousIndexer)
    indexer.engine = SimpleNamespace(
        release_indexer_gpu=lambda: released.append(True) or True
    )
    indexer.worker_id = "worker-1"
    indexer.actual_device = "cuda:0"
    indexer._last_embedding_activity = time.monotonic() - 60
    indexer._metrics = {
        "gpu_state": "idle",
        "embedding_model_gpu_resident": True,
    }
    monkeypatch.setattr(
        "backend.app.services.continuous_indexer.settings.indexer_release_gpu_when_idle",
        True,
    )
    monkeypatch.setattr(
        "backend.app.services.continuous_indexer.settings.indexer_gpu_idle_release_seconds",
        30.0,
    )

    assert indexer._release_idle_gpu_if_due() is True
    assert released == [True]
    assert indexer._metrics["gpu_state"] == "released_idle"
    assert indexer._metrics["embedding_model_gpu_resident"] is False


def test_indexer_restores_cuda_after_chat_even_while_ollama_is_warm(monkeypatch):
    moves: list[str] = []
    releases: list[str] = []
    model = SimpleNamespace(
        to=lambda device: moves.append(device),
        half=lambda: None,
    )
    service = KnowledgeEngineService.__new__(KnowledgeEngineService)
    service._indexer_embedding_target_device = "cuda:0"
    service._indexer_embedding_gpu_resident = False
    service._ready_pipeline = lambda response_length: SimpleNamespace(
        embedding_model=model
    )
    monkeypatch.setattr(
        "backend.app.services.knowledge_engine_service.settings.indexer_precision",
        "float16",
    )
    monkeypatch.setattr(
        "backend.app.services.knowledge_engine_service.settings.indexer_gpu_cooperative_mode",
        True,
    )
    monkeypatch.setattr(
        "backend.app.services.knowledge_engine_service.settings.ollama_model_name",
        "gemma3:12b",
    )
    monkeypatch.setattr(
        "backend.app.services.knowledge_engine_service.inspect_ollama_runtime",
        lambda model_name: {"model_loaded": True},
    )
    monkeypatch.setattr(
        "backend.app.services.knowledge_engine_service.release_ollama_runtime",
        lambda model_name: releases.append(model_name) or True,
    )

    assert service.ensure_indexer_embedding_device() is True
    assert releases == ["gemma3:12b"]
    assert moves == ["cuda:0"]
    assert service._indexer_embedding_gpu_resident is True


def test_gpu_process_telemetry_keeps_windows_na_memory(monkeypatch):
    responses = iter(
        [
            SimpleNamespace(stdout="50, 7000, 12227\n"),
            SimpleNamespace(
                stdout=(
                    "101, C:\\Program Files\\Ollama\\ollama.exe, [N/A]\n"
                    "202, C:\\Python\\python.exe, [N/A]\n"
                )
            ),
        ]
    )
    monkeypatch.setattr(
        "backend.app.services.gpu_resource_coordinator.shutil.which",
        lambda name: "nvidia-smi",
    )
    monkeypatch.setattr(
        "backend.app.services.gpu_resource_coordinator.subprocess.run",
        lambda *args, **kwargs: next(responses),
    )

    sample = inspect_gpu_runtime()

    assert sample["available"] is True
    assert sample["memory_used_mb"] == 7000
    assert sample["processes"][0]["kind"] == "ollama"
    assert sample["processes"][0]["memory_used_mb"] is None


def test_ollama_runtime_reports_full_gpu_without_fake_layer_count(monkeypatch):
    model = SimpleNamespace(
        model="gemma3:12b",
        name="gemma3:12b",
        size=8 * 1024 * 1024 * 1024,
        size_vram=8 * 1024 * 1024 * 1024,
        context_length=8192,
        expires_at=None,
    )
    monkeypatch.setattr(
        "backend.app.services.gpu_resource_coordinator.Client",
        lambda timeout: SimpleNamespace(ps=lambda: SimpleNamespace(models=[model])),
    )

    runtime = inspect_ollama_runtime("gemma3:12b")

    assert runtime["ollama_processor_type"] == "gpu"
    assert runtime["processor_gpu_percent"] == 100.0
    assert runtime["cpu_offload_detected"] is False
    assert runtime["gpu_layers_used"] is None
    assert runtime["gpu_layers_requested"] == -1


def test_pending_index_work_unloads_warm_ollama_runner(monkeypatch):
    states = iter(
        [
            {"model_loaded": True},
            {"model_loaded": False},
        ]
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "backend.app.services.gpu_resource_coordinator.inspect_ollama_runtime",
        lambda model_name: next(states),
    )
    monkeypatch.setattr(
        "backend.app.services.gpu_resource_coordinator.Client",
        lambda timeout: SimpleNamespace(
            generate=lambda **kwargs: calls.append(kwargs)
        ),
    )

    assert release_ollama_runtime("gemma3:12b") is True
    assert calls == [
        {
            "model": "gemma3:12b",
            "prompt": "",
            "stream": False,
            "keep_alive": 0,
        }
    ]
