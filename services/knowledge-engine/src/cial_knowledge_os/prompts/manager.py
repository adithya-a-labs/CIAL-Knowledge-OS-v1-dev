"""PromptManager public API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cache import PromptCache
from .loader import load_definitions, load_prompt_text
from .registry import PromptDefinition, PromptValidationError
from .renderer import render_prompt, validate_template_variables


@dataclass(frozen=True, slots=True)
class Prompt:
    """Loaded prompt content and metadata."""

    definition: PromptDefinition
    text: str

    @property
    def metadata(self) -> dict[str, Any]:
        return self.definition.metadata()


class PromptManager:
    """Load, cache, validate, and render registered prompts by logical name."""

    def __init__(
        self,
        *,
        registry_path: Path | None = None,
        prompt_root: Path | None = None,
        validate_on_load: bool = True,
    ) -> None:
        root = prompt_root or Path(__file__).resolve().parent
        registry = registry_path or root / "registry.yaml"
        self.prompt_root = root.resolve()
        self.registry_path = registry.resolve()
        self.cache = PromptCache()
        self._definitions = load_definitions(
            self.registry_path,
            prompt_root=self.prompt_root,
        )
        if validate_on_load:
            self.validate()

    def validate(self) -> None:
        """Fail fast when registry files and declared variables diverge."""

        errors: list[str] = []
        for definition in self._definitions.values():
            try:
                text = load_prompt_text(definition, self.cache)
                validate_template_variables(definition, text)
            except PromptValidationError as exc:
                errors.append(str(exc))
        if errors:
            raise PromptValidationError("Prompt validation failed: " + " | ".join(errors))

    def get(self, name: str) -> Prompt:
        """Return loaded prompt text and metadata for a logical prompt name."""

        definition = self._definitions.get(name)
        if definition is None:
            raise PromptValidationError(f"Missing prompt: {name}")
        return Prompt(
            definition=definition,
            text=load_prompt_text(definition, self.cache),
        )

    def render(manager, name: str, **variables: Any) -> str:
        """Render a registered prompt with strict variable validation."""

        prompt = manager.get(name)
        return render_prompt(prompt.definition, prompt.text, variables)

    def metadata(self, name: str) -> dict[str, Any]:
        """Return prompt metadata without rendering."""

        return self.get(name).metadata

    def registry(self) -> dict[str, dict[str, Any]]:
        """Return metadata for every registered prompt."""

        return {
            name: definition.metadata()
            for name, definition in sorted(self._definitions.items())
        }


DEFAULT_PROMPT_MANAGER = PromptManager()
