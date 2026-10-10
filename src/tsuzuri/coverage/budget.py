"""Deterministic baseline allocation for *proposal-originated* search slots.

Ratios are unvalidated operational hypotheses, not a mandatory proposal
acceptance quota. Broad/tail/targeted budgets are controlled separately.
"""

from __future__ import annotations

from pydantic import Field

from .contracts import ExplorationPhase, ImmutableContract


class ProposalBudget(ImmutableContract):
    phase: ExplorationPhase
    total_slots: int = Field(ge=0)
    evidence_derived_slots: int = Field(ge=0)
    hypothesis_derived_slots: int = Field(ge=0)


EVIDENCE_SHARES: dict[ExplorationPhase, float] = {
    ExplorationPhase.INITIAL: 0.50,
    ExplorationPhase.NORMAL: 0.70,
    ExplorationPhase.STAGNATION: 0.40,
}


def allocate_proposal_budget(
    total_slots: int, phase: ExplorationPhase
) -> ProposalBudget:
    """Round to nearest slot; ties favor evidence-derived work.

    This is a per-phase baseline. Callers must preserve multi-round opportunities
    for hypothetical exploration, especially when budgets are very small.
    """
    if total_slots < 0:
        raise ValueError("total_slots cannot be negative")
    share = EVIDENCE_SHARES[phase]
    evidence = int(total_slots * share + 0.5)
    return ProposalBudget(
        phase=phase,
        total_slots=total_slots,
        evidence_derived_slots=evidence,
        hypothesis_derived_slots=total_slots - evidence,
    )
