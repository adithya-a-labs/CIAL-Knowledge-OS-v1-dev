from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from cial_knowledge_os.runtime_env import load_server_environment, parse_env_file


REPO_ROOT = Path(__file__).resolve().parents[3]


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_literal_parser_handles_spaces_quotes_equals_and_no_execution(tmp_path: Path) -> None:
    env_file = _write(
        tmp_path / "Config With Spaces" / "runtime.env",
        "PLAIN=value\nQUOTED='path with spaces'\nTOKEN=a=b=c\nLITERAL=$(not-executed)\n",
    )

    values = parse_env_file(env_file)

    assert values == {
        "PLAIN": "value",
        "QUOTED": "path with spaces",
        "TOKEN": "a=b=c",
        "LITERAL": "$(not-executed)",
    }


def test_file_precedence_and_explicit_process_override(tmp_path: Path) -> None:
    low = _write(tmp_path / "root.env", "CIAL_QDRANT_API_KEY=low\nSETTING=low\n")
    high = _write(tmp_path / "protected.env", "CIAL_QDRANT_API_KEY=high\nSETTING=high\n")
    environment = {"CIAL_QDRANT_API_KEY": "caller"}

    report = load_server_environment(
        tmp_path,
        environ=environment,
        paths=(low, high),
        required_keys=("CIAL_QDRANT_API_KEY",),
    )

    assert environment["CIAL_QDRANT_API_KEY"] == "caller"
    assert environment["SETTING"] == "high"
    assert report.sources == (low.resolve(), high.resolve())


def test_missing_required_secret_fails_without_exposing_other_values(tmp_path: Path) -> None:
    env_file = _write(tmp_path / "runtime.env", "UNRELATED=synthetic-sensitive-value\n")

    with pytest.raises(RuntimeError) as error:
        load_server_environment(
            tmp_path,
            environ={},
            paths=(env_file,),
            required_keys=("CIAL_QDRANT_API_KEY",),
        )

    message = str(error.value)
    assert "CIAL_QDRANT_API_KEY" in message
    assert "synthetic-sensitive-value" not in message


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="Windows PowerShell unavailable")
def test_powershell_loader_works_from_fresh_process_and_space_path(tmp_path: Path) -> None:
    isolated_root = tmp_path / "Repository With Spaces"
    _write(
        isolated_root / "services" / "knowledge-engine" / "backend" / ".env",
        "CIAL_QDRANT_API_KEY=file-value\nDATABASE_URL=runtime-value\n",
    )
    loader = REPO_ROOT / "scripts" / "runtime_env.ps1"
    escaped_loader = str(loader).replace("'", "''")
    escaped_root = str(isolated_root).replace("'", "''")
    command = (
        f". '{escaped_loader}'; "
        f"Import-CialRuntimeEnvironment -RepoRoot '{escaped_root}' "
        "-RequiredKeys @('CIAL_QDRANT_API_KEY','DATABASE_URL') -Quiet | Out-Null; "
        "if ($env:CIAL_QDRANT_API_KEY -ne 'file-value') { exit 41 }; "
        "if ($env:DATABASE_URL -ne 'runtime-value') { exit 42 }"
    )
    environment = os.environ.copy()
    for name in ("CIAL_QDRANT_API_KEY", "DATABASE_URL", "CIAL_RUNTIME_ENV_FILE"):
        environment.pop(name, None)

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "file-value" not in result.stdout + result.stderr
    assert "runtime-value" not in result.stdout + result.stderr


def test_startup_contracts_share_qdrant_source_and_isolate_migrations() -> None:
    qdrant_start = (REPO_ROOT / "scripts" / "start_qdrant.ps1").read_text(encoding="utf-8")
    launcher = (REPO_ROOT / "Launch-CIAL-Knowledge-OS.ps1").read_text(encoding="utf-8")
    installer = (REPO_ROOT / "Install-CIAL-Knowledge-OS.ps1").read_text(encoding="utf-8")
    backend_start = (REPO_ROOT / "scripts" / "start_backend.ps1").read_text(encoding="utf-8")
    indexer = (REPO_ROOT / "scripts" / "start_indexer.ps1").read_text(encoding="utf-8")
    compose = (
        REPO_ROOT / "services" / "knowledge-engine" / "docker-compose.qdrant.yml"
    ).read_text(encoding="utf-8")
    alembic = (
        REPO_ROOT / "services" / "knowledge-engine" / "alembic" / "env.py"
    ).read_text(encoding="utf-8")

    assert "Import-CialRuntimeEnvironment" in qdrant_start
    assert "CIAL_QDRANT_API_KEY" in qdrant_start
    assert '"api-key" = $env:CIAL_QDRANT_API_KEY' in launcher
    assert "Clear-CialMigrationCredential" in launcher
    assert "Clear-CialMigrationCredential" in installer
    assert "Clear-CialMigrationCredential" in backend_start
    assert "Import-CialRuntimeEnvironment" in indexer
    assert "${CIAL_QDRANT_API_KEY:?" in compose
    assert "settings.database_url" not in alembic
    assert "CIAL_MIGRATION_DATABASE_URL is required" in alembic
