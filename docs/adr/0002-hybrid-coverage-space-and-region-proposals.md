# ADR-0002: 固定Subsetと動的Regionを併用するCoverage Space

- Status: **Accepted（設計合意、実装完了ではない）**
- Date: 2026-10-10
- Context: [Issue #4](https://github.com/upiscium/TSUZRI/issues/4)
- Related: [ADR-0003](0003-coverage-assessment-and-observation-integrity.md), [ADR-0004](0004-query-planning-authority-boundaries.md)

## Context

既知Eventだけを深掘りすると、そもそも発見されていないEventに到達できない。反対にLLMが無制限に探索領域を追加すると、カテゴリの増殖・重複・予算逸脱・再現性低下を招く。

## Decision

1. **Coverage Space Builder** は固定カテゴリセットから調査に適した **Subset** を選び、検索で得た情報や仮説から **動的Region** を提案・整理する。
2. 探索軸は `Subtopic`, `Source Type`, `Time Range`, `Search Strategy`, `Perspective`。Search Strategy（Broad/Tail/Targeted）は固定する。動的拡張は主にSubtopicとPerspectiveで使う。Source Typeは情報源の分類であり信用度の序列ではない。
3. 軸の完全な直積は列挙しない。関連性・未調査・観測結果に基づき、**疎なRegion集合**を維持する。未選択・未探索を「調査完了」と誤認しない。1 Eventが複数Regionに所属することを許す。
4. 動的Regionのライフサイクルは `CANDIDATE` → `ACTIVE` / `DEFERRED` / `MERGED`、また `ACTIVE` ⇄ `SATURATED` を基本とする。`SATURATED` は現在の探索条件下の暫定的な飽和であり、網羅済みを意味しない。Change / Gap / Audit によって再探索できる。不要候補は採用せず、理由を記録する。
5. カテゴリ生成は慎重に、既存カテゴリの再探索は比較的積極的にする。追加候補は関連性、既存Regionとの重複、Novelty、Coverage Gap、予想される発見価値とコストで評価する。Embedding上の孤立・低密度**だけ**では重要性やカテゴリ独立性を確定しない。
6. RegionProposal の起点は次の2種に区別する。
   - `EVIDENCE_DERIVED`：取得済み文書・Event・Claim等に由来する探索提案。観測したソースIDと理由を残す。未検証Provisionalが起点である可能性を消してはいけない。
   - `HYPOTHESIS_DERIVED`：未探索領域・検索偏り・想定外の観点を調べる探索仮説。原則、小規模な **Probe Exploration** で確かめてから本格的に拡張する。Probeの空振りは偽である証明にならず、`DEFERRED` として再訪を許す。
7. Builder は分類・重複・候補の妥当性を担当し、**予算を使って探索するかの最終判断は Exploration Controller** が持つ。Plannerによる提案が即時Region変更になってはならない。
8. 動的Regionは初期段階では **1回の調査実行内のみ** 保持する。固定セットをバージョン管理し、動的Regionの固定セットへの昇格は実験結果を確認した後の明示的な変更とする。自動の永続昇格はしない。

## Rationale

固定Subsetにより探索の土台と再現性を維持し、動的Regionにより固定語彙で予見できなかったTail Eventを探す余地を残す。探索実績が多いRegionほど注目される自己強化バイアスを抑えられる。

## Alternatives considered

- **完全固定のカテゴリセット**：未知Subtopicへの拡張性が不足。
- **全カテゴリを自由に動的生成**：スコープ逸脱や増殖を管理しにくい。
- **全軸の直積を網羅的に列挙**：探索コストが高すぎる。
- **Embeddingの距離のみでRegion確定**：意味的孤立と重要性・独立性は一致しない。

## Consequences

Regionの選定理由、起点、採用/保留/統合判断、復帰条件、どの検索がどのRegionを実際に探索したかを履歴に保持する必要がある。実装パラメータ・試験配分は [ADR-0005](0005-adaptive-exploration-budget-and-stopping.md) を参照。

## Revisit conditions

カテゴリ増殖率、未発見Tail Event、Probe有効率、誤統合、再探索の費用対効果が悪化した場合。カテゴリの永続共有は、調査横断のメリットが実測で明確になった場合にのみ別途検討する。
