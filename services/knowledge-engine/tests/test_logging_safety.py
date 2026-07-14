from __future__ import annotations

import logging

from cial_knowledge_os.logging_config import sanitize_log_extra


def test_sanitize_log_extra_renames_reserved_filename_without_mutating_input() -> None:
    original = {"filename": "unsupported.download", "event": "document_discovery"}
    sanitized = sanitize_log_extra(original)

    assert original["filename"] == "unsupported.download"
    assert "filename" not in sanitized
    assert sanitized["document_filename"] == "unsupported.download"


def test_sanitized_document_filename_logs_successfully(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        logging.getLogger("cial_knowledge_os.tests").warning(
            "document_type_not_ingested",
            extra=sanitize_log_extra({"document_filename": "unsupported.download"}),
        )

    assert caplog.records[-1].document_filename == "unsupported.download"
