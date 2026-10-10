"""Deterministic coverage measurement, independent of live search."""

import pytest
from pydantic import ValidationError

from tsuzuri.coverage import (
    CoverageReference,
    SearchObservation,
    SearchStrategy,
    assess_observations,
    score_coverage,
)


def observation(
    query: str,
    *,
    status: str = "success",
    reason: str | None = None,
    **gains: object,
) -> SearchObservation:
    return SearchObservation(
        objective_id="obj",
        region_id="reg",
        query=query,
        strategy=SearchStrategy.BROAD,
        status=status,
        results_returned=1 if status != "failed" else 0,
        failure_reason=reason,
        **gains,
    )


def test_unique_information_increment_not_url_count() -> None:
    first = observation(
        "q1",
        confirmed_event_ids=("event-1",),
        provisional_event_ids=("event-2",),
        confirmed_claim_ids=("claim-1",),
        provisional_claim_ids=("claim-2",),
        nonredundant_evidence_ids=("ev-1",),
        explored_region_ids=("region-new",),
    )
    second = observation(
        "q2",
        confirmed_event_ids=("event-1",),
        provisional_event_ids=("event-2",),
        confirmed_claim_ids=("claim-1",),
        nonredundant_evidence_ids=("ev-1", "ev-2"),
        explored_region_ids=("region-new",),
    )
    result = assess_observations([first, second])
    assert result.attempts == result.successful == 2
    assert result.observation_complete
    assert result.confirmed_event_gain == 1
    assert result.provisional_event_gain == 1
    assert result.confirmed_claim_gain == 1
    assert result.provisional_claim_gain == 1
    assert result.nonredundant_evidence_gain == 2
    assert result.exploration_region_gain == 1


def test_provisional_promotion_is_new_confirmed_gain() -> None:
    result = assess_observations(
        [
            observation(
                "verification query",
                confirmed_event_ids=("event-2",),
                confirmed_claim_ids=("claim-2",),
            )
        ],
        known_provisional_event_ids=("event-2",),
        known_provisional_claim_ids=("claim-2",),
    )
    assert result.confirmed_event_gain == 1
    assert result.confirmed_claim_gain == 1
    assert result.provisional_event_gain == 0


def test_search_degradation_is_not_successful_zero_discovery() -> None:
    failed = observation("bad", status="failed", reason="SearXNG upstream CAPTCHA")
    partial = observation("partial", status="partial", reason="Some engines timed out")
    result = assess_observations([failed, partial])
    assert not result.observation_complete
    assert result.failed == 1
    assert result.partial == 1
    assert result.confirmed_event_gain == 0
    assert len(result.observation_failures) == 2
    assert not assess_observations([]).observation_complete

    with pytest.raises(ValidationError, match="cannot report discoveries"):
        observation(
            "bad",
            status="failed",
            reason="offline",
            confirmed_event_ids=("invented",),
        )
    with pytest.raises(ValidationError, match="explain why"):
        observation("partial", status="partial")


def test_frozen_reference_recall_tracks_tail_and_minority_independently() -> None:
    reference = CoverageReference(
        relevant_event_ids=frozenset({"e1", "e2", "e3"}),
        tail_event_ids=frozenset({"e3"}),
        relevant_claim_ids=frozenset({"c1", "c2", "c3", "c4"}),
        minority_claim_ids=frozenset({"c4"}),
    )
    score = score_coverage(
        reference=reference,
        confirmed_event_ids=("e1", "e2", "e99"),
        confirmed_claim_ids=("c1", "c4"),
    )
    assert score.event_recall == pytest.approx(2 / 3)
    assert score.tail_event_recall == 0
    assert score.claim_recall == 0.5
    assert score.minority_claim_recall == 1

    with pytest.raises(ValidationError, match="subset"):
        CoverageReference(
            relevant_event_ids=frozenset({"e1"}),
            tail_event_ids=frozenset({"outside"}),
            relevant_claim_ids=frozenset(),
        )
