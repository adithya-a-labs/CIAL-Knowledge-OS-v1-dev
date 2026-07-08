# Prompt Catalog

Investigation scope: old CIAL Knowledge OS repository, with emphasis on the Phase 4 / Phase 4.5 knowledge engine. This catalog documents prompt strings, prompt-facing templates, generation constraints, and adjacent QA/evaluation prompt assets found in source, scripts, notebooks, docs, and reference notebooks. No implementation behavior was changed.

Key finding: the active Phase 4.5 answer quality behavior is concentrated in `src/cial_knowledge_os/phase4_pipeline.py`, supported by the older grounded prompt in `src/cial_knowledge_os/llm.py`, the context/citation templates in `context_builder.py`, `retrieval.py`, and `citations.py`, and the run defaults in `config.py` / `scripts/run_phase4_batch.py`.

## Grounded QA

### Phase 1-3 concise grounded prompt

1. File path: `src/cial_knowledge_os/llm.py`
2. Function/class: `build_grounded_prompt(question, context, no_evidence_response=...)`
3. Purpose: baseline local Ollama grounded QA prompt used by Phase 1, Phase 2, and Phase 3. Phase 4 keeps this contract as the grounding baseline but replaces the answer style with its own detailed prompt.
4. Exact prompt text:

```text
You are a strict grounded-answering system.

Answer the QUESTION using only the provided CONTEXT.

Rules:
1. Use only facts directly supported by the CONTEXT.
2. Do not use outside knowledge.
3. Do not guess, infer beyond the evidence, or generalize from related cybersecurity guidance.
4. If the CONTEXT is only loosely related, incomplete, ambiguous, or does not directly answer the QUESTION, reply exactly:
"{no_evidence_response}"
5. If the question asks for organization-specific facts, predictions, passwords, budgets, vendors, live status, or information not explicitly present in CONTEXT, reply exactly:
"{no_evidence_response}"
6. Cite supported claims inline using exact reference IDs such as [1].
7. Do not invent, alter, or renumber reference IDs.
8. Answer concisely.
9. Prefer 5â€“8 bullets unless the question requires a longer explanation.
10. Do not include long background explanations.
11. Do not restate the context.
12. Do not add filler, introductions, or conclusions.

CONTEXT
{context}

QUESTION
{question}

ANSWER
```

5. Variables inserted: `no_evidence_response`, `context`, `question`.
6. Where used: `generate_answer()` in `llm.py`; `BasicRAGPipeline.answer()`; `Phase2RAGPipeline._generate_grounded_answer()`; `Phase3RAGPipeline.answer()` stores it in `response["prompt"]`.
7. Affects: generation, summaries, citations, safe failure.
8. Quality notes: this prompt is strict and compact. The strongest quality constraints are direct evidence only, no outside knowledge, exact safe failure, and exact reference ID discipline.

### Safe failure responses

1. File path: `src/cial_knowledge_os/llm.py`
2. Function/class: module constant `PHASE1_NO_EVIDENCE_RESPONSE`
3. Purpose: exact refusal string for Phase 1.
4. Exact text:

```text
It is not available in the retrieved documents.
```

5. Variables inserted: none.
6. Where used: default `no_evidence_response` in `build_grounded_prompt()` and early return in `generate_answer()` when context is blank.
7. Affects: generation, evaluation, citations.
8. Quality notes: provides deterministic safe failure, but is less explanatory than the Phase 2-4 response.

1. File path: `src/cial_knowledge_os/context_builder.py`
2. Function/class: module constant `INSUFFICIENT_EVIDENCE_RESPONSE`
3. Purpose: exact Phase 2-4 insufficient-evidence answer.
4. Exact text:

```text
The retrieved documents do not contain sufficient evidence to answer this question. Based only on the indexed corpus, no reliable answer could be generated.
```

5. Variables inserted: none.
6. Where used: Phase 2/3 generation safe failure; Phase 4 prompt safe failure; answer-status classification; citation suppression on safe failure.
7. Affects: generation, evaluation, citations.
8. Quality notes: this is better than a generic refusal because it tells the user the limitation is indexed corpus evidence, not global truth.

## System Prompt

### Phase 4 detailed grounded decision-support prompt

1. File path: `src/cial_knowledge_os/phase4_pipeline.py`
2. Function/class: `Phase4RAGPipeline._build_phase4_prompt(question, context, weak_evidence=...)`
3. Purpose: active Phase 4 / Phase 4.5 answer-generation prompt over selected evidence only.
4. Exact prompt text, excluding conditional fragments shown separately below:

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

5. Variables inserted: `answer_detail_level`, `INSUFFICIENT_EVIDENCE_RESPONSE`, `content_requirements`, `weak_rule`, `minimum_words`, `maximum_words`, `structure`, `context`, `question`.
6. Where used: `_generate_grounded_answer()` invokes the LLM with it; `answer()` stores the same prompt in `response["prompt"]`; traces count prompt tokens from it.
7. Affects: generation, summaries, citations, response formatting, evidence-gap behavior.
8. Quality notes: this is the main high-quality Phase 4.5 prompt. It shifts from terse QA to evidence-grounded synthesis, while preserving strict citation and no-hallucination constraints.

### Phase 4 unstructured narrative variant

1. File path: `src/cial_knowledge_os/phase4_pipeline.py`
2. Function/class: `_build_phase4_prompt()`, branch `if not self.config.prefer_structured_answers`
3. Purpose: disables Markdown section planning and asks for a decision-oriented narrative.
4. Exact text:

```text
Use a coherent, decision-oriented narrative.
```

```text
- Produce a comprehensive, decision-oriented synthesis rather than a simple summary of retrieved evidence.
- Explain only implications, actions, risks, gaps, dependencies, procedures, and recommendations that directly answer the question and are supported by the selected evidence.
- Expand important concepts when the retrieved evidence provides sufficient detail.
- Explain why recommendations matter, not only what should be done.
- Where multiple evidence sources support the same conclusion, synthesize them into one coherent explanation rather than listing them independently.
- Discuss operational, security, governance, implementation, or compliance implications only when directly supported by the evidence.
- Highlight dependencies, assumptions, and evidence gaps where appropriate.
- Prioritize information density over answer length.
- Avoid filler, repetition, unsupported background, speculation, and artificial padding.
```

5. Variables inserted: none.
6. Where used: Phase 4 prompt when `prefer_structured_answers=False`.
7. Affects: generation, response formatting.
8. Quality notes: useful when heading-heavy output is undesirable while retaining evidence-driven synthesis.

### Phase 4 adaptive section variant

1. File path: `src/cial_knowledge_os/phase4_pipeline.py`
2. Function/class: `_build_phase4_prompt()`, branch `elif self.config.adaptive_answer_sections`
3. Purpose: default Phase 4.5 adaptive answer structure.
4. Exact text:

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

Conditional addition when `include_decision_notes=True`:

```text
Use Decision Notes only when they materially clarify a decision, follow-up validation, or unresolved evidence gap.
```

Content requirements in this branch:

```text
- Produce a comprehensive, enterprise-grade synthesis rather than a collection of extracted facts.
- Cover only the findings, implications, controls, risks, procedures, comparisons, dependencies, trade-offs, and next actions that directly answer the question.
- Expand important concepts when supported by the retrieved evidence.
- Explain not only what the evidence says, but why it matters for enterprise decision-making.
- When multiple sources contribute to the same conclusion, synthesize them into a single coherent explanation instead of listing them separately.
- For every recommendation, explain:
  - what should be done
  - why it matters
  - expected operational or security benefit
  - prerequisites or dependencies when supported by the evidence
- Discuss implementation complexity, governance considerations, operational impact, compliance implications, and long-term maintenance only when supported by the evidence.
- Prioritize recommendations only when the evidence supports an ordering.
- Clearly distinguish confirmed evidence from evidence gaps.
- Do not force unrelated analysis merely to fill a section.
- Prioritize information density over answer length.
- Avoid filler, repetition, unsupported background, speculation, and artificial padding.
```

5. Variables inserted: `decision_notes_family`.
6. Where used: default Phase 4 configuration: `prefer_structured_answers=True`, `adaptive_answer_sections=True`, `include_decision_notes=True`.
7. Affects: generation, response formatting, section headings, summaries, citations.
8. Quality notes: likely the largest contributor to higher-quality answers. It chooses answer shape from question intent without needing a separate planning agent, and it explicitly avoids forcing irrelevant sections.

### Phase 4 fixed structured variant

1. File path: `src/cial_knowledge_os/phase4_pipeline.py`
2. Function/class: `_build_phase4_prompt()`, branch `else` when structured answers are enabled but adaptive sections are disabled.
3. Purpose: reproducible earlier fixed Phase 4 template.
4. Exact text:

```text
Use clear Markdown headings and, where supported, organize the answer as:
- Executive answer
- Evidence-backed findings
- Operational implications
- Recommended controls or actions
- Risks, gaps, and caveats
```

Conditional addition when `include_decision_notes=True`:

```text
- Include a short Decision notes section that distinguishes immediate actions, follow-up validation, and unresolved evidence gaps.
```

Content requirements in this branch:

```text
- Produce a comprehensive, enterprise-grade synthesis rather than a simple summary of the retrieved evidence.
- Explain operational implications and supported recommended controls or actions.
- Explain why each recommendation matters and the expected operational or security benefit when supported by the evidence.
- Identify supported risks, evidence gaps, dependencies, implementation considerations, and caveats.
- Expand important concepts when the selected evidence provides sufficient detail.
- Where multiple evidence sources support the same conclusion, synthesize them into a single coherent explanation instead of listing them independently.
- Prioritize recommendations only when the evidence supports an ordering.
- Clearly distinguish confirmed evidence from unresolved evidence gaps.
- Prioritize information density over answer length.
- Avoid filler, repetition, unsupported background, speculation, and artificial padding.
```

5. Variables inserted: none beyond the conditional include-decision-notes text.
6. Where used: Phase 4 prompt when `adaptive_answer_sections=False`.
7. Affects: generation, response formatting.
8. Quality notes: strong for reproducibility; weaker than adaptive mode for varied question shapes because it always suggests the same section families.

### Weak-evidence caveat instruction

1. File path: `src/cial_knowledge_os/phase4_pipeline.py`
2. Function/class: `_build_phase4_prompt()`, `weak_rule`
3. Purpose: tells the model to disclose weak selected evidence.
4. Exact text:

```text
- All selected evidence is below the reranker threshold. State this limitation prominently, use cautious language, and recommend source verification before action.
```

5. Variables inserted: none.
6. Where used: appended only when `selection.weak_evidence` is true.
7. Affects: generation, summaries, evaluation safety.
8. Quality notes: reduces overconfident answers when retrieval found usable but low-confidence passages.

### Word-count instructions

1. File path: `src/cial_knowledge_os/phase4_pipeline.py`
2. Function/class: `_build_phase4_prompt()`, `minimum_words` and `maximum_words`
3. Purpose: answer-length control without authorizing unsupported padding.
4. Exact text:

```text
Aim for at least {effective_minimum} words when the evidence supports that depth. 
```

```text
Do not exceed {self.config.max_answer_words} words. Prefer concise prioritization over dropping citations or adding unsupported compression.
```

5. Variables inserted: `effective_minimum`, `max_answer_words`.
6. Where used: Phase 4 prompt when configured; `effective_minimum` is capped at `max_answer_words` when both are set.
7. Affects: generation, response length logic.
8. Quality notes: the phrase "when the evidence supports that depth" is important; it preserves grounding despite longer-answer targets.

## Context Template

### Phase 1 retrieval context block

1. File path: `src/cial_knowledge_os/retrieval.py`
2. Function/class: `format_retrieved_context(results, max_chars)`
3. Purpose: prompt context serialization for Basic RAG.
4. Exact template:

```text
[{rank}] {source} | {page_label} | chunk {result.get('chunk_id', 'n/a')} | score {result.get('score', 0.0):.3f}
{text}
```

5. Variables inserted: `rank`, `source`, `page_label`, `chunk_id`, `score`, truncated `text`.
6. Where used: `BasicRAGPipeline.answer()` and notebook 01 direct generation cells.
7. Affects: generation, citations.
8. Quality notes: compact and citation-friendly, but less explicit than Phase 2-4 context headers.

### Phase 2-4 selected context header

1. File path: `src/cial_knowledge_os/context_builder.py`
2. Function/class: private `_header(result, reference_id)` used by `compress_context()`
3. Purpose: final prompt evidence serialization for Phase 2, Phase 3, and Phase 4 selected evidence.
4. Exact template:

```text
[{reference_id}]
Document: {source_label(result)}
Page: {page_text}
Chunk ID: {result.get('chunk_id') or 'Not provided'}
{score_label}: {score_text}
{text}
```

5. Variables inserted: `reference_id`, `source_label`, `page_text`, `chunk_id`, `score_label`, `score_text`, fitted/truncated `text`.
6. Where used: `ContextBuilder.build()` -> `compress_context()` -> prompt `context`.
7. Affects: generation, citations, citation formatting, evidence selection.
8. Quality notes: the exact reference header gives the model stable IDs and provenance fields before each evidence block, improving citation accuracy.

### Phase 3/4 context artifact Markdown template

1. File path: `src/cial_knowledge_os/phase3_runner.py`
2. Function/class: `Phase3Runner._context_markdown()`
3. Purpose: export per-question evidence, prompt boundary, answer, and error for audit.
4. Exact template:

````text
# Question

{question}

# Retrieved Chunks

```json
{retrieved_json}
```

# Merged Context

```
{response.get('context') or ''}
```

# Prompt

```
{response.get('prompt') or ''}
```

# Generated Answer

{response.get('answer') or ''}

# Error

{error or 'None'}
````

5. Variables inserted: `question`, `retrieved_json`, `context`, `prompt`, `answer`, `error`.
6. Where used: Phase 3 and Phase 4 run bundle `context/*.md` exports.
7. Affects: exports, debugging, prompt comparison.
8. Quality notes: preserves the exact model input boundary and generated output for regression comparison.

## Citation Instructions

### Inline reference rules in prompts

1. File path: `src/cial_knowledge_os/llm.py`
2. Function/class: `build_grounded_prompt()`
3. Purpose: Phase 1-3 citation discipline.
4. Exact text:

```text
6. Cite supported claims inline using exact reference IDs such as [1].
7. Do not invent, alter, or renumber reference IDs.
```

5. Variables inserted: none.
6. Where used: Basic/Phase 2/Phase 3 generation.
7. Affects: citations, generation.
8. Quality notes: aligns answer markers with context block IDs.

1. File path: `src/cial_knowledge_os/phase4_pipeline.py`
2. Function/class: `_build_phase4_prompt()`
3. Purpose: Phase 4 citation discipline.
4. Exact text:

```text
3. Cite every key factual claim and recommendation inline using the exact reference IDs shown in the evidence, such as [1].
4. Do not invent, alter, or renumber reference IDs.
```

5. Variables inserted: none.
6. Where used: Phase 4 generation.
7. Affects: citations, generation, exports.
8. Quality notes: stronger than Phase 1-3 because it explicitly covers recommendations, not just factual claims.

### Plain-text reference appendix template

1. File path: `src/cial_knowledge_os/citations.py`
2. Function/class: `render_citations()`, `render_answer_with_citations()`
3. Purpose: deterministic citation appendix for generated answers.
4. Exact templates:

```text
[{reference_id}] {source} | page {page} | chunk {chunk_id} | score {score} | PDF {pdf_link}
```

```text
{cleaned_answer}

References:
{references}
```

5. Variables inserted: `reference_id`, source fields, optional `page`, optional `chunk_id`, optional `score`, optional `pdf_link`, `cleaned_answer`, `references`.
6. Where used: all phases after generation unless answer is a no-evidence response or citations are empty.
7. Affects: citations, exports, HTML/XLSX reporting.
8. Quality notes: deterministic post-processing repairs missing inline markers by including all retrieved evidence when needed.

### Phase 4 low-confidence answer prefix

1. File path: `src/cial_knowledge_os/phase4_pipeline.py`
2. Function/class: `Phase4RAGPipeline.answer()`
3. Purpose: deterministic prefix when weak evidence was allowed and the generated answer is otherwise answered.
4. Exact text:

```text
**Caution â€” low-confidence evidence:** The reranker found usable context, but all selected chunks were below the configured score threshold. Verify the cited sources before acting.
```

5. Variables inserted: none.
6. Where used: Phase 4 answer post-processing when `weak_evidence` and `weak_evidence_answer_allowed`.
7. Affects: generation output, summaries, citations.
8. Quality notes: adds visible confidence framing even if the model omits the weak-evidence caveat.

## Evaluation Prompts

No active LLM evaluation prompts were found in the Phase 4.5 engine. Evaluation is deterministic:

- `src/cial_knowledge_os/evaluation_metrics.py` checks keyword coverage, forbidden keywords, safe failure markers, hallucination heuristics, citation count, and citation metadata completeness.
- `src/cial_knowledge_os/experiment_runner.py` exports deterministic benchmark rows and calls `evaluate_answer()`.
- `src/cial_knowledge_os/evaluation_report.py` writes deterministic recommendation Markdown.

Evaluation prompt-like assets:

1. File path: `data/benchmarks/cisg/benchmark_answers.csv`
2. Function/class: loaded by `benchmark_loader.load_benchmark()`
3. Purpose: benchmark questions, expected keywords, forbidden keywords, expected behavior, and should-answer labels.
4. Exact prompt text: each row's `question` field is the user prompt; exact data remains in the CSV.
5. Variables inserted: none.
6. Where used: `ExperimentRunner`, optional `Phase3Runner` / `Phase4Runner` benchmark mode.
7. Affects: evaluation.
8. Quality notes: deterministic benchmark labels avoid LLM-as-judge variability.

Safe-failure markers used by deterministic evaluation:

```text
insufficient evidence
do not contain sufficient
could not find enough evidence
no reliable answer
cannot answer from
not available in the
```

## Retry Prompts

No alternate retry prompt was found. Phase 4 retries the same prompt after retryable local generation failures.

1. File path: `src/cial_knowledge_os/phase4_pipeline.py`
2. Function/class: `_generate_grounded_answer()`, `_is_retryable_generation_error()`
3. Purpose: retry local Ollama invocation without repeating retrieval/reranking.
4. Exact user-visible retry message:

```text
Generation failed; retrying attempt {next_attempt}/{total_attempts} after cooldown.
```

Retryable marker strings:

```text
model runner has unexpectedly stopped
model runner stopped
no data received from ollama stream
status code: 500
status code 500
responseerror
std::bad_alloc
connection reset
connection refused
connection aborted
timed out
timeout
stream
```

5. Variables inserted: `next_attempt`, `total_attempts`.
6. Where used: Phase 4 local generation retry loop.
7. Affects: generation reliability, exports, metrics.
8. Quality notes: retrying the exact same prompt preserves deterministic prompt behavior while handling transient local-model failures.

## Summarization Prompts

No active summarization LLM prompt was found in source modules for Phase 4.5. Summaries are deterministic aggregate reports.

Reference-only summarization prompt:

1. File path: `references/rag_from_scratch_12_to_14.ipynb`
2. Function/class: LangChain example `ChatPromptTemplate.from_template(...)`
3. Purpose: conceptual reference notebook, not active CIAL engine code.
4. Exact text:

```text
Summarize the following document:

{doc}
```

5. Variables inserted: `doc`.
6. Where used: reference notebook only.
7. Affects: none in active Phase 4.5 engine.
8. Quality notes: not recommended for restoring Phase 4.5 behavior because the implemented engine avoids summarizing whole documents before evidence selection.

## Export Prompts

No LLM export prompts were found. Export templates are deterministic Markdown/HTML/CSV/XLSX renderers.

Important export templates:

- `src/cial_knowledge_os/phase3_runner.py`: context artifact Markdown includes `# Prompt` with exact prompt text.
- `src/cial_knowledge_os/phase3_reporting.py`: safe Markdown renderer and standalone HTML report.
- `src/cial_knowledge_os/phase4_reporting.py`: Phase 4 HTML report, citation popover templates, evidence selection tables, and decision visualizations.
- `src/cial_knowledge_os/batch_qa.py`: CSV columns and retrieval trace strings.

Prompt-facing export text from `batch_qa.py`:

```text
Original Query
Rewritten Query
Keyword Expansion
Domain Reformulation
Retrieved {retrieved_count} chunks
Deduplicated to {deduplicated_count}
Neighbor Expanded to {expanded_count}
Final Context: {final_sections} merged sections
```

These do not affect model output; they affect inspectability.

## Prompt Variables

Core generation variables:

- `question`: user question passed into prompt.
- `context`: final fitted prompt context from retrieved/selected evidence.
- `no_evidence_response`: safe-failure response string.
- `INSUFFICIENT_EVIDENCE_RESPONSE`: Phase 2-4 safe-failure response.
- `answer_detail_level`: `concise`, `balanced`, or `detailed`; default `detailed`.
- `content_requirements`: branch-specific synthesis constraints.
- `structure`: branch-specific response formatting instructions.
- `weak_rule`: appended only when selected evidence is weak.
- `minimum_words`: generated from `min_answer_words`.
- `maximum_words`: generated from `max_answer_words`.
- `decision_notes_family`: appends `Decision Notes` to allowed adaptive section families when configured.
- `effective_minimum`: `min(min_answer_words, max_answer_words)` when both are set.

Context variables:

- `reference_id`: numeric evidence ID shown as `[n]`.
- `source_label(result)`: document/source label.
- `page_text`: source page or `Not provided`.
- `chunk_id`: chunk identifier or `Not provided`.
- `score_label`: `RRF Score` or `Similarity Score`.
- `score_text`: formatted score or `Not scored`.
- `text`: selected chunk text, optionally truncated by character or token budget.

Agentic-adjacent variables:

- `state.question`
- `state.phase4_answer_status`
- `state.response_plan`
- `state.evidence_quality`
- `state.selected_evidence`
- `state.draft_answer`
- `state.query_intent`
- `state.composed_prompt`

## Generation Parameters

### Phase 4 defaults

1. File path: `src/cial_knowledge_os/config.py`
2. Function/class: `Phase4Config`
3. Purpose: default Phase 4.5 generation and evidence-selection policy.
4. Relevant values:

```text
answer_detail_level = "detailed"
min_answer_words = 250
max_answer_words = None
prefer_structured_answers = True
adaptive_answer_sections = True
include_decision_notes = True
generation_retries = 2
retry_cooldown_seconds = 20.0
evidence_token_budget = 2400
selected_evidence_target_min_tokens = 800
selected_evidence_target_max_tokens = 1500
max_context_tokens = 4096
weak_evidence_answer_allowed = True
unsupported_query_detection_enabled = True
```

5. Variables inserted: these feed prompt branches and context/evidence budgets.
6. Where used: `Phase4RAGPipeline`, `Phase4Runner`, scripts, notebooks.
7. Affects: retrieval, generation, evaluation, exports, summaries, citations.
8. Quality notes: the selected-evidence token targets are as important as the prompt text because they prevent evidence starvation before generation.

### Local Ollama parameters

1. File path: `src/cial_knowledge_os/llm.py`
2. Function/class: `create_local_llm(config)`
3. Purpose: create deterministic local model adapter.
4. Exact generation config:

```python
OllamaLLM(model=config.ollama_model_name, temperature=0)
```

5. Variables inserted: `config.ollama_model_name`.
6. Where used: Basic/Phase 2/Phase 3/Phase 4 when no injected LLM is supplied.
7. Affects: generation.
8. Quality notes: `temperature=0` supports reproducibility and reduces citation drift. No `top_p` or stop sequences were found for the active Phase 4.5 generation path.

### Batch script run profile

1. File path: `scripts/run_phase4_batch.py`
2. Function/class: module `USER CONFIGURATION`, `build_config()`
3. Purpose: long-horizon/manual QA Phase 4 batch defaults.
4. Relevant exact values:

```text
QUESTIONS_FILE = PROJECT_ROOT / "data" / "manual_qa" / "CIAL_Enterprise_Long_Horizon_200_Questions.txt"
RUN_MODE = "manual_qa"
MAX_ANSWER_WORDS = 1200
ADAPTIVE_ANSWER_SECTIONS = True
GENERATION_RETRIES = 2
RETRY_COOLDOWN_SECONDS = 20
RERANKER_DEVICE = "auto"
RERANKER_BATCH_SIZE = 16
LOCAL_FILES_ONLY = False
QDRANT_MODE = "server"
QDRANT_URL = "http://localhost:6333"
QDRANT_BATCH_SIZE = 32
```

5. Variables inserted: CLI overrides can replace question file, mode, max words, retries, cooldown, reranker settings, and Qdrant settings.
6. Where used: `scripts/run_phase4_batch.py` and compatibility launcher `scripts/run_phase4_interactive.py`.
7. Affects: generation, evaluation/manual QA, exports.
8. Quality notes: `MAX_ANSWER_WORDS=1200` likely helped long-horizon answer completeness while the prompt preserved citation and anti-padding constraints.

### Notebook Phase 4 profile

1. File path: `notebooks/04_Reranking_and_Evidence_Selection.ipynb`
2. Function/class: Phase 4 configuration cell.
3. Purpose: notebook-run Phase 4 defaults.
4. Relevant exact values:

```text
answer_detail_level="detailed"
min_answer_words=250
max_answer_words=None
prefer_structured_answers=True
adaptive_answer_sections=True
include_decision_notes=True
generation_retries=2
retry_cooldown_seconds=20
```

5. Variables inserted: fed into `Phase4Config`.
6. Where used: notebook smoke/manual QA runs.
7. Affects: generation, exports, summaries.
8. Quality notes: same policy as source defaults; notebook text explicitly states evidence selection reduces irrelevant context, not answer depth.

### Multimodal test-corpus profile

1. File path: `notebooks/045_Multimodal_Test_Corpus_Evaluation.ipynb`
2. Function/class: Phase 4 configuration cell.
3. Purpose: smaller Phase 4 profile for multimodal/test corpus validation.
4. Relevant exact values:

```text
answer_detail_level="detailed"
min_answer_words=150
max_answer_words=None
prefer_structured_answers=True
adaptive_answer_sections=True
include_decision_notes=True
generation_retries=1
retry_cooldown_seconds=5
evidence_token_budget=1600
selected_evidence_target_min_tokens=600
selected_evidence_target_max_tokens=1000
```

5. Variables inserted: fed into `Phase4Config`.
6. Where used: notebook 045 batch/smoke runs.
7. Affects: generation, multimodal evidence summaries, exports.
8. Quality notes: lower word/token targets reflect smaller test corpus while preserving Phase 4.5 structure.

## Agentic Adjacent Prompts

These prompts live in the optional Phase 5 layer. They are not the default Phase 4.5 engine, but they consume Phase 4 selected evidence and are useful for comparing "Phase 4.5" or early agentic behavior.

### Prompt composer

1. File path: `src/cial_knowledge_os/agents/prompt_composer.py`
2. Function/class: `PromptComposer.run()`
3. Purpose: deterministic prompt assembly over Phase 4 selected evidence for agentic draft generation.
4. Exact prompt text:

```text
You are a local, evidence-grounded enterprise assistant.
Use only SELECTED EVIDENCE. Cite major claims with [n]. Do not invent facts.
Preserve and identify table, figure, image, screenshot, diagram, and OCR
evidence when present. If the Phase 4 status is unsupported_query or
insufficient_evidence, preserve that limitation and do not force an answer.

PHASE4 STATUS
{state.phase4_answer_status}

QUESTION
{state.question}

RESPONSE PLAN
{json.dumps(state.response_plan, ensure_ascii=False)}

EVIDENCE QUALITY
{json.dumps(state.evidence_quality, ensure_ascii=False, default=str)}

SELECTED EVIDENCE
{json.dumps(records, ensure_ascii=False, default=str)}

ANSWER
```

5. Variables inserted: `state.phase4_answer_status`, `state.question`, `state.response_plan`, `state.evidence_quality`, `records`.
6. Where used: `Phase5Pipeline` before `DraftGenerator`.
7. Affects: generation, citations, multimodal preservation.
8. Quality notes: explicitly preserves Phase 4 status and modality fields, preventing agentic layers from overriding safe failure.

### Query analyzer

1. File path: `src/cial_knowledge_os/agents/query_analyzer.py`
2. Function/class: `QueryAnalyzer.build_prompt()`
3. Purpose: structured intent classification.
4. Exact prompt text:

```text
Classify this enterprise knowledge question. Return JSON only.
Allowed intents: definition, comparison, procedure, checklist, risk_analysis,
prioritization, architecture, troubleshooting, decision_support, compliance,
policy_interpretation, current_data_query, unsupported_query, mixed.
Required keys: intent, domain, requires_current_data, requires_risk_review,
requires_compliance_review, recommended_answer_depth, reasoning.
QUESTION: {state.question}
```

5. Variables inserted: `state.question`.
6. Where used: optional `Phase5Pipeline`.
7. Affects: generation planning, risk/compliance routing.
8. Quality notes: enforces JSON-only intent metadata before response planning.

### Response planner

1. File path: `src/cial_knowledge_os/agents/response_planner.py`
2. Function/class: `ResponsePlanner.build_prompt()`
3. Purpose: evidence-aware answer format planning.
4. Exact prompt text:

```text
Plan an enterprise answer. Return JSON only.
Allowed formats: executive_brief, comparison_table, checklist, risk_matrix,
priority_matrix, step_by_step_procedure, architecture_explanation,
decision_report, narrative_synthesis, troubleshooting_guide, compliance_mapping.
Required keys: format, sections, citation_strategy, tone, must_include, avoid,
reasoning. Preserve available non-text evidence in the plan.
QUESTION: {state.question}
INTENT: {json.dumps(state.query_intent)}
PHASE4_STATUS: {state.phase4_answer_status}
EVIDENCE_COUNT: {len(state.selected_evidence)}
MODALITIES: {modalities}
```

5. Variables inserted: `state.question`, `state.query_intent`, `state.phase4_answer_status`, selected-evidence count, `modalities`.
6. Where used: optional `Phase5Pipeline`.
7. Affects: generation planning, summaries.
8. Quality notes: resembles a fuller version of Phase 4.5 adaptive sections, but outside the default Phase 4 engine.

### Critic, compliance, risk, and visual verification prompts

1. File path: `src/cial_knowledge_os/agents/answer_critic.py`
2. Function/class: `AnswerCritic.build_prompt()`
3. Exact prompt text:

```text
Critique only; do not rewrite. Return JSON only with:
passed, issues, severity (low|medium|high), revision_instructions.
Check completeness, missing sections, organization, repetition, unanswered
parts, weak reasoning, prioritization, and missing caveats.
QUESTION: {state.question}
PLAN: {json.dumps(state.response_plan)}
ANSWER: {state.draft_answer}
```

1. File path: `src/cial_knowledge_os/agents/compliance_agent.py`
2. Function/class: `ComplianceAgent.build_prompt()`
3. Exact prompt text:

```text
Review answer compliance against selected evidence. Return JSON
only with passed, unsupported_claims, citation_issues, grounding_score (0..1),
revision_required. Check citation discipline, weak evidence disclosure, and
enterprise policy caution.
EVIDENCE: {[item.to_dict() for item in state.selected_evidence]}
ANSWER: {state.draft_answer}
```

1. File path: `src/cial_knowledge_os/agents/risk_agent.py`
2. Function/class: `RiskAgent.build_prompt()`
3. Exact prompt text:

```text
Review risks. Return JSON only with passed, risks,
missing_caveats, risk_level (low|medium|high), revision_required.
For each applicable operational, cybersecurity, aviation safety, governance,
and compliance risk include category, severity, likelihood, mitigation_status,
and description. Flag unsafe recommendations and overconfident language.
QUESTION: {state.question}
ANSWER: {state.draft_answer}
```

1. File path: `src/cial_knowledge_os/agents/evidence_verifier.py`
2. Function/class: `EvidenceVerifier.run()`
3. Exact visual verification prompt:

```text
Verify whether the supplied visual evidence is consistent with the answer. Report discrepancies only.
```

5. Variables inserted: shown inline in each prompt.
6. Where used: optional `Phase5Pipeline`.
7. Affects: evaluation/verification and optional revision, not default Phase 4.
8. Quality notes: these prompts support post-generation QA, but the repository docs say Phase 5 is separate and Phase 4 behavior is preserved when disabled.

### One-time revision prompt addition

1. File path: `src/cial_knowledge_os/orchestration/phase5_pipeline.py`
2. Function/class: `Phase5Pipeline.answer()`
3. Purpose: append validation feedback for at most one revision.
4. Exact text:

```text
ONE-TIME REVISION REQUIREMENTS
{revision_notes}
```

5. Variables inserted: `revision_notes`.
6. Where used: optional Phase 5 when consensus returns `revise_once`.
7. Affects: generation, evaluation.
8. Quality notes: explicit stop condition avoids open-ended agentic loops.

## Manual QA Prompts

Manual QA assets are user-question prompt datasets, not system/developer prompt templates. They are consumed by `collect_batch_answers()`, `Phase4Runner`, scripts, and notebooks as question inputs.

Files inspected:

- `data/manual_qa/smoke_questions.txt` - 3 prompts.
- `data/manual_qa/phase4_questions_small.txt` - 13 prompts.
- `data/manual_qa/phase4_questions.txt` - 440 prompts.
- `data/manual_qa/phase4_hal.txt` - 34 prompts.
- `data/manual_qa/CIAL_Enterprise_Long_Horizon_10_Questions.txt` - 19 non-empty lines.
- `data/manual_qa/CIAL_Enterprise_Long_Horizon_200_Questions.txt` - 200 prompts.
- `data/manual_qa/CIAL_Enterprise_Stress_Test_500_Questions.txt` - 500 prompts.
- `data/manual_qa/CIAL_Multimodal_Test_Questions.txt` - 103 prompts.
- `data/manual_qa/easa_qns.txt` - 100 prompts.
- `data/manual_qa/airport_operations_questions.txt` - 12 prompts.
- `data/manual_qa/cybersecurity_questions.txt` - 15 prompts.

Important quality note: the stress-test set includes adversarial user prompts such as requests to ignore citations, reveal hidden system instructions, or use fake citations. These likely helped validate the strict grounding/citation rules.

## Reference Notebook Prompts

The `references/` notebooks contain LangChain educational prompt examples. Project rules state these are conceptual guides, not implementation templates. They are not active Phase 4.5 engine prompts.

Examples found:

- `references/rag_from_scratch_1_to_4.ipynb`: `hub.pull("rlm/rag-prompt")` and `Answer the question based only on the following context:\n{context}\n\nQuestion: {question}`.
- `references/rag_from_scratch_5_to_9.ipynb`: multi-query, RAG-fusion, decomposition, step-back, and HyDE prompt examples.
- `references/rag_from_scratch_10_and_11.ipynb`: query routing, prompt routing, and SQL/query-analysis examples.
- `references/rag_from_scratch_12_to_14.ipynb`: summarization prompt example.
- `references/rag_from_scratch_15_to_18.ipynb`: RAG-fusion and final RAG prompt examples.

Recommendation: do not restore these verbatim into the integrated repository unless deliberately implementing the referenced technique. The CIAL engine already replaced LLM query expansion with deterministic query transformations for local, auditable behavior.

## Recommendations

Preserve or selectively restore these high-value behaviors first:

- Phase 4 `_build_phase4_prompt()` with adaptive section selection.
- The Phase 4 citation rule requiring every key factual claim and recommendation to cite exact evidence IDs.
- The Phase 2-4 context header with `[reference_id]`, document, page, chunk ID, and score.
- `INSUFFICIENT_EVIDENCE_RESPONSE` and citation suppression for safe failures.
- Weak-evidence caveat instruction plus deterministic low-confidence answer prefix.
- `temperature=0` local Ollama generation.
- `min_answer_words` as a conditional target only, not a hard padding instruction.
- `max_answer_words` support from scripts for long manual QA runs.
- Phase 4 retry loop with same-prompt retry, not altered retry prompts.
- Context artifact exports that preserve retrieved chunks, final context, prompt, answer, and error.

Avoid restoring as Phase 4 defaults:

- Reference notebook OpenAI/LangChain prompts.
- LLM-based query expansion prompts from references, unless wrapped in local/offline controls.
- Any agentic Phase 5 prompt unless the integrated repository explicitly supports the Phase 5 validation workflow.

# Prompt Quality Comparison

Prompts and constraints most likely responsible for higher-quality original Phase 4.5 answers:

1. Adaptive Phase 4 section selection:
   The prompt maps question shapes to relevant answer families and says not to use every section by default. This likely improved answer structure without overfitting every answer to a fixed report template.

2. Enterprise-grade synthesis requirements:
   Phase 4 explicitly asks the model to interpret, connect, synthesize, explain why recommendations matter, and distinguish evidence from gaps. This is stronger than the Phase 1-3 concise bullet prompt.

3. Selected-evidence-only grounding:
   The Phase 4 prompt uses "SELECTED EVIDENCE" rather than broad retrieved context, and the pipeline enforces reranking and evidence selection before prompt construction.

4. Citation discipline for recommendations:
   "Cite every key factual claim and recommendation" likely improved trustworthiness compared with only citing factual statements.

5. Evidence-gap behavior:
   The model is instructed to answer supported parts and identify remaining gaps, instead of refusing whenever evidence is partial or hallucinating to fill missing pieces.

6. Conditional word-depth policy:
   `Aim for at least {effective_minimum} words when the evidence supports that depth` encourages more complete answers while keeping the anti-padding constraint.

7. Weak-evidence disclosure:
   Both prompt-level and deterministic answer-level caveats reduce overconfidence.

8. Deterministic generation configuration:
   `temperature=0`, exact context headers, exact safe-failure strings, and same-prompt retries reduce answer drift.

9. Prompt trace exports:
   Per-question context artifacts make regressions visible because the old system preserved the exact prompt boundary.

The single most important restore target is the full Phase 4 prompt builder, including its conditional fragments and the config defaults that activate adaptive sections.
