"""Deterministic candidate aggregation and document selection."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import math
import re

from tsuzuri.schemas import ExtractedDocument, SearchResult

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-]{3,}|[\u3040-\u30ff\u3400-\u9fff]{2,}")
STOPWORDS = {
    "about",
    "after",
    "from",
    "into",
    "latest",
    "news",
    "recent",
    "the",
    "this",
    "with",
}


def rank_search_results(
    results: Iterable[SearchResult], *, query: str
) -> list[SearchResult]:
    """Merge duplicate URLs and rank candidates across expanded queries."""
    grouped: dict[str, list[SearchResult]] = defaultdict(list)
    for result in results:
        grouped[result.normalized_url].append(result)

    ranked: list[SearchResult] = []
    query_tokens = _tokens(query)
    for matches in grouped.values():
        representative = min(matches, key=lambda item: item.rank)
        source_queries = {item.query for item in matches}
        engines = {item.engine for item in matches if item.engine}
        engine_hits = max([1, len(engines), *[item.engine_hits for item in matches]])
        searxng_score = max((item.score or 0.0) for item in matches)
        rrf_score = sum(1.0 / (60.0 + max(1, item.rank)) for item in matches)
        lexical_score = _lexical_relevance(
            query_tokens,
            " ".join(
                part for part in (representative.title, representative.snippet) if part
            ),
        )
        retrieval_score = (
            rrf_score
            + 0.20 * lexical_score
            + 0.03 * min(3, max(0, len(source_queries) - 1))
            + 0.01 * min(5.0, searxng_score)
            + 0.01 * min(3, max(0, engine_hits - 1))
        )
        ranked.append(
            representative.model_copy(
                update={
                    "retrieval_score": retrieval_score,
                    "query_hits": len(source_queries),
                    "engine_hits": engine_hits,
                }
            )
        )

    return sorted(
        ranked,
        key=lambda item: (-item.retrieval_score, item.rank, item.normalized_url),
    )


def select_documents(
    documents: Iterable[ExtractedDocument],
    *,
    query: str,
    max_documents: int,
    max_per_domain: int = 2,
) -> list[ExtractedDocument]:
    """Deduplicate content and select relevant, domain-diverse map candidates."""
    best_by_hash: dict[str, ExtractedDocument] = {}
    query_tokens = _tokens(query)

    for document in documents:
        existing = best_by_hash.get(document.content_hash)
        if existing is None or _document_score(
            document, query_tokens
        ) > _document_score(existing, query_tokens):
            best_by_hash[document.content_hash] = document

    ranked = sorted(
        best_by_hash.values(),
        key=lambda item: (
            -_document_score(item, query_tokens),
            item.search_rank,
            item.normalized_url,
        ),
    )

    selected: list[ExtractedDocument] = []
    domain_counts: dict[str, int] = defaultdict(int)
    domain_limit = max(1, max_per_domain)
    for document in ranked:
        if domain_counts[document.domain] >= domain_limit:
            continue
        selected.append(document)
        domain_counts[document.domain] += 1
        if len(selected) >= max_documents:
            break
    return selected


def _document_score(document: ExtractedDocument, query_tokens: set[str]) -> float:
    text = f"{document.title}\n{document.content[:6000]}"
    lexical = _lexical_relevance(query_tokens, text)
    length_quality = min(1.0, math.log10(max(10, len(document.content))) / 4.0)
    return (
        document.retrieval_score
        + 0.45 * lexical
        + 0.08 * length_quality
        + 0.02 * min(3, max(0, document.query_hits - 1))
    )


def _lexical_relevance(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    text_tokens = _tokens(text)
    return len(query_tokens & text_tokens) / len(query_tokens)


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
        if token.lower() not in STOPWORDS
    }
