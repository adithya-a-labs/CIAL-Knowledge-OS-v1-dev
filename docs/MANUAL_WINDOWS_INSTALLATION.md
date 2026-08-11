# CIAL Knowledge OS Manual Windows Installation Guide

This is the official fallback deployment runbook for a clean Windows 11 NVIDIA workstation when the automated installer is unavailable. It documents the repository as implemented. Run PowerShell **as Administrator** unless stated otherwise.

```text
Browser -> Vite preview             http://127.0.0.1:5173
        -> FastAPI/Uvicorn          http://127.0.0.1:8000
             -> PostgreSQL 18       localhost:5432
             -> Qdrant              localhost:6335 -> container:6333
             -> Ollama              http://127.0.0.1:11434
             -> NVIDIA CUDA models
             -> enterprise filesystem repository
```

Do not substitute embedded Qdrant, CPU PyTorch, or a different database architecture.

## 1. System Requirements

### Hardware and Windows

Repository-enforced requirements:

- Windows 11 x64, build 22000 or newer, with Administrator rights
- x64 CPU and hardware virtualization enabled for Docker/WSL2
- NVIDIA GPU and compatible current Windows driver
- at least 80 GB free on the clone drive
- internet during first installation

The code does not define hard CPU-core, RAM, or VRAM minima. A practical starting point for the configured 12B LLM and indexing workload is 8 modern CPU cores, 32 GB RAM, and 16 GB NVIDIA VRAM; these are capacity recommendations, not code requirements.

Verify:

```powershell
winver
systeminfo.exe | Select-String 'System Type|Virtualization'
Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion
Get-PSDrive C
```

### Required software

| Component | Required version/configuration | Purpose |
|---|---|---|
| Git for Windows | Current supported | Clone/upgrades |
| Python | Exactly 3.11 x64 | Backend/models/migrations |
| PyTorch | `torch==2.13.0` from `cu132` index | CUDA inference; CPU unsupported |
| Node.js | Official LTS, `>=20.19` | Frontend |
| npm/Corepack | Official Node distribution | pnpm activation/repair |
| pnpm | Exactly `10.33.4` | Locked frontend install |
| Docker Desktop/WSL2 | Current | PostgreSQL and Qdrant |
| PostgreSQL | Docker image `postgres:18` | Metadata/auth/control plane |
| Qdrant | `qdrant/qdrant:v1.18.2` | Vectors |
| Ollama | Current Windows release | Local generation API |
| Ollama model | `gemma3:12b` | Generation |
| Hugging Face | `BAAI/bge-m3` | Embeddings |
| Hugging Face | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Reranking |
| Tesseract | UB Mannheim x64 build | OCR |
| LibreOffice | Current x64 | Office-to-PDF rendering |
| VC++ runtime | Microsoft 2015–2022 x64 | Native dependencies |

The standalone NVIDIA CUDA Toolkit is not required. The PyTorch wheel includes its CUDA runtime; the NVIDIA driver must support it.

## 2. Clone Repository

```powershell
Set-Location C:\
New-Item -ItemType Directory -Path C:\CIAL -Force
Set-Location C:\CIAL
git clone https://github.com/adithya-a-labs/CIAL-Knowledge-OS-v1-dev.git
Set-Location .\CIAL-Knowledge-OS-v1-dev
git status
```

Required layout:

```text
frontend\package.json
frontend\pnpm-lock.yaml
services\knowledge-engine\requirements.txt
services\knowledge-engine\pyproject.toml
services\knowledge-engine\alembic.ini
services\knowledge-engine\backend\app\main.py
services\knowledge-engine\docker-compose.qdrant.yml
scripts\configure_corpus_repository.ps1
```

Validate:

```powershell
$required=@('frontend\package.json','frontend\pnpm-lock.yaml','services\knowledge-engine\requirements.txt','services\knowledge-engine\alembic.ini','services\knowledge-engine\backend\app\main.py','services\knowledge-engine\docker-compose.qdrant.yml','scripts\configure_corpus_repository.ps1')
$required | ForEach-Object { if(-not(Test-Path -LiteralPath $_)){throw "Missing $_"} }
```

## 3. Install Windows Prerequisites

### WSL2

Enable firmware virtualization first, then:

```powershell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
wsl.exe --update
wsl.exe --set-default-version 2
```

Restart if requested. Verify with `wsl.exe --status`.

### NVIDIA driver

Purpose: expose the NVIDIA GPU to the pinned CUDA PyTorch runtime. Official source: <https://www.nvidia.com/Download/index.aspx>

Install the current driver approved for the workstation GPU, restart Windows, then verify:

```powershell
nvidia-smi.exe
Get-CimInstance Win32_VideoController | Where-Object Name -match NVIDIA | Select-Object Name,DriverVersion
```

The GPU and driver must be reported without an `nvidia-smi` error. Driver presence alone does not certify PyTorch; section 5 is the authoritative CUDA test.

### Git

Purpose: clone and upgrade. Official source: <https://git-scm.com/download/win>

```powershell
winget install --id Git.Git --exact --silent --accept-package-agreements --accept-source-agreements
git --version
```

Expected: `git version ...`.

### Python 3.11

Purpose: backend and model runtime. Official source: <https://www.python.org/downloads/windows/>

```powershell
winget install --id Python.Python.3.11 --exact --silent --accept-package-agreements --accept-source-agreements
py -3.11 --version
py -3.11 -c "import sys; print(sys.executable); print(sys.version); print(sys.maxsize > 2**32)"
```

Expected: Python `3.11.x` and `True`.

### Official Node LTS

Purpose: frontend. Official source: <https://nodejs.org/en/download>

```powershell
winget install --id OpenJS.NodeJS.LTS --exact --silent --accept-package-agreements --accept-source-agreements
& 'C:\Program Files\nodejs\node.exe' --version
& 'C:\Program Files\nodejs\npm.cmd' --version
& 'C:\Program Files\nodejs\corepack.cmd' --version
```

Expected: Node `20.19` or newer. Use the absolute official paths; do not use broken NVM shims.

### Docker Desktop

Purpose: PostgreSQL/Qdrant. Official source: <https://www.docker.com/products/docker-desktop/>

```powershell
winget install --id Docker.DockerDesktop --exact --silent --accept-package-agreements --accept-source-agreements
```

Restart if required, start Docker Desktop with the WSL2 backend, then verify:

```powershell
docker.exe --version
docker.exe version
docker.exe info
docker.exe compose version
```

Fallback Compose path:

```powershell
& 'C:\Program Files\Docker\Docker\resources\bin\docker-compose.exe' version
```

### Ollama

Purpose: `gemma3:12b`. Official source: <https://ollama.com/download/windows>

```powershell
winget install --id Ollama.Ollama --exact --silent --accept-package-agreements --accept-source-agreements
ollama.exe --version
```

### Tesseract

Purpose: OCR. Official source: <https://github.com/UB-Mannheim/tesseract/wiki>

```powershell
winget install --id UB-Mannheim.TesseractOCR --exact --silent --accept-package-agreements --accept-source-agreements
& 'C:\Program Files\Tesseract-OCR\tesseract.exe' --version
```

### LibreOffice

Purpose: Office rendering. Official source: <https://www.libreoffice.org/download/download-libreoffice/>

```powershell
winget install --id TheDocumentFoundation.LibreOffice --exact --silent --accept-package-agreements --accept-source-agreements
& 'C:\Program Files\LibreOffice\program\soffice.exe' --version
$office='C:\Program Files\LibreOffice\program'
$path=[Environment]::GetEnvironmentVariable('Path','Machine')
if(($path -split ';') -notcontains $office){[Environment]::SetEnvironmentVariable('Path',"$path;$office",'Machine')}
```

Open a new terminal and run `Get-Command soffice.exe`. This PATH step is mandatory because the document renderer resolves `soffice` with executable discovery.

### VC++ runtime

Official source: <https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist>

```powershell
winget install --id 'Microsoft.VCRedist.2015+.x64' --exact --silent --accept-package-agreements --accept-source-agreements
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' | Select-Object Installed,Version
```

Expected: `Installed = 1`.

## 4. Backend Setup

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -c "import sys; print(sys.executable); assert sys.version_info[:2]==(3,11)"
```

Install CUDA PyTorch first using section 5. Then:

```powershell
python -m pip install -r .\services\knowledge-engine\requirements.txt
python -m pip install -e .\services\knowledge-engine
python -m pip check
Set-Location .\services\knowledge-engine
..\..\.venv\Scripts\python.exe -c "import fastapi,uvicorn,sqlalchemy,alembic,psycopg,qdrant_client,ollama,pytesseract,fitz,docling,sentence_transformers,cial_knowledge_os; print('imports OK')"
Set-Location ..\..
```

`services\knowledge-engine\requirements.txt` is the actual environment input. It intentionally currently includes runtime, model, document, database, and test packages. Do not substitute the root requirements file or selectively omit entries.

The complete direct Python manifest currently is:

```text
docling==2.107.0
fastapi==0.139.0
httpx==0.28.1
langchain-core==1.4.8
langchain-ollama==1.1.0
langchain-text-splitters==1.1.2
matplotlib==3.11.0
numpy==2.3.5
ollama==0.6.2
openpyxl==3.1.5
pandas==3.0.3
Pillow==12.0.0
psutil==7.2.2
PyMuPDF==1.28.0
python-multipart==0.0.20
pytesseract==0.3.13
qdrant-client==1.18.0
rank-bm25==0.2.2
sentence-transformers==5.6.0
tiktoken==0.13.0
uvicorn==0.50.0
sqlalchemy==2.0.51
alembic==1.17.2
psycopg[binary]==3.3.2
accelerate
beautifulsoup4
huggingface-hub
jsonschema
loguru
lxml
markdown
orjson
pdfplumber
pydantic-settings
pypdf
pytest
pytest-asyncio
python-docx
python-dotenv
PyYAML
rapidfuzz
rich
safetensors
tokenizers
transformers
unstructured
watchdog
xlrd
```

Torch is intentionally commented out in the requirements file and must be installed separately from the CUDA index. Transitive versions are resolved by pip; record `python -m pip freeze` in the deployment evidence.

## 5. CUDA PyTorch

```powershell
.\.venv\Scripts\python.exe -m pip uninstall -y torch torchvision torchaudio
.\.venv\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cu132 torch==2.13.0
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.device_count()); [print(torch.cuda.get_device_name(i)) for i in range(torch.cuda.device_count())]; assert torch.__version__.split('+')[0]=='2.13.0'; assert torch.version.cuda; assert torch.cuda.is_available(); assert torch.cuda.device_count()>0"
```

Repeat the verification after installing backend requirements. Never continue with a CPU build or unavailable CUDA.

## 6. Frontend Setup

```powershell
& 'C:\Program Files\nodejs\corepack.cmd' enable
& 'C:\Program Files\nodejs\corepack.cmd' prepare pnpm@10.33.4 --activate
& 'C:\Program Files\nodejs\pnpm.cmd' --version
Set-Location .\frontend
& 'C:\Program Files\nodejs\pnpm.cmd' install --frozen-lockfile
& 'C:\Program Files\nodejs\pnpm.cmd' run typecheck
& 'C:\Program Files\nodejs\pnpm.cmd' run build
Set-Location ..
Test-Path .\frontend\dist\public\index.html
```

Expected pnpm: `10.33.4`; final path check: `True`.

The complete direct frontend manifest is installed from `package.json`, `pnpm-workspace.yaml`, and `pnpm-lock.yaml`. Runtime declarations are `react-markdown@^10.1.0` and `remark-gfm@^4.0.1`. Direct development/build declarations are:

```text
@hookform/resolvers, @radix-ui/react-accordion, @radix-ui/react-alert-dialog,
@radix-ui/react-aspect-ratio, @radix-ui/react-avatar, @radix-ui/react-checkbox,
@radix-ui/react-collapsible, @radix-ui/react-context-menu, @radix-ui/react-dialog,
@radix-ui/react-dropdown-menu, @radix-ui/react-hover-card, @radix-ui/react-label,
@radix-ui/react-menubar, @radix-ui/react-navigation-menu, @radix-ui/react-popover,
@radix-ui/react-progress, @radix-ui/react-radio-group, @radix-ui/react-scroll-area,
@radix-ui/react-select, @radix-ui/react-separator, @radix-ui/react-slider,
@radix-ui/react-slot, @radix-ui/react-switch, @radix-ui/react-tabs,
@radix-ui/react-toast, @radix-ui/react-toggle, @radix-ui/react-toggle-group,
@radix-ui/react-tooltip, @tailwindcss/typography, @tailwindcss/vite,
@tanstack/react-query, @types/node, @types/react, @types/react-dom,
@vitejs/plugin-react, @workspace/api-client-react, class-variance-authority,
clsx, cmdk, date-fns, embla-carousel-react, framer-motion, input-otp,
lucide-react, next-themes, pdfjs-dist, playwright, react, react-day-picker,
react-dom, react-hook-form, react-icons, react-pdf, react-resizable-panels,
recharts, sonner, tailwind-merge, tailwindcss, tw-animate-css, typescript,
vaul, vite, wouter, zod
```

Important exact/direct values include React/React DOM `19.1.0`, TypeScript `5.9.3`, Playwright `1.54.1`, `pdfjs-dist@^6.1.200`, `react-pdf@^10.4.1`, Vite `^7.3.2`, Tailwind CSS `^4.1.14`, and local workspace package `@workspace/api-client-react`. The lockfile is authoritative for all transitive versions; never translate this list into individual npm installs.

## 7. PostgreSQL

Actual configuration:

```text
image: postgres:18
container: cial-knowledge-os-v1-dev-postgres
volume: cial_postgres_data
port: 5432
database: cial_knowledge_os_dev
user: postgres
```

Generate and escrow a strong password. Keep it in memory for container creation:

```powershell
$secure=Read-Host 'PostgreSQL password' -AsSecureString
$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try{$PgPassword=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
$exists=docker.exe ps -a --format '{{.Names}}' | Select-String '^cial-knowledge-os-v1-dev-postgres$'
if(-not $exists){
  docker.exe run -d --name cial-knowledge-os-v1-dev-postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=$PgPassword -e POSTGRES_DB=cial_knowledge_os_dev -p 5432:5432 -v cial_postgres_data:/var/lib/postgresql/data postgres:18
}else{docker.exe start cial-knowledge-os-v1-dev-postgres}
docker.exe exec cial-knowledge-os-v1-dev-postgres psql -U postgres -d cial_knowledge_os_dev -c "SELECT current_database(),current_user,1;"
```

Expected database/user/test: `cial_knowledge_os_dev`, `postgres`, `1`.

`DATABASE_URL`:

```text
postgresql+psycopg://postgres:<URL-ENCODED-PASSWORD>@localhost:5432/cial_knowledge_os_dev
```

URL-encode reserved password characters. Never assume changing `POSTGRES_PASSWORD` changes an initialized volume.

## 8. Qdrant

```powershell
scripts\start_qdrant.bat
.venv\Scripts\python.exe services\knowledge-engine\scripts\check_qdrant_health.py --url http://localhost:6335 --collection cial_phase4
```

The Compose file uses `qdrant/qdrant:v1.18.2`, container `cial-knowledge-os-v1-dev-qdrant`, host port 6335, container port 6333, restart `unless-stopped`, and persistent volume `cial_qdrant_storage`. The application collection is `cial_phase4`; after indexing:

The health script authenticates collection checks without printing the API key.

Never use `docker compose down -v` or clear the collection during repair/upgrade.

## 9. Ollama

```powershell
try{Invoke-RestMethod http://127.0.0.1:11434/api/tags|Out-Null}catch{Start-Process ollama.exe -ArgumentList serve -WindowStyle Hidden}
ollama.exe pull gemma3:12b
ollama.exe list
ollama.exe show gemma3:12b
```

The first column of `ollama list` must contain exact name `gemma3:12b`.

## 10. Hugging Face Models

```powershell
$env:TRANSFORMERS_OFFLINE='0'; $env:HF_HUB_OFFLINE='0'
@'
from huggingface_hub import snapshot_download
from sentence_transformers import SentenceTransformer, CrossEncoder
e=snapshot_download(repo_id="BAAI/bge-m3")
r=snapshot_download(repo_id="cross-encoder/ms-marco-MiniLM-L-6-v2")
em=SentenceTransformer(e,device="cuda",local_files_only=True)
print(e,em.encode(["CIAL verification"],convert_to_tensor=True).device)
rr=CrossEncoder(r,device="cuda",local_files_only=True)
print(r,rr.predict([("query","document")])[0])
'@ | .\.venv\Scripts\python.exe -
```

Default cache: `%USERPROFILE%\.cache\huggingface`, unless `HF_HOME` is set. After both CUDA loads pass, set offline runtime flags and verify:

```powershell
$env:TRANSFORMERS_OFFLINE='1'; $env:HF_HUB_OFFLINE='1'
.\.venv\Scripts\python.exe -c "from sentence_transformers import SentenceTransformer,CrossEncoder; SentenceTransformer('BAAI/bge-m3',device='cuda',local_files_only=True); CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2',device='cuda',local_files_only=True); print('offline OK')"
```

## 11. OCR and Document Rendering

```powershell
$env:TESSERACT_CMD='C:\Program Files\Tesseract-OCR\tesseract.exe'
.\.venv\Scripts\python.exe -c "import os,pytesseract; pytesseract.pytesseract.tesseract_cmd=os.environ['TESSERACT_CMD']; print(pytesseract.get_tesseract_version())"
$smoke=Join-Path $env:TEMP 'cial-office-smoke'; New-Item -ItemType Directory -Force $smoke|Out-Null
Set-Content (Join-Path $smoke 'test.txt') 'CIAL rendering test'
soffice.exe --headless --convert-to pdf --outdir $smoke (Join-Path $smoke 'test.txt')
Test-Path (Join-Path $smoke 'test.pdf')
```

Expected final result: `True`.

## 12. Environment Configuration

### Backend

```powershell
Copy-Item .\services\knowledge-engine\backend\.env.example .\services\knowledge-engine\backend\.env
```

Set in `services\knowledge-engine\backend\.env`:

```dotenv
CIAL_AUTO_INDEX_ON_STARTUP=false
CIAL_FORCE_REBUILD_ON_STARTUP=false
CIAL_STARTUP_INDEX_TIMEOUT_SECONDS=0
CIAL_APP_DATA_DIR=data
CIAL_OUTPUTS_DIR=outputs
CIAL_MODELS_DIR=models
DATABASE_URL=postgresql+psycopg://cial_runtime:<URL-ENCODED-RUNTIME-PASSWORD>@localhost:5432/cial_knowledge_os_dev
CIAL_AUTH_SECRET_KEY=<LONG-RANDOM-SECRET>
CIAL_CORPUS_SYNC_ON_STARTUP=false
CIAL_CORPUS_WATCH=true
CIAL_CORPUS_HASH=sha256
CIAL_CORPUS_WATCH_DEBOUNCE_MS=750
CIAL_CORPUS_FILE_STABILITY_INTERVAL_MS=500
CIAL_CORPUS_FILE_STABILITY_CHECKS=3
CIAL_CORPUS_RECONCILE_INTERVAL_SECONDS=300
CIAL_METADATA_BATCH_SIZE=500
CIAL_INDEXER_ENABLED=true
CIAL_INDEXER_POLL_SECONDS=1
CIAL_INDEXER_LEASE_SECONDS=120
CIAL_INDEXER_HEARTBEAT_SECONDS=15
CIAL_INDEXER_HEARTBEAT_STALE_SECONDS=45
CIAL_INDEXER_MAX_ATTEMPTS=5
CIAL_INDEXER_RETRY_BACKOFF_SECONDS=5
CIAL_INDEXER_EXTRACTION_WORKERS=4
CIAL_INDEXER_PREPARED_QUEUE_SIZE=8
CIAL_INDEXER_EMBED_QUEUE_SIZE=4096
CIAL_INDEXER_WRITE_QUEUE_SIZE=16
CIAL_INDEXER_EMBED_BATCH_SIZE=64
CIAL_INDEXER_EMBED_MAX_BATCH_TOKENS=32768
CIAL_INDEXER_EMBED_MAX_WAIT_MS=75
CIAL_INDEXER_QDRANT_BATCH_SIZE=128
CIAL_INDEXER_DEVICE=auto
CIAL_INDEXER_PRECISION=auto
CIAL_INDEXER_GPU_POLICY=balanced
CIAL_BM25_REFRESH_DEBOUNCE_SECONDS=2
CIAL_QDRANT_MODE=server
CIAL_QDRANT_URL=http://localhost:6335
CIAL_QDRANT_API_KEY=<LONG-RANDOM-QDRANT-KEY>
CIAL_QDRANT_BATCH_SIZE=32
CIAL_QDRANT_UPSERT_WAIT=true
CIAL_OLLAMA_MODEL_NAME=gemma3:12b
CIAL_EMBEDDING_MODEL_NAME=BAAI/bge-m3
CIAL_RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2
CIAL_RERANKER_DEVICE=auto
CIAL_RERANKER_BATCH_SIZE=16
CIAL_LOCAL_FILES_ONLY=true
CIAL_MAX_ANSWER_WORDS=1200
CIAL_GENERATION_RETRIES=2
CIAL_RETRY_COOLDOWN_SECONDS=20
CIAL_CHAT_DEBUG=false
TRANSFORMERS_OFFLINE=1
HF_HUB_OFFLINE=1
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Do not add `CIAL_CORPUS_ROOT` when using saved application configuration. Restrict `.env` ACLs because it contains secrets.

```powershell
$account=[Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls.exe .\services\knowledge-engine\backend\.env /inheritance:r
icacls.exe .\services\knowledge-engine\backend\.env /grant:r "${account}:(F)" 'BUILTIN\Administrators:(F)' 'NT AUTHORITY\SYSTEM:(F)'
```

Optional auth settings and their implemented defaults are `CIAL_AUTH_COOKIE_NAME=cial_auth_session`, `CIAL_AUTH_SESSION_TTL_HOURS=168`, `CIAL_AUTH_COOKIE_SECURE=false` in development, `CIAL_AUTH_ALLOW_USER_HEADERS=true` outside production, `CIAL_AUTH_DEFAULT_ORGANIZATION_CODE=CIAL`, `CIAL_AUTH_DEFAULT_ROLE_NAME=Viewer`, and `CIAL_AUTH_DEFAULT_DEPARTMENT_CODE=shared-knowledge`. For a local HTTP deployment keep secure cookies false; for a production HTTPS reverse proxy set `CIAL_ENV=production`, use secure cookies, and review allowed origins before exposure.

### Frontend

```powershell
Copy-Item .\frontend\.env.example .\frontend\.env
```

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_ENABLE_AUTH=true
VITE_ENABLE_REAL_AI=true
```

Rebuild after changing `VITE_` values.

### Backend environment precedence

Files load without overriding an existing process variable. Later file values win:

1. root `.env`
2. `services\knowledge-engine\.env`
3. `services\knowledge-engine\backend\.env`
4. existing process environment overrides all files

An optional protected file selected by `CIAL_RUNTIME_ENV_FILE` has higher file
priority than `backend/.env` but remains below explicit process values. See
[`RUNTIME_CONFIGURATION.md`](RUNTIME_CONFIGURATION.md) for the complete flow.

Do not place `CIAL_MIGRATION_DATABASE_URL` in any of these normal runtime
files. Store it in protected `outputs\installer\runtime\migration.env` as a
literal `KEY=VALUE` assignment. Alembic requires that scoped credential and
does not fall back to `DATABASE_URL`.

### Corpus precedence

1. `CIAL_CORPUS_ROOT` / `CORPUS_ROOT`
2. saved application config (`data\config\application.json`, or `CIAL_APPLICATION_CONFIG` / `CIAL_APP_CONFIG_FILE` / `CIAL_CONFIG_FILE`)
3. deprecated `CIAL_DATA_DIR`
4. `data\files`

## 13. Enterprise Repository

Choose/create the directory explicitly. Local, mapped, and accessible UNC paths are supported.

```powershell
.\scripts\configure_corpus_repository.ps1 -RepositoryPath 'D:\CIAL\KnowledgeRepository'
# UNC example:
# .\scripts\configure_corpus_repository.ps1 -RepositoryPath '\\server\share\CIAL-Knowledge'
```

The helper validates read/write access and writes `data\config\application.json`; documents are not copied. It preserves other configured repositories. Expected enterprise entry:

```json
{"id":"enterprise","repository_id":"repo-<16-hex>","name":"Enterprise Knowledge Repository","type":"filesystem","path":"D:\\CIAL\\KnowledgeRepository","enabled":true,"role":"primary"}
```

The stable ID is `repo-` plus the first 16 hex characters of SHA-256 over the resolved, case-folded path.

```powershell
$c=Get-Content .\data\config\application.json -Raw|ConvertFrom-Json
$r=$c.repositories|Where-Object id -eq enterprise
$r; Test-Path -LiteralPath $r.path -PathType Container
```

## 14. Database Migrations

```powershell
Set-Location .\services\knowledge-engine
..\..\.venv\Scripts\python.exe -m alembic heads
..\..\.venv\Scripts\python.exe -m alembic current
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m alembic current
Set-Location ..\..
```

Final current revision must equal dynamic head and show `(head)`. Never automatically downgrade or edit historical migrations.

## 15. First Startup

Backend, matching the production-style launcher:

```powershell
$env:PYTHONPATH="$PWD\services\knowledge-engine;$PWD\services\knowledge-engine\src"
Set-Location .\services\knowledge-engine
..\..\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Development helper: `scripts\start_backend.ps1 -Port 8000` (uses reload mode).

In another terminal, production frontend:

```powershell
$env:PORT='5173'; $env:VITE_API_BASE_URL='http://127.0.0.1:8000'
Set-Location .\frontend
.\node_modules\.bin\vite.cmd preview --host 127.0.0.1
```

Open <http://127.0.0.1:5173/login>. `scripts\start_frontend.ps1` runs the development server and is not the production-preview path.

Verify backend:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health | Format-List
```

Required: `service=cial-knowledge-os`, `application_version=0.1.0`,
`phase=4.5`, `api_ready=true`, and `retrieval_ready=true`, with the configured
`repository_id`. The indexer may still be draining work; inspect
`indexer_seen`, `indexer_state`, `queue_depth`, and `index_fresh` separately.

For retained manual evidence, create `outputs\manual\logs` and redirect the
backend/indexer/frontend terminal output there, or use `Tee-Object`. Backend
startup logs should show only query-runtime readiness and Uvicorn startup.
Indexer logs show watcher/reconciliation, queue claims, extraction, embedding,
Qdrant writes, and BM25 publication. Frontend output should identify Vite
preview and port 5173. Treat database errors, indexer heartbeat loss, failed
indexing, or port fallback as deployment failures.

The hardened daily launcher requires installer fingerprint state. For a purely manual deployment where that state does not exist, use the explicit commands above.

## 16. Acceptance Tests

### Infrastructure, auth, and session

```powershell
$base='http://127.0.0.1:8000'; $web=New-Object Microsoft.PowerShell.Commands.WebRequestSession
$health=Invoke-RestMethod "$base/api/health"; $health|Format-List
Invoke-RestMethod http://localhost:6335/collections/cial_phase4
ollama.exe show gemma3:12b
$email="manual-$([guid]::NewGuid().ToString('N'))@localhost.invalid"; $password="Cial!$([guid]::NewGuid().ToString('N'))aA1"
$signup=@{full_name='Manual Verification';email=$email;password=$password}|ConvertTo-Json
Invoke-WebRequest "$base/api/auth/signup" -Method Post -ContentType application/json -Body $signup -WebSession $web
Invoke-WebRequest "$base/api/auth/me" -WebSession $web
Invoke-WebRequest "$base/api/auth/logout" -Method Post -ContentType application/json -Body '{}' -WebSession $web
try{Invoke-WebRequest "$base/api/auth/me" -WebSession $web -ErrorAction Stop;throw 'Expected 401'}catch{if([int]$_.Exception.Response.StatusCode -ne 401){throw}}
$login=@{email=$email;password=$password}|ConvertTo-Json
Invoke-WebRequest "$base/api/auth/login" -Method Post -ContentType application/json -Body $login -WebSession $web
```

### Corpus, retrieval, isolation, and citations

```powershell
Invoke-RestMethod "$base/api/corpus/sync" -Method Post
$tree=Invoke-RestMethod "$base/api/corpus/tree"; $tree|ConvertTo-Json -Depth 10
$body=@{question='What is one fact explicitly stated in the active CIAL knowledge repository?';selected_document_ids=@();selected_folder_ids=@();response_length='quick';include_sources=$true}|ConvertTo-Json
$chat=Invoke-RestMethod "$base/api/chat" -Method Post -ContentType application/json -Body $body
$chat.answer; $chat.citations|Format-List
```

Pass criteria: non-empty grounded answer, evidence citations, every citation matches the active `repository_id`, and selected document/folder context restricts retrieval. In the UI verify Knowledge Center, search, Settings, repository visibility, document previews, spreadsheet/slide previews, OCR-derived content, context filtering, and repository isolation.

### PDF navigation

```powershell
$citation=$chat.citations|Where-Object{$_.file_type -eq 'pdf' -and $_.document_id -and $_.page}|Select-Object -First 1
$pdf=Invoke-WebRequest "$base/api/corpus/document/$($citation.document_id)/file" -WebSession $web
$pdf.StatusCode; $pdf.Headers['Content-Type']; $pdf.Headers['Content-Disposition']
```

Expected: 200, `application/pdf`, and `inline`. Open:

```text
http://127.0.0.1:8000/api/corpus/document/<id>/file#page=<page>
```

Confirm the native viewer and “Open Full Workspace” preserve the exact page. If no cited PDF has page metadata, record **not certified**, not passed.

After completing the auth tests, remove the generated temporary user without exposing database credentials:

```powershell
$env:CIAL_MANUAL_TEST_EMAIL=$email
$env:PYTHONPATH="$PWD\services\knowledge-engine;$PWD\services\knowledge-engine\src"
.\.venv\Scripts\python.exe -c "import os; from sqlalchemy import text; from backend.app.db.session import engine; c=engine.connect(); t=c.begin(); c.execute(text('DELETE FROM users WHERE lower(email)=lower(:email)'),{'email':os.environ['CIAL_MANUAL_TEST_EMAIL']}); t.commit(); c.close()"
Remove-Item Env:CIAL_MANUAL_TEST_EMAIL
```

## 17. Troubleshooting

| Problem | Likely cause | Resolution |
|---|---|---|
| `py -3.11` fails | Python missing/wrong launcher | Install Python 3.11; verify `py -0p` |
| Broken `.venv` | Wrong interpreter/pip | Rename it; recreate with `py -3.11 -m venv .venv` |
| `pip check` fails | Incomplete/conflicting dependencies | Reinstall actual requirements and editable package |
| CPU Torch/CUDA false | Wrong wheel or driver | Reinstall pinned `cu132` wheel; update NVIDIA driver |
| Broken Node/NVM | User shim selected | Use official absolute Node/npm/Corepack paths |
| pnpm wrong | Corepack not activated | Prepare exact `pnpm@10.33.4` |
| Frozen install fails | Lock/package mismatch | Correct lockfile on development machine; do not bypass frozen mode |
| Build cannot clear `dist` | Existing CIAL Vite/file lock | Stop only known CIAL preview, retry |
| Docker unavailable | Desktop stopped/WSL/reboot | Start Docker, finish WSL2, restart, verify `docker info` |
| Compose unavailable | Plugin resolution | Use bundled absolute `docker-compose.exe` |
| PostgreSQL auth fails | Existing volume has old password | Restore original `DATABASE_URL`; never reinitialize/delete automatically |
| Port 5432 conflict | Other listener | Identify with `Get-NetTCPConnection`; do not kill blindly |
| Alembic fails | DB/revision problem | Fix DB; inspect `current`/`heads`; never reset/downgrade |
| Qdrant 6335 fails | Container stopped/conflict | Inspect `docker ps`, logs, and port owner |
| `cial_phase4` absent | Indexing not completed | Check corpus documents and backend readiness |
| Ollama API fails | Service stopped/port conflict | Start `ollama serve`; verify `/api/tags` identity |
| Model absent | Wrong/missing tag | Pull exact `gemma3:12b` |
| HF offline failure | Missing/partial cache | Temporarily enable online mode; restage affected model; verify offline |
| HF CUDA failure | Corrupt cache/VRAM/driver | Repair affected snapshot; inspect GPU; no CPU fallback |
| Repository absent | Bad config/env override | Check precedence and saved path; remove unintended override |
| Mapped drive absent | Elevated session cannot see mapping | Use accessible UNC path |
| OCR failure | Wrong Tesseract path | Set absolute `TESSERACT_CMD`; rerun smoke test |
| Office preview failure | `soffice` missing from PATH | Add LibreOffice program directory; headless smoke-test |
| Auth 503 | DB/migrations unavailable | Verify DB and upgrade Alembic head |
| Session lost | Host changed/secret changed | Keep `127.0.0.1` origin and preserve auth secret |
| Frontend wrong API | Stale Vite build | Correct `.env`, rebuild, restart preview |
| Citation 404 | File moved/stale metadata | Sync corpus; verify source remains under active root |
| PDF wrong page | Missing/wrong metadata/fragment | Inspect citation page and `#page=N` URL |
| Preview conversion fails | LibreOffice/output permissions | Verify `soffice` and `outputs\rendered` access |

Diagnostics:

```powershell
Get-NetTCPConnection -State Listen|Where-Object LocalPort -in 5173,8000,5432,6335,11434
docker.exe ps -a
docker.exe logs cial-knowledge-os-v1-dev-postgres
docker.exe logs cial-knowledge-os-v1-dev-qdrant
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

## 18. Upgrade Procedure

1. Complete section 19 backups.
2. Stop only known CIAL backend/frontend processes.
3. Update safely:

   ```powershell
   git status
   git fetch origin
   git pull --ff-only
   ```

4. If backend dependency inputs changed, reinstall requirements/editable package and run `pip check`.
5. Reverify pinned CUDA Torch.
6. If `package.json` or lockfile changed, run frozen pnpm install, typecheck, and build.
7. Do not replace a live Qdrant image without reviewing its supported storage upgrade path.
8. Run Alembic heads/current/upgrade head.
9. Restart and repeat section 16.

Corpus files stay in place; PostgreSQL data stays in `cial_postgres_data`; vectors stay in the Qdrant volume; model caches are not removed.

## 19. Backup Strategy

PostgreSQL:

```powershell
New-Item -ItemType Directory -Force .\outputs\backups|Out-Null
docker.exe exec cial-knowledge-os-v1-dev-postgres pg_dump -U postgres -d cial_knowledge_os_dev -Fc -f /tmp/cial_knowledge_os_dev.dump
docker.exe cp cial-knowledge-os-v1-dev-postgres:/tmp/cial_knowledge_os_dev.dump .\outputs\backups\cial_knowledge_os_dev.dump
Get-Item .\outputs\backups\cial_knowledge_os_dev.dump
```

Qdrant collection snapshot:

```powershell
$snapshot=Invoke-RestMethod -Method Post http://localhost:6335/collections/cial_phase4/snapshots
$snapshotName=$snapshot.result.name
Invoke-WebRequest "http://localhost:6335/collections/cial_phase4/snapshots/$snapshotName" -OutFile ".\outputs\backups\$snapshotName"
```

Record/download the snapshot through Qdrant's snapshot API. Do not blindly copy a live volume.

Back up the enterprise repository through the corporate file backup system. Securely back up:

```text
services\knowledge-engine\backend\.env
frontend\.env
data\config\application.json
outputs\installer\runtime\postgres-password.txt (if present)
```

For offline recovery, preserve Ollama storage, `%USERPROFILE%\.cache\huggingface`, and the deployed Git commit/tag.

## 20. Uninstall

Back up first. Stop known application processes and containers without deleting data:

```powershell
docker.exe stop cial-knowledge-os-v1-dev-postgres
docker.exe stop cial-knowledge-os-v1-dev-qdrant
```

Archive/remove the clone through the IT software-removal process. This preserves Docker volumes, enterprise documents, Ollama models, and HF caches.

Only with explicit authorization and verified backups may IT separately remove the PostgreSQL container/`cial_postgres_data`, Qdrant container/Compose volume, exact Ollama model (`ollama rm gemma3:12b`), the two specific HF repository caches, and application config/secrets. Never delete the enterprise repository, run broad Docker volume prune, or broadly clear model caches. Remove shared prerequisites only after dependency review.

## 21. Verification Checklist

### Workstation

- [ ] Windows 11 x64 build 22000+
- [ ] Administrator access
- [ ] Virtualization/WSL2 ready
- [ ] 80 GB free
- [ ] NVIDIA GPU/driver detected
- [ ] Git verified
- [ ] Python 3.11 x64 verified
- [ ] Official Node LTS `>=20.19`
- [ ] npm/Corepack verified
- [ ] pnpm exactly `10.33.4`
- [ ] Docker/Compose ready
- [ ] VC++ runtime installed
- [ ] Tesseract smoke test passed
- [ ] LibreOffice PATH/conversion passed

### Backend and models

- [ ] Repository `.venv` uses Python 3.11
- [ ] Actual requirements/editable package installed
- [ ] `pip check` passes
- [ ] Torch exactly `2.13.0`, CUDA available
- [ ] Expected GPUs visible
- [ ] `BAAI/bge-m3` loads on CUDA/offline
- [ ] reranker loads on CUDA/offline
- [ ] Ollama API ready
- [ ] exact `gemma3:12b` present

### Data/configuration

- [ ] PostgreSQL 18 and persistent volume ready
- [ ] Authenticated `SELECT 1` succeeds
- [ ] Qdrant 6335/API/volume ready
- [ ] backend/frontend `.env` correct
- [ ] secrets protected
- [ ] repository accessible
- [ ] stable `repository_id` saved
- [ ] no unintended corpus env override
- [ ] Alembic current equals head

### Application

- [ ] Typecheck/build pass
- [ ] Backend identity/readiness pass
- [ ] Login page opens
- [ ] Signup/login/me/logout pass
- [ ] Logged-out protected route returns 401
- [ ] Repository visible in Knowledge Center
- [ ] Corpus sync/search pass
- [ ] Grounded retrieval/context filtering pass
- [ ] Repository isolation/citations pass
- [ ] Document/OCR/Office previews pass
- [ ] Inline PDF endpoint passes
- [ ] Citation opens exact PDF page
- [ ] Settings page works
- [ ] Backup baseline/evidence archived
- [ ] Installation complete
