"""Final report validation and source rendering."""

import re
from collections.abc import Iterable

from tsuzuri.schemas import (
    ExtractedDocument,
    FinalReport,
    MapSummary,
    ReportSynthesis,
)

SOURCE_ID_PATTERN = re.compile(r"\[Source-(\d+)]")


def extract_cited_source_ids(markdown: str) -> list[str]:
    """Return unique source IDs cited in Markdown, preserving first-seen order."""
    cited: list[str] = []
    seen: set[str] = set()
    for match in SOURCE_ID_PATTERN.finditer(markdown):
        source_id = f"Source-{match.group(1)}"
        if source_id in seen:
            continue
        seen.add(source_id)
        cited.append(source_id)
    return cited


def validate_citations(
    markdown: str, documents: Iterable[ExtractedDocument]
) -> list[str]:
    """Return citation IDs that do not exist in extracted documents."""
    known_ids = {document.doc_id for document in documents}
    return [
        source_id
        for source_id in extract_cited_source_ids(markdown)
        if source_id not in known_ids
    ]


def render_final_report(
    title: str, body_markdown: str, documents: Iterable[ExtractedDocument]
) -> FinalReport:
    """Append a Sources section and return final report metadata."""
    document_by_id = {document.doc_id: document for document in documents}
    cited_source_ids = extract_cited_source_ids(body_markdown)
    warnings = [
        f"Unknown citation: {source_id}"
        for source_id in cited_source_ids
        if source_id not in document_by_id
    ]

    source_lines = []
    for source_id in cited_source_ids:
        document = document_by_id.get(source_id)
        if document is None:
            continue
        source_lines.append(f"- [{source_id}] {document.title} - {document.url}")

    sources_section = "\n".join(source_lines)
    markdown = f"# {title}\n\n{body_markdown.strip()}"
    if sources_section:
        markdown = f"{markdown}\n\n## Sources\n\n{sources_section}"

    return FinalReport(
        title=title,
        markdown=markdown,
        cited_source_ids=cited_source_ids,
        source_count=len(source_lines),
        warnings=warnings,
    )


def render_synthesized_report(
    *,
    query: str,
    synthesis: ReportSynthesis,
    documents: Iterable[ExtractedDocument],
) -> FinalReport:
    """Render a structured global reduce result into cited Markdown."""
    lines = ["## Executive Summary", ""]
    for point in synthesis.executive_summary:
        lines.append(f"- {point.text}{_citation_suffix(point.source_ids)}")

    lines.extend(["", "## Key Developments", ""])
    for point in synthesis.key_developments:
        lines.append(f"- {point.text}{_citation_suffix(point.source_ids)}")

    lines.extend(["", "## Uncertainties", ""])
    if synthesis.uncertainties:
        for point in synthesis.uncertainties:
            lines.append(f"- {point.text}{_citation_suffix(point.source_ids)}")
    else:
        lines.append(
            "- No material uncertainty was identified in the selected sources."
        )

    title = synthesis.headline.strip() or f"Research Brief: {query}"
    return render_final_report(title, "\n".join(lines), documents)


def render_news_brief(
    *,
    query: str,
    summaries: Iterable[MapSummary],
    documents: Iterable[ExtractedDocument],
    min_relevance_score: int = 3,
) -> FinalReport:
    """Render a deterministic fallback brief from map summaries."""
    useful_summaries = [
        summary
        for summary in summaries
        if not summary.is_search_noise
        and summary.relevance_score >= min_relevance_score
    ]
    if not useful_summaries:
        return render_final_report(
            f"Research Brief: {query}",
            "No sufficiently relevant source summaries were generated.",
            documents,
        )

    lines = ["## Executive Summary", ""]
    for summary in useful_summaries[:10]:
        lines.append(f"- {summary.short_summary} [{summary.doc_id}]")

    lines.extend(["", "## Key Facts", ""])
    for summary in useful_summaries[:10]:
        for fact in summary.key_facts[:3]:
            lines.append(f"- {fact} [{summary.doc_id}]")

    lines.extend(["", "## Uncertainties", ""])
    uncertainties = [
        (summary.doc_id, uncertainty)
        for summary in useful_summaries
        for uncertainty in summary.uncertainties[:2]
    ]
    if uncertainties:
        for doc_id, uncertainty in uncertainties[:10]:
            lines.append(f"- {uncertainty} [{doc_id}]")
    else:
        lines.append(
            "- No major uncertainties were identified in the selected summaries."
        )

    return render_final_report(f"Research Brief: {query}", "\n".join(lines), documents)


def _citation_suffix(source_ids: list[str]) -> str:
    unique_ids = list(dict.fromkeys(source_ids))
    return "".join(f" [{source_id}]" for source_id in unique_ids)
