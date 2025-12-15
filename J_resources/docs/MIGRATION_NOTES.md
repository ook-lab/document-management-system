# データベーススキーマ変更: full_text → attachment_text

## 変更日
2025-12-13

## 変更理由
`full_text`というカラム名が誤解を招いていました。実際にはドキュメント全体のテキストではなく、**添付ファイルから抽出したテキストのみ**を保存していました。

## 変更内容

### データベーススキーマ
- **変更前**: `documents.full_text`
- **変更後**: `documents.attachment_text`
- **SQL**: `database/schema_updates/rename_full_text_to_attachment_text.sql`

### データの意味の明確化

| カラム名 | 内容 | 例 |
|---------|------|---|
| `attachment_text` | 添付ファイル（PDF, DOCX等）から抽出したテキスト | PDFの内容 |
| `classroom_subject` | Classroom投稿の件名 | "明日の課題について" |
| `classroom_post_text` | Classroom投稿の本文 | "明日までに提出してください" |
| `summary` | AI生成のサマリー | "数学の課題..." |

### 修正したファイル

#### 主要パイプライン
- [x] `pipelines/two_stage_ingestion.py` (404行目)
- [x] `pipelines/gmail_ingestion.py` (667行目)

#### 再処理スクリプト
- [x] `reprocess_classroom_documents_v2.py` (405行目)

#### UIコンポーネント
- [x] `app.py` (436行目)
- [x] `ui/review_ui.py` (671行目)
- [x] `ui/components/email_viewer.py` (118, 236, 323行目)
- [x] `ui/email_inbox.py` (42行目)

#### その他
- [ ] `core/ai/stageC_extractor.py` - パラメータ名`full_text`は関数インターフェースのため保留
- [ ] `scripts/one_time/*` - ワンタイムスクリプトのため必要に応じて個別対応

### 修正不要なファイル

以下のファイルは関数パラメータ名として`full_text`を使用していますが、これは「抽出済みテキスト」を意味するため、カラム名とは関係ありません：

- `core/ai/stageC_extractor.py` - `extract_metadata(full_text, ...)`
- `ui/components/manual_text_correction.py` - Stage 2再実行時のパラメータ

## 今後の対応が必要な箇所

### scripts/one_time/ ディレクトリのスクリプト
以下のワンタイムスクリプトは、実行時にエラーが出る可能性があります。必要に応じて`full_text`→`attachment_text`に修正してください：

- `scripts/one_time/migrate_to_chunks.py`
- `scripts/one_time/regenerate_all_embeddings.py`
- `scripts/one_time/regenerate_embeddings_simple.py`
- `scripts/one_time/emergency_diagnose_and_fix.py`
- `ui/utils/stageC_reprocessor.py`

## ロールバック方法

万が一問題が発生した場合、以下のSQLでロールバック可能です：

```sql
ALTER TABLE documents
RENAME COLUMN attachment_text TO full_text;
```

ただし、コードも元に戻す必要があります。

## テスト確認事項

- [ ] 新規ドキュメント取り込み（PDF添付ファイルあり）
- [ ] Classroom投稿（添付ファイルなし）の再処理
- [ ] メール取り込み
- [ ] UI上での表示（検索、詳細表示）
- [ ] 既存データの正常表示

## 影響を受ける機能

✅ **影響なし（正常動作）:**
- ドキュメント検索
- チャンク化処理（attachment_textは使用していないため）
- AI処理（その場で抽出したextracted_textを使用）

⚠️ **要確認:**
- email_inbox.pyのキーワード検索（カラム名変更済み）
- UIでのテキスト表示（attachment_text使用箇所修正済み）
