"""Prompt template variable parsing and rendering."""

from __future__ import annotations

from collections.abc import Mapping
from string import Formatter
from typing import Any

from .registry import PromptDefinition, PromptValidationError


def variables_in_template(template: str) -> set[str]:
    """Return Python format fields used by a prompt template."""

    variables: set[str] = set()
    formatter = Formatter()
    for _, field_name, _, _ in formatter.parse(template):
        if field_name:
            variables.add(field_name)
    return variables


def _root_variable(field_name: str) -> str:
    return field_name.replace("[", ".").split(".", 1)[0]


def validate_template_variables(
    definition: PromptDefinition,
    template: str,
) -> None:
    """Ensure registry-declared variables exactly match template placeholders."""

    found = variables_in_template(template)
    declared = set(definition.variables)
    missing_declarations = found - declared
    unused_declarations = declared - found
    errors: list[str] = []
    if missing_declarations:
        errors.append(
            "undeclared variables "
            f"{sorted(missing_declarations)} in {definition.name}"
        )
    if unused_declarations:
        errors.append(
            "unused declared variables "
            f"{sorted(unused_declarations)} in {definition.name}"
        )
    if errors:
        raise PromptValidationError("; ".join(errors))


def render_prompt(
    definition: PromptDefinition,
    template: str,
    variables: Mapping[str, Any],
) -> str:
    """Render a prompt with strict missing/extra variable checks."""

    required = set(definition.variables)
    supplied = set(variables)
    required_roots = {_root_variable(name) for name in required}
    missing = {
        name
        for name in required
        if name not in supplied and _root_variable(name) not in supplied
    }
    unused = {
        name
        for name in supplied
        if name not in required and name not in required_roots
    }
    errors: list[str] = []
    if missing:
        errors.append(f"missing variables {sorted(missing)}")
    if unused:
        errors.append(f"unused variables {sorted(unused)}")
    if errors:
        raise PromptValidationError(
            f"Invalid variables for prompt '{definition.name}': "
            + "; ".join(errors)
        )
    try:
        return template.format(**dict(variables))
    except KeyError as exc:
        raise PromptValidationError(
            f"Missing variable {exc!s} for prompt '{definition.name}'."
        ) from exc
