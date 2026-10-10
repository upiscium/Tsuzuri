"""Immutable, run-scoped boundaries for coverage-aware iterative discovery.

These contracts do not change the existing single-pass production pipeline.
They intentionally keep policy (stop, allocation) out of the Query Planner.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImmutableContract(BaseModel):
    """Serializable value without untracked fields or in-place mutation."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class SearchStrategy(StrEnum):
    BROAD = "broad"
    TAIL = "tail"
    TARGETED = "targeted"


class ProposalOrigin(StrEnum):
    EVIDENCE_DERIVED = "evidence_derived"
    HYPOTHESIS_DERIVED = "hypothesis_derived"


class ExplorationPhase(StrEnum):
    INITIAL = "initial"
    NORMAL = "normal"
    STAGNATION = "stagnation"


class CoverageRegion(ImmutableContract):
    """One sparse, potentially overlapping slice of the exploration space."""

    region_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    axis: Literal[
        "subtopic", "source_type", "time_range", "search_strategy", "perspective"
    ]
    origin: Literal["fixed", "dynamic"]
    state: Literal["candidate", "active", "saturated", "deferred", "merged"] = (
        "candidate"
    )
    parent_region_ids: tuple[str, ...] = ()


class RegionProposal(ImmutableContract):
    """An advisory suggestion, never authorization to change a region."""

    proposal_id: str = Field(min_length=1)
    origin_region_id: str = Field(min_length=1)
    origin: ProposalOrigin
    suggested_label: str = Field(min_length=1)
    suggested_axis: Literal["subtopic", "source_type", "time_range", "perspective"]
    rationale: str = Field(min_length=1)
    source_document_ids: tuple[str, ...] = ()
    source_event_ids: tuple[str, ...] = ()
    source_claim_ids: tuple[str, ...] = ()
    origin_is_provisional: bool = False

    @model_validator(mode="after")
    def require_observed_origin(self) -> Self:
        if self.origin == ProposalOrigin.EVIDENCE_DERIVED and not (
            self.source_document_ids or self.source_event_ids or self.source_claim_ids
        ):
            raise ValueError("evidence-derived proposals require an observed source")
        return self


class SearchObjective(ImmutableContract):
    """Controller-owned scope and resource ceiling for one planned search batch."""

    objective_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    round_index: int = Field(ge=0)
    region_id: str = Field(min_length=1)
    strategy: SearchStrategy
    purpose: str = Field(min_length=1)
    max_queries: int = Field(ge=1)
    known_event_ids: tuple[str, ...] = ()
    known_claim_ids: tuple[str, ...] = ()
    constraints: tuple[tuple[str, str], ...] = ()


class QueryPlan(ImmutableContract):
    """Planner-owned query text plus optional *non-binding* region proposals."""

    objective_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    queries: tuple[str, ...] = Field(min_length=1)
    region_proposals: tuple[RegionProposal, ...] = ()

    @model_validator(mode="after")
    def validate_queries(self) -> Self:
        if any(not item.strip() for item in self.queries):
            raise ValueError("query strings must be nonempty")
        if len(set(self.queries)) != len(self.queries):
            raise ValueError("duplicate queries in the same plan")
        return self


def validate_plan_scope(objective: SearchObjective, plan: QueryPlan) -> None:
    """Reject unauthorized changes to scope or query count before execution."""

    if plan.objective_id != objective.objective_id:
        raise ValueError("planner returned a different objective_id")
    if plan.region_id != objective.region_id:
        raise ValueError("planner changed the authorized coverage region")
    if len(plan.queries) > objective.max_queries:
        raise ValueError("planner exceeded the controller's query budget")
    if any(
        proposal.origin_region_id != objective.region_id
        for proposal in plan.region_proposals
    ):
        raise ValueError("region proposal must reference its originating region")


class SearchObservation(ImmutableContract):
    """A search outcome as reported by retrieval/extraction/verifier authorities.

    Confirmed identifiers MUST have been grounded against recorded source text
    upstream. Merely finding a URL or generating an LLM claim is not confirmation.
    `partial` includes degraded upstream engines with potentially usable results.
    """

    objective_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    strategy: SearchStrategy
    status: Literal["success", "partial", "failed"]
    results_returned: int = Field(ge=0)
    failure_reason: str | None = None
    confirmed_event_ids: tuple[str, ...] = ()
    provisional_event_ids: tuple[str, ...] = ()
    confirmed_claim_ids: tuple[str, ...] = ()
    provisional_claim_ids: tuple[str, ...] = ()
    nonredundant_evidence_ids: tuple[str, ...] = ()
    explored_region_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def verify_observation_consistency(self) -> Self:
        if self.status != "success" and not self.failure_reason:
            raise ValueError("partial or failed observation must explain why")
        if self.status == "failed":
            if self.results_returned != 0 or (
                self.confirmed_event_ids
                or self.provisional_event_ids
                or self.confirmed_claim_ids
                or self.provisional_claim_ids
                or self.nonredundant_evidence_ids
            ):
                raise ValueError("failed observation cannot report discoveries")
        return self


class CoverageAssessment(ImmutableContract):
    """Observations only. No decision to continue, change strategy, or stop."""

    attempts: int
    successful: int
    partial: int
    failed: int
    observation_complete: bool
    confirmed_event_gain: int
    provisional_event_gain: int
    confirmed_claim_gain: int
    provisional_claim_gain: int
    nonredundant_evidence_gain: int
    exploration_region_gain: int
    observation_failures: tuple[str, ...] = ()
