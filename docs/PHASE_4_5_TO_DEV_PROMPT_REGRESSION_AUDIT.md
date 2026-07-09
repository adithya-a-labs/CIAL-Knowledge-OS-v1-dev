# Phase 4.5 To Dev Prompt Regression Audit

Date: 2026-07-09
Workspace: `E:\Adithya A\CIAL-Project\CIAL-Knowledge-OS-v1-dev`
Baseline used: git commit `33e6772 feat(prompts): add Phase 4.5 prompt management system`

## Executive Summary

The active prompt template files did not regress. The Phase 4.5 elite prompt shell, adaptive section instructions, citation rules, safe-failure text, context headers, and deterministic Ollama temperature remain present in current dev.

The strongest quality regression candidates are prompt-pipeline configuration and orchestration drift around the unchanged prompts:

1. The API chat layer always applies response-length profiles that cap `max_answer_words` to 250, 700, or 1200. Source/notebook Phase 4.5 defaults use `max_answer_words=None`, while the batch QA script uses 1200 only as an explicit run profile.
2. The frontend now sends real selected document/folder context, but `KnowledgeEngineService.answer_question()` still calls `pipeline.run(request.question)` and does not apply `selected_document_ids` or `selected_folder_ids` to generation context. This can make dev answers feel less targeted even though the prompt is unchanged.
3. The current frontend/backend payload can include `profile` and `max_answer_words`, but the service currently selects only by `request.response_length`. That makes it easy to believe an elite or operational profile is active when the backend is actually using a generic short/medium/long cap.
4. The API response strips most Phase 4.5 trace fields (`prompt`, `context`, `selected_evidence`, `token_efficiency`, `evidence_confidence`) before returning to the frontend. That does not directly weaken answers, but it hides prompt/context regressions during dev testing.

No evidence was found that Qdrant, PostgreSQL, corpus sync, ingestion, or corpus architecture caused the answer-style regression. Do not change those systems to fix this class of issue.

## Prompt Pipeline Diagram

```text
User question
  -> frontend responseLength/profile/context payload
  -> POST /api/chat
  -> ChatRequest parsing
  -> KnowledgeEngineService._ready_pipeline(response_length)
  -> _apply_response_length(config, response_length)
  -> Phase4RAGPipeline.run(question)
  -> deterministic query variants
  -> dense/BM25 hybrid retrieval
  -> RRF fusion
  -> cross-encoder reranking
  -> EvidenceSelector
  -> ContextBuilder.compress_context()
  -> PromptManager.render("generation.phase4_system")
       + adaptive/structured/narrative fragment
       + content requirements fragment
       + weak-evidence fragment when applicable
       + min/max word instructions
       + SELECTED EVIDENCE block
  -> OllamaLLM(model=config.ollama_model_name, temperature=0)
  -> citation rendering
  -> API response adapter
```

## Phase 4.5 Vs Dev Comparison

| Area | Phase 4.5 baseline | Current dev | Changed | Quality impact |
| --- | --- | --- | --- | --- |
| Prompt registry/templates | `prompts/registry.yaml` and `generation/phase4/*.md` introduced at `33e6772` | Same files and content in current dev | No | No template regression found |
| System/generation prompt | `generation.phase4_system` via `Phase4RAGPipeline._build_phase4_prompt()` | Same | No | Elite shell still exists |
| Adaptive sections | Default `adaptive_answer_sections=True` | Guard confirms true | No | Adaptive formatting still active |
| Citation instructions | Cite every key factual claim and recommendation with exact `[n]` IDs | Same | No | Citation instruction remains strong |
| Context header | `[n]`, document, page, chunk ID, score | Same | No | Provenance packaging remains strong |
| Local generation parameters | `OllamaLLM(..., temperature=0)` | Same | No | Determinism preserved |
| Source Phase4Config max words | `max_answer_words=None` | Source default still `None` | No in core | Core Phase 4.5 remains uncapped by default |
| Backend API max words | API applies `short=(120,250)`, `medium=(250,700)`, `long=(350,1200)` | Same as `33e6772`, active in dev | Yes vs source/notebook baseline | High risk for weaker, less complete answers |
| Batch QA profile | `MAX_ANSWER_WORDS=1200`, adaptive sections true | Same | No | Good for manual QA, but not same as API medium |
| Frontend selected context | Earlier seeded mock context IDs | Current real corpus context defaults to persisted/empty selection | Yes | Medium risk: user-selected context is not honored by backend generation |
| Backend selected context handling | `selected_document_ids` accepted but not used by generation | Still not used; current schema also has folders/profile/max words | Yes vs user expectation | Medium/high risk for apparent wrong or generic answers |
| API trace visibility | Phase runners export prompt/context artifacts | Chat response returns only answer, citations, sources, metadata | Yes vs batch workflow | Medium diagnostic risk |

## All Prompt File Paths

Active prompt package:

- `services/knowledge-engine/src/cial_knowledge_os/prompts/registry.yaml`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/cache.py`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/loader.py`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/manager.py`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/registry.py`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/renderer.py`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/grounded_qa.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/phase4_system.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/adaptive_sections.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/adaptive_content_requirements.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/structured_sections.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/structured_content_requirements.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/narrative_sections.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/narrative_content_requirements.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/decision_notes_family.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/decision_notes_instruction.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/structured_decision_notes_instruction.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/weak_evidence.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/minimum_words.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/maximum_words.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/evaluation/phase1_no_evidence.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/evaluation/insufficient_evidence.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/templates/context_template.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/templates/retrieval_context_block.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/templates/answer_template.md`

Placeholder prompt folders with no active Phase 4.5 LLM prompts:

- `services/knowledge-engine/src/cial_knowledge_os/prompts/extraction/README.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/exports/README.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/multimodal/README.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/archived/README.md`

Prompt documentation:

- `docs/architecture/PROMPT_ARCHITECTURE.md`
- `docs/architecture/PROMPT_CATALOG.md`
- `services/knowledge-engine/docs/backend/notebooks/04_Reranking_and_Evidence_Selection.ipynb`
- `services/knowledge-engine/docs/backend/notebooks/045_Multimodal_Test_Corpus_Evaluation.ipynb`
- root `notebooks/*.ipynb` copies

Manual QA question prompt assets:

- `data/manual_qa/smoke_questions.txt`
- `data/manual_qa/phase4_questions_small.txt`
- `data/manual_qa/phase4_questions.txt`
- `data/manual_qa/phase4_hal.txt`
- `data/manual_qa/CIAL_Enterprise_Long_Horizon_10_Questions.txt`
- `data/manual_qa/CIAL_Enterprise_Long_Horizon_200_Questions.txt`
- `data/manual_qa/CIAL_Enterprise_Stress_Test_500_Questions.txt`
- `data/manual_qa/CIAL_Multimodal_Test_Questions.txt`
- `data/manual_qa/easa_qns.txt`
- `data/manual_qa/airport_operations_questions.txt`
- `data/manual_qa/cybersecurity_questions.txt`

## Prompt Map

| Stage | File path | Function/class | Purpose | Prompt/template | Variables | Output expectation | Phase 4.5 existed | Dev changed | Possible quality impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Prompt registry | `prompts/registry.yaml` | `PromptManager` | Logical prompt lookup | YAML registry | prompt names, variables | Validated prompt objects | Yes | No | None |
| Phase 1-3 grounded QA | `prompts/generation/phase4/grounded_qa.md` | `llm.build_grounded_prompt()` | Concise strict grounded prompt | Exact file text | `no_evidence_response`, `context`, `question` | Concise cited answer or no-evidence string | Yes | No | Lower quality only if Phase 4 prompt is bypassed |
| Phase 4.5 system/generation | `prompts/generation/phase4/phase4_system.md` | `Phase4RAGPipeline._build_phase4_prompt()` | Enterprise decision-support answer | Exact file text | `answer_detail_level`, safe-failure text, fragments, `context`, `question` | Structured grounded synthesis | Yes | No | Highest-value prompt remains active |
| Adaptive sections | `prompts/generation/phase4/adaptive_sections.md` | `_build_phase4_prompt()` adaptive branch | Question-shaped headings | Exact file text | `decision_notes_family` | Relevant Markdown sections only | Yes | No | Still active by default |
| Adaptive synthesis rules | `prompts/generation/phase4/adaptive_content_requirements.md` | `_build_phase4_prompt()` | Enterprise synthesis requirements | Exact file text | none | Dense, grounded, decision-ready answer | Yes | No | Still active |
| Fixed sections | `structured_sections.md` | `_build_phase4_prompt()` non-adaptive branch | Fixed report outline | Exact file text | optional decision note | Repeatable structured answer | Yes | No | Not active by default |
| Narrative sections | `narrative_sections.md` | `_build_phase4_prompt()` narrative branch | Narrative answer style | Exact file text | none | Coherent narrative | Yes | No | Not active by default |
| Weak evidence | `weak_evidence.md` | `_build_phase4_prompt()` | Model-level caveat | Exact file text | none | Prominent low-confidence disclosure | Yes | No | Still active when weak |
| Min words | `minimum_words.md` | `_build_phase4_prompt()` | Conditional depth target | Exact file text | `effective_minimum` | More complete answer when evidence supports | Yes | No | Active, but API cap can limit depth |
| Max words | `maximum_words.md` | `_build_phase4_prompt()` | Upper bound | Exact file text | `max_answer_words` | Concise prioritization | Yes | No | High risk when API cap is too low |
| Safe failure | `evaluation/insufficient_evidence.md` | `context_builder.INSUFFICIENT_EVIDENCE_RESPONSE` | Deterministic refusal | Exact file text | none | No citations on no evidence | Yes | No | Still active |
| Context packaging | `templates/context_template.md` | `context_builder._header()` | Evidence block header | Exact file text | `reference_id`, source, page, chunk, score | Stable evidence IDs | Yes | No | Still strong |
| Reference appendix | `templates/answer_template.md` | `citations.render_answer_with_citations()` | Deterministic references | Exact file text | `cleaned_answer`, `references` | Answer plus References | Yes | No | Still strong |
| Query rewrite | `query_transformations.py` | `QueryTransformer` | Deterministic query variants | No LLM prompt | query string | Query variants | Yes | No prompt regression | Not prompt cause |
| Retrieval planning | `phase3_pipeline.py`, `phase4_pipeline.py` | retrieval/rerank/select methods | Deterministic orchestration | No LLM prompt | config and query | Selected evidence | Yes | No prompt regression | Do not change blindly |
| API answer profile | `backend/app/services/knowledge_engine_service.py` | `_apply_response_length()` | Sets prompt depth/cap | Not a prompt file | `response_length` | Mutated config | Yes in API baseline, different from core baseline | Active | High risk for shorter answers |
| Frontend profile mapping | `frontend/src/api/adapters.ts` | `toApiResponseLength()` | Maps UI mode to API profile | Not a prompt file | responseLength | `short/medium/long` | Frontend changed later | Yes | Medium/high risk in dev testing |

## Exact Key Prompt Text

### Phase 4.5 System Prompt

```text
You are a strict grounded-answering system producing a {self.config.answer_detail_level} decision-support answer.

Answer the QUESTION using only the provided SELECTED EVIDENCE.

Grounding rules:
1. Use only facts directly supported by SELECTED EVIDENCE.
2. Do not use outside knowledge, invent controls, or infer unsupported organization-specific details.
3. Cite every key factual claim and recommendation inline using the exact reference IDs shown in the evidence, such as [1].
4. Do not invent, alter, or renumber reference IDs.
5. If evidence supports only part of the question, answer that part and identify the remaining gap.
6. Reply exactly "{INSUFFICIENT_EVIDENCE_RESPONSE}" only when SELECTED EVIDENCE is empty or contains no usable information.

Answer requirements:
- Produce a {self.config.answer_detail_level} synthesis from the selected evidence.
- Produce a comprehensive, enterprise-grade synthesis that balances depth with clarity.
- Think like an experienced enterprise consultant preparing advice for a technical decision-maker.
- Do not merely summarize retrieved passages; interpret, connect, and synthesize them into a coherent explanation.
- Expand important concepts only when supported by the retrieved evidence.
- Explain relationships between findings instead of presenting isolated facts.
- Prioritize information density over answer length.
- Every recommendation must remain fully grounded in the selected evidence.
{content_requirements}{weak_rule}{minimum_words}{maximum_words}
{structure}
SELECTED EVIDENCE
{context}

QUESTION
{question}

ANSWER
```

### Adaptive Section Fragment

```text
Choose the answer structure that best fits the question. Do not use every section by default. Use only sections that improve clarity.

Allowed section families (select only the relevant ones):
- Direct Answer
- Overview
- Key Concepts
- Key Findings
- Evidence
- Top Risks
- Business Impact
- Recommended Controls
- Recommended Actions
- Step-by-Step Procedure
- Comparison
- Key Differences
- Recommendation
- Priority Matrix
- Implementation Checklist
- Owners and Dependencies
- Operational Implications
- Evidence Gaps
- Caveats
- Next Actions
- Immediate / Next / Later Actions{decision_notes_family}

Question-shape guidance:
- If the question asks "what is", "define", or "explain", prefer Overview + Key Concepts + Evidence.
- If it asks about risks or biggest threats, prefer Top Risks + Business Impact + Recommended Controls.
- If it asks "how should we" or "what should we do", prefer Recommended Actions + Implementation Checklist + Caveats.
- If it asks to compare or distinguish differences, prefer Comparison + Key Differences + Recommendation.
- If it asks for a process, procedure, or steps, prefer Step-by-Step Procedure + Owners and Dependencies + Evidence.
- If it asks to prioritize, prefer Priority Matrix + Immediate / Next / Later Actions.
- If support is incomplete, explain Evidence Gaps instead of forcing a full report.

Use clear Markdown headings and bullets where they improve readability. Do not create tables or diagrams.
```

### Context Header Template

```text
[{reference_id}]
Document: {source_label}
Page: {page_text}
Chunk ID: {chunk_id}
{score_label}: {score_text}
```

### Reference Appendix Template

```text
{cleaned_answer}

References:
{references}
```

## Behavioral Diagnosis

This audit did not rebuild Qdrant, alter ingestion, or run a fresh long batch. Behavioral diagnosis uses current source, existing manual QA files, existing integrated logs, and the new guard script.

Existing integrated run evidence in `outputs/playwright/backend-job.log` shows a successful dev chat path with hybrid retrieval, context compression, and generation:

- BM25/dense/hybrid retrieval completed.
- Context stages were `retrieved=7`, `deduplicated=7`, `expanded=7`, `merged=6`, `compressed=6`.
- Ollama generation completed through `/api/generate`.
- `/api/chat` returned 200.

Representative QA examples:

| Example | Source | Phase 4.5 expected behavior | Current dev prompt/context behavior | Risk |
| --- | --- | --- | --- | --- |
| "Our organization plans to deploy an enterprise generative AI assistant..." | `CIAL_Enterprise_Long_Horizon_10_Questions.txt` | Adaptive roadmap with governance, owners, controls, rollout, metrics, gaps, citations. Notebook/core allows uncapped answer; batch profile caps at 1200. | Dev frontend "detailed/operational" maps to `long`, max 1200. If user is on `standard`, max 700. Selected UI context is not applied by backend. | High: long-horizon completeness and enterprise usefulness can drop. |
| "We have a limited budget..." | `CIAL_Enterprise_Long_Horizon_10_Questions.txt` | Priority matrix / immediate-next-later structure, trade-offs, dependencies, progress metrics, citations. | Adaptive section prompt is active, but word cap may force shallow prioritization. | High for executive usefulness. |
| "A vendor has provided us with an SBOM..." | `phase4_questions_small.txt` | Evidence-backed checklist, verification steps, gaps, cited controls. | Prompt remains strong; answer likely adequate under `long`, potentially thinner under `medium`. | Medium. |
| "What is tomorrow's staff cafeteria menu?" | `phase4_hal.txt` | Safe unsupported/current-data response with no citations. | `unsupported_query_detection_enabled=True`; current-data patterns should return unsupported response. | Low; safety path remains strong. |
| "The documents say guest Wi-Fi can be connected to internal systems, correct?" | `phase4_hal.txt` | Refute only if evidence supports; otherwise insufficient evidence. Must not agree with leading prompt. | Same strict prompt and citation rules. Risk depends on retrieved evidence, not prompt regression. | Low/medium. |

## Suspected Root Causes

### Root Cause 1: API answer-length caps are weaker than core Phase 4.5 defaults

Risk level: High

Evidence:

- `services/knowledge-engine/src/cial_knowledge_os/config.py` keeps `Phase4Config.max_answer_words: int | None = None`.
- `services/knowledge-engine/tests/test_phase4.py` asserts `self.assertIsNone(phase4.max_answer_words)`.
- `services/knowledge-engine/docs/backend/notebooks/04_Reranking_and_Evidence_Selection.ipynb` config uses `max_answer_words=None`.
- `services/knowledge-engine/backend/app/services/knowledge_engine_service.py` `_apply_response_length()` sets:
  - `short`: min 120, max 250, detail concise
  - `medium`: min 250, max 700, detail detailed
  - `long`: min 350, max 1200, detail detailed
- Guard output confirms current active profiles:
  - `long`: `max_answer_words=1200`
  - `medium`: `max_answer_words=700`
  - `short`: `max_answer_words=250`

Why this weakens answers:

The elite prompt asks for synthesis, implications, dependencies, recommendations, and evidence gaps. A 700-word cap is often too tight for long-horizon enterprise questions. Even 1200 can be less complete than the uncapped notebook/core profile.

Recommended fix:

Add an explicit elite/phase45 profile rather than changing retrieval. Options:

- Backend: add `response_length="elite"` or use existing `profile="operational"` to preserve `max_answer_words=None` or a clearly intentional high cap.
- Frontend: map "Operational" to the elite profile, not just `long`.
- Guard/test: assert operational/elite prints `max_answer_words=None` or the intended cap.

Exact files to patch later:

- `services/knowledge-engine/backend/app/schemas/chat.py`
- `services/knowledge-engine/backend/app/services/knowledge_engine_service.py`
- `frontend/src/api/types.ts`
- `frontend/src/api/adapters.ts`
- `frontend/src/components/assistant/AssistantSettingsPopover.tsx`
- `services/knowledge-engine/tests/test_backend_config.py` or a new prompt-profile test

### Root Cause 2: Selected frontend context is not used by backend generation

Risk level: Medium/high

Evidence:

- `frontend/src/api/adapters.ts` sends `selected_document_ids` and `selected_folder_ids`.
- Current `services/knowledge-engine/backend/app/schemas/chat.py` accepts these fields.
- `services/knowledge-engine/backend/app/services/knowledge_engine_service.py` `answer_question()` calls `pipeline.run(request.question)` and does not pass selected IDs/folders into retrieval or context building.

Why this weakens answers:

Users can select a document/folder and expect the model to ground itself in that scope, but the generation path remains corpus-wide. The prompt may still be elite, but the selected evidence may not match the user's intended source set.

Recommended fix:

Do not alter Qdrant or corpus architecture blindly. First decide the intended semantics:

- If selected documents are only UI context chips, label them as such and do not imply retrieval scope.
- If selected documents must scope retrieval, implement an explicit filter path in the backend service and add tests proving selected IDs affect candidate/context packaging.

Exact files to patch later:

- `services/knowledge-engine/backend/app/services/knowledge_engine_service.py`
- `services/knowledge-engine/backend/app/schemas/chat.py`
- retrieval filter boundary only if proven necessary
- frontend helper copy/labels if selected context remains non-binding

### Root Cause 3: Request-level `max_answer_words` is accepted/sent but not applied

Risk level: Medium

Evidence:

- `frontend/src/api/adapters.ts` sends `max_answer_words` for quick mode.
- Current `ChatRequest` accepts `max_answer_words`.
- `KnowledgeEngineService.answer_question()` ignores `request.max_answer_words`.

Why this weakens/debug-confuses answers:

The payload suggests prompt caps are controlled per request, but only `response_length` matters. Future testers can misread captured payloads and assume the elite pipeline is active with a certain cap.

Recommended fix:

If per-request caps are intended, apply them after `_apply_response_length()` with validation and guard output. If not intended, remove the unused request field and frontend payload to avoid false diagnostics.

### Root Cause 4: Chat API hides prompt/context trace diagnostics

Risk level: Medium

Evidence:

- Phase runners export `context/*.md` with `# Prompt`, `# Merged Context`, and answers.
- Chat API response model returns answer, citations, sources, metadata only.
- Current integrated report validates UI behavior, not active prompt text or selected-evidence diagnostics.

Why this weakens debugging:

The dev UI can produce weaker answers while still passing API/browser checks because those checks do not assert prompt name, max words, adaptive sections, citation mode, selected evidence count, or final context.

Recommended fix:

Keep production response compact, but add a guarded debug endpoint or optional debug flag that returns prompt profile metadata. The new script `scripts/prompt_pipeline_guard.py` covers the static part.

## Regression Guard Added

New file:

- `scripts/prompt_pipeline_guard.py`

It prints:

- active generation prompt name
- active system prompt name
- answer mode
- min/max answer words
- adaptive sections status
- citation mode
- retrieval context count
- model name
- temperature/top_p/max tokens
- evidence token budgets
- prompt fragment names and registry versions

Commands:

```powershell
.\.venv\Scripts\python.exe scripts\prompt_pipeline_guard.py --response-length long
.\.venv\Scripts\python.exe scripts\prompt_pipeline_guard.py --response-length medium
.\.venv\Scripts\python.exe scripts\prompt_pipeline_guard.py --response-length short
```

Observed output summary:

| Profile | Answer mode | Min words | Max words | Adaptive | Prompt |
| --- | --- | ---: | ---: | --- | --- |
| short | concise | 120 | 250 | true | `generation.phase4_system` |
| medium | detailed | 250 | 700 | true | `generation.phase4_system` |
| long | detailed | 350 | 1200 | true | `generation.phase4_system` |

## Recommended Fix Plan

1. Restore a true elite API profile.
   - Add backend support for an `elite` or `operational` profile that keeps Phase 4.5 adaptive sections and removes the max-word cap, or uses a deliberately high cap.
   - Map frontend "Operational" to that profile.

2. Make selected context semantics explicit.
   - Either implement backend filtering from selected document/folder IDs or remove/rename UI behavior that implies selected scope.
   - Add tests around selected-context effect before changing retrieval internals.

3. Remove or honor `max_answer_words`.
   - Avoid accepting a field that has no effect.
   - If honored, show the effective value in guard/debug metadata.

4. Add prompt-profile regression tests.
   - Assert default/operational active prompt is `generation.phase4_system`.
   - Assert adaptive section prompt is active.
   - Assert citation mode is inline IDs plus References appendix.
   - Assert elite max-word policy matches the intended Phase 4.5 standard.

5. Add one behavioral golden check using fake retrieval/LLM.
   - Use a long-horizon manual QA question.
   - Assert final prompt contains adaptive sections, enterprise synthesis requirements, citation rule, selected evidence headers, and the intended max-word policy.

## Tests To Run After Patching

Backend:

```powershell
cd services\knowledge-engine
..\..\.venv\Scripts\python.exe -m pytest tests\test_prompt_manager.py tests\test_phase4.py tests\test_backend_config.py
```

Guard:

```powershell
cd ..\..
.\.venv\Scripts\python.exe scripts\prompt_pipeline_guard.py --response-length long
```

Frontend:

```powershell
cd frontend
pnpm.cmd run typecheck
pnpm.cmd run build
```

Integrated smoke:

```powershell
powershell -File scripts\run_integrated_playwright_verification.ps1
```

Manual QA after fixes:

```powershell
cd services\knowledge-engine
..\..\.venv\Scripts\python.exe scripts\run_phase4_batch.py --questions-file ..\..\data\manual_qa\CIAL_Enterprise_Long_Horizon_10_Questions.txt --max-questions 3
```

## Files Touched In This Audit

- Added `docs/PHASE_4_5_TO_DEV_PROMPT_REGRESSION_AUDIT.md`
- Added `scripts/prompt_pipeline_guard.py`

No Qdrant, PostgreSQL, corpus, ingestion, retrieval, reranking, or generation architecture files were changed.
