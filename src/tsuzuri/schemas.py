"""Pydantic schemas for the research pipeline."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SearchResult(BaseModel):
    """Raw result returned by a search engine."""

    model_config = ConfigDict(frozen=True)

    search_id: str
    query: str
    url: HttpUrl
    normalized_url: str
    title: str | None = None
    snippet: str | None = None
    engine: str | None = None
    score: float | None = None
    category: str | None = None
    rank: int
    published_hint: str | None = None
    language_hint: str | None = None
    retrieval_score: float = 0.0
    query_hits: int = 1
    engine_hits: int = 1


class FilteredUrl(BaseModel):
    """Search result after deterministic URL filtering and ranking."""

    model_config = ConfigDict(frozen=True)

    search_id: str
    query: str
    url: HttpUrl
    normalized_url: str
    title: str | None = None
    snippet: str | None = None
    domain: str
    rank: int
    document_type: Literal["html", "pdf", "unknown"]
    published_hint: str | None = None
    retrieval_score: float = 0.0
    query_hits: int = 1
    engine_hits: int = 1


class ExtractedDocument(BaseModel):
    """Document text extracted from HTML or PDF."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    url: HttpUrl
    final_url: HttpUrl | None = None
    normalized_url: str
    document_type: Literal["html", "pdf"]
    title: str
    content: str
    estimated_tokens: int
    domain: str
    language: str | None = None
    extraction_method: Literal[
        "httpx_trafilatura", "playwright_trafilatura", "pymupdf_pdf"
    ]
    status_code: int | None = None
    content_type: str | None = None
    response_bytes: int | None = None
    raw_chars: int | None = None
    content_hash: str
    fetched_at: datetime
    source_query: str
    search_rank: int
    published_hint: str | None = None
    retrieval_score: float = 0.0
    query_hits: int = 1
    engine_hits: int = 1


class FailedFetch(BaseModel):
    """Fetch attempt that did not produce a valid extracted document."""

    model_config = ConfigDict(frozen=True)

    url: HttpUrl
    final_url: HttpUrl | None = None
    normalized_url: str
    document_type: Literal["html", "pdf", "unknown"]
    domain: str
    source_query: str
    search_rank: int
    reason: str
    detail: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    response_bytes: int | None = None
    raw_chars: int | None = None
    extracted_chars: int | None = None
    failed_at: datetime


class MapSummary(BaseModel):
    """Per-document LLM summary."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    title: str
    document_type: Literal["html", "pdf"]
    language: str | None = None
    relevance_score: int = Field(ge=1, le=5)
    is_news_like: bool
    is_search_noise: bool
    topic_tags: list[str]
    entities: list[str]
    event_date: str | None = None
    published_date: str | None = None
    key_facts: list[str]
    claims: list[str]
    uncertainties: list[str]
    conflicting_points: list[str]
    short_summary: str


class ClusterSummary(BaseModel):
    """Reduced summary for a cluster of related documents."""

    model_config = ConfigDict(frozen=True)

    cluster_id: str
    topic: str
    source_doc_ids: list[str]
    key_developments: list[str]
    agreed_facts: list[str]
    disputed_claims: list[str]
    uncertainties: list[str]
    representative_sources: list[str]
    summary: str


class CitedPoint(BaseModel):
    """One synthesized statement grounded in one or more source IDs."""

    model_config = ConfigDict(frozen=True)

    text: str
    source_ids: list[str] = Field(min_length=1)


class ReportSynthesis(BaseModel):
    """Structured global reduce output for the final report."""

    model_config = ConfigDict(frozen=True)

    headline: str
    executive_summary: list[CitedPoint]
    key_developments: list[CitedPoint]
    uncertainties: list[CitedPoint] = Field(default_factory=list)


class FinalReport(BaseModel):
    """Final rendered Markdown report with citation metadata."""

    model_config = ConfigDict(frozen=True)

    title: str
    markdown: str
    cited_source_ids: list[str]
    source_count: int
    warnings: list[str]
