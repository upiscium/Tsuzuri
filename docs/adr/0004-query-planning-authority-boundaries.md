# ADR-0004: CoverageとQuery Planningの責務・変更権限を分離する

- Status: **Accepted（設計合意、実装完了ではない）**
- Date: 2026-10-10
- Context: [Issue #4](https://github.com/upiscium/TSUZRI/issues/4)
- Related: [ADR-0002](0002-hybrid-coverage-space-and-region-proposals.md), [ADR-0003](0003-coverage-assessment-and-observation-integrity.md)

## Context

Query Plannerが任意に探索範囲を変更できると、計画されたRegionと実際に検索したRegionが食い違う。Coverage評価が不正確になり、未調査領域へ予算を割く仕組みも機能しなくなる。ただしPlannerの柔軟なクエリ表現は探索に有用である。

## Decision

| コンポーネント | 担当 | 行わないこと |
| --- | --- | --- |
| **Coverage Space Builder** | 固定Subset、動的Region提案の分類・重複判定・カテゴリ状態 | 探索予算の確定 |
| **Coverage Evaluator** | 発見・充実・未調査・観測失敗の評価 | 停止指示、クエリ生成 |
| **Exploration Controller** | 戦略選択、Regionの実際の採否、優先度、予算、再計画、停止 | 検索文字列の具体的生成 |
| **Query Planner** | SearchObjectiveからQueryPlanを生成、RegionProposalを提出 | 探索領域や配分予算の直接変更 |

1. Controller → Planner は **SearchObjective**（run/round、region、strategy、目的、既知Event/Claim、期間等の制約、検索予算）を渡す。
2. Planner → 検証境界 は **QueryPlan**（対象objective/region、検索クエリ、独立したRegionProposal）を返す。実行前にobjective、region、query count等が許可範囲内であることを検査する。
3. **Query Reformulation**（言い換え）と**Local Exploration**（指定Region内での探索観点の調整）はPlannerの責任として許可する。**Coverage Expansion**（新しいSubtopic・別Regionへの実質変更）はPlannerが**提案のみ**行う。
4. RegionProposalはBuilderで既存カテゴリとの重複・関連性等を評価し、Controllerが予算を伴う採否を決定する。提案は現在のSearchObjectiveを遡及的に書き換えない。偶然発見した情報は適切なEvent/Regionへ保存可能であり、範囲逸脱の黙認とは区別する。
5. 通常のRegion採用・再配分は**ラウンド境界**で実施する。ただし重要な新規Eventなどによって例外的な再計画が必要な場合、Controllerへ即時提案できる。例外も許可・使用予算・実際の探索範囲を記録し、以前の実績を書き換えない。
6. 未検証のEvent/Claimは **検索仮説として、制約付きで** Targeted Investigationに利用できる。ただし保存文書中の位置への参照が必要で、検索クエリで事実と断定しない。未検証候補から未検証候補へ無制限に連鎖探索せず、間に原文検証を挟む。Evidenceが見つからないことだけを `REJECTED` の根拠にしない。
7. Provisional候補によるTargeted探索の目的は、`evidence_enrichment`、`claim_verification`、`contradiction_investigation` 等に分ける。第4の独立探索戦略は新設しない。

## Rationale

各コンポーネントは最適化・変更したいタイミングが異なる。入力・出力と権限境界を固定することで、ルール / LLM / Embeddingを独立に比較でき、LLMのスコープ逸脱が停止判定や予算を汚染しない。

## Alternatives considered

- **PlannerがRegion・予算も自由に変更**：Topic Drift、偏り、再現性低下のため不採用。
- **Plannerはクエリの言い換えしかできない**：未知観点の提案能力を制約するため不採用。
- **Provisionalを検証まで検索不可**：少数派情報への探索が遅れるため不採用。ただし連鎖探索は制限する。

## Consequences

契約検証、提案キュー、クエリ単位のregion帰属・使用予算の監査が必要。Plannerの予測したExpected Gainと実際の確認済みGainは分けて記録する。

## Revisit conditions

許可境界がTail Event Recallを妨げる実証、提案評価の遅延で重要な探索機会を失う実証、例外再計画の頻発が観測された場合。
