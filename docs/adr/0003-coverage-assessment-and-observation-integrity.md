# ADR-0003: Coverageの測定は発見・充実・観測の信頼性を分ける

- Status: **Accepted（設計合意、実装完了ではない）**
- Date: 2026-10-10
- Context: [Issue #4](https://github.com/upiscium/TSUZRI/issues/4)
- Related: [ADR-0001](0001-event-centric-evidence-and-reporting.md), [ADR-0005](0005-adaptive-exploration-budget-and-stopping.md)

## Context

追加URL数や検索結果件数は、Event/Claimを新たに発見した程度を測れない。検索結果が0件でも、探索飽和とエンジンの障害は異なる。さらにLLM抽出直後の未検証候補を成果に算入すると、発見率が人工的に高くなる。

## Decision

1. **Coverage Evaluator** は結果を観測・集計するだけで、予算配分・検索継続・停止を決定しない。
2. 情報増分は次の独立指標として保持し、単純な総記事数に置換しない。
   - **Event Gain**：同一性判定後の新規関連Event。
   - **Claim Gain**：新規の独立Atomic Claim。異説や反証も含む。
   - **Evidence Gain**：既知Claimについて新しい観測・詳細・反証・根拠を加える**非冗長**Evidence。転載や同義の多数記事を件数だけで高く評価しない。
   - **Exploration Gain**：これまで未探索だったRegion/軸・観点への到達。EventやClaimの真の網羅率の代用品ではない。
3. **Discovery Gain**（Event/Claimの新発見）と **Enrichment Gain**（非冗長Evidence・不足Aspectの補完）を区別する。新しい情報がないという観測は、存在しないという証拠ではない。
4. Event/Claimの発見は **Provisional Gain**（候補）と **Confirmed Gain**（重複照合・保存原文に対するGroundingを通過）に分ける。Confirmedは真偽の保証ではない。ProvisionalをConfirmedとして加算しない。Provisional→Confirmedの昇格は検証済みの増分として記録する。
5. Coverageには **Observed Coverage**（発見済みEventの把握状況）と **Exploration Coverage**（探索した領域・戦略・ソース・期間）を併記する。未知Eventを含む真の分母がない場合、便宜的な「Coverage 95%」を保証しない。
6. Searchの結果は成功 / 部分成功 / 失敗を明示し、CAPTCHA、429、抽出失敗、エンジン停止等は **Observation Reliability** として別記録する。観測不能を「新規発見0件の正常な検索」として飽和判定に入力しない。
7. Event、Claim、Evidenceの識別子、観測クエリ、探索ラウンド、Region、検索戦略、実行コストを関連付け、各戦略の限界発見率を計算できるようにする。絶対閾値と重みは評価で決定する。

## Rationale

DiscoveryとEnrichment、ProvisionalとConfirmed、探索面積と情報充足、成功と失敗を分けることで、「検索を続ける価値があるか」を解釈可能にする。未確認のMinority Claimを監査可能な形で追跡し、成功と誤認せずに追加調査できる。

## Alternatives considered

- **検索URLの増分だけを最大化**：重複報道に予算を使い続ける。
- **暫定候補も全件Confirmed扱い**：LLMの誤抽出に高い報酬を与える。
- **Embedding密度から真のCoverage率を推定**：未発見Eventはベクトル化すらされていない。
- **全Gainを一つの固定スコアへ早期統合**：目的・コスト・観測失敗の相違が見えなくなる。

## Consequences

GroundingとEvent/Claim同一性の精度に指標の品質が依存する。まず識別と検証を測れる評価基盤を作り、スコアの重み・停止閾値は後から較正する。

## Revisit conditions

誤抽出によるGain水増し、過度な重複排除によるMinority Claim欠落、障害を正常ゼロとみなす誤判定、Gainと人手Coverage評価の不整合が見つかった場合。
