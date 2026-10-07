from tsuzuri.search.query_builder import build_queries


def test_build_queries_includes_original_query_first() -> None:
    assert build_queries(
        "  AI regulation latest developments  ", max_generated_queries=3
    )[0] == ("AI regulation latest developments")


def test_build_queries_uses_topic_neutral_expansions() -> None:
    queries = build_queries(
        "AI regulation latest developments", max_generated_queries=3
    )

    assert queries == [
        "AI regulation latest developments",
        "AI regulation latest developments recent developments",
        "AI regulation latest developments official",
    ]


def test_build_queries_returns_original_when_limit_is_one() -> None:
    assert build_queries("AI regulation", max_generated_queries=1) == ["AI regulation"]
