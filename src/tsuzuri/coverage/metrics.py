"""Pure offline coverage accounting and frozen-reference benchmark metrics."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field, model_validator

from .contracts import CoverageAssessment, ImmutableContract, SearchObservation


def assess_observations(
    observations: Iterable[SearchObservation],
    *,
    known_confirmed_event_ids: Iterable[str] = (),
    known_provisional_event_ids: Iterable[str] = (),
    known_confirmed_claim_ids: Iterable[str] = (),
    known_provisional_claim_ids: Iterable[str] = (),
    known_evidence_ids: Iterable[str] = (),
    known_region_ids: Iterable[str] = (),
) -> CoverageAssessment:
    """Count unique information increment, never URLs or repeated mentions.

    Previously grounded and provisional IDs are tracked independently so
    promoting a candidate to grounded counts as *confirmed* gain. Grounding,
    identity matching and evidence nonredundancy must be established upstream.
    """
    batch = list(observations)
    confirmed_events: set[str] = set()
    provisional_events: set[str] = set()
    confirmed_claims: set[str] = set()
    provisional_claims: set[str] = set()
    nonredundant_evidence: set[str] = set()
    explored_regions: set[str] = set()
    failures: list[str] = []

    for item in batch:
        confirmed_events.update(item.confirmed_event_ids)
        provisional_events.update(item.provisional_event_ids)
        confirmed_claims.update(item.confirmed_claim_ids)
        provisional_claims.update(item.provisional_claim_ids)
        nonredundant_evidence.update(item.nonredundant_evidence_ids)
        explored_regions.update(item.explored_region_ids)
        if item.status != "success":
            failures.append(item.failure_reason or "unknown retrieval degradation")

    # A grounded promotion cannot remain counted as merely provisional.
    provisional_events.difference_update(confirmed_events)
    provisional_claims.difference_update(confirmed_claims)
    historical_confirmed_events = set(known_confirmed_event_ids)
    historical_provisional_events = set(known_provisional_event_ids)
    historical_confirmed_claims = set(known_confirmed_claim_ids)
    historical_provisional_claims = set(known_provisional_claim_ids)
    return CoverageAssessment(
        attempts=len(batch),
        successful=sum(item.status == "success" for item in batch),
        partial=sum(item.status == "partial" for item in batch),
        failed=sum(item.status == "failed" for item in batch),
        observation_complete=bool(batch) and not failures,
        confirmed_event_gain=len(confirmed_events - historical_confirmed_events),
        provisional_event_gain=len(
            provisional_events
            - historical_confirmed_events
            - historical_provisional_events
        ),
        confirmed_claim_gain=len(confirmed_claims - historical_confirmed_claims),
        provisional_claim_gain=len(
            provisional_claims
            - historical_confirmed_claims
            - historical_provisional_claims
        ),
        nonredundant_evidence_gain=len(nonredundant_evidence - set(known_evidence_ids)),
        exploration_region_gain=len(explored_regions - set(known_region_ids)),
        observation_failures=tuple(failures),
    )


class CoverageReference(ImmutableContract):
    """Human-reviewed labels for a *fixed* benchmark fixture.

    These labels are explicitly incomplete in open-world, live searching.
    """

    relevant_event_ids: frozenset[str]
    tail_event_ids: frozenset[str] = Field(default_factory=frozenset)
    relevant_claim_ids: frozenset[str]
    minority_claim_ids: frozenset[str] = Field(default_factory=frozenset)

    @model_validator(mode="after")
    def check_subsets(self) -> "CoverageReference":
        if not self.tail_event_ids <= self.relevant_event_ids:
            raise ValueError("tail events must be a subset of relevant events")
        if not self.minority_claim_ids <= self.relevant_claim_ids:
            raise ValueError("minority claims must be a subset of relevant claims")
        return self


class CoverageBenchmarkScore(ImmutableContract):
    event_recall: float | None
    tail_event_recall: float | None
    claim_recall: float | None
    minority_claim_recall: float | None


def _recall(found: set[str], reference: frozenset[str]) -> float | None:
    if not reference:
        return None
    return len(found & reference) / len(reference)


def score_coverage(
    *,
    reference: CoverageReference,
    confirmed_event_ids: Iterable[str],
    confirmed_claim_ids: Iterable[str],
) -> CoverageBenchmarkScore:
    """Only grounded discoveries count toward recall on reference labels."""
    events = set(confirmed_event_ids)
    claims = set(confirmed_claim_ids)
    return CoverageBenchmarkScore(
        event_recall=_recall(events, reference.relevant_event_ids),
        tail_event_recall=_recall(events, reference.tail_event_ids),
        claim_recall=_recall(claims, reference.relevant_claim_ids),
        minority_claim_recall=_recall(claims, reference.minority_claim_ids),
    )
