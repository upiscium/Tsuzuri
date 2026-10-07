"""Prompt construction for local LLM steps."""

import json

from tsuzuri.schemas import ExtractedDocument, MapSummary


def build_map_prompt(document: ExtractedDocument) -> str:
    """Build a URL-free prompt for per-document summarization."""
    return f"""You are summarizing a source document for a research brief.

Rules:
- Return valid JSON only. Do not wrap it in Markdown.
- Do not infer facts not present in the source text.
- Normalize Japanese content into English.
- Use the exact doc_id shown below.
- Do not include URLs.
- If the document is irrelevant or search noise, set is_search_noise=true and relevance_score<=2.
- Prefer concrete facts, dates, entities, and explicit uncertainty over generic prose.

Required JSON schema:
{{
  "doc_id": "{document.doc_id}",
  "title": "string",
  "document_type": "html or pdf",
  "language": "en, ja, or null",
  "relevance_score": 1,
  "is_news_like": true,
  "is_search_noise": false,
  "topic_tags": ["string"],
  "entities": ["string"],
  "event_date": null,
  "published_date": null,
  "key_facts": ["string"],
  "claims": ["string"],
  "uncertainties": ["string"],
  "conflicting_points": ["string"],
  "short_summary": "string"
}}

Doc ID: {document.doc_id}
Title: {document.title}
Document Type: {document.document_type}

Extracted Content:
{document.content[:12000]}
"""


def build_reduce_prompt(query: str, summaries: list[MapSummary]) -> str:
    """Build a URL-free global reduce prompt from validated map summaries."""
    payload = [
        {
            "doc_id": summary.doc_id,
            "title": summary.title,
            "relevance_score": summary.relevance_score,
            "topic_tags": summary.topic_tags,
            "entities": summary.entities,
            "event_date": summary.event_date,
            "published_date": summary.published_date,
            "key_facts": summary.key_facts,
            "claims": summary.claims,
            "uncertainties": summary.uncertainties,
            "conflicting_points": summary.conflicting_points,
            "short_summary": summary.short_summary,
        }
        for summary in summaries
    ]
    return f"""Synthesize the source summaries into one concise research brief.

Research query:
{query}

Rules:
- Return valid JSON only. Do not wrap it in Markdown.
- Use only facts supported by the provided summaries.
- Every factual point must cite one or more exact source IDs from the input.
- Combine duplicate reporting of the same event instead of repeating it.
- Prefer the newest update when sources describe different stages of the same event.
- Preserve meaningful disagreements and uncertainty.
- Do not include URLs.
- Do not invent source IDs.

Required JSON schema:
{{
  "headline": "string",
  "executive_summary": [
    {{"text": "string", "source_ids": ["Source-1"]}}
  ],
  "key_developments": [
    {{"text": "string", "source_ids": ["Source-1", "Source-2"]}}
  ],
  "uncertainties": [
    {{"text": "string", "source_ids": ["Source-3"]}}
  ]
}}

Validated map summaries:
{json.dumps(payload, ensure_ascii=False)}
"""


def build_repair_prompt(invalid_json: str, error: str) -> str:
    """Build a prompt that asks the model to repair invalid JSON only."""
    return f"""Repair the following invalid JSON response.

Return valid JSON only. Do not include Markdown or commentary.

Validation error:
{error}

Invalid response:
{invalid_json}
"""
