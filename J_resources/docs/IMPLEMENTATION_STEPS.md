# Classroom統合修正 - 実装手順

## 実施日: 2025-12-10

このドキュメントでは、Classroom情報の空欄問題を解決するための実装手順を説明します。

## 🎯 解決する問題

1. **Classroom情報が空欄** - 送信者、送信日時、件名がSupabaseに保存されない
2. **source_typeが上書きされる** - 'classroom'が'drive'で上書きされる
3. **モデル情報の不足** - テキスト抽出とVisionで使用したモデルが区別されない

## 📝 実装手順

### ステップ1: Supabaseでデータベースマイグレーションを実行

1. Supabaseダッシュボードにログイン
2. SQL Editorを開く
3. 以下のファイルの内容をコピーして実行:

```sql
-- ファイル: database/migration_classroom_fields.sql
```

**実行内容**:
- Classroom情報用フィールド（送信者、送信日時、件名等）を追加
- テキスト抽出とVisionモデル情報用フィールドを追加
- インデックスを作成

**確認方法**:
```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'documents'
AND column_name LIKE 'classroom_%'
ORDER BY column_name;
```

### ステップ2: GASスクリプトを更新

1. Google Apps Scriptエディタを開く
2. 既存の `syncAllClassroomsToDocuments` 関数を以下のファイルの内容で置き換え:

```javascript
// ファイル: gas/ClassroomToSupabase_updated.gs
```

**主な変更点**:
- 送信者情報の取得: `Classroom.UserProfiles.get(creatorUserId)`
- 件名の設定: お知らせ/課題/資料ごとに適切な件名を設定
- Classroom固有フィールドの追加: `classroom_sender`, `classroom_sender_email`, etc.

**テスト実行**:
```javascript
function testSingleCourse() {
  // テスト用に1つのコースだけ処理
  // TARGET_COURSESに特定のコースIDを設定して実行
}
```

### ステップ3: Pythonコードを確認（自動的に更新済み）

以下のファイルが修正されています:

**ファイル**: `pipelines/two_stage_ingestion.py`

**変更点**:
1. `source_type` が引数またはfile_metaから取得されるように修正（418行目）
2. `text_extraction_model` と `vision_model` を記録（423-424行目）
3. Classroom情報フィールドを再処理時も保持（455行目）

**確認コマンド**:
```bash
cd /Users/ookuboyoshinori/document_management_system
git diff pipelines/two_stage_ingestion.py
```

## ✅ 動作確認

### 1. データベーススキーマの確認

```sql
-- Supabase SQL Editorで実行
SELECT
  classroom_sender,
  classroom_sender_email,
  classroom_sent_at,
  classroom_subject,
  classroom_course_name,
  source_type,
  file_name
FROM documents
WHERE source_type IN ('classroom', 'classroom_text')
ORDER BY classroom_sent_at DESC
LIMIT 10;
```

**期待される結果**:
- `classroom_sender`: 送信者名が表示される
- `classroom_sender_email`: メールアドレスが表示される
- `classroom_sent_at`: 送信日時が表示される
- `classroom_subject`: 件名が表示される

### 2. モデル情報の確認

```sql
-- Supabase SQL Editorで実行
SELECT
  file_name,
  stage1_model,
  stage2_model,
  text_extraction_model,
  vision_model,
  source_type
FROM documents
WHERE created_at > NOW() - INTERVAL '1 day'
LIMIT 10;
```

**期待される結果**:
- `stage1_model`: 'gemini-2.5-flash' などが表示
- `stage2_model`: 'claude-haiku-4-5-20251001' などが表示
- `text_extraction_model`: 'pdfplumber' などが表示
- `vision_model`: 'gemini-2.5-flash-vision' などが表示

### 3. source_typeの確認

```sql
-- Supabase SQL Editorで実行
SELECT
  source_type,
  COUNT(*) as count
FROM documents
GROUP BY source_type
ORDER BY count DESC;
```

**期待される結果**:
- `classroom`: X件
- `classroom_text`: Y件
- `drive`: Z件
- `gmail`: W件

※ source_typeが適切に保持されていることを確認

## 🐛 トラブルシューティング

### 問題1: Classroom情報がまだ空欄

**原因**: データベースマイグレーションが実行されていない

**解決策**:
```sql
-- Supabaseでフィールドの存在を確認
\d documents
```

フィールドが存在しない場合、ステップ1を再実行

### 問題2: 送信者情報が "Unknown" になる

**原因**: Classroom API の権限不足

**解決策**:
1. GASスクリプトを実行して権限リクエストを承認
2. `Classroom.UserProfiles.get()` の権限を確認

### 問題3: エラーログに "23505" (重複エラー) が表示される

**原因**: 既に同じ source_id のレコードが存在

**解決策**:
- 正常な動作です（重複を防ぐための仕組み）
- 既存レコードは更新されず、スキップされます

### 問題4: source_type が 'drive' で上書きされる

**原因**: 古いPythonコードがキャッシュされている

**解決策**:
```bash
# Pythonプロセスを再起動
pkill -f "python.*app.py"

# または、サーバーを再起動
cd /Users/ookuboyoshinori/document_management_system
python app.py
```

## 📊 データの流れ

```
Google Classroom
  ↓ (GASスクリプト: 1時間ごと)
Supabase documents テーブル
  - source_type: 'classroom' または 'classroom_text'
  - classroom_sender: 送信者名
  - classroom_sender_email: メールアドレス
  - classroom_sent_at: 送信日時
  - classroom_subject: 件名
  ↓ (Pythonパイプライン: 自動処理)
AI処理（Stage 1 → Stage 2）
  - stage1_model: Gemini 2.5 Flash
  - stage2_model: Claude Haiku 4.5
  - text_extraction_model: pdfplumber等
  - vision_model: Gemini Vision等
  ↓
完全なドキュメントレコード
  - 全フィールドが埋まった状態
  - 検索可能なembedding
  - 構造化されたメタデータ
```

## 📚 関連ドキュメント

- [詳細な実装サマリー](docs/CLASSROOM_INTEGRATION_SUMMARY.md)
- [データベーススキーマ](database/schema_v4_unified.sql)
- [マイグレーションSQL](database/migration_classroom_fields.sql)

## 🎉 完了確認

すべてのステップが完了したら、以下を確認してください:

- [ ] Supabaseでマイグレーションを実行した
- [ ] GASスクリプトを更新した
- [ ] GASスクリプトを実行してエラーがないことを確認した
- [ ] Supabaseで新しいレコードにClassroom情報が含まれていることを確認した
- [ ] source_typeが'classroom'または'classroom_text'であることを確認した
- [ ] モデル情報が記録されていることを確認した

---

**実装完了日**: 2025-12-10
**次回レビュー**: 1週間後（動作確認）
