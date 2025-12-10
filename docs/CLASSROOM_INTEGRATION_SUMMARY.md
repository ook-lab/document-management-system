# Classroom統合とSupabase修正のまとめ

## 実装日: 2025-12-10

## 概要

Google ClassroomからSupabaseへのデータ統合を改善し、Classroom固有の情報（送信者、送信日時、件名など）を正しく保存できるようにしました。また、source_typeの上書き問題を修正し、テキスト抽出とVision処理のモデル情報を記録できるようにしました。

## 実施した変更

### 1. データベーススキーマの拡張

**ファイル**: `database/migration_classroom_fields.sql`

#### 追加したフィールド

| フィールド名 | データ型 | 説明 |
|------------|---------|------|
| `classroom_sender` | VARCHAR(500) | Classroom送信者の表示名 |
| `classroom_sender_email` | VARCHAR(500) | Classroom送信者のメールアドレス |
| `classroom_sent_at` | TIMESTAMP WITH TIME ZONE | Classroom送信日時 |
| `classroom_subject` | TEXT | Classroom投稿の件名・タイトル |
| `classroom_course_id` | VARCHAR(200) | ClassroomコースID |
| `classroom_course_name` | VARCHAR(500) | Classroomコース名 |
| `text_extraction_model` | TEXT | テキスト抽出に使用したモデル（pdfplumber等） |
| `vision_model` | TEXT | Vision処理に使用したAIモデル（Gemini Vision等） |

#### 実行方法

1. Supabase SQLエディタを開く
2. `migration_classroom_fields.sql` の内容をコピー
3. SQLエディタに貼り付けて実行

### 2. GASスクリプトの修正

**ファイル**: `gas/ClassroomToSupabase_updated.gs`

#### 主な変更点

1. **送信者情報の取得**
   ```javascript
   const userProfile = Classroom.UserProfiles.get(creatorUserId);
   senderName = userProfile.name.fullName || 'Unknown';
   senderEmail = userProfile.emailAddress || '';
   ```

2. **件名の設定**
   - お知らせ: テキストの最初の100文字を件名として使用
   - 課題: `title` を件名として使用
   - 資料: `title` を件名として使用

3. **Supabaseに送信するデータ構造**
   ```javascript
   {
     source_type: 'classroom' または 'classroom_text',
     classroom_sender: senderName,
     classroom_sender_email: senderEmail,
     classroom_sent_at: creationTime,
     classroom_subject: postSubject,
     classroom_course_id: COURSE_ID,
     classroom_course_name: COURSE_NAME,
     // ... その他のフィールド
   }
   ```

#### 使用方法

1. Google Apps Scriptエディタで既存のスクリプトを開く
2. `ClassroomToSupabase_updated.gs` の内容で更新
3. スクリプトを保存して実行

### 3. Pythonパイプラインの修正

**ファイル**: `pipelines/two_stage_ingestion.py`

#### 主な変更点

1. **source_typeの上書き問題を修正**
   ```python
   async def process_file(
       self,
       file_meta: Dict[str, Any],
       workspace: str = "personal",
       force_reprocess: bool = False,
       source_type: str = "drive"  # 新規追加
   ) -> Optional[Dict[str, Any]]:
   ```

   - `source_type` を引数として追加（デフォルト値は `"drive"`）
   - `file_meta` に `source_type` が含まれていればそちらを優先

2. **テキスト抽出とVisionモデルの記録**
   ```python
   text_extraction_model = base_metadata.get('extractor', None)
   vision_model = base_metadata.get('vision_model', None)

   document_data = {
       ...
       "text_extraction_model": text_extraction_model,
       "vision_model": vision_model,
       ...
   }
   ```

3. **GAS由来フィールドの保持**
   ```python
   preserve_fields = [
       'doc_type',
       'workspace',
       'source_type',
       'classroom_sender',
       'classroom_sender_email',
       'classroom_sent_at',
       'classroom_subject',
       'classroom_course_id',
       'classroom_course_name'
   ] if force_reprocess else []
   ```

   再処理時にGASから送信されたClassroom情報を保持するように設定

## 動作フロー

### Classroomからの取り込みフロー

```
1. GASスクリプトが1時間ごとに実行
   ↓
2. アクティブなコース一覧を取得
   ↓
3. 各コースの投稿を取得（お知らせ、課題、資料）
   ↓
4. 各投稿の送信者情報を取得
   ↓
5. Classroom情報（送信者、日時、件名等）を含めてSupabaseに送信
   ↓
6. Supabaseに保存（source_type='classroom' または 'classroom_text'）
   ↓
7. Pythonパイプラインが処理（Stage 1 → Stage 2）
   ↓
8. 再処理時もClassroom情報は保持される
```

## データの流れ

### GAS → Supabase

```json
{
  "source_type": "classroom",
  "source_id": "file_id_or_post_id",
  "file_name": "ファイル名 or text_only",
  "classroom_sender": "田中太郎",
  "classroom_sender_email": "tanaka@example.com",
  "classroom_sent_at": "2025-12-10T10:30:00Z",
  "classroom_subject": "今日の宿題について",
  "classroom_course_id": "123456789",
  "classroom_course_name": "5年B組",
  "workspace": "ikuya_classroom",
  "doc_type": "5年B組",
  "full_text": "投稿の本文...",
  "metadata": {
    "post_type": "お知らせ",
    "sender_name": "田中太郎",
    "sender_email": "tanaka@example.com"
  }
}
```

### Pythonパイプライン処理後

```json
{
  // GASから送信された情報（保持される）
  "source_type": "classroom",
  "classroom_sender": "田中太郎",
  "classroom_sender_email": "tanaka@example.com",
  "classroom_sent_at": "2025-12-10T10:30:00Z",
  "classroom_subject": "今日の宿題について",
  "classroom_course_id": "123456789",
  "classroom_course_name": "5年B組",

  // Pythonパイプラインが追加する情報
  "stage1_model": "gemini-2.5-flash",
  "stage2_model": "claude-haiku-4-5-20251001",
  "text_extraction_model": "pdfplumber",
  "vision_model": "gemini-2.5-flash-vision",
  "summary": "AI生成の要約...",
  "embedding": [...],
  "confidence": 0.92,
  "processing_status": "completed"
}
```

## トラブルシューティング

### 問題: Classroom情報が空欄になる

**原因**: データベースマイグレーションが実行されていない

**解決策**:
1. `database/migration_classroom_fields.sql` をSupabase SQLエディタで実行
2. GASスクリプトを再実行

### 問題: source_typeが'drive'で上書きされる

**原因**: 古いPythonコードが動作している

**解決策**:
1. `pipelines/two_stage_ingestion.py` が最新版であることを確認
2. Pythonプロセスを再起動

### 問題: 送信者情報の取得に失敗する

**原因**: Google Classroom APIの権限不足

**解決策**:
1. GASスクリプトで `Classroom.UserProfiles.get()` の権限を承認
2. スクリプト実行時に表示される権限リクエストを承認

## 今後の拡張

### 検討中の機能

1. **コメントの取得**
   - 投稿に対するコメントも取得してmetadataに保存

2. **提出状況の記録**
   - 課題の場合、提出状況も記録

3. **添付ファイルの種類別処理**
   - PDF以外のファイル（画像、動画等）も処理

4. **既読管理**
   - 既に処理済みの投稿をスキップする仕組みの改善

## 参考資料

- [Google Classroom API - UserProfiles](https://developers.google.com/classroom/reference/rest/v1/userProfiles)
- [Supabase PostgreSQL Functions](https://supabase.com/docs/guides/database/functions)
- [PDF処理 - pdfplumber](https://github.com/jsvine/pdfplumber)

## 変更履歴

| 日付 | 変更内容 | 担当者 |
|------|---------|--------|
| 2025-12-10 | Classroom情報フィールド追加、source_type修正、モデル情報記録 | Claude Code |
