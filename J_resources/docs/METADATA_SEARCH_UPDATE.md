# メタデータ検索機能の追加

## 問題点

現在、`weekly_schedule`などのメタデータはデータベースに保存されているものの、検索機能では見つけることができません。
具体的には：
- 「12月5日」や「委員会活動」などで検索してもヒットしない
- metadataフィールドの内容が埋め込みベクトル生成の対象外
- metadataフィールドの内容が全文検索（TSVector）の対象外

## 解決策

### 1. Python側の修正（完了）

**ファイル**: `pipelines/two_stage_ingestion.py`

- `flatten_metadata_to_text()` 関数を追加
  - `weekly_schedule`、`text_blocks`、`special_events`等を平坦化
  - 検索可能なテキストに変換

- Embedding生成時にメタデータを含める
  - 本文（7000文字）+ メタデータ（1000文字）を結合してembedding生成
  - これにより、セマンティック検索でメタデータがヒットするようになる

### 2. データベース側の修正（要適用）

**ファイル**: `database/schema_updates/add_metadata_to_search.sql`

このSQLファイルをSupabaseのSQL Editorで実行してください。

#### 実行内容：

1. **新カラム追加**: `documents.metadata_searchable_text`
   - メタデータから抽出した検索可能テキストを保存

2. **PostgreSQL関数**: `extract_searchable_metadata()`
   - JSONB形式のmetadataから検索可能テキストを抽出
   - `weekly_schedule`の日付、イベント、科目等をすべて展開

3. **トリガー更新**: `documents_tsvector_update_trigger()`
   - `full_text` + `metadata_searchable_text` を結合してTSVectorを生成
   - 新規データの挿入/更新時に自動実行

4. **既存データ更新**
   - 既存の全ドキュメントのメタデータを再インデックス

5. **インデックス作成**
   - `metadata_searchable_text`のGINインデックスを作成

### 3. UI側の修正（完了）

**ファイル**: `ui/review_ui.py`
- JSON表示を `expanded=False` → `expanded=True` に変更
- 入れ子の配列も完全に表示されるようになった

**ファイル**: `ui/components/table_editor.py`
- テーブル高さを `height=400` → `height=600` に変更
- より多くの行が一度に表示されるようになった

## 適用手順

### ステップ1: データベース更新

1. Supabaseダッシュボードにログイン
2. SQL Editorを開く
3. `database/schema_updates/add_metadata_to_search.sql` の内容を貼り付け
4. 実行（既存データが多い場合は数分かかる可能性あり）

### ステップ2: 既存データの再取り込み（推奨）

メタデータを含むembeddingを生成するため、既存ドキュメントを再処理します：

```bash
# 学年通信など重要なドキュメントを再取り込み
python -m pipelines.two_stage_ingestion --file-id <Google Drive File ID>
```

または、すべてのドキュメントを一括再処理：

```python
# scripts/reindex_all_documents.py を実行
```

### ステップ3: 動作確認

1. Streamlit UIを起動
```bash
streamlit run ui/review_ui.py
```

2. 検索テスト
   - 「12月5日」で検索
   - 「委員会活動」で検索
   - 「金曜日」で検索

3. 結果確認
   - 学年通信がヒットすること
   - weekly_scheduleの内容が検索できること

## 確認用SQLクエリ

### metadata_searchable_text が生成されているか確認
```sql
SELECT
    file_name,
    doc_type,
    LEFT(metadata_searchable_text, 200) as searchable_preview
FROM documents
WHERE metadata_searchable_text IS NOT NULL
LIMIT 10;
```

### 特定のキーワードで検索テスト
```sql
SELECT
    file_name,
    metadata_searchable_text
FROM documents
WHERE
    metadata_searchable_text LIKE '%12月5日%'
    OR metadata_searchable_text LIKE '%委員会%'
    OR full_text_tsv @@ plainto_tsquery('simple', '12月5日');
```

### TSVectorが正しく更新されているか確認
```sql
SELECT
    file_name,
    ts_rank(full_text_tsv, plainto_tsquery('simple', '委員会活動')) as rank
FROM documents
WHERE full_text_tsv @@ plainto_tsquery('simple', '委員会活動')
ORDER BY rank DESC
LIMIT 5;
```

## 期待される効果

### Before（修正前）
- ❌ 「12月5日」で検索してもヒットしない
- ❌ 「委員会活動」で検索してもヒットしない
- ❌ weekly_scheduleのデータが検索対象外
- ❌ JSON表示が折りたたまれていて見にくい
- ❌ テーブルが小さくて全データが見えない

### After（修正後）
- ✅ 「12月5日」で学年通信がヒット
- ✅ 「委員会活動」でイベントが見つかる
- ✅ 日付、曜日、科目名、イベント名すべてが検索可能
- ✅ JSON表示がデフォルトで展開され、全データが見える
- ✅ テーブル高さが増加し、スクロールが減る
- ✅ セマンティック検索でもメタデータがマッチ

## トラブルシューティング

### Q: SQLエラーが出る
A: PostgreSQL 12以上が必要です。Supabaseは対応しているはずですが、エラーメッセージを確認してください。

### Q: 既存データが検索できない
A: `UPDATE documents SET ...` のクエリが完了するまで待ってください。数千件のドキュメントがある場合は時間がかかります。

### Q: 新規データは検索できるが、古いデータが検索できない
A: トリガーは新規データのみに適用されます。既存データは手動でUPDATEクエリを実行する必要があります。

### Q: Embeddingを再生成したい
A: `pipelines/two_stage_ingestion.py` を使って該当ドキュメントを再取り込みしてください。

## 関連ファイル

- `pipelines/two_stage_ingestion.py` - Embedding生成ロジック
- `database/schema_updates/add_metadata_to_search.sql` - データベーススキーマ更新
- `ui/review_ui.py` - JSON表示設定
- `ui/components/table_editor.py` - テーブル表示設定
- `fix_sql_function.sql` - 検索関数（既存）

## 今後の改善案

1. **メタデータ専用検索フィルタ**
   - UIに「メタデータのみ検索」チェックボックスを追加

2. **ファセット検索**
   - 日付範囲、曜日、科目名でフィルタリング

3. **ハイライト表示**
   - 検索結果でマッチした部分を強調表示

4. **構造化クエリ**
   - JSONPathを使った高度な検索（例: `$.weekly_schedule[?(@.day=='金')]`）
