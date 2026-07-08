"""Prompt registry and file loading."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .cache import PromptCache
from .registry import PromptDefinition, PromptValidationError, load_registry_yaml


def _as_prompt_entries(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    prompts = raw.get("prompts")
    if not isinstance(prompts, Mapping):
        raise PromptValidationError("Prompt registry must contain a 'prompts' mapping.")
    return prompts


def load_definitions(registry_path: Path, *, prompt_root: Path) -> dict[str, PromptDefinition]:
    """Load and validate logical prompt definitions."""

    registry = load_registry_yaml(registry_path)
    entries = _as_prompt_entries(registry)
    definitions: dict[str, PromptDefinition] = {}
    root = prompt_root.resolve()
    for name, raw_entry in entries.items():
        if not isinstance(name, str) or not name.strip():
            raise PromptValidationError("Prompt registry names must be non-empty strings.")
        if name in definitions:
            raise PromptValidationError(f"Duplicate prompt name: {name}")
        if not isinstance(raw_entry, Mapping):
            raise PromptValidationError(f"Prompt '{name}' must be a mapping.")
        logical_path = raw_entry.get("file")
        if not isinstance(logical_path, str) or not logical_path.strip():
            raise PromptValidationError(f"Prompt '{name}' is missing a file path.")
        if Path(logical_path).is_absolute():
            raise PromptValidationError(f"Prompt '{name}' path must be relative.")
        resolved = (root / logical_path).resolve()
        if root not in resolved.parents and resolved != root:
            raise PromptValidationError(f"Prompt '{name}' path escapes prompt root.")
        if not resolved.is_file():
            raise PromptValidationError(f"Prompt '{name}' file does not exist: {logical_path}")
        variables = raw_entry.get("variables", [])
        if variables is None:
            variables = []
        if not isinstance(variables, list) or not all(isinstance(item, str) for item in variables):
            raise PromptValidationError(f"Prompt '{name}' variables must be a list of strings.")
        definitions[name] = PromptDefinition(
            name=name,
            path=resolved,
            logical_path=logical_path,
            version=str(raw_entry.get("version") or ""),
            category=str(raw_entry.get("category") or ""),
            description=str(raw_entry.get("description") or ""),
            variables=tuple(variables),
            strip_final_newline=bool(raw_entry.get("strip_final_newline", False)),
        )
    return definitions


def load_prompt_text(definition: PromptDefinition, cache: PromptCache) -> str:
    """Load prompt text and apply registry-specified normalization."""

    text = cache.get(definition.path)
    if definition.strip_final_newline and text.endswith("\n"):
        text = text[:-1]
    return text
