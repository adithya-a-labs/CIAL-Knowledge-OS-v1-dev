"""Prompt registry schema and validation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class PromptValidationError(ValueError):
    """Raised when prompt registry or render validation fails."""


class DuplicateKeyLoader(yaml.SafeLoader):
    """YAML loader that fails on duplicate mapping keys."""


def _construct_mapping(loader: DuplicateKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise PromptValidationError(f"Duplicate registry key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


DuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    """One logical prompt registry entry."""

    name: str
    path: Path
    logical_path: str
    version: str
    category: str
    description: str
    variables: tuple[str, ...]
    strip_final_newline: bool = False

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.logical_path,
            "version": self.version,
            "category": self.category,
            "description": self.description,
            "variables": list(self.variables),
            "strip_final_newline": self.strip_final_newline,
        }


def load_registry_yaml(path: Path) -> Mapping[str, Any]:
    """Load registry YAML and reject duplicate keys."""

    try:
        loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=DuplicateKeyLoader)
    except PromptValidationError:
        raise
    except yaml.YAMLError as exc:
        raise PromptValidationError(f"Invalid prompt registry YAML: {path}") from exc
    if not isinstance(loaded, Mapping):
        raise PromptValidationError("Prompt registry must be a mapping.")
    return loaded
