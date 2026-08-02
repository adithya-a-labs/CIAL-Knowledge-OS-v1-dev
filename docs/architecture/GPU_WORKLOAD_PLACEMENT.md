# GPU Workload Placement

Measured on 2026-08-01. Configured `auto` or `num_gpu=-1` values are intent,
not proof of CUDA execution.

## Host and process topology

- Windows 11 build 26200; AMD Ryzen AI 9 HX 370 (12C/24T); 31.1 GiB RAM.
- NVIDIA GeForce RTX 5070 Ti Laptop GPU, 12,227 MiB VRAM, driver 591.84.
- Python 3.11.9; PyTorch 2.13.0+cu132; cuDNN 92000; CUDA capability 12.0.
- CUDA, fp16, and bf16 tests passed in the repository virtual environment.
- Ollama 0.32.5; `gemma3:12b` Q4_K_M, 12.2B parameters.

FastAPI owns one query BGE-M3 and one reranker instance. The standalone
indexer owns a separate BGE-M3 because model objects cannot be safely shared
across processes. Ollama owns Gemma. Heavy loading occurs in serving/indexer
startup, not per request or in the Uvicorn reload supervisor.

## Final placement map

| Component | Device | Reason |
|---|---|---|
| Ollama Gemma generation | NVIDIA GPU | Measured `100% GPU`, 9,634 MiB peak, and nonzero utilization. |
| Indexer BGE-M3 embeddings | NVIDIA GPU, fp16 | Measured `cuda:0` parameters and batch inference; cooperative release/yield enabled. |
| Query BGE-M3 | CPU, float32 | CUDA latency is lower, but its 2,339 MiB residency leaves unsafe headroom beside Ollama. |
| Cross-encoder reranker | NVIDIA GPU, float32 | Material speedup for about 257 MiB observed VRAM delta. |
| BM25, Qdrant, PostgreSQL | CPU/network | No tensor inference in these components. |
| OCR, parsing, hashing, metadata, watchers | CPU | File/parser/OCR/database work; current OCR engine has no CUDA path. |
| FastAPI routing, queueing, Caddy, mDNS, firewall, React, previews | CPU/network | Control-plane, transport, and UI work. |

## Benchmarks

All neural tests used cached local models. CUDA timings synchronized the device.

| Query BGE-M3 | p50 | p95 | p99 | VRAM delta |
|---|---:|---:|---:|---:|
| CPU single | 165.54 ms | 177.80 ms | 177.80 ms | 0 MiB |
| CUDA single | 22.73 ms | 30.76 ms | 30.76 ms | 2,339 MiB |
| CPU burst of 4 | 220.58 ms | 246.33 ms | 246.33 ms | 0 MiB |
| CUDA burst of 4 | 38.40 ms | 49.37 ms | 49.37 ms | 2,339 MiB |

| Reranker candidates | CPU p50 | CUDA p50 | CPU/s | CUDA/s |
|---:|---:|---:|---:|---:|
| 8 | 36.66 ms | 15.27 ms | 218.2 | 524.1 |
| 16 | 49.34 ms | 13.56 ms | 324.3 | 1,179.9 |
| 32 | 93.29 ms | 26.11 ms | 343.0 | 1,225.4 |
| 64 | 197.69 ms | 47.65 ms | 323.7 | 1,343.0 |
| 128 | 367.53 ms | 56.38 ms | 348.3 | 2,270.4 |
| 250 | 830.36 ms | 137.53 ms | 301.1 | 1,817.7 |

| Indexer fp16 batch | p50 | Chunks/s | Peak allocated | Total GPU used |
|---:|---:|---:|---:|---:|
| 1 | 30.79 ms | 32.5 | 1,120.0 MiB | 3,636 MiB |
| 16 | 70.39 ms | 227.3 | 1,187.9 MiB | 3,636 MiB |
| 32 | 125.62 ms | 254.7 | 1,261.2 MiB | 3,636 MiB |
| 64 | 264.92 ms | 241.6 | 1,406.7 MiB | 3,636 MiB |
| 128 | 500.42 ms | 255.8 | 1,698.3 MiB | 3,636 MiB |
| 256 | 1,094.62 ms | 233.9 | 2,287.2 MiB | 4,480 MiB |

Batch 64 is safe. The adaptive controller may grow toward 128 under the 0.70
VRAM target. Batch 256 was safe in isolation but slower per chunk than 128, so
it remains a ceiling rather than a target.

## Ollama evidence and startup defect

Before any edit or restart, direct `num_gpu=-1` generation showed zero GPU
utilization, 707 MiB steady device use, and `ollama ps` reported `100% CPU`.
Ollama's log exposed only its CPU inference device. Omitting `num_gpu` produced
the same result, proving CIAL payload forwarding was not the cause.

After one controlled Ollama restart, its discovery log identified CUDA0,
compute 12.0, and 10.8 GiB available. The unchanged request then reported
`100% GPU`, peaked at 9,634 MiB and 67% utilization, generated at 45.33 tok/s,
and evaluated the prompt at 124 tok/s. Cold TTFT was 9.22 seconds, dominated by
a 9.05-second model load. This proves full GPU residency for the 4,096-token
runner; it does not invent an unavailable layer count.

If startup exposes only CPU, restart Ollama and recheck its discovery log and
`ollama ps`. Telemetry reports `placement_matches_request` and a bounded
fallback reason; it does not silently label CPU execution as GPU.

## VRAM and arbitration

Warm Ollama uses about 9.6 GiB. The small reranker can coexist. A CUDA query
BGE-M3 would reduce measured headroom to roughly 250 MiB, so query embedding is
intentionally CPU. The indexer owns the fp16 BGE-M3 CUDA window only after
Ollama is released.

Chat priority uses a cross-process marker with reference-counted owners.
Overlapping or nested owners cannot clear another active request. The indexer
checks between bounded batches, releases CUDA, waits through an event-aware
loop, and restores the concrete resolved CUDA device before encode. `finally`
paths release priority on cancellation/error. Generation concurrency is one.

## Validation, fallback, and observability

- Explicit `cuda`/`cuda:N` fails when unavailable or invalid; it never silently
  becomes CPU. `auto` may use CPU only when CUDA is unavailable and records
  `auto_resolved_to_cpu_cuda_unavailable`.
- Explicit CPU indexing rejects fp16/bf16. Invalid Ollama layer counts and
  generation concurrency greater than one fail configuration validation.
- Authenticated telemetry includes GPU name/driver/utilization, used/free/total
  VRAM, Ollama processor/memory, requested/resolved devices, dtypes, fallback
  reasons, model-load counts, batch/VRAM target, and yield/residency state.
- Telemetry excludes prompts, answers, document names, private paths, raw
  command lines, credentials, vectors, and auth tokens.

## Live end-to-end validation

The final authenticated browser run used a disposable local viewer account.
Quick and Detailed grounded chats completed with citations (23.1 seconds and
19.1 seconds in the UI). Two overlapping Detailed requests both completed
(21.2 seconds and 26.0 seconds), exercising the single-generation admission
path. During a CIAL chat, 131 external samples measured 12.2% average and 99%
peak GPU utilization with 9,782 MiB peak total VRAM; `ollama ps` reported the
loaded Gemma runner as `100% GPU`.

Cancelling a generation produced the expected `Stopped` state and left no
chat-priority marker, confirming cleanup of the GPU lease. Chat remained
available while the UI reported `Updating knowledge`. This run did not force a
new indexing job solely to manufacture overlap, so deterministic coordinator
tests are the evidence for indexer yield/resume while a chat lease is active.

The authenticated system-status endpoint then reported query BGE-M3 on CPU
float32, reranker on `cuda:0` float32, Ollama full-GPU placement, and model-load
count 1 for both in-process query models. After a controlled indexer restart,
the worker reported `cuda:0`/fp16 and model-load count 1, then
`released_idle`, actual CPU residency, and zero allocated/reserved Torch VRAM.
Its live heartbeat included the RTX 5070 Ti name, driver 591.84, and
used/free/total VRAM.

The disposable viewer correctly received HTTP 403 at the administrator-only
System Monitor route, so the page itself could not be visually inspected under
that account. Its typed production build and backend response contract were
validated instead. A pre-existing development-console `useAuth must be used
within AuthProvider` message was observed during initial routing and is outside
this device-placement change.

## Troubleshooting and limits

```powershell
nvidia-smi
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
ollama --version
ollama ps
ollama show gemma3:12b
curl.exe http://127.0.0.1:8000/api/health
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

WDDM returns per-process memory as `[N/A]`; total VRAM, Ollama's process API,
process identity, and process-local PyTorch allocation are therefore
correlated. Ollama does not publish a trustworthy used-layer count, so that
field stays null. The external Ollama service owns GPU discovery; the backend
reports a mismatch but cannot repair it without restarting that service.
