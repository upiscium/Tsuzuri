"""Domain, extension, and obvious low-value page filtering."""

from collections import defaultdict
from collections.abc import Iterable
from urllib.parse import urlsplit

from tsuzuri.filtering.url_normalizer import classify_document_type, get_domain
from tsuzuri.schemas import FilteredUrl, SearchResult

LOW_VALUE_PATH_SEGMENTS = {
    "author",
    "authors",
    "category",
    "categories",
    "login",
    "search",
    "tag",
    "tags",
}
LOW_VALUE_TITLES = {
    "home",
    "login",
    "search",
    "search results",
    "subscribe",
}


def filter_search_results(
    results: Iterable[SearchResult],
    *,
    blocked_domains: set[str],
    blocked_extensions: set[str],
    max_urls_per_domain: int,
) -> list[FilteredUrl]:
    """Apply deterministic URL filters and per-domain diversity limits."""
    domain_counts: dict[str, int] = defaultdict(int)
    filtered: list[FilteredUrl] = []

    for result in results:
        normalized_url = result.normalized_url
        domain = get_domain(normalized_url)
        if not domain or _is_blocked_domain(domain, blocked_domains):
            continue
        if _has_blocked_extension(normalized_url, blocked_extensions):
            continue
        if _looks_like_low_value_page(result):
            continue
        if domain_counts[domain] >= max_urls_per_domain:
            continue

        domain_counts[domain] += 1
        filtered.append(
            FilteredUrl(
                search_id=result.search_id,
                query=result.query,
                url=result.url,
                normalized_url=normalized_url,
                title=result.title,
                snippet=result.snippet,
                domain=domain,
                rank=result.rank,
                document_type=classify_document_type(normalized_url),
                published_hint=result.published_hint,
                retrieval_score=result.retrieval_score,
                query_hits=result.query_hits,
                engine_hits=result.engine_hits,
            )
        )

    return filtered


def _is_blocked_domain(domain: str, blocked_domains: set[str]) -> bool:
    return any(
        domain == blocked or domain.endswith(f".{blocked}")
        for blocked in blocked_domains
    )


def _has_blocked_extension(url: str, blocked_extensions: set[str]) -> bool:
    lower_url = url.lower().split("?", maxsplit=1)[0]
    return any(
        lower_url.endswith(extension.lower())
        for extension in blocked_extensions
        if extension.lower() != ".pdf"
    )


def _looks_like_low_value_page(result: SearchResult) -> bool:
    path_segments = {
        segment.lower()
        for segment in urlsplit(result.normalized_url).path.split("/")
        if segment
    }
    if path_segments & LOW_VALUE_PATH_SEGMENTS:
        return True

    title = (result.title or "").strip().lower()
    return title in LOW_VALUE_TITLES
