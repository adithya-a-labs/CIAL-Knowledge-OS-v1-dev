# Prompt Profile Fix

Date: 2026-07-09

This note documents the prompt-orchestration fixes implemented after
`docs/PHASE_4_5_TO_DEV_PROMPT_REGRESSION_AUDIT.md`.

## Profile Mapping

The chat API now accepts both the new UI profiles and legacy profile names.

| UI label | API profile | Effective detail | Min words | Max words |
| --- | --- | --- | ---: | ---: |
| Quick | `quick` | `concise` | 120 | 250 |
| Standard | `standard` | `detailed` | 250 | 700 |
| Detailed | `detailed` | `detailed` | 350 | 2000 |
| Operational | `operational` | `detailed` | 350 | None |
| Elite | `elite` | `detailed` | 350 | None |

Legacy mappings remain supported:

| Legacy value | Canonical profile |
| --- | --- |
| `short` | `quick` |
| `medium` | `standard` |
| `long` | `detailed` |

`operational` and `elite` preserve the Phase 4.5 elite behavior by keeping
`generation.phase4_system`, adaptive sections, Decision Notes, strict citation
rules, and no default max-word cap.

## Request Max Words

`max_answer_words` is now honored when explicitly supplied. It is validated to
the range `100..5000` and applied after profile defaults. If omitted, the
profile default is used.

## Selected Context

Selected documents and folders now scope retrieval/evidence through a minimal
adapter boundary:

- No selection: normal corpus-wide retrieval.
- Selected documents: restrict candidate chunks to those documents.
- Selected folders: expand folders to descendant active documents and restrict
  candidate chunks to that document union.
- Selected documents plus folders: use the union.

The filter matches indexed chunk metadata through `relative_path`. To avoid a
Qdrant schema or retrieval rewrite, selected-context mode temporarily increases
retrieval candidate breadth and then applies a post-retrieval relative-path
filter before reranking/evidence selection sees candidates.

Limitation: because this is a post-retrieval filter, a selected document that
does not appear in the enlarged candidate pool may still produce insufficient
evidence. A future Qdrant payload filter can improve recall, but that should be
implemented as a deliberate retrieval change with its own tests.

Invalid selected document or folder IDs return `422`.

## Debug Metadata

Every chat response metadata now includes effective prompt/profile fields:

- `profile`
- `effective_min_answer_words`
- `effective_max_answer_words`
- `answer_detail_level`
- `prompt_name`
- `adaptive_sections`
- `citation_mode`
- `temperature`
- `evidence_token_budget`
- `max_context_tokens`
- retrieval/context/evidence counts
- selected-context counts and filter mode

Full prompt/context previews are still not returned by default. They are
included only when the request sets `include_debug=true` and the backend has
`CIAL_CHAT_DEBUG=true`.

## Guard

Use:

```powershell
.\.venv\Scripts\python.exe scripts\prompt_pipeline_guard.py --profile operational
```

Expected key output:

```text
explicit_profile          : operational
max_answer_words          : None
active_generation_prompt  : generation.phase4_system
active_section_prompt     : generation.adaptive_sections
temperature               : 0
```

Continuous indexing is a prompt non-regression change. No mapping, word limit,
selected-context rule, debug field, safe-failure string, prompt registry entry,
or generation temperature in this document was changed.
