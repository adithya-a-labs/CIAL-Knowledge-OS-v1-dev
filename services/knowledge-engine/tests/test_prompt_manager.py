from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cial_knowledge_os.prompts import DEFAULT_PROMPT_MANAGER, PromptManager
from cial_knowledge_os.prompts.registry import PromptValidationError


class PromptManagerTests(unittest.TestCase):
    def test_default_registry_loads_and_exposes_metadata(self) -> None:
        registry = DEFAULT_PROMPT_MANAGER.registry()

        self.assertIn("generation.phase4_system", registry)
        self.assertEqual(
            registry["generation.phase4_system"]["version"],
            "phase4",
        )
        self.assertEqual(
            DEFAULT_PROMPT_MANAGER.metadata("generation.grounded_qa")[
                "category"
            ],
            "generation",
        )

    def test_render_rejects_missing_and_unused_variables(self) -> None:
        with self.assertRaisesRegex(PromptValidationError, "missing variables"):
            DEFAULT_PROMPT_MANAGER.render(
                "generation.grounded_qa",
                no_evidence_response="No evidence.",
                context="Context.",
            )

        with self.assertRaisesRegex(PromptValidationError, "unused variables"):
            DEFAULT_PROMPT_MANAGER.render(
                "evaluation.insufficient_evidence",
                extra="not allowed",
            )

    def test_registry_validation_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "prompt.md").write_text("Hello {name}\n", encoding="utf-8")
            (root / "registry.yaml").write_text(
                "\n".join(
                    [
                        "version: 1",
                        "prompts:",
                        "  demo.prompt:",
                        "    file: prompt.md",
                        "    variables: [name]",
                        "  demo.prompt:",
                        "    file: prompt.md",
                        "    variables: [name]",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                PromptValidationError,
                "Duplicate registry key",
            ):
                PromptManager(
                    registry_path=root / "registry.yaml",
                    prompt_root=root,
                )

    def test_registry_validation_rejects_variable_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "prompt.md").write_text("Hello {name}\n", encoding="utf-8")
            (root / "registry.yaml").write_text(
                "\n".join(
                    [
                        "version: 1",
                        "prompts:",
                        "  demo.prompt:",
                        "    file: prompt.md",
                        "    variables: [unused]",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                PromptValidationError,
                "undeclared variables",
            ):
                PromptManager(
                    registry_path=root / "registry.yaml",
                    prompt_root=root,
                )


if __name__ == "__main__":
    unittest.main()
