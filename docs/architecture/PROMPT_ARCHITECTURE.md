# Prompt Architecture

`docs/architecture/PROMPT_CATALOG.md` is the canonical source for Phase 4.5 prompt behavior. The implementation keeps those prompts in a versioned registry under `services/knowledge-engine/src/cial_knowledge_os/prompts/` and routes code through logical prompt names instead of file paths.

## Structure

```text
prompts/
  manager.py
  loader.py
  registry.py
  renderer.py
  cache.py
  registry.yaml
  generation/
    phase4/
    archived/
  evaluation/
  extraction/
  exports/
  multimodal/
  templates/
```

Active Phase 4.5 generation prompts live in `generation/phase4/`. `generation/archived/` is reserved for retired versions. Future prompt work must add new versioned files or archived copies; Phase 4 prompt files must not be overwritten for Phase 5 or agentic behavior.

## Registry

`registry.yaml` maps logical names to files, version, category, description, and declared variables. Pipelines call logical names such as:

- `generation.grounded_qa`
- `generation.phase4_system`
- `generation.adaptive_sections`
- `generation.structured_sections`
- `generation.narrative_sections`
- `generation.weak_evidence`
- `evaluation.insufficient_evidence`
- `templates.context_template`
- `templates.answer_template`

No pipeline should reference prompt filenames directly.

## Loading And Rendering

`PromptManager` owns the runtime API:

```python
PromptManager.get(name)
PromptManager.render(name, **variables)
```

`get()` returns prompt text plus metadata. `render()` validates supplied variables exactly before calling Python format rendering.

## Validation

The default prompt manager validates at import/startup and fails fast on:

- missing prompt files
- duplicate YAML registry keys
- invalid or escaping paths
- undeclared template variables
- declared but unused variables
- missing render variables
- unused render variables

The prompt cache reloads a file when its modification time changes, which keeps local development ergonomic without weakening startup validation.

## Prompt Flow

```text
Question
  -> Retrieval
  -> EvidenceSelection
  -> ContextBuilder
  -> PromptManager
  -> LLM
  -> GroundedAnswer
  -> CitationRenderer
```

Retrieval, reranking, evidence selection, token budgeting, retry behavior, answer-length settings, temperature, and citation post-processing remain outside prompt management.

## Prompt Catalog Mapping

The catalog section "Phase 1-3 concise grounded prompt" maps to `generation.grounded_qa`.

The catalog section "Phase 4 detailed grounded decision-support prompt" maps to `generation.phase4_system` plus these fragments:

- `generation.adaptive_sections`
- `generation.structured_sections`
- `generation.narrative_sections`
- `generation.adaptive_content_requirements`
- `generation.structured_content_requirements`
- `generation.narrative_content_requirements`
- `generation.weak_evidence`
- `generation.minimum_words`
- `generation.maximum_words`

Safe-failure strings map to:

- `evaluation.phase1_no_evidence`
- `evaluation.insufficient_evidence`

Prompt-facing deterministic templates map to:

- `templates.context_template`
- `templates.retrieval_context_block`
- `templates.answer_template`

## Configuration Boundaries

Prompt management does not change Phase 4.5 configuration defaults:

- `answer_detail_level`
- `min_answer_words`
- `max_answer_words`
- `prefer_structured_answers`
- `adaptive_answer_sections`
- `include_decision_notes`
- `generation_retries`
- `retry_cooldown_seconds`
- evidence token budgets
- weak-evidence policy

The manager renders only the prompt strings implied by those existing settings.

## Phase Boundaries

This architecture intentionally excludes Phase 5, agentic planning, notebook behavior changes, retrieval rewrites, generation rewrites, and prompt rewrites. Agentic-adjacent prompts from the catalog remain documented only unless a separate Phase 5 implementation explicitly adds them under a new versioned registry path.

The continuous-indexing process split does not modify prompt files, registry
resolution, response profiles, evidence selection, citation discipline,
safe-failure text, retry prompts, or temperature. It changes only how committed
retrieval generations become available to the existing prompt pipeline.
