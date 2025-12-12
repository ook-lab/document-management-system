-- ========================================
-- v10: documents テーブルへのINSERT時に自動でキューに追加するトリガー
-- ========================================
-- 作成日: 2025-12-12
-- 目的: GASからdocumentsにINSERTされたときに、自動的にdocument_reprocessing_queueにタスクを追加
-- 設計書: docs/GAS_INTEGRATION_GUIDE.md に基づく
-- ========================================

-- ========================================
-- トリガー関数: documents INSERT時に自動でキューに追加
-- ========================================

CREATE OR REPLACE FUNCTION auto_add_to_reprocessing_queue()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  -- processing_status が pending の場合のみキューに追加
  IF NEW.processing_status = 'pending' THEN

    -- 重複チェック: 既にキューに登録されている場合はスキップ
    IF EXISTS (
      SELECT 1
      FROM document_reprocessing_queue
      WHERE document_id = NEW.id
        AND status IN ('pending', 'processing')
    ) THEN
      -- 既にキューに存在する場合はスキップ
      RETURN NEW;
    END IF;

    -- キューに追加
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
      -- ingestion_route に応じて理由を設定
      CASE
        WHEN NEW.ingestion_route = 'classroom' THEN 'classroom_initial_import'
        WHEN NEW.ingestion_route = 'drive' THEN 'drive_initial_import'
        WHEN NEW.ingestion_route = 'gmail' THEN 'gmail_initial_import'
        ELSE 'initial_import'
      END,
      'full',  -- 全処理
      0,       -- 優先度: デフォルト
      true,    -- workspaceを保持
      NEW.file_name,
      NEW.workspace,
      NEW.doc_type,
      NEW.source_id,
      'supabase_trigger'  -- 作成者
    );

    -- ログ出力（開発環境のみ有効にする場合）
    -- RAISE NOTICE 'Auto-queued document: % (file_name: %)', NEW.id, NEW.file_name;
  END IF;

  RETURN NEW;
END;
$$;

-- ========================================
-- トリガーの作成
-- ========================================

-- 既存のトリガーがあれば削除
DROP TRIGGER IF EXISTS trigger_auto_queue_on_insert ON documents;

-- 新しいトリガーを作成
CREATE TRIGGER trigger_auto_queue_on_insert
AFTER INSERT ON documents
FOR EACH ROW
EXECUTE FUNCTION auto_add_to_reprocessing_queue();

-- ========================================
-- 動作確認用クエリ（コメントアウト）
-- ========================================

/*
-- テスト: documentsにサンプルデータを挿入
INSERT INTO documents (
  source_type,
  source_id,
  file_name,
  workspace,
  doc_type,
  processing_status,
  ingestion_route
) VALUES (
  'classroom',
  'test_source_id_' || gen_random_uuid()::text,
  'テスト課題.pdf',
  'ikuya_classroom',
  '数学I',
  'pending',
  'classroom'
);

-- キューに追加されたか確認
SELECT
  q.id,
  q.document_id,
  q.original_file_name,
  q.reprocess_reason,
  q.status,
  q.created_by
FROM document_reprocessing_queue q
ORDER BY q.created_at DESC
LIMIT 5;
*/

-- ========================================
-- 注意事項
-- ========================================

-- 1. このトリガーは documents テーブルへの INSERT 時のみ動作します
-- 2. processing_status が 'pending' のレコードのみがキューに追加されます
-- 3. 既にキューに登録されているドキュメントは重複追加されません
-- 4. UPDATE 時には動作しません（必要に応じて別のトリガーを作成）

-- ========================================
-- ロールバック用（必要時のみ実行）
-- ========================================

/*
-- トリガーを削除
DROP TRIGGER IF EXISTS trigger_auto_queue_on_insert ON documents;

-- 関数を削除
DROP FUNCTION IF EXISTS auto_add_to_reprocessing_queue();
*/
