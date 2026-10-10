# ADR-0005: 発見率に基づくラウンド単位の探索予算・停止制御

- Status: **Accepted（方針確定、数値は実験用仮説）**
- Date: 2026-10-10
- Context: [Issue #4](https://github.com/upiscium/TSUZRI/issues/4)
- Related: [ADR-0002](0002-hybrid-coverage-space-and-region-proposals.md), [ADR-0003](0003-coverage-assessment-and-observation-integrity.md)

## Context

検索回数だけのHard Capは発見途中で探索を切る。反対に、発見率だけで止めると検索障害、既知情報への検索偏り、未知Eventの存在を見落とす。探索戦略の短期的な発見率だけを最大化するとTail Explorationが枯渇する。

## Decision

1. 探索戦略は **Broad Exploration**（未発見Event）、**Tail Exploration**（孤立・少数報道・未探索観点）、**Targeted Investigation**（既知Event/ClaimのEvidence、検証、異説）の3種とする。複数戦略の探索機会を**調査実行全体で**確保する。毎ラウンド必ず3種を実行する必要はない。
2. まず **A：ラウンド単位の適応的再配分** を採用する。1ラウンドは目標・予算の決定→検索・抽出・検証→情報増分/観測健全性評価の単位。**B：検索ごとの逐次再配分** は同等予算の比較試験で明確な改善が示された場合にのみ導入する。
3. Controllerは確認済みEvent/Claimの限界発見量、非冗長Evidence、未探索Region、Provisional検証待ち、観測失敗、検索/Fetch/LLMコストに基づいて次ラウンドの戦略・Regionを決める。Provisional候補が多いだけで探索継続の成果とは見なさない。
4. **RegionProposal起点の追加探索枠に限定して**、`EVIDENCE_DERIVED : HYPOTHESIS_DERIVED` の暫定配分を以下に設定する。

   | フェーズ | Evidence由来 | Hypothesis由来 | 意図 |
   | --- | ---: | ---: | --- |
   | 探索初期 | 50% | 50% | 既知情報が少ない段階で探索幅を確保 |
   | 通常時 | 70% | 30% | 観測に裏付けられた展開を優先しつつ未知探索を維持 |
   | 発見率停滞時 | 40% | 60% | 視点・領域の偏りを検査 |

   これは **初期実験の設定候補であり、性能が立証された最適比率ではない**。Broad/Tail/Targeted全体予算に適用しない。採択件数のノルマではない。弱い提案を比率に合わせて採用しない。小予算では丸めにより枠がゼロになり得るため、複数ラウンドにわたりHypothesisへの探索機会を保つ。
5. 単純な「N回で停止」を**通常の停止基準にしない**。確認済みDiscovery/Enrichmentの限界増分が下がったら、まず別の検索戦略・Region・Perspectiveを試し、未探索の重要GapとObservation Reliabilityを確認してから **SATURATED候補** にする。`SATURATED` は可逆で、完全網羅の宣言ではない。
6. **Hard Cap（時間、検索回数、Fetch、LLMコストなど）は安全上限として残す**。安全上限到達による終了、観測不良による中断、情報増分が飽和したと判断した終了を別々の理由で記録し、未探索領域を報告する。
7. エンジン429/CAPTCHA/タイムアウト等による検索不能は「正常なゼロ発見」と区別し、飽和の根拠にしない。観測失敗時は予算再調整か中断を検討する。

## Rationale

通常は有望な情報源を深掘りしつつ、未知・少数報道Eventを探す探索機会を保つ。発見率低下は終了命令でなく **戦略変更のトリガー** となる。

## Alternatives considered

- **検索回数固定で通常終了**：探索途中の打切りリスク。
- **発見率のみで直ちに終了**：検索障害・探索偏りを飽和と誤認。
- **全ラウンド固定比率で配分**：新しい情報の発見状況に対応できない。
- **初手から逐次最適化（B）**：コスト・複雑性の増加を裏付ける証拠がない。

## Consequences

ラウンド、戦略、QueryPlan、実行結果、発見量、予算の実績、停止理由を追跡可能にする。探索コストの定義・具体的上限・閾値・配分係数は評価の結果で定める（**現時点で固定しない**）。

## Revisit conditions

同一リソースでB方式がTail Event Recall / Minority Claim Recall / 限界Gainを改善した場合、あるいはA方式で重要な未発見Eventの系統的取りこぼし・過大な予算消費が判明した場合。
