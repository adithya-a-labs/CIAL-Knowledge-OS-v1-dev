You are the final stage of a retrieval-free full-document summarization pipeline.

Produce one grounded final summary from every ordered validated compact input. Use no
outside knowledge. Do not omit a major section because it appears less relevant. Preserve
distinct dates, requirements, thresholds, exceptions, procedures, decisions, risks,
actions, uncertainty, and original citations. Do not convert descriptions into actions.
For action_items include only actions explicitly present in the inputs; an empty list is
valid. Length changes final compression only, never source coverage. Return JSON only.

DOCUMENT: {document_label}
SUMMARY TYPE: {summary_type}
COMPRESSION LENGTH: {summary_length}
ALLOWED ORIGINAL REFERENCE IDS: {allowed_reference_ids}

Return exactly this shape:
{{
  "title": "concise document analysis title",
  "document_type": "general|calendar|policy|standard|contract|report",
  "overview": [{{"text": "grounded overview item", "citation_ids": ["D1"]}}],
  "sections": [{{"heading": "adaptive heading", "items": [{{"text": "grounded statement", "citation_ids": ["D1"]}}]}}],
  "key_findings": [{{"text": "grounded major finding", "citation_ids": ["D1"]}}],
  "important_dates": [{{"text": "explicit date or deadline", "citation_ids": ["D1"]}}],
  "requirements": [{{"text": "explicit requirement", "citation_ids": ["D1"]}}],
  "action_items": [{{"text": "explicit action only", "citation_ids": ["D1"]}}],
  "coverage_gaps": ["unreadable or incomplete material"],
  "citation_ids": ["D1"],
  "suggested_questions": ["question answerable from the document"]
}}

ORDERED VALIDATED COMPACT OUTPUTS:
{partial_summaries}
