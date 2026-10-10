# Coverage-first discovery — P0 baseline contracts

Implementation anchor: [#4](https://github.com/upiscium/TSUZRI/issues/4).

## Context

The current production pipeline uses deterministic query expansion, a
one-shot search, fetching, per-document Map, and global Reduce. It does
not yet extract stable EventMention/Atomic Claim identities, retain an
immutable raw-response archive, verify original-text evidence, or run
adaptive discovery loops. It **must not** suddenly count URL hits or
LLM-generated candidates as grounded coverage.

## Scope of this P0 slice

A new `tsuzuri.coverage` library provides only:

- Immutable, strict `CoverageRegion`, `RegionProposal`, `SearchObjective`,
  `QueryPlan`, `SearchObservation`, and `CoverageAssessment` contracts.
- A boundary check that rejects Planner alterations of the Controller's
  objective/region/query budget. New regions are proposals, never edits.
- Independent event, claim, and nonredundant-evidence gain accounting,
  with provisional/confirmed transitions and explicit failed/partial search
  observation. No stop policy is run here.
- A labeled-reference scoring helper for Event Recall, Tail Event Recall,
  Claim Recall and Minority Claim Recall. Empty reference classes produce
  `None`, not an invented 100% coverage claim.
- Deterministic *proposal-originated* exploratory slot allocation: initial
  E:H = 50:50; normal = 70:30; stagnation = 40:60. Not a required acceptance
  share. Tiny budgets may not fit both; the future Controller must preserve
  hypothesis opportunities across rounds.
- Pure, offline unit tests. No live LLM, SearXNG, network or deployment
  dependency is introduced.

The stage ratios are **untested hypotheses**, not proven optimums. Counts
require stable IDs and genuinely grounded evidence assignments from later
archive/extraction/verifier slices. `CoverageAssessment.observation_complete`
reports observation integrity, **not** sufficient coverage or stop approval.
`HYPOTHESIS_DERIVED` needs a small probe before full-scale adoption.

## Next gates

1. Freeze representative *real* source snapshots with hand-reviewed event/claim
   labels and source offsets, including low-frequency stories, conflicting claims,
   false merges, noisy pages and SearXNG engine failure.
2. Implement raw bytes archive-before-extraction and make source provenance
   mandatory before the verifier can mark claims as grounded.
3. Build sparse Coverage Space Builder and Evaluator from verified registrations,
   preserving many-to-many category assignments and candidate identity.
4. Add separate round-based Controller and deterministic Planner B1 behind an
   opt-in flag with audit records of allocation, proposals, stop reasons and
   actual search result status. Leave existing B0 as control.
5. Then compare optional LLM Planner B2, Embedding B3, and per-search scheduling
   against cost-normalized real-fixture and separately recorded live evaluation.

Run `just check-all` before merging. Initial code is deliberately not wired
into `MinimalPipeline.run` to avoid changing established v0.2 behavior.
