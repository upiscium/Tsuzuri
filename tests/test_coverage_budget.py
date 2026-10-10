"""Initial proposal budget ratios are testable hypotheses, not quotas."""

import pytest

from tsuzuri.coverage import ExplorationPhase, allocate_proposal_budget


@pytest.mark.parametrize(
    ("phase", "expected_evidence", "expected_hypothesis"),
    [
        (ExplorationPhase.INITIAL, 5, 5),
        (ExplorationPhase.NORMAL, 7, 3),
        (ExplorationPhase.STAGNATION, 4, 6),
    ],
)
def test_stage_baselines(
    phase: ExplorationPhase, expected_evidence: int, expected_hypothesis: int
) -> None:
    allocation = allocate_proposal_budget(10, phase)
    assert allocation.evidence_derived_slots == expected_evidence
    assert allocation.hypothesis_derived_slots == expected_hypothesis
    assert allocation.total_slots == expected_evidence + expected_hypothesis


def test_small_budget_does_not_force_acceptance() -> None:
    allocation = allocate_proposal_budget(1, ExplorationPhase.NORMAL)
    assert allocation.evidence_derived_slots == 1
    assert allocation.hypothesis_derived_slots == 0
    assert allocate_proposal_budget(0, ExplorationPhase.NORMAL).total_slots == 0
    with pytest.raises(ValueError, match="negative"):
        allocate_proposal_budget(-1, ExplorationPhase.NORMAL)
