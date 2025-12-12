# GAS統合ガイド - Classroom & Driveルート統合版

**作成日**: 2025-12-12
**対象**: Google Apps Script (GAS) からSupabaseへのデータ投入仕様

---

## 📋 概要

このガイドでは、ClassroomルートとDriveルートを統合し、GASからSupabaseへデータを投入する方法を説明します。

### 統合前の構成
```
【Classroomルート】
GAS → Supabase (documents) → reprocess_classroom_documents_v2.py

【ファイルルート】
daily_sync.py → Google Drive → TwoStageIngestionPipeline
```

### 統合後の構成
```
【統一ルート】
GAS (Classroom & Drive監視)
  ↓
Supabase (documents テーブル - メタデータのみ)
  ↓
Supabase (document_reprocessing_queue - 処理キュー)
  ↓
reprocess_classroom_documents_v2.py (定期実行 - AI処理)
  ↓
完了 (full_text, summary, metadata等が生成される)
```

---

## 🎯 設計原則

### 責任の分離
- **GAS**: データ収集のみ（AI処理なし）
- **Python**: AI処理のみ（Gemini分類、Claude抽出、チャンク化等）

### 処理フロー
1. GASが情報をSupabaseに投入（`processing_status = 'pending'`）
2. GASが同時に`document_reprocessing_queue`にタスクを追加
3. Python（reprocess_classroom_documents_v2.py）が定期実行でキューを処理
4. AI処理完了後、`processing_status = 'completed'` に更新

---

## 📊 Supabaseへの投入仕様

### documents テーブル

#### 必須フィールド

| フィールド | 型 | 説明 | 例 |
|-----------|---|------|---|
| `source_type` | VARCHAR(50) | データソースの種類 | `'classroom'`, `'classroom_text'`, `'drive'` |
| `source_id` | VARCHAR(500) | 一意識別子（重複チェック用） | Google Drive ファイルID、Classroom投稿ID |
| `file_name` | VARCHAR(500) | ファイル名 | `'数学課題.pdf'`, `'text_only'` |
| `workspace` | VARCHAR(50) | ワークスペース | `'ikuya_classroom'`, `'ema_classroom'` |
| `doc_type` | VARCHAR(100) | ドキュメントタイプ | クラス名（例: `'5年B組'`, `'数学I'`） |
| `processing_status` | VARCHAR(50) | 処理状態 | **`'pending'`** (固定) |
| `ingestion_route` | VARCHAR(50) | 取り込みルート | `'classroom'`, `'drive'` |

#### オプションフィールド

| フィールド | 型 | 説明 | 例 |
|-----------|---|------|---|
| `source_url` | TEXT | ソースURL | Google DriveのURL |
| `full_text` | TEXT | 全文（Classroom投稿本文） | `'【課題】期末試験の範囲について'` |
| `metadata` | JSONB | メタデータ | `{"course_name": "数学I", "sender_name": "田中先生"}` |
| `created_at` | TIMESTAMP | 作成日時 | `'2025-12-12T10:30:00Z'` |

#### Classroom固有フィールド（拡張）

| フィールド | 型 | 説明 | 例 |
|-----------|---|------|---|
| `classroom_sender` | VARCHAR(200) | 送信者名 | `'田中太郎'` |
| `classroom_sender_email` | VARCHAR(500) | 送信者メール | `'tanaka@example.com'` |
| `classroom_sent_at` | TIMESTAMP | 送信日時 | `'2025-12-10T15:00:00Z'` |
| `classroom_subject` | TEXT | 件名/タイトル | `'期末試験の範囲について'` |
| `classroom_course_id` | VARCHAR(200) | コースID | Classroom API のコースID |
| `classroom_course_name` | VARCHAR(500) | コース名 | `'5年B組'` |

---

## 🔧 GASからの投入パターン

### パターン1: Classroom添付ファイル

```javascript
{
  source_type: 'classroom',
  source_id: '<Google Drive ファイルID>',  // コピー先のファイルID
  source_url: '<Google Drive URL>',
  file_name: '数学課題.pdf',
  full_text: '【課題】期末試験の範囲について\n...',  // 投稿本文
  workspace: 'ikuya_classroom',
  doc_type: '数学I',  // クラス名
  processing_status: 'pending',  // ★固定
  ingestion_route: 'classroom',

  classroom_sender: '田中太郎',
  classroom_sender_email: 'tanaka@example.com',
  classroom_sent_at: '2025-12-10T15:00:00Z',
  classroom_subject: '期末試験の範囲について',
  classroom_course_id: '12345',
  classroom_course_name: '数学I',

  metadata: {
    'original_classroom_id': '<元のファイルID>',
    'post_id': '<投稿ID>',
    'post_type': '課題',
    'course_name': '数学I',
    'sender_name': '田中太郎'
  },
  created_at: '2025-12-12T10:30:00Z'
}
```

### パターン2: Classroomテキストのみ投稿

```javascript
{
  source_type: 'classroom_text',
  source_id: '<Classroom投稿ID>',  // 投稿IDを一意識別子として使用
  source_url: null,
  file_name: 'text_only',
  full_text: '【お知らせ】明日は休講です',
  workspace: 'ikuya_classroom',
  doc_type: '数学I',
  processing_status: 'pending',  // ★固定
  ingestion_route: 'classroom',

  classroom_sender: '田中太郎',
  classroom_sender_email: 'tanaka@example.com',
  classroom_sent_at: '2025-12-10T15:00:00Z',
  classroom_subject: '明日は休講です',
  classroom_course_id: '12345',
  classroom_course_name: '数学I',

  metadata: {
    'post_type': 'お知らせ',
    'course_name': '数学I',
    'sender_name': '田中太郎'
  },
  created_at: '2025-12-12T10:30:00Z'
}
```

### パターン3: Google Driveファイル（新規）

```javascript
{
  source_type: 'drive',
  source_id: '<Google Drive ファイルID>',
  source_url: '<Google Drive URL>',
  file_name: '会議資料.pdf',
  workspace: 'business',  // または 'personal'
  doc_type: null,  // AI分類に任せる場合はnull
  processing_status: 'pending',  // ★固定
  ingestion_route: 'drive',

  metadata: {
    'folder_name': '2025年度資料',
    'mime_type': 'application/pdf'
  },
  created_at: '2025-12-12T10:30:00Z'
}
```

---

## 🔄 自動キュー追加の仕組み

### 方法1: GASから直接キュー追加（推奨）

GASが`documents`テーブルにINSERT後、`document_reprocessing_queue`にも追加：

```javascript
// Step 1: documentsテーブルに投入
const insertResponse = UrlFetchApp.fetch(
  SUPABASE_URL + '/rest/v1/documents?on_conflict=source_id',
  {
    method: 'post',
    headers: { /* ... */ },
    payload: JSON.stringify(recordsToInsert)
  }
);

// Step 2: 挿入されたドキュメントIDを取得
const insertedDocs = JSON.parse(insertResponse.getContentText());

// Step 3: キューに追加
const queueRecords = insertedDocs.map(doc => ({
  document_id: doc.id,
  reprocess_reason: 'classroom_initial_import',
  reprocess_type: 'full',
  priority: 0,
  preserve_workspace: true,
  original_file_name: doc.file_name,
  original_workspace: doc.workspace,
  original_doc_type: doc.doc_type,
  original_source_id: doc.source_id,
  created_by: 'gas_classroom_sync'
}));

UrlFetchApp.fetch(
  SUPABASE_URL + '/rest/v1/document_reprocessing_queue',
  {
    method: 'post',
    headers: { /* ... */ },
    payload: JSON.stringify(queueRecords)
  }
);
```

### 方法2: Supabase Trigger（自動化）

**より推奨**: Supabaseのトリガーで自動化

```sql
-- documents テーブルへのINSERT時に自動でキューに追加
CREATE OR REPLACE FUNCTION auto_add_to_reprocessing_queue()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  -- processing_status が pending の場合のみキューに追加
  IF NEW.processing_status = 'pending' THEN
    INSERT INTO document_reprocessing_queue (
      document_id,
      reprocess_reason,
      reprocess_type,
      priority,
      preserve_workspace,
      original_file_name,
      original_workspace,
      original_doc_type,
      original_source_id,
      created_by
    ) VALUES (
      NEW.id,
      CASE
        WHEN NEW.ingestion_route = 'classroom' THEN 'classroom_initial_import'
        WHEN NEW.ingestion_route = 'drive' THEN 'drive_initial_import'
        ELSE 'initial_import'
      END,
      'full',
      0,
      true,
      NEW.file_name,
      NEW.workspace,
      NEW.doc_type,
      NEW.source_id,
      'supabase_trigger'
    );
  END IF;

  RETURN NEW;
END;
$$;

-- トリガーを作成
CREATE TRIGGER trigger_auto_queue_on_insert
AFTER INSERT ON documents
FOR EACH ROW
EXECUTE FUNCTION auto_add_to_reprocessing_queue();
```

**メリット**:
- GAS側の実装がシンプル（documentsへのINSERTのみ）
- キューへの追加漏れがない
- 一貫性が保証される

---

## ⚙️ Python側の処理（reprocess_classroom_documents_v2.py）

### 定期実行

```bash
# cron等で定期実行（例: 10分ごと）
*/10 * * * * cd /path/to/project && python reprocess_classroom_documents_v2.py --process-queue --limit=50
```

### 処理フロー

1. `document_reprocessing_queue`から`status = 'pending'` or `'failed'`（リトライ対象）を取得
2. 優先順位: `pending` > `failed`、`priority` DESC、`created_at` ASC
3. AI処理実行:
   - **StageA**: Gemini 2.5 Flash（分類）
   - **StageB**: Gemini 2.5 Pro（Vision）
   - **StageC**: Claude Haiku 4.5（詳細抽出）
4. チャンク化: メタデータチャンク + 小チャンク + 大チャンク
5. `documents.processing_status = 'completed'` に更新
6. `document_reprocessing_queue.status = 'completed'` に更新

### リトライ戦略

- **最大試行回数**: 3回（`max_attempts = 3`）
- **自動リトライ**: `status = 'failed'` かつ `attempt_count < max_attempts`
- **優先順位**: `pending` を優先、`failed` は後回し

---

## 📝 実装チェックリスト

### GAS側

- [ ] `processing_status = 'pending'` を設定
- [ ] `ingestion_route` を設定（`'classroom'` or `'drive'`）
- [ ] Classroom固有フィールドを設定（該当する場合）
- [ ] `on_conflict=source_id` で重複回避
- [ ] （オプション）`document_reprocessing_queue` に手動追加
- [ ] （推奨）Supabase Triggerで自動キュー追加を設定

### Supabase側

- [ ] Trigger `trigger_auto_queue_on_insert` を作成
- [ ] `get_next_reprocessing_task` 関数がfailedリトライに対応

### Python側

- [ ] `reprocess_classroom_documents_v2.py` を定期実行（cron等）
- [ ] ログ監視体制を構築
- [ ] エラー通知（失敗が3回連続した場合）

---

## 🔍 トラブルシューティング

### Q: ドキュメントが処理されない

**確認事項**:
1. `documents.processing_status` が `'pending'` になっているか
2. `document_reprocessing_queue` にタスクが追加されているか
3. `reprocess_classroom_documents_v2.py` が正常に動作しているか

```sql
-- 未処理のドキュメントを確認
SELECT id, file_name, processing_status, created_at
FROM documents
WHERE processing_status = 'pending'
ORDER BY created_at DESC
LIMIT 10;

-- キューの状態を確認
SELECT status, COUNT(*) as count
FROM document_reprocessing_queue
GROUP BY status;
```

### Q: 処理が失敗し続ける

**確認事項**:
1. エラーメッセージを確認（`document_reprocessing_queue.last_error_message`）
2. API制限に達していないか（Gemini, Claude）
3. ファイルにアクセスできるか（権限、存在確認）

```sql
-- 失敗したタスクの詳細
SELECT
  q.document_id,
  q.original_file_name,
  q.attempt_count,
  q.last_error_message,
  q.last_attempt_at
FROM document_reprocessing_queue q
WHERE q.status = 'failed'
  AND q.attempt_count >= q.max_attempts
ORDER BY q.last_attempt_at DESC
LIMIT 10;
```

---

## 📚 関連ドキュメント

- `PROJECT_EVALUATION_REPORT_20251212.md`: プロジェクト全体評価
- `reprocess_classroom_documents_v2.py`: 再処理スクリプト
- `database/schema_updates/v9_add_reprocessing_queue.sql`: キューテーブル定義
- `pipelines/two_stage_ingestion.py`: AI処理パイプライン

---

## 🎉 まとめ

### 統合のメリット

1. **コード重複削減**: `daily_sync.py` が不要に
2. **責任の明確化**: GAS=データ収集、Python=AI処理
3. **処理の一貫性**: 単一のパイプラインで管理
4. **リトライ機能**: 自動で最大3回リトライ
5. **運用コスト削減**: 同じフローで全データを処理

### 次のステップ

1. Supabase Triggerを作成
2. 既存のGASスクリプトを更新（`processing_status = 'pending'` を追加）
3. `reprocess_classroom_documents_v2.py` を定期実行に設定
4. `daily_sync.py` をアーカイブ

---

**最終更新**: 2025-12-12
**作成者**: Claude Code (Sonnet 4.5)
