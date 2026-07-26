"""Cross-process chat priority and safe local GPU telemetry."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from threading import Event, Lock, Thread
import time
from typing import Any, Iterator

from ollama import Client

from backend.app.core.config import settings


class GpuResourceCoordinator:
    """Coordinate Ollama generation and background embedding without killing processes."""

    def __init__(self, marker_path: Path | None = None) -> None:
        runtime_root = settings.data_root_path / "runtime"
        self.marker_path = marker_path or runtime_root / "chat-gpu-priority.json"
        self.stale_seconds = max(
            float(settings.chat_request_timeout_seconds) + 30.0,
            180.0,
        )

    @contextmanager
    def chat_priority(self, request_id: str) -> Iterator[None]:
        if not settings.ollama_gpu_priority_enabled:
            yield
            return
        try:
            self.marker_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.marker_path.with_suffix(
                f".{os.getpid()}.{request_id}.tmp"
            )
            payload = {
                "request_id": request_id,
                "pid": os.getpid(),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "started_epoch": time.time(),
            }
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(temporary, self.marker_path)
        except OSError:
            # Coordination is an optimization. A read-only runtime directory
            # must never make chat unavailable.
            yield
            return
        try:
            yield
        finally:
            try:
                current = json.loads(self.marker_path.read_text(encoding="utf-8"))
                if current.get("request_id") == request_id:
                    self.marker_path.unlink(missing_ok=True)
            except (OSError, ValueError, TypeError):
                pass

    def chat_active(self) -> bool:
        try:
            payload = json.loads(self.marker_path.read_text(encoding="utf-8"))
            started = float(payload.get("started_epoch") or 0)
        except (OSError, ValueError, TypeError):
            return False
        if started <= 0 or time.time() - started > self.stale_seconds:
            try:
                self.marker_path.unlink(missing_ok=True)
            except OSError:
                pass
            return False
        return True

    def wait_for_chat(self, stop_event: Any) -> float:
        started = time.monotonic()
        while self.chat_active() and not stop_event.is_set():
            stop_event.wait(settings.gpu_priority_poll_seconds)
        return max(0.0, time.monotonic() - started)


def inspect_gpu_runtime() -> dict[str, Any]:
    """Return bounded, content-free NVIDIA process and memory telemetry."""

    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"available": False, "processes": []}
    try:
        summary = subprocess.run(
            [
                executable,
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
        values = [item.strip() for item in summary.stdout.splitlines()[0].split(",")]
        process_result = subprocess.run(
            [
                executable,
                "--query-compute-apps=pid,process_name,used_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
        processes = []
        for line in process_result.stdout.splitlines()[:32]:
            parts = [item.strip() for item in line.split(",", 2)]
            if len(parts) != 3:
                continue
            name = Path(parts[1]).name.casefold()
            kind = (
                "ollama"
                if "ollama" in name
                else "python"
                if "python" in name
                else "other"
            )
            processes.append(
                {
                    "pid": int(parts[0]),
                    "kind": kind,
                    "memory_used_mb": (
                        float(parts[2])
                        if parts[2].replace(".", "", 1).isdigit()
                        else None
                    ),
                }
            )
        return {
            "available": True,
            "utilization_percent": float(values[0]),
            "memory_used_mb": float(values[1]),
            "memory_total_mb": float(values[2]),
            "processes": processes,
            "ollama_memory_mb": sum(
                float(item["memory_used_mb"] or 0)
                for item in processes
                if item["kind"] == "ollama"
            ),
            "python_memory_mb": sum(
                float(item["memory_used_mb"] or 0)
                for item in processes
                if item["kind"] == "python"
            ),
        }
    except (OSError, ValueError, subprocess.SubprocessError, IndexError):
        return {"available": False, "processes": []}


def inspect_ollama_runtime(model_name: str | None = None) -> dict[str, Any]:
    """Report Ollama's measured runtime placement without inventing layer counts."""

    try:
        models = Client(timeout=2).ps().models
    except Exception:
        return {
            "available": False,
            "ollama_processor_type": "unavailable",
            "gpu_layers_used": None,
            "cpu_offload_detected": None,
        }
    selected = next(
        (
            item
            for item in models
            if model_name is None
            or item.model == model_name
            or item.name == model_name
        ),
        None,
    )
    if selected is None:
        return {
            "available": True,
            "model_loaded": False,
            "ollama_processor_type": "not_loaded",
            "gpu_layers_used": None,
            "cpu_offload_detected": None,
        }
    size = int(selected.size or 0)
    size_vram = int(selected.size_vram or 0)
    gpu_ratio = (size_vram / size) if size > 0 else 0.0
    processor_type = (
        "gpu"
        if gpu_ratio >= 0.98
        else "hybrid"
        if size_vram > 0
        else "cpu"
    )
    return {
        "available": True,
        "model_loaded": True,
        "model": selected.model or selected.name,
        "ollama_processor_type": processor_type,
        "processor_gpu_percent": round(gpu_ratio * 100, 1),
        # Ollama's process API exposes bytes and processor percentage, not the
        # runtime layer count. Null is intentional and prevents fake telemetry.
        "gpu_layers_used": None,
        "gpu_layers_requested": settings.ollama_num_gpu,
        "gpu_memory_used": round(size_vram / (1024 * 1024), 1),
        "cpu_offload_detected": processor_type in {"cpu", "hybrid"},
        "context_length": selected.context_length,
        "expires_at": (
            selected.expires_at.isoformat() if selected.expires_at else None
        ),
    }


def release_ollama_runtime(model_name: str) -> bool:
    """Unload a warm Ollama runner when pending indexing needs the GPU."""

    runtime = inspect_ollama_runtime(model_name)
    if not runtime.get("model_loaded"):
        return False
    try:
        Client(timeout=10).generate(
            model=model_name,
            prompt="",
            stream=False,
            keep_alive=0,
        )
    except Exception:
        return False
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if not inspect_ollama_runtime(model_name).get("model_loaded", True):
            return True
        time.sleep(0.1)
    return False


class GenerationGpuSampler:
    """Sample NVIDIA utilization throughout one generation stage."""

    def __init__(self, model_name: str, *, interval_seconds: float = 0.25) -> None:
        self.model_name = model_name
        self.interval_seconds = interval_seconds
        self._stop = Event()
        self._lock = Lock()
        self._samples: list[dict[str, Any]] = []
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = Thread(
            target=self._run,
            name="generation-gpu-sampler",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            sample = inspect_gpu_runtime()
            with self._lock:
                self._samples.append(sample)
            self._stop.wait(self.interval_seconds)

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        with self._lock:
            samples = list(self._samples)
        valid = [sample for sample in samples if sample.get("available")]
        final_gpu = inspect_gpu_runtime()
        ollama = inspect_ollama_runtime(self.model_name)
        utilization = [
            float(sample["utilization_percent"])
            for sample in valid
            if sample.get("utilization_percent") is not None
        ]
        used_memory = [
            float(sample["memory_used_mb"])
            for sample in valid
            if sample.get("memory_used_mb") is not None
        ]
        return {
            **ollama,
            "gpu_memory_total": final_gpu.get("memory_total_mb"),
            "generation_gpu_utilization": (
                round(sum(utilization) / len(utilization), 1)
                if utilization
                else None
            ),
            "generation_gpu_utilization_peak": (
                max(utilization) if utilization else None
            ),
            "generation_gpu_memory_peak": max(used_memory) if used_memory else None,
            "generation_gpu_samples": len(valid),
        }
