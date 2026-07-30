from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
GENERATED_AT = datetime.now().astimezone().isoformat(timespec="seconds")
SCHEMA_VERSION = "1.0.0"


def write(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def write_json(
    relative_path: str,
    dataset_id: str,
    classification: str,
    items: list[dict],
    *,
    limitations: list[str] | None = None,
) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "dataset_id": dataset_id,
        "classification": classification,
        "items": items,
    }
    if limitations:
        payload["limitations"] = limitations
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


E_LIBRARY = [
    "evidence/screenshots/desktop/library_1440x900.png",
    "evidence/screenshots/desktop/library_1024x768.png",
    "evidence/screenshots/tablet/library_768x1024.png",
    "evidence/screenshots/mobile/library_390x844.png",
]
E_NOTEBOOK = [
    "evidence/screenshots/mobile/empty_notebook_390x844.png",
    "evidence/accessibility_snapshots/a11y_notebook_sanitized.txt",
    "evidence/dom_snapshots/notebook_structure_sanitized.md",
]
E_STUDIO = [
    "evidence/accessibility_snapshots/a11y_studio_sanitized.txt",
    "evidence/dom_snapshots/studio_structure_sanitized.md",
]


routes = [
    {
        "route_id": "route-library",
        "url_pattern": "/",
        "surface_ids": ["surface-library"],
        "sensitive_parameters_removed": True,
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY,
    },
    {
        "route_id": "route-notebook",
        "url_pattern": "/notebook/{redacted_notebook_id}",
        "surface_ids": [
            "surface-notebook-shell",
            "surface-sources",
            "surface-chat",
            "surface-studio",
        ],
        "sensitive_parameters_removed": True,
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK + E_STUDIO,
    },
]

surfaces = [
    ("surface-library", "Notebook library", "route-library", "OBSERVED"),
    ("surface-empty-notebook", "Empty notebook", "route-notebook", "OBSERVED"),
    ("surface-notebook-shell", "Notebook shell", "route-notebook", "OBSERVED"),
    ("surface-sources", "Sources panel/tab", "route-notebook", "OBSERVED"),
    ("surface-source-import", "Source import dialog", "route-notebook", "OBSERVED"),
    ("surface-source-preview", "Source preview", "route-notebook", "OBSERVED"),
    ("surface-chat", "Grounded chat", "route-notebook", "OBSERVED"),
    ("surface-citation-detail", "Citation detail overlay", "route-notebook", "OBSERVED"),
    ("surface-notes", "Notes editor and cards", "route-notebook", "OBSERVED"),
    ("surface-studio", "Studio generator grid", "route-notebook", "OBSERVED"),
    ("surface-artifact-card", "Studio artifact card", "route-notebook", "OBSERVED"),
    ("surface-artifact-viewer", "Studio artifact viewer", "route-notebook", "OBSERVED"),
    ("surface-share", "Notebook sharing dialog", "route-notebook", "OBSERVED"),
    ("surface-settings", "Global settings menu", "route-notebook", "OBSERVED"),
    ("surface-runtime", "Browser runtime observations", "route-notebook", "OBSERVED"),
]
surfaces_json = [
    {
        "surface_id": sid,
        "name": name,
        "route_id": route_id,
        "classification": classification,
        "evidence_paths": E_LIBRARY if sid == "surface-library" else E_NOTEBOOK + E_STUDIO,
    }
    for sid, name, route_id, classification in surfaces
]

control_names = [
    ("control-library-filter", "Library filter radios", "surface-library"),
    ("control-library-view", "Grid/list view radios", "surface-library"),
    ("control-library-search", "Open search", "surface-library"),
    ("control-library-sort", "Most recent sort", "surface-library"),
    ("control-create-notebook", "Create notebook", "surface-library"),
    ("control-source-add", "Add source", "surface-sources"),
    ("control-source-select-all", "Select all sources", "surface-sources"),
    ("control-source-checkbox", "Per-source checkbox", "surface-sources"),
    ("control-source-row", "Source row preview trigger", "surface-sources"),
    ("control-source-more", "Source overflow", "surface-sources"),
    ("control-source-back", "Source preview Back", "surface-source-preview"),
    ("control-source-open", "Open source in new tab", "surface-source-preview"),
    ("control-chat-input", "Query box", "surface-chat"),
    ("control-chat-submit", "Submit", "surface-chat"),
    ("control-chat-stop", "Stop response", "surface-chat"),
    ("control-citation", "Inline citation", "surface-chat"),
    ("control-citation-view-source", "View citation source", "surface-citation-detail"),
    ("control-note-add", "Add note", "surface-notes"),
    ("control-note-title", "Editable note title", "surface-notes"),
    ("control-note-body", "Rich-text note body", "surface-notes"),
    ("control-note-delete", "Delete and confirm", "surface-notes"),
    ("control-share", "Share notebook", "surface-share"),
    ("control-share-copy", "Copy link", "surface-share"),
    ("control-settings", "Settings", "surface-settings"),
    ("control-analytics", "Analytics icon button", "surface-notebook-shell"),
    ("control-studio-output", "Studio output trigger", "surface-studio"),
    ("control-studio-customise", "Studio customise trigger", "surface-studio"),
    ("control-artifact-more", "Artifact overflow", "surface-artifact-card"),
    ("control-artifact-share", "Artifact share", "surface-artifact-viewer"),
    ("control-artifact-close", "Artifact Back/Close/Escape", "surface-artifact-viewer"),
]
controls_json = [
    {
        "control_id": cid,
        "name": name,
        "surface_id": surface_id,
        "states": ["default", "focus", "disabled", "active"]
        if cid in {"control-chat-submit", "control-studio-customise"}
        else ["default", "focus", "active"],
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY if surface_id == "surface-library" else E_NOTEBOOK + E_STUDIO,
    }
    for cid, name, surface_id in control_names
]

component_names = [
    ("component-library-toolbar", "Library toolbar", "surface-library"),
    ("component-notebook-header", "Notebook header", "surface-notebook-shell"),
    ("component-responsive-tabs", "Responsive panel tabs", "surface-notebook-shell"),
    ("component-sources-panel", "Sources panel", "surface-sources"),
    ("component-source-row", "Source row", "surface-sources"),
    ("component-source-preview", "Source preview", "surface-source-preview"),
    ("component-chat-thread", "Chat thread", "surface-chat"),
    ("component-chat-composer", "Chat composer", "surface-chat"),
    ("component-citation-chip", "Citation chip", "surface-chat"),
    ("component-citation-overlay", "Citation detail overlay", "surface-citation-detail"),
    ("component-note-editor", "Rich note editor", "surface-notes"),
    ("component-note-card", "Note card", "surface-notes"),
    ("component-studio-grid", "Studio output grid", "surface-studio"),
    ("component-artifact-card", "Artifact card", "surface-artifact-card"),
    ("component-dialog-viewer", "Dialog artifact viewer", "surface-artifact-viewer"),
    ("component-inline-player", "Inline audio/video player", "surface-artifact-viewer"),
    ("component-iframe-activity", "Iframe quiz/flashcards activity", "surface-artifact-viewer"),
    ("component-share-dialog", "Share dialog", "surface-share"),
    ("component-settings-menu", "Settings menu", "surface-settings"),
]
components_json = [
    {
        "component_id": cid,
        "name": name,
        "surface_id": surface_id,
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY if surface_id == "surface-library" else E_NOTEBOOK + E_STUDIO,
    }
    for cid, name, surface_id in component_names
]

flows = [
    ("flow-library-create", "Library to new empty notebook", ["route-library", "surface-empty-notebook"]),
    ("flow-source-text", "Add copied-text source and process", ["surface-source-import", "surface-sources"]),
    ("flow-source-web", "Add permitted website source and process", ["surface-source-import", "surface-sources"]),
    ("flow-source-pdf", "Upload fixture PDF", ["surface-source-import"]),
    ("flow-source-preview", "Open source preview and return", ["surface-sources", "surface-source-preview"]),
    ("flow-chat-one-source", "Ask with one selected source", ["surface-chat"]),
    ("flow-chat-two-source", "Repeat with both sources", ["surface-chat"]),
    ("flow-citation", "Open citation detail and return", ["surface-chat", "surface-citation-detail"]),
    ("flow-note", "Create, edit, persist, menu, delete note", ["surface-notes"]),
    ("flow-studio", "Generate and inspect every Studio output", ["surface-studio", "surface-artifact-viewer"]),
    ("flow-persistence", "Reload, library return, exact notebook reopen", ["route-library", "route-notebook"]),
]
flow_items = [
    {
        "flow_id": fid,
        "name": name,
        "surface_ids": surface_ids,
        "status": "incomplete_tooling"
        if fid == "flow-source-pdf"
        else "completed",
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK + E_STUDIO,
    }
    for fid, name, surface_ids in flows
]

transitions = [
    ("transition-library-create", "library", "empty_notebook", "Create new notebook"),
    ("transition-source-dialog", "sources_empty", "source_import_dialog", "Add source"),
    ("transition-text-processing", "copied_text_form", "source_processing", "Insert"),
    ("transition-text-ready", "source_processing", "source_ready", "processing completion"),
    ("transition-web-processing", "website_form", "source_processing", "Insert"),
    ("transition-web-ready", "source_processing", "source_ready", "processing completion"),
    ("transition-source-deselect", "both_selected", "one_selected", "source checkbox"),
    ("transition-source-reselect", "one_selected", "both_selected", "source checkbox"),
    ("transition-chat-submit", "composer_ready", "generating", "Enter"),
    ("transition-chat-complete", "generating", "answer_complete", "stream completion"),
    ("transition-citation-open", "answer_complete", "citation_detail", "citation chip"),
    ("transition-citation-close", "citation_detail", "answer_complete", "Escape"),
    ("transition-source-open", "source_list", "source_preview", "source row"),
    ("transition-source-return", "source_preview", "source_list", "Back/panel restore"),
    ("transition-note-generate", "studio", "note_editor", "Add note"),
    ("transition-note-close", "note_editor", "note_card", "Close note"),
    ("transition-note-delete", "note_card", "note_deleted", "Confirm deletion"),
    ("transition-artifact-generate", "studio_ready", "artifact_generating", "output trigger"),
    ("transition-artifact-ready", "artifact_generating", "artifact_card", "completion"),
    ("transition-artifact-open", "artifact_card", "artifact_viewer", "card"),
    ("transition-artifact-close", "artifact_viewer", "artifact_card", "Back/Close/Escape"),
    ("transition-share-open", "notebook", "share_dialog", "Share notebook"),
    ("transition-settings-open", "notebook", "settings_menu", "Settings"),
    ("transition-reload", "notebook", "notebook_restored", "reload"),
    ("transition-library-return", "notebook", "library", "browser back"),
]
transition_items = [
    {
        "transition_id": tid,
        "from_state": from_state,
        "to_state": to_state,
        "trigger": trigger,
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK + E_STUDIO,
    }
    for tid, from_state, to_state, trigger in transitions
]

layout_items = [
    {
        "measurement_id": "layout-library-default",
        "surface_id": "surface-library",
        "viewport": {"width": 728, "height": 763, "device_pixel_ratio": 2},
        "scroll_size": {"width": 728, "height": 763},
        "horizontal_overflow": False,
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY,
    },
    {
        "measurement_id": "layout-notebook-1440",
        "surface_id": "surface-notebook-shell",
        "viewport": {"width": 1440, "height": 900},
        "sources_panel_width": 315,
        "studio_panel_width": 315,
        "layout_mode": "three_columns",
        "horizontal_overflow": False,
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK,
    },
    {
        "measurement_id": "layout-notebook-1024",
        "surface_id": "surface-notebook-shell",
        "viewport": {"width": 1024, "height": 768},
        "sources_panel_width": 209,
        "studio_panel_width": 209,
        "layout_mode": "three_columns",
        "horizontal_overflow": False,
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK,
    },
    {
        "measurement_id": "layout-notebook-768",
        "surface_id": "surface-notebook-shell",
        "viewport": {"width": 768, "height": 1024},
        "tab_widths": {"sources": 267, "chat": 245, "studio": 256},
        "layout_mode": "single_panel_tabs",
        "horizontal_overflow": False,
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK,
    },
    {
        "measurement_id": "layout-notebook-390",
        "surface_id": "surface-notebook-shell",
        "viewport": {"width": 390, "height": 844},
        "tab_widths": {"sources": 141, "chat": 119, "studio": 130},
        "layout_mode": "single_panel_tabs",
        "horizontal_overflow": False,
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK,
    },
    {
        "measurement_id": "layout-source-preview-728",
        "surface_id": "surface-source-preview",
        "viewport": {"width": 728, "height": 763},
        "panel_rect": {"x": 0, "y": 153, "width": 728, "height": 610},
        "back_button_rect": {"x": 16, "y": 169, "width": 40, "height": 40},
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK,
    },
    {
        "measurement_id": "layout-citation-detail-728",
        "surface_id": "surface-citation-detail",
        "viewport": {"width": 728, "height": 763},
        "overlay_rect": {"x": 483, "y": 469, "width": 420, "height": 274},
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK,
    },
]

design_tokens = [
    {
        "token_id": "token-font-control",
        "name": "Control font",
        "value": "Google Sans Text",
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY,
    },
    {
        "token_id": "token-font-size-control",
        "name": "Control font size",
        "value": "14px",
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY,
    },
    {
        "token_id": "token-radius-pill",
        "name": "Pill control radius",
        "value": "96px",
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY,
    },
    {
        "token_id": "token-library-dark-background",
        "name": "Observed dark background",
        "value": "rgb(34, 38, 43)",
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY,
    },
    {
        "token_id": "token-library-dark-text",
        "name": "Observed dark foreground",
        "value": "rgb(199, 199, 199)",
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY,
    },
]

responsive_items = [
    {
        "responsive_id": "responsive-1440",
        "viewport": "1440x900",
        "library": "Toolbar, filters, grid/list controls, and Create are visible.",
        "notebook": "Sources, Chat, and Studio remain simultaneous columns.",
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY + E_NOTEBOOK,
    },
    {
        "responsive_id": "responsive-1024",
        "viewport": "1024x768",
        "library": "Desktop controls remain visible.",
        "notebook": "Three-column layout remains; side panels narrow to about 209px.",
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY + E_NOTEBOOK,
    },
    {
        "responsive_id": "responsive-768",
        "viewport": "768x1024",
        "library": "Library retains filters and view controls.",
        "notebook": "Equal-priority Sources/Chat/Studio tabs replace simultaneous panels.",
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY + E_NOTEBOOK,
    },
    {
        "responsive_id": "responsive-390",
        "viewport": "390x844",
        "library": "Grid/list toggles hide; Create, search, sort, and horizontally clipped filters remain.",
        "notebook": "Single active panel with Sources/Chat/Studio tabs; no document-level horizontal overflow.",
        "classification": "OBSERVED",
        "evidence_paths": E_LIBRARY + E_NOTEBOOK,
    },
]

accessibility_items = [
    {
        "finding_id": "a11y-001",
        "severity": "positive",
        "surface_id": "surface-notebook-shell",
        "finding": "Sources, Chat, and Studio expose tab roles at narrow widths.",
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK,
    },
    {
        "finding_id": "a11y-002",
        "severity": "positive",
        "surface_id": "surface-sources",
        "finding": "Source selection exposes named checkboxes and checked state.",
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK,
    },
    {
        "finding_id": "a11y-003",
        "severity": "positive",
        "surface_id": "surface-artifact-viewer",
        "finding": "Mind Map exposes a tree and explicit arrow-key/Enter instructions.",
        "classification": "OBSERVED",
        "evidence_paths": E_STUDIO,
    },
    {
        "finding_id": "a11y-004",
        "severity": "medium",
        "surface_id": "surface-notebook-shell",
        "finding": "The analytics icon enters focus order with the literal accessible name 'trending_up'.",
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK,
    },
    {
        "finding_id": "a11y-005",
        "severity": "medium",
        "surface_id": "surface-source-preview",
        "finding": "Returning from source preview left focus on BODY rather than the source trigger.",
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK,
    },
    {
        "finding_id": "a11y-006",
        "severity": "medium",
        "surface_id": "surface-artifact-viewer",
        "finding": "Mind Map Escape dismissal returned focus to BODY rather than the artifact card.",
        "classification": "OBSERVED",
        "evidence_paths": E_STUDIO,
    },
    {
        "finding_id": "a11y-007",
        "severity": "medium",
        "surface_id": "surface-artifact-viewer",
        "finding": "Escape did not close the iframe-based Quiz viewer; its explicit Close control worked.",
        "classification": "OBSERVED",
        "evidence_paths": E_STUDIO,
    },
    {
        "finding_id": "a11y-008",
        "severity": "positive",
        "surface_id": "surface-chat",
        "finding": "Keyboard Enter and the Submit button share the chat submission path.",
        "classification": "OBSERVED",
        "evidence_paths": E_NOTEBOOK,
    },
]

runtime_items = [
    {
        "runtime_id": "runtime-001",
        "observation": "Copied-text and website sources exposed processing then ready states.",
        "classification": "OBSERVED",
        "evidence_paths": ["evidence/performance/runtime_observations_sanitized.md"],
    },
    {
        "runtime_id": "runtime-002",
        "observation": "One-source answer completed with four citation anchors using source 1 only.",
        "classification": "OBSERVED",
        "evidence_paths": ["evidence/performance/runtime_observations_sanitized.md"],
    },
    {
        "runtime_id": "runtime-003",
        "observation": "The repeated two-source answer completed with six anchors using source ordinals 1 and 2.",
        "classification": "OBSERVED",
        "evidence_paths": ["evidence/performance/runtime_observations_sanitized.md"],
    },
    {
        "runtime_id": "runtime-004",
        "observation": "All nine Studio outputs reached completed artifact-card state; Video remained long-running before later completing.",
        "classification": "OBSERVED",
        "evidence_paths": ["evidence/performance/runtime_observations_sanitized.md"],
    },
    {
        "runtime_id": "runtime-005",
        "observation": "Reload restored both generic chat turns and all ten citation anchors.",
        "classification": "OBSERVED",
        "evidence_paths": ["evidence/performance/runtime_observations_sanitized.md"],
    },
    {
        "runtime_id": "runtime-006",
        "observation": "The console captured 28 warning/error events across five unique sanitized messages.",
        "classification": "OBSERVED",
        "evidence_paths": ["evidence/console/console_observations_sanitized.md"],
    },
]

feature_rows = [
    ("feature-library", "Notebook library", "Library", "Find/create notebooks", "Open root", "Filterable library", "Authenticated session", "Empty library supported", "Skeleton/loading", "Unknown", "Full toolbar", "Full toolbar", "Compact controls", "OBSERVED", "Adopt IA", ";".join(E_LIBRARY)),
    ("feature-create", "Notebook creation", "Library", "Start workspace", "Create new", "Empty notebook", "Authenticated session", "Blank canvas", "Route transition", "Unknown", "Button", "Button", "Button", "OBSERVED", "Adopt", ";".join(E_NOTEBOOK)),
    ("feature-source-import", "Source import", "Sources", "Add evidence", "Add source", "Import dialog", "Source adapters", "Instructional empty state", "Processing row", "Retry only if surfaced", "Panel", "Tab panel", "Tab panel", "OBSERVED", "Adapt to Corpus API", ";".join(E_NOTEBOOK)),
    ("feature-source-select", "Source selection", "Sources", "Control grounding", "Checkbox", "Selected context changes", "Ready sources", "No rows", "Disabled during processing", "Unknown", "Persistent panel", "Tab", "Tab", "OBSERVED", "High", ";".join(E_NOTEBOOK)),
    ("feature-source-preview", "Source preview", "Sources", "Inspect evidence", "Source row", "In-panel preview", "Preview adapter", "N/A", "Content loading", "Open-in-new-tab fallback", "Left panel", "Full tab", "Full tab", "OBSERVED", "Reuse shared viewer", ";".join(E_NOTEBOOK)),
    ("feature-chat", "Grounded chat", "Chat", "Ask questions", "Enter/Submit", "Answer with citations", "Selected sources", "Prompt suggestions", "Generating/Stop", "Retry not observed", "Center column", "Tab", "Tab", "OBSERVED", "High", ";".join(E_NOTEBOOK)),
    ("feature-citations", "Inline citations", "Chat", "Trace claims", "Citation chip", "Citation detail", "Source mapping", "No citations", "N/A", "No previous/next observed", "Inline overlay", "Dialog/overlay", "Dialog/overlay", "OBSERVED", "Critical", ";".join(E_NOTEBOOK)),
    ("feature-notes", "Notes", "Studio", "Persist user synthesis", "Add note", "Rich editor/card", "Notebook persistence", "Add note", "Generating note", "Delete confirmation", "Studio column", "Tab", "Tab", "OBSERVED", "Adopt with PG", ";".join(E_STUDIO)),
    ("feature-audio", "Audio Overview", "Studio", "Audio synthesis", "Audio Overview", "Inline player", "Studio job", "Disabled without sources", "Minutes-long generation", "Not observed", "Card/player", "Card/player", "Card/player", "OBSERVED", "Defer", ";".join(E_STUDIO)),
    ("feature-video", "Video Overview", "Studio", "Video synthesis", "Video Overview", "Custom dialog/player", "Studio job", "Disabled without sources", "Long-running generation", "Not observed", "Card/player", "Card/player", "Card/player", "OBSERVED", "Defer", ";".join(E_STUDIO)),
    ("feature-slide", "Slide deck", "Studio", "Presentation output", "Slide deck", "Dialog viewer", "Studio job", "Disabled without sources", "Generating card", "Not observed", "Dialog", "Dialog", "Dialog", "OBSERVED", "Optional", ";".join(E_STUDIO)),
    ("feature-mindmap", "Mind Map", "Studio", "Explore concepts", "Mind Map", "Interactive tree", "Studio job", "Disabled without sources", "Generating card", "Not observed", "Dialog", "Dialog", "Dialog", "OBSERVED", "Adopt selectively", ";".join(E_STUDIO)),
    ("feature-report", "Reports", "Studio", "Structured synthesis", "Reports/type", "Document viewer", "Studio job", "Disabled without sources", "Generating card", "Not observed", "Dialog", "Dialog", "Dialog", "OBSERVED", "High", ";".join(E_STUDIO)),
    ("feature-flashcards", "Flashcards", "Studio", "Study activity", "Flashcards", "Iframe activity", "Studio job", "Disabled without sources", "Generating card", "Not observed", "Dialog", "Dialog", "Dialog", "OBSERVED", "Low", ";".join(E_STUDIO)),
    ("feature-quiz", "Quiz", "Studio", "Assessment activity", "Quiz", "Iframe activity", "Studio job", "Disabled without sources", "Generating card", "Not observed", "Dialog", "Dialog", "Dialog", "OBSERVED", "Low", ";".join(E_STUDIO)),
    ("feature-infographic", "Infographic", "Studio", "Visual synthesis", "Infographic", "Zoomable image", "Studio job", "Disabled without sources", "Generating card", "Not observed", "Dialog", "Dialog", "Dialog", "OBSERVED", "Optional", ";".join(E_STUDIO)),
    ("feature-table", "Data table", "Studio", "Structured comparison", "Data table", "Table viewer", "Studio job", "Disabled without sources", "Generating card", "Not observed", "Dialog", "Dialog", "Dialog", "OBSERVED", "High", ";".join(E_STUDIO)),
    ("feature-share", "Sharing", "Notebook header", "Collaborate", "Share notebook", "Share dialog", "Account/access model", "N/A", "N/A", "Save disabled until change", "Dialog", "Dialog", "Dialog", "OBSERVED", "Defer until ACL lifecycle", ";".join(E_NOTEBOOK)),
    ("feature-settings", "Settings", "Header", "Global preferences", "Settings", "Menu", "Account configuration", "N/A", "N/A", "Unknown", "Menu", "Menu", "Menu", "OBSERVED", "Do not copy", ";".join(E_NOTEBOOK)),
    ("feature-persistence", "Session restoration", "Notebook", "Resume work", "Reload/reopen", "Turns/citations restored", "Server persistence", "Valid empty state", "Loading before restore", "Unknown", "Yes", "Yes", "Yes", "OBSERVED", "Critical", ";".join(E_NOTEBOOK)),
]


write(
    "README.md",
    f"""
# NotebookLM adaptation research

Generated: {GENERATED_AT}

This folder is a research-only external benchmark for a future CIAL notebook
workspace. It does not contain application implementation, tests, dependency
changes, configuration, migrations, database writes, or production-document
edits.

## Scope and evidence

The audit covers the NotebookLM library, controlled notebook creation, empty
state, copied-text and permitted-web sources, source selection/preview, grounded
chat, citations, notes, every visible Studio output, sharing, settings,
keyboard/accessibility behavior, persistence, and four responsive viewports.
Only the controlled test notebook was opened.

Evidence is organized under `evidence/`. Screenshots are privacy-cropped;
accessibility and DOM snapshots are structural reconstructions containing no
answer text, source contents, private notebook titles, account identifiers, or
session data. `evidence/fixtures/` is separate **RESEARCH_TEST_DATA**, not a
NotebookLM observation.

## Classifications

- **OBSERVED**: directly verified through the authorized browser session.
- **INFERRED**: a reasonable interpretation of observed behavior.
- **RECOMMENDED**: a proposed CIAL product/architecture decision.
- **UNKNOWN**: unavailable or not externally observable.

## Privacy

Artifacts intentionally exclude email addresses, account/profile identifiers,
cookies, tokens, authorization data, session identifiers, signed URLs, private
notebook titles, source contents, query/answer text, and raw request payloads.
Routes use placeholders. Network evidence is category-only; where the browser
surface exposed no network stream, that absence is recorded as a limitation.

## How to use this research

Use stable IDs to join reports, `data/`, `evidence/`, and Mermaid diagrams.
Adopt interaction principles, not Google branding or implementation assumptions.
CIAL recommendations remain subordinate to the current filesystem, PostgreSQL,
Qdrant, Corpus API, document-preview, RBAC/ACL, and personal-workspace contracts.
""",
)

write(
    "ANALYSIS_MANIFEST.md",
    f"""
# Analysis manifest

- Date: 2026-07-30
- Generated at: {GENERATED_AT}
- Tools: Chrome extension browser control with Playwright-style DOM/role APIs;
  browser console reader; repository shell; PyPDF/PyMuPDF visual fixture QA
- Browser: Chrome, existing authenticated session
- Starting URL: `https://notebooklm.google.com/`
- Authorized profile classification: `authorized_test_profile`
- Viewports: 1440x900, 1024x768, 768x1024, 390x844
- Test-source types: one copied-text source, one permitted W3C website source;
  one benign PDF fixture prepared but not uploaded
- Completed flows: library, notebook creation, empty state, copied text, website,
  processing/ready, selection, source preview, one-vs-two-source chat, citations,
  notes, all nine Studio outputs, artifact viewers/actions, share/settings
  inspection, keyboard focus order, reload, back, library return, exact reopen,
  and four responsive checks
- Incomplete flows: PDF upload; observable source/Studio failure and Retry;
  citation Previous/Next (not present); direct network payload/timing capture;
  Playwright trace export

## Tooling limitations (not NotebookLM defects)

1. Installing/enabling the Chrome extension restarted its connection and released
   the controlled tab once. The persisted notebook was reopened by its exact
   controlled title.
2. Chrome file upload required "Allow access to file URLs". The chooser rejected
   or failed to open before this permission was available, so the PDF fixture was
   not transmitted.
3. Poppler `pdftoppm` was unavailable. PyMuPDF rendered the fixture successfully
   and the PNG was visually verified.
4. The connected browser API exposed console logs but no raw network/CDP stream
   and no trace-export API. No request URLs, headers, payloads, or credentials
   were collected.
5. Screenshot capture timed out while background media generation was active.
   Five earlier privacy-cropped screenshots remain; no unredacted temporary
   screenshot remains.

## Final counts

| Item | Count |
|---|---:|
| Routes | {len(routes)} |
| Surfaces | {len(surfaces_json)} |
| Controls | {len(controls_json)} |
| Components | {len(components_json)} |
| Screenshots | 5 |
| Accessibility snapshots | 3 |
| DOM snapshots | 3 |
| Traces | 0 |
| User flows | {len(flow_items)} |
| State transitions | {len(transition_items)} |
| Network categories | 0 (capture unavailable) |
| Console warning/error events | 28 |
| Unique sanitized console messages | 5 |
| Responsive checks | {len(responsive_items)} |
| Unresolved observations | 6 |

## Validation status

The final validation script parses every JSON file, checks the CSV, Mermaid,
screenshot index, evidence index, privacy patterns, output containment, and Git
path scope. Results are appended here after generation.
""",
)

write(
    "EXECUTIVE_SUMMARY.md",
    """
# Executive summary

## Observed interaction principles

1. **Context is explicit.** Source checkboxes make the grounding set visible and
   reversible. Repeating one identical question produced four citation anchors
   from source 1 with one source selected, then six anchors using source
   ordinals 1 and 2 with both selected.
2. **Desktop and narrow layouts preserve the same mental model.** At 1440 and
   1024, Sources, Chat, and Studio coexist as columns. At 768 and 390, the same
   three areas become equal-priority tabs without document-level horizontal
   overflow.
3. **Evidence stays near claims.** Inline citation buttons open a compact detail
   surface and provide a source action. Source preview remains a first-class
   notebook surface.
4. **Long jobs are durable objects.** Studio uses disabled generating cards,
   completion announcements, persistent cards, viewers, menus, source counts,
   ratings, and sharing/download actions. All nine visible output types
   ultimately completed.
5. **Lightweight knowledge capture is embedded.** Notes combine generation,
   rich editing, autosave-on-close, overflow actions, conversion, export, and
   confirmed deletion.
6. **Restoration is observable.** Reload and exact reopening restored both
   controlled chat turns and all ten citation anchors.

## Recommended CIAL direction

Build a CIAL-native three-surface notebook: **Context / Conversation / Outputs**.
Reuse the Corpus API and shared document viewer; persist notebook, notes, chat,
citations, selections, and artifact jobs in PostgreSQL; keep files authoritative
on the filesystem and retrieval in Qdrant; stream query and artifact lifecycle
events from the offline backend.

Adopt explicit source selection, evidence-proximate citations, durable async job
cards, and responsive panel-to-tab reflow. Adapt them to CIAL's persistent global
navigation, calm premium enterprise design, indexing visibility, folder/document
context, ACL badges, evidence-strength indicators, and source page/chunk
navigation. Do not copy Google branding, cloud-only source adapters, account-level
sharing assumptions, or opaque AI orchestration.
""",
)

write(
    "reports/ROUTE_AND_SURFACE_INVENTORY.md",
    """
# Route and surface inventory

| ID | Route | Surface | Classification |
|---|---|---|---|
| route-library | `/` | Library filters, search, sort, view mode, Create | OBSERVED |
| route-notebook | `/notebook/{redacted_notebook_id}` | Header, Sources, Chat, Studio | OBSERVED |

The notebook route contains import dialogs, source preview, citation detail,
note editor/cards, share dialog, settings menu, artifact cards, dialog viewers,
inline media players, and iframe learning activities. Route identifiers and
notebook IDs are never retained.
""",
)

write(
    "reports/INFORMATION_ARCHITECTURE.md",
    """
# Information architecture

NotebookLM uses a shallow two-route architecture:

1. **Library**: discover, filter, sort, change view, or create.
2. **Notebook**: one persistent shell containing:
   - **Sources**: ingest, select, sort, preview, manage;
   - **Chat**: ask, stream, cite, save, rate;
   - **Studio**: generate notes and durable output artifacts.

The key design move is not the visual three-column layout itself; it is the
stable semantic triad. Desktop renders the triad simultaneously, while tablet
and mobile render it as tabs. Overlays remain subordinate to the active surface.
""",
)

write(
    "reports/USER_FLOW_MAP.md",
    """
# User flow map

## Completed controlled flow

Library -> Create -> Empty notebook -> Sources -> Add copied text -> Processing
-> Ready -> Add website -> Processing -> Ready -> Select one source -> Ask ->
Answer complete (4 citations, source 1) -> Select both -> Repeat -> Answer
complete (6 citations, sources 1 and 2) -> Citation detail -> Source preview ->
Return -> Note create/edit/close/menu/delete -> Studio generation -> Artifact
cards/viewers -> Reload -> Library return -> Exact notebook reopen.

The PDF fixture path stopped before transmission because the Chrome extension
required file-URL access. This is a tooling limitation, not a NotebookLM error.
""",
)

write(
    "reports/UI_STATE_MACHINE.md",
    """
# UI state machine

Major state families:

- Library: loading -> ready -> filtered/sorted/view-mode -> creating.
- Sources: empty -> import dialog -> form -> processing -> ready -> selected /
  deselected -> preview.
- Chat: empty -> draft -> submitting -> generating/Stop -> completed/citations.
- Citation: closed -> detail overlay -> source action -> closed.
- Notes: none -> generating -> editor -> autosaved card -> menu -> confirmed delete.
- Studio: ready -> customisation (where applicable) -> generating disabled card
  -> completed card -> viewer/menu.
- Persistence: route loading -> restored notebook state.

No product failure/retry state was safely induced. Retry remains UNKNOWN.
""",
)

write(
    "reports/COMPONENT_INVENTORY.md",
    """
# Component inventory

The observed system is composed of a library toolbar/card list, notebook header,
responsive tab set, sources panel, import dialog, source row/checkbox, in-panel
source preview, chat thread/composer, citation chip/detail overlay, rich note
editor/card, Studio grid, generating/artifact cards, modal document/image/tree
viewers, inline audio/video players, iframe quiz/flashcards activities, share
dialog, and settings/overflow menus.

Repeated component contracts are more valuable to CIAL than pixel matching:
named triggers, explicit disabled/progress states, durable card identity, source
count, common Back/Share/More/rating chrome, and source inspection.
""",
)

write(
    "reports/DESIGN_SYSTEM_ANALYSIS.md",
    """
# Design system analysis

## Observed

- Google Sans Text at 14px on controls.
- Pill controls with computed 96px radius.
- Dark library sample: `rgb(34, 38, 43)` background and
  `rgb(199, 199, 199)` foreground.
- Repeated 40px icon/button targets and 48px responsive tabs.
- Material-symbol iconography, compact surfaces, low-shadow treatment.
- Active/selected/disabled states use shape, fill, and availability changes.

## Recommended for CIAL

Retain CIAL tokens, typography, restrained depth, persistent navigation, and
premium enterprise density. Borrow the hierarchy and state clarity, not Google
fonts, Material icons, branding, or exact colors. Give every icon-only control a
human accessible name; the observed analytics control exposed `trending_up`.
""",
)

write(
    "reports/RESPONSIVE_BEHAVIOUR.md",
    """
# Responsive behaviour

| Viewport | Library | Notebook | Overflow |
|---|---|---|---|
| 1440x900 | Full toolbar/filter/view controls | Three columns; side panels ~315px | None |
| 1024x768 | Full desktop controls | Three columns; side panels ~209px | None |
| 768x1024 | Full library controls | Sources/Chat/Studio tabs (267/245/256px) | None |
| 390x844 | Grid/list controls hidden; compact Create/search/sort | Tabs (141/119/130px), one active panel | None |

Primary source, chat/citation, and Studio flows were exercised at each breakpoint.
The narrow interaction model changes from simultaneous comparison to explicit
panel switching while preserving labels and route state.
""",
)

write(
    "reports/NETWORK_AND_RUNTIME_OBSERVATIONS.md",
    """
# Network and runtime observations

## Observed

- Copied-text and website imports exposed processing then ready states.
- Chat exposed a Stop control during generation and completed with citations.
- Studio displayed disabled generating cards and later completion announcements.
- Video explicitly warned that generation may take a while and later completed.
- Reload restored two controlled chat turns and ten citation anchors.
- Console capture contained 28 warning/error events across five sanitized unique
  messages: a closed async extension message channel, default logger warning,
  two experimentation lookup warnings, and a missing config ID/name warning.

## Unavailable

The connected Chrome surface exposed console logs but not a raw network/CDP
request stream, Performance Timeline resource entries, or trace export. Therefore
request hosts, payloads, headers, auth data, streaming frame shapes, CLS, and
network timings are UNKNOWN rather than inferred.
""",
)

write(
    "reports/ACCESSIBILITY_AUDIT.md",
    """
# Accessibility audit

## Positive observations

- Narrow panels expose proper tab roles and selected state.
- Source selection exposes named checkboxes and checked state.
- Chat supports keyboard Enter and a named Submit control.
- Dialog viewers expose Back/Share/Close/More controls.
- Mind Map exposes a tree plus arrow-key and Enter instructions.
- Share dialog exposes form controls and disabled state.

## Findings

| ID | Severity | Finding |
|---|---|---|
| a11y-004 | Medium | Analytics enters focus order as `trending_up`. |
| a11y-005 | Medium | Source-preview return left focus on BODY. |
| a11y-006 | Medium | Mind Map Escape close left focus on BODY. |
| a11y-007 | Medium | Escape did not close iframe Quiz; explicit Close did. |

Observed header focus order began Settings -> Create -> Copy -> analytics icon ->
Share -> selected Studio tab -> Audio -> Customise Audio -> Slide deck.
No automated WCAG conformance claim is made.
""",
)

write(
    "reports/ERROR_AND_EDGE_STATES.md",
    """
# Error and edge states

## Observed

- Empty notebook with three starter prompts.
- Submit disabled with no query.
- Source More/customise controls disabled during processing/generation.
- Share Owner combobox and Save button disabled without a permitted change.
- Async source processing and long-running Studio generation remain visible.
- Delete note requires explicit confirmation.
- Reload briefly showed shell loading before persisted content returned.

## Not observed

- NotebookLM source-processing failure/retry.
- Studio artifact failure/retry.
- Offline product messaging.
- Unsupported-source product error.
- Citation Previous/Next controls.

The PDF upload block came from Chrome extension file permission and is not
classified as a NotebookLM defect.
""",
)

write(
    "reports/NOTEBOOKLM_FEATURE_MATRIX.md",
    """
# NotebookLM feature matrix

The machine-readable matrix is `data/feature_matrix.csv`.

Highest-value observed features for CIAL are explicit selected-source context,
grounded chat with inline citations, durable async artifact cards, responsive
Context/Chat/Studio reflow, rich notes, source inspection, and route/session
restoration. Cloud sharing, Drive import, multimedia generation, global account
settings, and proprietary discovery are not direct adoption targets.
""",
)

write(
    "reports/CIAL_NOTEBOOK_ADAPTATION.md",
    """
# CIAL notebook adaptation

## 1. Adopt Interaction Principle

### Explicit context selection
- NotebookLM observation: source checkboxes visibly change grounding.
- CIAL value: prevents hidden retrieval scope.
- Adaptation: selected document/folder chips backed by Corpus IDs.
- Dependencies: Corpus tree, chat request context, PostgreSQL persistence.
- Risks: stale selection after ACL/index changes.
- Priority: P0.
- Evidence: `flow-chat-one-source`, `flow-chat-two-source`.

### Evidence-proximate citations
- Observation: citation anchors open detail and source actions.
- Value: verifiable enterprise answers.
- Adaptation: shared CIAL viewer deep-linked by document/page/chunk.
- Dependencies: preview resolver, citation DTO, ACL filter.
- Risks: imperfect text highlight; use cited-page/excerpt fallback.
- Priority: P0.

### Durable async outputs
- Observation: generating cards become persistent artifact cards/viewers.
- Value: long local jobs can continue without blocking chat.
- Adaptation: PostgreSQL artifact jobs and SSE/NDJSON progress.
- Dependencies: worker queue, filesystem artifacts, audit events.
- Risks: GPU contention, cancellation, quota and retention policy.
- Priority: P1.

## 2. Adapt To CIAL Visual Language

Use CIAL typography, spacing, calm contrast, enterprise iconography, persistent
global navigation, and explicit system status. Preserve the semantic triad and
responsive reflow; do not reproduce Google styling. Add strong focus restoration
and human accessible names.

## 3. Adapt To Offline Architecture

Filesystem remains authoritative for source files; PostgreSQL owns notebook,
selection, note, chat, citation, artifact-job, ACL, and lifecycle metadata;
Qdrant remains vector search; Corpus API hides storage; the shared document
preview resolves citations; local Ollama/worker processes generate answers and
artifacts. No cloud dependency is required.

## 4. Do Not Copy

Do not copy Google branding, proprietary discovery/ranking assumptions, Drive
coupling, account-level share defaults, opaque generation orchestration,
Material icon labels, or multimedia-first product priority.

## 5. Add CIAL Specific Capability

Add folder and document context, index readiness per source, evidence strength,
page/chunk citation navigation, ACL/visibility badges, personal-workspace owner
isolation, audit history, local model/profile choice, system health, and safe
degraded retrieval states.

## 6. Defer Pending Decision

Defer audio/video, flashcards/quiz, public sharing, external website ingestion,
artifact export formats, and real-time multi-user editing until security,
offline model quality, GPU scheduling, retention, and product demand are decided.
""",
)

write(
    "reports/PROPOSED_CIAL_COMPONENT_ARCHITECTURE.md",
    """
# Proposed CIAL component architecture

## Reuse existing CIAL components

- Persistent global navigation and adaptive appearance control.
- Corpus tree/folder/document picker.
- `SourceViewerPanel`, `DocumentViewerPanel`, and format renderers.
- Assistant composer, streamed lifecycle, citations, Retry/Stop.
- System-status and indexing-state surfaces.
- Shared dialogs, menus, buttons, focus management, and ACL guards.

## New notebook-specific components

```text
NotebookWorkspacePage
|- NotebookHeader
|- NotebookResponsiveLayout
|  |- NotebookContextPanel
|  |  |- NotebookSourceList
|  |  `- NotebookSourceStateRow
|  |- NotebookConversationPanel
|  |  |- NotebookThread
|  |  `- NotebookComposer
|  `- NotebookOutputsPanel
|     |- NotebookNoteCard/Editor
|     |- ArtifactLauncherGrid
|     `- ArtifactJobCard/ArtifactViewer
`- NotebookOverlayHost
   |- CitationDetail
   |- ContextPicker
   `- SharePolicyDialog (deferred)
```

Page state owns notebook identity and responsive active panel. Context state owns
selected Corpus IDs and readiness. Conversation state owns persisted session,
messages, citations, and stream lifecycle. Output state owns notes and artifact
jobs. The shared document viewer owns page/chunk/highlight state.
""",
)

write(
    "reports/PROPOSED_CIAL_API_CONTRACTS.md",
    """
# Proposed CIAL API contracts

Architecture only; no backend changes are made.

## Notebook and context

- `POST /api/notebooks` -> `{id, title, workspace_id, created_at}`
- `GET /api/notebooks/{id}` -> shell, selected context, latest conversation, jobs
- `PATCH /api/notebooks/{id}` -> title/preferences with optimistic version
- `PUT /api/notebooks/{id}/context` -> `{document_ids, folder_ids}`
- `GET /api/notebooks/{id}/sources` -> Corpus metadata plus indexing/readiness

All IDs are server-authorized. Folder expansion and path resolution remain in
Corpus services; the frontend never submits filesystem paths.

## Chat

- `POST /api/notebooks/{id}/chat/stream`
  - request: `{question, session_id, selected_document_ids,
    selected_folder_ids, profile, response_length}`
  - events: `connected`, `validating`, `loading_generation`, `searching`,
    `reranking`, `generating`, `citation`, `completed`, `failed`, `cancelled`
  - terminal payload persists message IDs, citations, safe diagnostics, and
    degraded stage; never raw prompts or unauthorized evidence.

## Citations and preview

Reuse `GET /api/corpus/document/{id}/preview?page=&chunk_id=` and file/view routes.
Citation DTO: `{citation_id, document_id, page, chunk_id, label, excerpt_available}`.
Authorization is re-evaluated on every resolve.

## Notes

- `POST /api/notebooks/{id}/notes`
- `PATCH /api/notebooks/{id}/notes/{note_id}` with version/updated_at
- `DELETE /api/notebooks/{id}/notes/{note_id}` with audit event
- optional `POST .../{note_id}/commit-source` to create a versioned private source

Database save and indexing state are separate.

## Artifact jobs

- `POST /api/notebooks/{id}/artifacts` -> `202 {job_id, artifact_type, status}`
- `GET /api/notebooks/{id}/artifacts`
- `GET /api/notebooks/{id}/artifacts/{artifact_id}`
- `GET /api/notebooks/{id}/artifacts/stream` -> SSE job transitions
- `POST .../{job_id}/cancel` and `/retry`
- `DELETE .../{artifact_id}` with confirmation and audit

Artifacts are written below an authorized workspace output root; PostgreSQL owns
metadata and status. Errors are typed: `not_ready`, `forbidden`, `source_changed`,
`generation_timeout`, `generation_failed`, `cancelled`, `artifact_unavailable`.

## Authorization

Every endpoint requires authenticated access context, notebook/workspace access,
current ACL/RBAC resolution, owner isolation for personal workspaces, and audit
events for share/delete/export. Sharing APIs remain deferred until grant,
revocation, expiry, inheritance, and notification contracts are approved.
""",
)

write(
    "reports/PLAYWRIGHT_REGRESSION_SPEC.md",
    """
# Proposed CIAL Playwright regression specification

Do not execute these scenarios as part of this research.

1. **Create notebook**
   - Precondition: authenticated user with notebook permission.
   - Steps: library -> Create.
   - Assert: empty context/chat/output state, route, accessible headings.
2. **Context selection changes grounding**
   - Attach two authorized Corpus documents.
   - Ask identical question with one then both selected.
   - Assert selected IDs in request, citation document IDs within selection,
     no answer-text snapshot, no unauthorized source.
3. **Citation deep link**
   - Click citation; assert detail role/name, document/page/chunk resolver,
     shared viewer highlight fallback, Escape and focus restoration.
4. **Source processing**
   - Assert queued/extracting/embedding/ready and typed failed/retry states.
5. **Notes**
   - Create/edit/close/reload/reopen/delete; assert PostgreSQL persistence,
     separate indexing state, confirmation and focus restoration.
6. **Artifact lifecycle**
   - Parameterize every enabled artifact type.
   - Assert 202 job, progress events, durable card, viewer, menu, cancel/retry,
     error state, permissions, and retention.
7. **Responsive matrix**
   - 1440x900 and 1024x768: three surfaces present.
   - 768x1024 and 390x844: named tabs, one active panel, no horizontal overflow.
   - Repeat context -> chat -> citation -> output navigation.
8. **Accessibility**
   - Named icon buttons, tab semantics, focus order, trap, Escape, restoration,
     reduced motion, disabled states, 40px minimum targets, axe where appropriate.
9. **Persistence and navigation**
   - Reload, browser back to library, exact reopen; assert context, chat,
     citations, notes, artifact jobs, and active panel restoration.
10. **Authorization failure**
    - Remove access between selection and query; assert context removal, 403,
      no cached evidence leak, no broadened fallback.
""",
)

write(
    "reports/SCREENSHOT_INDEX.md",
    """
# Screenshot index

All screenshots are privacy-cropped and contain no account identifiers or
private existing notebook titles.

| ID | Viewport | State | Path |
|---|---|---|---|
| shot-library-1440 | 1440x900 | Library controls | `evidence/screenshots/desktop/library_1440x900.png` |
| shot-library-1024 | 1024x768 | Library controls | `evidence/screenshots/desktop/library_1024x768.png` |
| shot-library-768 | 768x1024 | Library controls | `evidence/screenshots/tablet/library_768x1024.png` |
| shot-library-390 | 390x844 | Compact library controls | `evidence/screenshots/mobile/library_390x844.png` |
| shot-empty-390 | 390x844 | Empty controlled notebook | `evidence/screenshots/mobile/empty_notebook_390x844.png` |

Additional notebook screenshots were not retained because Chrome capture timed
out during background media generation. Structural DOM/accessibility evidence
was retained instead; no unredacted temporary image remains.
""",
)

write(
    "evidence/accessibility_snapshots/a11y_library_sanitized.txt",
    """
classification: OBSERVED
surface_id: surface-library
route_id: route-library
roles:
- button Settings
- radiogroup: All (checked), My notebooks, Featured notebooks, Collections
- button Open search
- radiogroup: Grid view (checked), List view
- button Most recent
- button Create new notebook
privacy: notebook cards and account controls omitted
""",
)

write(
    "evidence/accessibility_snapshots/a11y_notebook_sanitized.txt",
    """
classification: OBSERVED
surface_id: surface-notebook-shell
roles:
- narrow tablist: Sources, Chat, Studio
- source checkboxes: Select all, source-01, source-02
- source preview: Back, Open in new tab, Open source guide
- chat textbox: Query box
- chat button: Submit
- citation buttons: 10 total across two controlled turns
- citation detail: dialog/complementary named Citation details
- header: Settings, Create notebook, Copy notebook, analytics icon, Share notebook
privacy: account, source text, answer text, notebook ID omitted
""",
)

write(
    "evidence/accessibility_snapshots/a11y_studio_sanitized.txt",
    """
classification: OBSERVED
surface_id: surface-studio
output triggers:
- Audio Overview
- Slide deck
- Video Overview
- Mind Map
- Reports
- Flashcards
- Quiz
- Infographic
- Data table
common viewer controls:
- Back/Close, Share, More options, source count, rating
specialized controls:
- audio/video playback and seeking
- slide Revise and Start slideshow
- mind-map tree, expand, zoom, image download
- infographic zoom
- data table semantic table
- quiz/flashcards iframe activity
privacy: generated titles and contents omitted
""",
)

write(
    "evidence/dom_snapshots/library_structure_sanitized.md",
    """
# Sanitized library structure

Header -> library filter group -> search/view/sort/create controls -> featured
section -> recent section. Notebook cards and all private titles are omitted.
At 390px, grid/list controls are absent and the filter row is visually clipped
within the viewport without document-level overflow.
""",
)

write(
    "evidence/dom_snapshots/notebook_structure_sanitized.md",
    """
# Sanitized notebook structure

NotebookHeader
-> SourcesPanel/Tab
   -> AddSource, SourceSelection, SourceRows, SourcePreview
-> ChatPanel/Tab
   -> Thread, CitationButtons, Composer
-> StudioPanel/Tab
   -> OutputTriggers, JobCards, ArtifactCards, Notes

No route ID, source contents, query text, answer text, or account data is stored.
""",
)

write(
    "evidence/dom_snapshots/studio_structure_sanitized.md",
    """
# Sanitized Studio structure

Nine output triggers share durable generating/card states. Completed artifacts
use common viewer chrome and specialized bodies: inline media, slide/image/tree
dialogs, semantic table/report, and iframe learning activities. Generated
titles and contents are omitted.
""",
)

write(
    "evidence/network/network_categories_sanitized.md",
    """
# Sanitized network categories

Classification: UNKNOWN

The connected Chrome browser surface did not expose network/CDP request events
or Performance Timeline resource entries. No URLs, request headers, auth data,
payloads, response bodies, streaming frames, or signed links were collected.
Network category count is therefore zero, not inferred from product behavior.
""",
)

write(
    "evidence/console/console_observations_sanitized.md",
    """
# Sanitized console observations

Classification: OBSERVED

The browser console reader returned 28 warning/error events and five unique
sanitized messages:

1. async extension message channel closed before a response;
2. default root logger warning;
3. missing experimentation gate lookup;
4. missing experimentation experiment lookup;
5. no config ID or name found.

Messages contained no retained URLs, identifiers, credentials, or content.
Attribution to NotebookLM versus browser extension is not externally certain.
""",
)

write(
    "evidence/performance/runtime_observations_sanitized.md",
    """
# Runtime observations

Classification: OBSERVED unless marked UNKNOWN.

- Source imports: visible processing -> ready.
- Chat: Stop control during generation -> completed citations.
- One-source result: 4 citation anchors, source ordinal 1 only.
- Two-source result: 6 citation anchors, ordinals 1 and 2.
- Studio: disabled generating cards -> completion announcements -> 9 cards.
- Video: explicit long-running state -> later completed card.
- Reload/reopen: 2 controlled turns and 10 citation anchors restored.
- Horizontal overflow: absent at all four requested viewports.
- Navigation/resource/CLS timings: UNKNOWN; performance entries unavailable.
""",
)

write(
    "evidence/traces/TRACE_UNAVAILABLE.md",
    """
# Trace export unavailable

Classification: UNKNOWN

The selected Chrome browser API exposed Playwright-style DOM interaction but no
trace-start/trace-stop/export capability. No trace was created elsewhere.
Major flows are represented by sanitized structural evidence and state IDs.
""",
)

write(
    "evidence/fixtures/README.md",
    """
# Research test fixtures

Classification: UNKNOWN (not a product finding)

Data category: RESEARCH_TEST_DATA

These files are controlled, non-sensitive test data and are not NotebookLM
observations:

- `generate_test_pdf.py`
- `notebooklm_benchmark_source.pdf`
- `notebooklm_benchmark_source_render.png`

The PDF was generated and visually verified. It was not uploaded because the
Chrome extension required file-URL access.
""",
)

write(
    "diagrams/information_architecture.mmd",
    """
flowchart LR
  LIB[route-library] --> NB[route-notebook]
  NB --> SRC[Sources]
  NB --> CHAT[Chat]
  NB --> STUDIO[Studio]
  SRC --> PREVIEW[Source preview]
  CHAT --> CIT[Citation detail]
  STUDIO --> NOTE[Notes]
  STUDIO --> ART[Artifact cards/viewers]
""",
)
write(
    "diagrams/user_flow.mmd",
    """
flowchart LR
  A[Library] --> B[Create]
  B --> C[Empty notebook]
  C --> D[Add sources]
  D --> E[Select context]
  E --> F[Ask]
  F --> G[Answer + citations]
  G --> H[Inspect source]
  G --> I[Create note]
  G --> J[Generate Studio artifacts]
  J --> K[Viewer/actions]
""",
)
write(
    "diagrams/notebook_state_machine.mmd",
    """
stateDiagram-v2
  [*] --> Empty
  Empty --> SourceProcessing: add source
  SourceProcessing --> Ready: success
  Ready --> Generating: submit
  Generating --> Complete: terminal answer
  Complete --> CitationDetail: citation
  CitationDetail --> Complete: Escape
  Ready --> ArtifactGenerating: Studio trigger
  ArtifactGenerating --> ArtifactReady: completion
  ArtifactReady --> ArtifactViewer: open
  ArtifactViewer --> ArtifactReady: close
""",
)
write(
    "diagrams/component_hierarchy.mmd",
    """
flowchart TD
  Shell[Notebook shell]
  Shell --> Header
  Shell --> Layout
  Layout --> SourcesPanel
  Layout --> ChatPanel
  Layout --> StudioPanel
  ChatPanel --> CitationDetail
  SourcesPanel --> SourcePreview
  StudioPanel --> NoteEditor
  StudioPanel --> ArtifactCard
  ArtifactCard --> ArtifactViewer
""",
)
write(
    "diagrams/proposed_cial_architecture.mmd",
    """
flowchart LR
  UI[CIAL Notebook UI] --> API[FastAPI notebook contracts]
  API --> PG[(PostgreSQL metadata/control plane)]
  API --> CORPUS[Corpus API]
  CORPUS --> FS[(Authoritative filesystem)]
  API --> PREVIEW[Shared document preview]
  API --> QUERY[Loaded query pipeline]
  QUERY --> QD[(Qdrant)]
  QUERY --> OLLAMA[Local Ollama]
  API --> JOBS[Durable artifact jobs]
  JOBS --> WORKER[Offline worker]
  WORKER --> FS
  API --> AUTH[RBAC + ACL + owner isolation]
""",
)

write_json("data/routes.json", "dataset-routes", "OBSERVED", routes)
write_json("data/surfaces.json", "dataset-surfaces", "OBSERVED", surfaces_json)
write_json("data/controls.json", "dataset-controls", "OBSERVED", controls_json)
write_json("data/components.json", "dataset-components", "OBSERVED", components_json)
write_json("data/user_flows.json", "dataset-user-flows", "OBSERVED", flow_items)
write_json("data/state_transitions.json", "dataset-transitions", "OBSERVED", transition_items)
write_json("data/layout_measurements.json", "dataset-layout", "OBSERVED", layout_items)
write_json("data/design_tokens.json", "dataset-design-tokens", "OBSERVED", design_tokens)
write_json("data/responsive_observations.json", "dataset-responsive", "OBSERVED", responsive_items)
write_json("data/accessibility_findings.json", "dataset-accessibility", "OBSERVED", accessibility_items)
write_json(
    "data/network_request_categories.json",
    "dataset-network-categories",
    "UNKNOWN",
    [],
    limitations=["Network/CDP request stream unavailable; no raw request data collected."],
)
write_json("data/runtime_observations.json", "dataset-runtime", "OBSERVED", runtime_items)

evidence_items = []
for evidence_id, path, kind, classification in [
    ("evidence-shot-001", "evidence/screenshots/desktop/library_1440x900.png", "screenshot", "OBSERVED"),
    ("evidence-shot-002", "evidence/screenshots/desktop/library_1024x768.png", "screenshot", "OBSERVED"),
    ("evidence-shot-003", "evidence/screenshots/tablet/library_768x1024.png", "screenshot", "OBSERVED"),
    ("evidence-shot-004", "evidence/screenshots/mobile/library_390x844.png", "screenshot", "OBSERVED"),
    ("evidence-shot-005", "evidence/screenshots/mobile/empty_notebook_390x844.png", "screenshot", "OBSERVED"),
    ("evidence-a11y-001", "evidence/accessibility_snapshots/a11y_library_sanitized.txt", "accessibility", "OBSERVED"),
    ("evidence-a11y-002", "evidence/accessibility_snapshots/a11y_notebook_sanitized.txt", "accessibility", "OBSERVED"),
    ("evidence-a11y-003", "evidence/accessibility_snapshots/a11y_studio_sanitized.txt", "accessibility", "OBSERVED"),
    ("evidence-dom-001", "evidence/dom_snapshots/library_structure_sanitized.md", "dom_structure", "OBSERVED"),
    ("evidence-dom-002", "evidence/dom_snapshots/notebook_structure_sanitized.md", "dom_structure", "OBSERVED"),
    ("evidence-dom-003", "evidence/dom_snapshots/studio_structure_sanitized.md", "dom_structure", "OBSERVED"),
    ("evidence-network-001", "evidence/network/network_categories_sanitized.md", "network_limitation", "UNKNOWN"),
    ("evidence-console-001", "evidence/console/console_observations_sanitized.md", "console", "OBSERVED"),
    ("evidence-performance-001", "evidence/performance/runtime_observations_sanitized.md", "runtime", "OBSERVED"),
    ("evidence-trace-001", "evidence/traces/TRACE_UNAVAILABLE.md", "trace_limitation", "UNKNOWN"),
]:
    evidence_items.append(
        {
            "evidence_id": evidence_id,
            "path": path,
            "kind": kind,
            "classification": classification,
            "privacy_sanitized": True,
            "evidence_paths": [path],
        }
    )
write_json("data/evidence_index.json", "dataset-evidence-index", "OBSERVED", evidence_items)

matrix_path = ROOT / "data/feature_matrix.csv"
matrix_path.parent.mkdir(parents=True, exist_ok=True)
with matrix_path.open("w", encoding="utf-8", newline="") as stream:
    writer = csv.writer(stream)
    writer.writerow(
        [
            "feature_id",
            "feature",
            "surface",
            "purpose",
            "trigger",
            "result",
            "dependencies",
            "empty_state",
            "loading_state",
            "error_state",
            "desktop_behaviour",
            "tablet_behaviour",
            "mobile_behaviour",
            "classification",
            "cial_relevance",
            "evidence_paths",
        ]
    )
    writer.writerows(feature_rows)

print(
    json.dumps(
        {
            "generated_at": GENERATED_AT,
            "routes": len(routes),
            "surfaces": len(surfaces_json),
            "controls": len(controls_json),
            "components": len(components_json),
            "flows": len(flow_items),
            "transitions": len(transition_items),
            "features": len(feature_rows),
        }
    )
)
