-- 【実行場所】: Supabase SQL Editor
-- 【目的】: ドキュメントの再処理状態を管理するテーブルを追加
-- 【バージョン】: v9
-- 【作成日】: 2025-12-09

BEGIN;

-- ========================================
-- document_reprocessing_queue テーブル作成
-- ========================================
-- ドキュメントの再処理キューと状態を管理するテーブル
-- Google Classroomドキュメントなど、再処理が必要な文書を追跡

CREATE TABLE IF NOT EXISTS document_reprocessing_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 対象ドキュメント
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- 処理状態
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed', 'skipped'

    -- 再処理情報
    reprocess_reason TEXT,  -- 再処理の理由（例: 'initial_classroom_import', 'metadata_update', 'embedding_regeneration'）
    reprocess_type VARCHAR(100),  -- 再処理タイプ（例: 'full', 'metadata_only', 'embedding_only'）
    priority INTEGER DEFAULT 0,  -- 優先度（高い数値ほど優先）

    -- 試行回数と結果
    attempt_count INTEGER DEFAULT 0,  -- 試行回数
    max_attempts INTEGER DEFAULT 3,  -- 最大試行回数
    last_attempt_at TIMESTAMP WITH TIME ZONE,  -- 最後の試行日時
    last_error_message TEXT,  -- 最後のエラーメッセージ
    error_details JSONB,  -- エラー詳細（スタックトレースなど）

    -- 処理設定
    preserve_workspace BOOLEAN DEFAULT true,  -- workspaceを保持するか
    force_reprocess BOOLEAN DEFAULT true,  -- 強制再処理フラグ
    processing_options JSONB,  -- その他の処理オプション

    -- 元のドキュメント情報（参照用、削除されても履歴として残す）
    original_file_name VARCHAR(500),
    original_workspace VARCHAR(50),
    original_doc_type VARCHAR(100),
    original_source_id VARCHAR(500),

    -- 処理結果
    processing_started_at TIMESTAMP WITH TIME ZONE,  -- 処理開始時刻
    processing_completed_at TIMESTAMP WITH TIME ZONE,  -- 処理完了時刻
    processing_duration_ms INTEGER,  -- 処理時間（ミリ秒）

    -- 処理者情報
    created_by VARCHAR(200),  -- キュー登録者（例: 'system', 'admin@example.com'）
    processed_by VARCHAR(200),  -- 処理実行者（例: 'reprocessor_script', 'worker_01'）

    -- タイムスタンプ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- インデックス作成
-- ========================================

-- ドキュメントIDでの検索（同じドキュメントの再処理履歴を確認）
CREATE INDEX IF NOT EXISTS idx_reprocessing_queue_document_id
    ON document_reprocessing_queue(document_id);

-- 処理状態での検索（pending, processing などでフィルタ）
CREATE INDEX IF NOT EXISTS idx_reprocessing_queue_status
    ON document_reprocessing_queue(status);

-- 優先度順での検索（処理順序の決定）
CREATE INDEX IF NOT EXISTS idx_reprocessing_queue_priority
    ON document_reprocessing_queue(priority DESC, created_at ASC);

-- 複合インデックス: 未処理のキューを優先度順に取得
CREATE INDEX IF NOT EXISTS idx_reprocessing_queue_pending
    ON document_reprocessing_queue(status, priority DESC, created_at ASC)
    WHERE status IN ('pending', 'failed');

-- 元のsource_idでの検索（Google Drive IDなどで検索）
CREATE INDEX IF NOT EXISTS idx_reprocessing_queue_source_id
    ON document_reprocessing_queue(original_source_id);

-- ========================================
-- トリガー: updated_at の自動更新
-- ========================================

DROP TRIGGER IF EXISTS trigger_reprocessing_queue_updated_at ON document_reprocessing_queue;
CREATE TRIGGER trigger_reprocessing_queue_updated_at
    BEFORE UPDATE ON document_reprocessing_queue
    FOR EACH ROW
    EXECUTE PROCEDURE refresh_updated_at_column();

-- ========================================
-- 便利な関数: キューに追加
-- ========================================

CREATE OR REPLACE FUNCTION add_document_to_reprocessing_queue(
    p_document_id UUID,
    p_reason TEXT DEFAULT 'manual_reprocess',
    p_reprocess_type VARCHAR(100) DEFAULT 'full',
    p_priority INTEGER DEFAULT 0,
    p_preserve_workspace BOOLEAN DEFAULT true,
    p_created_by VARCHAR(200) DEFAULT 'system'
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_queue_id UUID;
    v_doc RECORD;
BEGIN
    -- ドキュメント情報を取得
    SELECT id, file_name, workspace, doc_type, source_id
    INTO v_doc
    FROM documents
    WHERE id = p_document_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Document not found: %', p_document_id;
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
        p_document_id,
        p_reason,
        p_reprocess_type,
        p_priority,
        p_preserve_workspace,
        v_doc.file_name,
        v_doc.workspace,
        v_doc.doc_type,
        v_doc.source_id,
        p_created_by
    )
    RETURNING id INTO v_queue_id;

    RETURN v_queue_id;
END;
$$;

-- ========================================
-- 便利な関数: 次の処理対象を取得
-- ========================================

CREATE OR REPLACE FUNCTION get_next_reprocessing_task(
    p_worker_id VARCHAR(200) DEFAULT 'default_worker'
)
RETURNS TABLE (
    queue_id UUID,
    document_id UUID,
    file_name VARCHAR(500),
    reprocess_type VARCHAR(100),
    preserve_workspace BOOLEAN,
    processing_options JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_queue_id UUID;
BEGIN
    -- 最も優先度が高く、古い pending/failed タスクを取得してロック
    -- failedは自動リトライ対象（最大3回まで）
    SELECT id INTO v_queue_id
    FROM document_reprocessing_queue
    WHERE (status = 'pending' OR status = 'failed')
        AND attempt_count < max_attempts
    ORDER BY
        CASE WHEN status = 'pending' THEN 0 ELSE 1 END,  -- pendingを優先
        priority DESC,
        created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;  -- 他のワーカーがロックしているタスクはスキップ

    IF v_queue_id IS NULL THEN
        -- 処理するタスクがない
        RETURN;
    END IF;

    -- ステータスを processing に更新
    UPDATE document_reprocessing_queue
    SET status = 'processing',
        processing_started_at = NOW(),
        processed_by = p_worker_id,
        attempt_count = attempt_count + 1,
        last_attempt_at = NOW()
    WHERE id = v_queue_id;

    -- タスク情報を返す
    RETURN QUERY
    SELECT
        q.id,
        q.document_id,
        q.original_file_name,
        q.reprocess_type,
        q.preserve_workspace,
        q.processing_options
    FROM document_reprocessing_queue q
    WHERE q.id = v_queue_id;
END;
$$;

-- ========================================
-- 便利な関数: タスク完了を記録
-- ========================================

CREATE OR REPLACE FUNCTION mark_reprocessing_task_completed(
    p_queue_id UUID,
    p_success BOOLEAN,
    p_error_message TEXT DEFAULT NULL,
    p_error_details JSONB DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_started_at TIMESTAMP WITH TIME ZONE;
    v_duration_ms INTEGER;
BEGIN
    -- 開始時刻を取得
    SELECT processing_started_at INTO v_started_at
    FROM document_reprocessing_queue
    WHERE id = p_queue_id;

    -- 処理時間を計算（ミリ秒）
    IF v_started_at IS NOT NULL THEN
        v_duration_ms := EXTRACT(EPOCH FROM (NOW() - v_started_at)) * 1000;
    END IF;

    IF p_success THEN
        -- 成功
        UPDATE document_reprocessing_queue
        SET status = 'completed',
            processing_completed_at = NOW(),
            processing_duration_ms = v_duration_ms,
            last_error_message = NULL,
            error_details = NULL
        WHERE id = p_queue_id;
    ELSE
        -- 失敗
        UPDATE document_reprocessing_queue
        SET status = 'failed',
            processing_completed_at = NOW(),
            processing_duration_ms = v_duration_ms,
            last_error_message = p_error_message,
            error_details = p_error_details
        WHERE id = p_queue_id;
    END IF;
END;
$$;

-- ========================================
-- 便利な関数: 失敗タスクを再試行キューに戻す
-- ========================================

CREATE OR REPLACE FUNCTION retry_failed_reprocessing_tasks(
    p_max_attempts INTEGER DEFAULT 3
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated_count INTEGER;
BEGIN
    -- 失敗したタスクのうち、まだ試行回数が残っているものを pending に戻す
    UPDATE document_reprocessing_queue
    SET status = 'pending',
        processing_started_at = NULL,
        processing_completed_at = NULL
    WHERE status = 'failed'
        AND attempt_count < p_max_attempts;

    GET DIAGNOSTICS v_updated_count = ROW_COUNT;

    RETURN v_updated_count;
END;
$$;

-- ========================================
-- コメント追加
-- ========================================

COMMENT ON TABLE document_reprocessing_queue IS '
ドキュメント再処理キュー。
Google Classroomドキュメントなど、再処理が必要な文書の状態を管理。
ワーカーが並列処理する際のロック機構も提供。
';

COMMENT ON COLUMN document_reprocessing_queue.status IS '
処理状態:
- pending: 処理待ち
- processing: 処理中
- completed: 完了
- failed: 失敗
- skipped: スキップ（処理不要と判断）
';

COMMENT ON COLUMN document_reprocessing_queue.reprocess_reason IS '
再処理の理由:
- initial_classroom_import: Google Classroomからの初回インポート
- metadata_update: メタデータの更新
- embedding_regeneration: Embeddingの再生成
- schema_migration: スキーマ変更に伴う再処理
- manual_reprocess: 手動での再処理リクエスト
';

COMMENT ON COLUMN document_reprocessing_queue.priority IS '
優先度（高い数値ほど優先）。
デフォルトは0。緊急の再処理は10以上を推奨。
';

COMMENT ON FUNCTION get_next_reprocessing_task IS '
次の処理対象タスクを取得し、自動的に processing ステータスに変更。
FOR UPDATE SKIP LOCKED により並列ワーカーでの競合を防止。
';

COMMIT;
