"""Safe server-side environment file resolution shared by Python entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import MutableMapping, Sequence


_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class EnvironmentLoadReport:
    sources: tuple[Path, ...]
    loaded_keys: tuple[str, ...]


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse literal KEY=VALUE assignments without expansion or execution."""

    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        if "=" not in line:
            raise ValueError(
                f"Invalid environment assignment in {path} at line {line_number}; "
                "expected KEY=VALUE."
            )
        key, value = line.split("=", 1)
        key = key.strip()
        if not _KEY_PATTERN.fullmatch(key):
            raise ValueError(
                f"Invalid environment key in {path} at line {line_number}."
            )
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def default_server_env_paths(repo_root: Path) -> tuple[Path, ...]:
    service_root = repo_root / "services" / "knowledge-engine"
    return (
        repo_root / ".env",
        service_root / ".env",
        service_root / "backend" / ".env",
    )


def load_server_environment(
    repo_root: Path,
    *,
    environ: MutableMapping[str, str] | None = None,
    paths: Sequence[Path] | None = None,
    required_keys: Sequence[str] = (),
) -> EnvironmentLoadReport:
    """Load low-to-high-priority server files while preserving caller overrides."""

    target = os.environ if environ is None else environ
    original_keys = set(target)
    candidates = list(paths or default_server_env_paths(repo_root))
    custom_path = target.get("CIAL_RUNTIME_ENV_FILE", "").strip()
    if custom_path:
        custom = Path(custom_path).expanduser()
        if not custom.is_absolute():
            custom = repo_root / custom
        custom = custom.resolve()
        if not custom.is_file():
            raise FileNotFoundError(
                "CIAL_RUNTIME_ENV_FILE does not identify a readable file."
            )
        if custom not in candidates:
            candidates.append(custom)

    merged: dict[str, str] = {}
    sources: list[Path] = []
    for candidate in candidates:
        candidate = Path(candidate).resolve()
        if not candidate.is_file():
            continue
        merged.update(parse_env_file(candidate))
        sources.append(candidate)

    loaded: list[str] = []
    for key, value in merged.items():
        if key not in original_keys:
            target[key] = value
            loaded.append(key)

    missing = [name for name in required_keys if not target.get(name, "").strip()]
    if missing:
        raise RuntimeError(
            "Required server configuration is missing: "
            + ", ".join(missing)
            + ". No values were printed."
        )
    return EnvironmentLoadReport(tuple(sources), tuple(loaded))
