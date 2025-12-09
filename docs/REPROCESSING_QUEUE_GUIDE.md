# ドキュメント再処理キュー - 使用ガイド

## 概要

`document_reprocessing_queue` テーブルを使用した、ドキュメントの再処理管理システムです。
Google Classroom ドキュメントなどの一括再処理を、処理状態を追跡しながら安全に実行できます。

## 主な機能

### ✅ 処理状態の追跡
- `pending` (待機中) → `processing` (処理中) → `completed` (完了) / `failed` (失敗)
- リアルタイムで処理進捗を確認可能

### ✅ 重複処理の防止
- 同じドキュメントの重複処理を自動で防止
- データベースレベルでのロック機構

### ✅ エラーハンドリング
- 失敗したタスクの詳細なエラーメッセージを記録
- 自動リトライ機構（最大3回まで）

### ✅ 並列処理対応
- 複数ワーカーでの並列処理が可能
- `FOR UPDATE SKIP LOCKED` によるデッドロック防止

---

## セットアップ

### 1. データベーステーブルの作成

Supabase SQL Editor で以下のファイルを実行してください：

```sql
-- database/schema_updates/v9_add_reprocessing_queue.sql
```

このSQLファイルは以下を作成します：
- `document_reprocessing_queue` テーブル
- インデックス（高速検索用）
- 便利な関数（キュー追加、タスク取得、完了マークなど）

### 2. スクリプトの確認

新しいスクリプト `reprocess_classroom_documents_v2.py` を使用します。

---

## 基本的な使い方

### 📋 ステップ1: キューの現状確認

```bash
# ドライラン（確認のみ、実際の処理は行わない）
python reprocess_classroom_documents_v2.py --dry-run
```

**出力例:**
```
================================================================================
Google Classroom ドキュメント再処理スクリプト v2
================================================================================
🔍 DRY RUN モード: 実際の処理は行いません

================================================================================
キュー統計
================================================================================
待機中 (pending):       0件
処理中 (processing):    0件
完了   (completed):     0件
失敗   (failed):        0件
スキップ (skipped):     0件
--------------------------------------------------------------------------------
合計:                   0件
================================================================================
```

---

### 📥 ステップ2: キューにドキュメントを追加

```bash
# ikuya_classroom ワークスペースのドキュメント50件をキューに追加
python reprocess_classroom_documents_v2.py --populate-only --limit=50
```

**処理内容:**
- `workspace='ikuya_classroom'` のドキュメントを検索
- 最大50件をキューに登録（`pending` 状態）
- 既にキューに登録済みのドキュメントはスキップ

**出力例:**
```
📥 キューへの追加を開始...
  対象ワークスペース: ikuya_classroom
  最大件数: 50
  Workspace保持: True

キュー追加完了: 45件追加, 5件スキップ

================================================================================
キュー統計
================================================================================
待機中 (pending):      45件
処理中 (processing):    0件
完了   (completed):     0件
失敗   (failed):        0件
スキップ (skipped):     0件
--------------------------------------------------------------------------------
合計:                  45件
================================================================================
```

---

### ⚙️ ステップ3: キューから処理実行

```bash
# キューから10件を処理
python reprocess_classroom_documents_v2.py --process-queue --limit=10
```

**処理内容:**
- キューから優先度順にタスクを取得
- Google Drive からファイルを取得
- 2段階パイプライン（Gemini分類 + Claude抽出）で処理
- 処理結果を `completed` または `failed` としてマーク

**確認プロンプト:**
```
処理を開始しますか？ (y/N): y
```

**出力例:**
```
⚙️  キューからの処理を開始...

================================================================================
[1/10] 処理開始: 学年通信（29）.pdf
Queue ID: 12345678-abcd-...
Document ID: 87654321-dcba-...
ファイルID: 1a2b3c4d5e6f7g8h9i0j
Workspace: ikuya_classroom (preserve=True)
✅ 再処理成功: 学年通信（29）.pdf
進捗: 成功=1, 失敗=0, 合計=1

================================================================================
[2/10] 処理開始: 価格表.pdf
...
```

---

### 🔄 ステップ4: 一括実行（推奨）

キュー追加と処理を一度に実行:

```bash
# 20件を追加して、すべて処理
python reprocess_classroom_documents_v2.py --limit=20
```

---

## 高度な使い方

### 🔧 オプション一覧

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--dry-run` / `-n` | 確認のみ（処理を実行しない） | False |
| `--populate-only` | キュー追加のみ | False |
| `--process-queue` | キュー処理のみ | False |
| `--limit=N` | 処理する最大件数 | 100 |
| `--no-preserve-workspace` | Workspaceを保持しない（Stage1 AIに判定させる） | False（保持する） |

### 使用例

```bash
# 例1: 5件だけ試しに処理
python reprocess_classroom_documents_v2.py --limit=5

# 例2: Workspaceを再判定させる
python reprocess_classroom_documents_v2.py --no-preserve-workspace --limit=10

# 例3: キューに100件追加（処理はしない）
python reprocess_classroom_documents_v2.py --populate-only --limit=100

# 例4: 既存キューから30件だけ処理
python reprocess_classroom_documents_v2.py --process-queue --limit=30
```

---

## エラーハンドリング

### 失敗したタスクの確認

Supabase SQL Editor で以下のクエリを実行:

```sql
-- 失敗したタスクを確認
SELECT
    original_file_name,
    last_error_message,
    attempt_count,
    last_attempt_at
FROM document_reprocessing_queue
WHERE status = 'failed'
ORDER BY last_attempt_at DESC;
```

### 失敗したタスクを再試行

```sql
-- 失敗タスクを pending に戻す（最大3回まで試行）
SELECT retry_failed_reprocessing_tasks(3);
```

その後、再度処理スクリプトを実行:

```bash
python reprocess_classroom_documents_v2.py --process-queue --limit=50
```

---

## キューの管理

### キューの統計を確認

```sql
SELECT
    status,
    COUNT(*) as count
FROM document_reprocessing_queue
GROUP BY status;
```

### 特定のドキュメントをキューに追加

```sql
-- 手動でドキュメントをキューに追加
SELECT add_document_to_reprocessing_queue(
    p_document_id := '12345678-abcd-efgh-ijkl-mnopqrstuvwx',
    p_reason := 'manual_metadata_update',
    p_reprocess_type := 'full',
    p_priority := 10,  -- 優先度を高くする
    p_preserve_workspace := true,
    p_created_by := 'admin@example.com'
);
```

### 完了したタスクを削除（クリーンアップ）

```sql
-- 完了済みタスクを削除（30日以上前のもの）
DELETE FROM document_reprocessing_queue
WHERE status = 'completed'
  AND processing_completed_at < NOW() - INTERVAL '30 days';
```

---

## トラブルシューティング

### Q1: キューに追加されるが、処理が進まない

**原因:** `processing` 状態で止まっている可能性
**解決策:**

```sql
-- 長時間 processing のままのタスクを確認
SELECT * FROM document_reprocessing_queue
WHERE status = 'processing'
  AND processing_started_at < NOW() - INTERVAL '1 hour';

-- 手動で pending に戻す
UPDATE document_reprocessing_queue
SET status = 'pending',
    processing_started_at = NULL
WHERE status = 'processing'
  AND processing_started_at < NOW() - INTERVAL '1 hour';
```

### Q2: 同じドキュメントが重複して追加される

**原因:** `status = 'completed'` のタスクは重複チェックから除外されます
**解決策:** 完了済みタスクは定期的に削除するか、追加前に手動確認

```sql
-- 特定ドキュメントのキュー履歴を確認
SELECT * FROM document_reprocessing_queue
WHERE document_id = '12345678-abcd-...';
```

### Q3: エラーメッセージ "duplicate key"

**原因:** `source_id` の重複
**解決策:** スクリプトが自動で古いレコードを削除して再試行します。それでも失敗する場合:

```sql
-- 重複レコードを確認
SELECT source_id, COUNT(*)
FROM documents
GROUP BY source_id
HAVING COUNT(*) > 1;

-- 古い方を手動削除
DELETE FROM documents
WHERE id = '古いドキュメントID';
```

---

## ベストプラクティス

### 1. 段階的に処理する

```bash
# まず5件で動作確認
python reprocess_classroom_documents_v2.py --limit=5

# 問題なければ50件
python reprocess_classroom_documents_v2.py --limit=50

# 全件処理
python reprocess_classroom_documents_v2.py --limit=1000
```

### 2. 定期的にキューをクリーンアップ

```sql
-- 月次クリーンアップ（完了済みタスクを削除）
DELETE FROM document_reprocessing_queue
WHERE status IN ('completed', 'skipped')
  AND processing_completed_at < NOW() - INTERVAL '30 days';
```

### 3. エラーログを確認

```bash
# ログファイルを確認（Loguru使用）
tail -f logs/reprocessing_*.log
```

---

## データベース関数リファレンス

### `add_document_to_reprocessing_queue()`

ドキュメントをキューに追加

**パラメータ:**
- `p_document_id` (UUID): ドキュメントID
- `p_reason` (TEXT): 再処理の理由
- `p_reprocess_type` (VARCHAR): 再処理タイプ（'full', 'metadata_only', 'embedding_only'）
- `p_priority` (INTEGER): 優先度（デフォルト: 0）
- `p_preserve_workspace` (BOOLEAN): workspaceを保持（デフォルト: true）
- `p_created_by` (VARCHAR): 登録者

**戻り値:** キューID (UUID)

---

### `get_next_reprocessing_task()`

次の処理対象タスクを取得

**パラメータ:**
- `p_worker_id` (VARCHAR): ワーカーID

**戻り値:** タスク情報（queue_id, document_id, file_name, ...）

**注意:** この関数は自動的にタスクを `processing` に変更し、ロックします

---

### `mark_reprocessing_task_completed()`

タスクを完了/失敗としてマーク

**パラメータ:**
- `p_queue_id` (UUID): キューID
- `p_success` (BOOLEAN): 成功したか
- `p_error_message` (TEXT): エラーメッセージ（失敗時）
- `p_error_details` (JSONB): エラー詳細（失敗時）

---

### `retry_failed_reprocessing_tasks()`

失敗したタスクを再試行キューに戻す

**パラメータ:**
- `p_max_attempts` (INTEGER): 最大試行回数（デフォルト: 3）

**戻り値:** 再試行に戻したタスク数

---

## まとめ

このシステムを使用することで：

1. ✅ **安全な再処理**: 処理状態を追跡し、重複を防止
2. ✅ **エラー管理**: 失敗したタスクを記録し、リトライ可能
3. ✅ **スケーラビリティ**: 並列ワーカーでの処理に対応
4. ✅ **可視性**: リアルタイムで処理進捗を確認

大規模なドキュメント再処理も、安心して実行できます！

---

## サポート

問題が発生した場合:
1. このドキュメントの「トラブルシューティング」を確認
2. データベースのエラーログを確認
3. 開発チームに連絡

**作成日:** 2025-12-09
**バージョン:** v1.0
