"""Experimental, side-effect-free coverage contracts and quality metrics.

Nothing in this package changes production search behavior until the
archive, extraction, verification and controller boundaries are implemented.
"""

from .budget import ProposalBudget, allocate_proposal_budget
from .contracts import (
    CoverageAssessment,
    CoverageRegion,
    ExplorationPhase,
    ProposalOrigin,
    QueryPlan,
    RegionProposal,
    SearchObjective,
    SearchObservation,
    SearchStrategy,
    validate_plan_scope,
)
from .metrics import (
    CoverageBenchmarkScore,
    CoverageReference,
    assess_observations,
    score_coverage,
)

__all__ = [
    "CoverageAssessment",
    "CoverageBenchmarkScore",
    "CoverageReference",
    "CoverageRegion",
    "ExplorationPhase",
    "ProposalBudget",
    "ProposalOrigin",
    "QueryPlan",
    "RegionProposal",
    "SearchObjective",
    "SearchObservation",
    "SearchStrategy",
    "allocate_proposal_budget",
    "assess_observations",
    "score_coverage",
    "validate_plan_scope",
]
