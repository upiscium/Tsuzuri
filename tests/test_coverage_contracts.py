"""Baseline contracts: authority boundaries and proposal provenance."""

import pytest
from pydantic import ValidationError

from tsuzuri.coverage import (
    CoverageRegion,
    ProposalOrigin,
    QueryPlan,
    RegionProposal,
    SearchObjective,
    SearchStrategy,
    validate_plan_scope,
)


def objective() -> SearchObjective:
    return SearchObjective(
        objective_id="objective-1",
        run_id="run-1",
        round_index=2,
        region_id="region-kernel",
        strategy=SearchStrategy.TAIL,
        purpose="Find under-reported regressions",
        max_queries=3,
    )


def test_plan_stays_inside_controller_authorized_scope() -> None:
    approved = objective()
    proposal = RegionProposal(
        proposal_id="proposal-1",
        origin_region_id=approved.region_id,
        origin=ProposalOrigin.HYPOTHESIS_DERIVED,
        suggested_label="Unreported filesystem regressions",
        suggested_axis="subtopic",
        rationale="A separate topic is not yet explored",
    )
    plan = QueryPlan(
        objective_id=approved.objective_id,
        region_id=approved.region_id,
        queries=("linux security patch regression", "linux regression file system"),
        region_proposals=(proposal,),
    )
    validate_plan_scope(approved, plan)
    assert plan.region_proposals[0].origin == ProposalOrigin.HYPOTHESIS_DERIVED

    with pytest.raises(ValueError, match="authorized coverage region"):
        validate_plan_scope(approved, plan.model_copy(update={"region_id": "another"}))
    with pytest.raises(ValueError, match="query budget"):
        validate_plan_scope(
            approved,
            QueryPlan(
                objective_id=approved.objective_id,
                region_id=approved.region_id,
                queries=("one", "two", "three", "four"),
            ),
        )


def test_evidence_derived_requires_tracked_source() -> None:
    base = dict(
        proposal_id="p2",
        origin_region_id="region-kernel",
        suggested_label="Container escape patches",
        suggested_axis="subtopic",
        rationale="Observed claim suggests an adjacent area",
    )
    with pytest.raises(ValidationError, match="observed source"):
        RegionProposal(**base, origin=ProposalOrigin.EVIDENCE_DERIVED)

    observed = RegionProposal(
        **base,
        origin=ProposalOrigin.EVIDENCE_DERIVED,
        source_claim_ids=("claim-7",),
        origin_is_provisional=True,
    )
    assert observed.origin_is_provisional is True
    with pytest.raises(ValueError, match="originating region"):
        validate_plan_scope(
            objective(),
            QueryPlan(
                objective_id="objective-1",
                region_id="region-kernel",
                queries=("test",),
                region_proposals=(
                    observed.model_copy(update={"origin_region_id": "wrong-region"}),
                ),
            ),
        )


def test_models_are_immutable_and_strict() -> None:
    region = CoverageRegion(
        region_id="r1", label="Upstream security", axis="subtopic", origin="fixed"
    )
    with pytest.raises(ValidationError):
        region.region_id = "edited"
    assert isinstance(objective().constraints, tuple)
    with pytest.raises(ValidationError):
        CoverageRegion(
            region_id="r1",
            label="Upstream security",
            axis="subtopic",
            origin="fixed",
            unexpected="planner controls budget",
        )
    with pytest.raises(ValidationError, match="duplicate queries"):
        QueryPlan(objective_id="o", region_id="r", queries=("same", "same"))
