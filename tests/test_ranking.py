from datetime import UTC, datetime

from tsuzuri.filtering.ranking import rank_search_results, select_documents
from tsuzuri.schemas import ExtractedDocument, SearchResult


def _result(
    *,
    query: str,
    url: str,
    rank: int,
    title: str,
    engine: str,
) -> SearchResult:
    return SearchResult(
        search_id=f"{query}-{rank}",
        query=query,
        url=url,
        normalized_url=url,
        title=title,
        snippet="AI regulation policy update",
        engine=engine,
        rank=rank,
    )


def test_rank_search_results_rewards_cross_query_consensus() -> None:
    results = [
        _result(
            query="AI regulation",
            url="https://example.com/a",
            rank=3,
            title="AI regulation update",
            engine="a",
        ),
        _result(
            query="AI regulation official",
            url="https://example.com/a",
            rank=2,
            title="AI regulation update",
            engine="b",
        ),
        _result(
            query="AI regulation",
            url="https://example.com/b",
            rank=1,
            title="Other AI regulation story",
            engine="a",
        ),
    ]

    ranked = rank_search_results(results, query="AI regulation")

    assert ranked[0].normalized_url == "https://example.com/a"
    assert ranked[0].query_hits == 2
    assert ranked[0].engine_hits == 2
    assert ranked[0].retrieval_score > ranked[1].retrieval_score


def _document(
    doc_id: str,
    *,
    content_hash: str,
    title: str,
    content: str,
    retrieval_score: float,
    domain: str = "example.com",
) -> ExtractedDocument:
    return ExtractedDocument(
        doc_id=doc_id,
        url=f"https://example.com/{doc_id}",
        normalized_url=f"https://example.com/{doc_id}",
        document_type="html",
        title=title,
        content=content,
        estimated_tokens=20,
        domain=domain,
        extraction_method="httpx_trafilatura",
        content_hash=content_hash,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_query="AI regulation",
        search_rank=1,
        retrieval_score=retrieval_score,
    )


def test_select_documents_deduplicates_content_and_ranks_relevance() -> None:
    documents = [
        _document(
            "Source-1",
            content_hash="same",
            title="Unrelated page",
            content="Generic content " * 50,
            retrieval_score=0.01,
        ),
        _document(
            "Source-2",
            content_hash="same",
            title="AI regulation policy update",
            content="AI regulation policy details " * 50,
            retrieval_score=0.10,
        ),
        _document(
            "Source-3",
            content_hash="other",
            title="AI regulation official announcement",
            content="AI regulation regulator policy " * 50,
            retrieval_score=0.20,
        ),
    ]

    selected = select_documents(
        documents,
        query="AI regulation",
        max_documents=2,
    )

    assert [document.doc_id for document in selected] == ["Source-3", "Source-2"]


def test_select_documents_enforces_domain_diversity() -> None:
    documents = [
        _document(
            "Source-1",
            content_hash="1",
            title="AI regulation one",
            content="AI regulation policy " * 50,
            retrieval_score=0.30,
            domain="same.example",
        ),
        _document(
            "Source-2",
            content_hash="2",
            title="AI regulation two",
            content="AI regulation policy " * 50,
            retrieval_score=0.29,
            domain="same.example",
        ),
        _document(
            "Source-3",
            content_hash="3",
            title="AI regulation three",
            content="AI regulation policy " * 50,
            retrieval_score=0.28,
            domain="other.example",
        ),
    ]

    selected = select_documents(
        documents,
        query="AI regulation",
        max_documents=3,
        max_per_domain=1,
    )

    assert [document.doc_id for document in selected] == ["Source-1", "Source-3"]
