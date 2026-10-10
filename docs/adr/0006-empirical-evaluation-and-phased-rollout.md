# ADR-0006: Coverage改善は比較実験を通じて段階的に導入する

- Status: **Accepted（評価方針。モデル・閾値・効果は未確定）**
- Date: 2026-10-10
- Context: [Issue #4](https://github.com/upiscium/TSUZRI/issues/4)
- Related: [P0 Draft PR #5](https://github.com/upiscium/TSUZRI/pull/5)

## Context

LLM Planner、Embeddingの密度解析、逐次予算制御などは発見能力を改善する可能性があるが、効果が未測定の段階で統合すると、何が効いたのか分からなくなる。現行の動作する単発検索とMap/Reduceを不用意に壊すべきではない。

## Decision

1. **比較条件を独立させる**。
   - **B0**：現行のトピック中立・固定ルールによるクエリ拡張。
   - **B1**：Coverage Stateを利用するルールベースの追加探索。
   - **B2**：B1と同等の観測情報を受け取るLLM Query Planner。
   - **B3**：EmbeddingでRegion/Claim候補を検出しLLM Plannerと組み合わせる。
2. 同一の探索予算・評価入力で比較し、**Event Recall / Tail Event Recall / Minority Claim Recall / Claim Coverage / Grounding品質 / Event誤マージ / 重複率 / 限界Confirmed Gain / 検索・推論時間 / tokenコスト**を測る。発見率に関しては新URL件数ではなく重複解消後のEvent/Claimを評価する。
3. **凍結したソーススナップショットと人手確認済みのEvent/Claim/Evidence正解ラベル**を使うオフライン評価を基礎とし、ライブSearXNG/Fetch評価を別に記録する。正解集合は探索・人手アノテーションの到達範囲に依存し、未知の全Eventを含む保証をしない。
4. 停止品質は、停止後に別戦略で追加探索する監査を設け、重要Event/Claimがどれだけ残ったかから評価する。Embedding上の密度を真の網羅率や信頼性と同一視しない。
5. 段階的に実装する。
   - **P0**：評価契約、探索状態・予算境界のデータ構造、オフラインテスト。現行実行パスは維持。
   - **P1**：原文バイト列の不変アーカイブ、EventMention / Atomic Claim / Evidence の来歴とVerification。
   - **P2**：疎なCoverage Space、Builder/Evaluator、カテゴリのライフサイクルと観測記録。
   - **P3**：Controllerのラウンド単位適応制御、B1のルールベースPlanner、停止・Budget監査。
   - **P4**：B2/B3は品質とコストの比較結果に応じて選択導入。B（検索単位再配分）も同様。
   - **P5**：隔離・認証境界を守った実運用、実績収集、回帰テストによる継続改善。
6. 実行時のソース・取得失敗・プロンプト・出力・評価を再現可能にする。公開向け認証なしAPIの外部開放はしない。ユーザー長期プロファイル学習や調査横断の自動カテゴリ統合は初期スコープ外とする。
7. 設計方針そのものと **比率、閾値、LLM/Embedding構成といった検証待ちの仮説**を区別する。実装から課題が発見されたら、実測に基づき改訂し、必要な場合は新ADRで判断を置き換える。

## Rationale

「複雑そうだから採用」ではなく、同等条件での実測品質に基づいて実装・保守コストに見合う方式を選べる。

## Alternatives considered

- **最初から全部を実装して統合評価のみ行う**：要因分離ができず、高コスト。
- **オンライン評価だけで比較**：検索エンジンの変動や外乱で再現性が低い。
- **Embedding/LLM導入を先に決め、ルールベースを省く**：効果を説明するBaselineが失われる。

## Consequences

手作業のラベル付け・固定fixture整備が先行コストになる。反面、性能悪化を早期に検出できる。既存の `AGENTS.md` に従いRuff、mypy、pytestを確認し、ライブ実行を省略した場合は明記する。

## Revisit conditions

ラベル付き評価集合が実運用から大きく乖離した場合、B2/B3が重要なTail Eventを継続的に改善した場合、逐次制御の追加コストに見合う成果が実証された場合。
