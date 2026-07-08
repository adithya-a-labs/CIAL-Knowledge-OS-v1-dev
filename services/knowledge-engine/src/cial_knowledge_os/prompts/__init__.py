"""Prompt registry and rendering API for CIAL Knowledge OS."""

from .manager import DEFAULT_PROMPT_MANAGER, PromptManager
from .registry import PromptDefinition, PromptValidationError

__all__ = [
    "DEFAULT_PROMPT_MANAGER",
    "PromptDefinition",
    "PromptManager",
    "PromptValidationError",
]
