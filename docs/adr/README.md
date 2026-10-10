# TSUZRI Architecture Decision Records

このディレクトリは、TSUZRI の **合意済みの設計判断（なぜ、その構成を選んだか）** を記録する。実装の進捗、タスクの順序、テストの実行記録は Issue / PR / `impl-plans/` で管理し、ADR と混同しない。

## 採択済み ADR

| ID | 判断 | 状態 |
| --- | --- | --- |
| [0001](0001-event-centric-evidence-and-reporting.md) | Event / Claim / Evidence を中心とした情報統合と原文根拠の検証 | Accepted |
| [0002](0002-hybrid-coverage-space-and-region-proposals.md) | 固定カテゴリSubset＋動的Region生成と提案管理 | Accepted |
| [0003](0003-coverage-assessment-and-observation-integrity.md) | Discovery / Enrichment、暫定 / 検証済み発見、観測の健全性 | Accepted |
| [0004](0004-query-planning-authority-boundaries.md) | Builder / Evaluator / Controller / Planner の責務分離 | Accepted |
| [0005](0005-adaptive-exploration-budget-and-stopping.md) | ラウンド単位の適応的探索予算と停止方針 | Accepted |
| [0006](0006-empirical-evaluation-and-phased-rollout.md) | 比較評価を優先した段階的導入 | Accepted |

## 記録ルール

- **Status: Accepted** は「設計方針として採用済み」を指し、機能の実装・検証完了を意味しない。
- 各 ADR は **Context / Decision / Rationale / Alternatives / Consequences / Revisit conditions** を保持する。
- 数値（探索比率、閾値、試行回数など）が「初期の仮説」か「変更禁止の制約」かを明示する。実測で妥当性を評価する値を確定性能として記載しない。
- 重要な方針変更は既存ADRを黙って改変せず、新ADRで **Supersedes** の関係を明記する。誤記訂正・リンク修正は既存ADRを更新してよい。
- 実験結果によるパラメータ調整は、それが設計の責務・権限境界を変えない限り ADR 改訂ではなく実装設定・実験記録で扱う。

## 参照

- [実装・実験の統括 Issue #4](https://github.com/upiscium/TSUZRI/issues/4)
- [P0 コントラクト Draft PR #5](https://github.com/upiscium/TSUZRI/pull/5)
- [P0 実装計画](../../impl-plans/coverage-first-p0.md)（PR #5 で追加されるため、未マージ時はリンク先が存在しない）

記録日：2026-10-10（JST）。
