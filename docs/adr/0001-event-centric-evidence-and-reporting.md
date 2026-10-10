# ADR-0001: Event 中心の情報統合・原文根拠の検証・Coverage-first な出力

- Status: **Accepted（設計合意、実装完了ではない）**
- Date: 2026-10-10
- Context: [Issue #4](https://github.com/upiscium/TSUZRI/issues/4)

## Context

現行の単発 Search → Fetch → Map → Reduce では、同じ出来事を報じる複数ページの重複、1ページに含まれる複数の出来事、引用先の原文によらない主張の取り扱いが曖昧になる。ページ単位の件数は調査の網羅性を表さない。

## Decision

1. 情報モデルは **Topic → Storyline → Event** を基礎とする。Storyline は経時的に発展する話題、Event は具体的な出来事。1 Event は複数 Storyline に属してよく、1文書は複数 Event を言及してよい。
2. 文書から先に **EventMention** を抽出し、人物・主体、行為、対象、時刻・期間などを使って Event 同一性を後から判定する。関係は `same_as`, `possibly_same_as`, `follows`, `responds_to`, `related_to` を区別する。曖昧なら独立 Event と関係を残す。推移律による安易な連鎖マージは禁止する。
3. **Atomic Claim** は単独で原文と照合できる最小の命題とし、発言主体・時制・条件・不確実性を失わない。Claim の `equivalent`, `supports`, `contradicts`, `qualifies`, `related` は区別し、見かけの矛盾を同じ時間・断定度と決めつけない。
4. **Archive Authority** は意味処理・テキスト抽出の前に、取得した **原本レスポンスのバイト列** とハッシュ、要求URL、最終URL、取得時刻、取得状況を保持する。抽出・変換・Claim/Evidence には原本への追跡可能な参照（原文箇所と変換の系譜）を持たせる。後段は原本を書き換えない。永続化媒体（ファイルストア等）は別途実装で選択する。
5. **Extraction と Verification の責務を分離**する。Verification Authority が決めるのは「記録済み原文がそのClaimの根拠となっているか」であり、客観的な真偽や発言者・団体の信用度ではない。
6. 根拠判定と出力は次の扱いにする。
   - `GROUNDED`：原文に対応する主張として Main に記載可能（出典・帰属を保持）。
   - `CONTESTED`：矛盾するそれぞれのClaimが原文に根拠を持つとき、争点を明記して Main に記載。
   - `UNVERIFIED`：原文根拠が未確認の候補は理由と不足根拠を添えて Appendix に隔離。
   - `REJECTED`：原文と整合しない抽出結果は監査記録に残し、報告本文に使用しない。
7. **Coverage-first / importance-adaptive** な出力にする。「掲載するか」と「どのくらい詳しく説明するか」を分離し、重要・関連性の高いEventを詳述、その他の関連Eventは簡潔に記載する。量が多いときは本文と網羅的なEvent一覧を分け、未調査範囲や省略理由を明示する。

## Rationale

同じURLが増えても新規Eventが増えるとは限らない。また、Minority Claim や矛盾するClaimを過度な要約・マージで消さず、読者が元資料まで遡れる構造が必要になる。

## Alternatives considered

- **ページ単位の要約を主な統合単位にする**：重複と複数Event混在を扱いにくいため不採用。
- **LLM要約をそのまま根拠とみなす**：原文支持の確認にならないため不採用。
- **人物・組織の信頼性をスコアリングして真偽判定する**：今回の目的を超えるため対象外。

## Consequences

EventMention同一性、Claim分割、原本保存、Evidence検証が必要で、実装コストが増える。一方、検索・統合・出力・評価の責任範囲を明確化できる。最初から永続Knowledge Graphや調査を横断したユーザープロファイル学習は実装しない。

## Revisit conditions

独立アノテーションによる Event の誤マージ・分割、Atomic Claim の歪み、原文支持の誤認、重要なTail Eventの省略が測定された場合に見直す。
