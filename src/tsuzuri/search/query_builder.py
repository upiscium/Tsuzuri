"""Rule-based, topic-neutral search query expansion."""

DEFAULT_EXPANSIONS = [
    "latest",
    "recent developments",
    "official",
    "analysis",
]


def build_queries(query: str, *, max_generated_queries: int) -> list[str]:
    """Build deterministic topic-neutral queries, always including the original."""
    clean_query = " ".join(query.split())
    if max_generated_queries <= 1:
        return [clean_query]

    queries = [clean_query]
    for suffix in DEFAULT_EXPANSIONS:
        if len(queries) >= max_generated_queries:
            break
        expanded = _expand_query(clean_query, suffix)
        if expanded not in queries:
            queries.append(expanded)
    return queries


def _expand_query(query: str, suffix: str) -> str:
    lower = query.lower()
    if suffix == "latest" and ("latest" in lower or "recent" in lower):
        return query
    if suffix == "recent developments" and "recent" in lower:
        return query
    return f"{query} {suffix}"
