-- ====================================================================
-- 関数・トリガーの更新（新テーブル名対応）
-- ====================================================================
-- 実行場所: Supabase SQL Editor
-- 実行タイミング: table_consolidation_and_rename.sql の実行後
-- ====================================================================

BEGIN;

-- ====================================================================
-- STEP 1: correction_history 関連の関数更新
-- ====================================================================

-- ロールバック関数を新テーブル名に対応
CREATE OR REPLACE FUNCTION rollback_document_metadata(p_document_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_latest_correction_id BIGINT;
    v_old_metadata JSONB;
BEGIN
    -- 最新の修正履歴IDを取得
    SELECT latest_correction_id INTO v_latest_correction_id
    FROM "10_rd_source_docs"
    WHERE id = p_document_id;

    -- 修正履歴が存在しない場合
    IF v_latest_correction_id IS NULL THEN
        RAISE EXCEPTION '修正履歴が存在しません: document_id=%', p_document_id;
    END IF;

    -- 修正前のメタデータを取得
    SELECT old_metadata INTO v_old_metadata
    FROM "99_lg_correction_history"
    WHERE id = v_latest_correction_id;

    -- 10_rd_source_docsテーブルを更新（ロールバック）
    UPDATE "10_rd_source_docs"
    SET metadata = v_old_metadata,
        latest_correction_id = NULL
    WHERE id = p_document_id;

    -- ロールバック後のメタデータを返す
    RETURN v_old_metadata;
END;
$$ LANGUAGE plpgsql;

-- ====================================================================
-- STEP 2: 70. チラシ関連のトリガー・関数更新
-- ====================================================================

-- updated_at自動更新関数（共通）
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 70_rd_flyer_docs の updated_at トリガー
DROP TRIGGER IF EXISTS update_flyer_documents_updated_at ON "70_rd_flyer_docs";
CREATE TRIGGER update_flyer_documents_updated_at
    BEFORE UPDATE ON "70_rd_flyer_docs"
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 70_rd_flyer_items の updated_at トリガー
DROP TRIGGER IF EXISTS update_flyer_products_updated_at ON "70_rd_flyer_items";
CREATE TRIGGER update_flyer_products_updated_at
    BEFORE UPDATE ON "70_rd_flyer_items"
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 70_rd_flyer_docs の検索ベクトル更新関数
CREATE OR REPLACE FUNCTION flyer_documents_search_vector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', coalesce(NEW.flyer_title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.organization, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(NEW.attachment_text, '')), 'C') ||
        setweight(to_tsvector('simple', coalesce(NEW.summary, '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tsvector_update_flyer_documents ON "70_rd_flyer_docs";
CREATE TRIGGER tsvector_update_flyer_documents
    BEFORE INSERT OR UPDATE ON "70_rd_flyer_docs"
    FOR EACH ROW
    EXECUTE FUNCTION flyer_documents_search_vector_update();

-- 70_rd_flyer_items の検索ベクトル更新関数
CREATE OR REPLACE FUNCTION flyer_products_search_vector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', coalesce(NEW.product_name, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.brand, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(NEW.category, '')), 'C') ||
        setweight(to_tsvector('simple', coalesce(NEW.extracted_text, '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tsvector_update_flyer_products ON "70_rd_flyer_items";
CREATE TRIGGER tsvector_update_flyer_products
    BEFORE INSERT OR UPDATE ON "70_rd_flyer_items"
    FOR EACH ROW
    EXECUTE FUNCTION flyer_products_search_vector_update();

-- ====================================================================
-- STEP 3: 99. ログ・システム関連の関数更新
-- ====================================================================

-- refresh_updated_at_column 関数（99_lg_reprocess_queue用）
CREATE OR REPLACE FUNCTION refresh_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 99_lg_reprocess_queue の updated_at トリガー
DROP TRIGGER IF EXISTS trigger_reprocessing_queue_updated_at ON "99_lg_reprocess_queue";
CREATE TRIGGER trigger_reprocessing_queue_updated_at
    BEFORE UPDATE ON "99_lg_reprocess_queue"
    FOR EACH ROW
    EXECUTE FUNCTION refresh_updated_at_column();

-- キューに追加する関数（テーブル名はそのまま documents を参照）
-- ※ユーザー指示により documents テーブルへの参照は変更しない
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
    INSERT INTO "99_lg_reprocess_queue" (
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

-- 次の処理対象を取得する関数
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
    SELECT id INTO v_queue_id
    FROM "99_lg_reprocess_queue"
    WHERE (status = 'pending' OR status = 'failed')
        AND attempt_count < max_attempts
    ORDER BY
        CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
        priority DESC,
        created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;

    IF v_queue_id IS NULL THEN
        RETURN;
    END IF;

    UPDATE "99_lg_reprocess_queue"
    SET status = 'processing',
        processing_started_at = NOW(),
        processed_by = p_worker_id,
        attempt_count = attempt_count + 1,
        last_attempt_at = NOW()
    WHERE id = v_queue_id;

    RETURN QUERY
    SELECT
        q.id,
        q.document_id,
        q.original_file_name,
        q.reprocess_type,
        q.preserve_workspace,
        q.processing_options
    FROM "99_lg_reprocess_queue" q
    WHERE q.id = v_queue_id;
END;
$$;

-- タスク完了を記録する関数
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
    SELECT processing_started_at INTO v_started_at
    FROM "99_lg_reprocess_queue"
    WHERE id = p_queue_id;

    IF v_started_at IS NOT NULL THEN
        v_duration_ms := EXTRACT(EPOCH FROM (NOW() - v_started_at)) * 1000;
    END IF;

    IF p_success THEN
        UPDATE "99_lg_reprocess_queue"
        SET status = 'completed',
            processing_completed_at = NOW(),
            processing_duration_ms = v_duration_ms,
            last_error_message = NULL,
            error_details = NULL
        WHERE id = p_queue_id;
    ELSE
        UPDATE "99_lg_reprocess_queue"
        SET status = 'failed',
            processing_completed_at = NOW(),
            processing_duration_ms = v_duration_ms,
            last_error_message = p_error_message,
            error_details = p_error_details
        WHERE id = p_queue_id;
    END IF;
END;
$$;

-- 失敗タスクを再試行キューに戻す関数
CREATE OR REPLACE FUNCTION retry_failed_reprocessing_tasks(
    p_max_attempts INTEGER DEFAULT 3
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated_count INTEGER;
BEGIN
    UPDATE "99_lg_reprocess_queue"
    SET status = 'pending',
        processing_started_at = NULL,
        processing_completed_at = NULL
    WHERE status = 'failed'
        AND attempt_count < p_max_attempts;

    GET DIAGNOSTICS v_updated_count = ROW_COUNT;

    RETURN v_updated_count;
END;
$$;

-- ====================================================================
-- 完了メッセージ
-- ====================================================================

DO $$
BEGIN
    RAISE NOTICE '✅ 関数・トリガーの更新が完了しました';
    RAISE NOTICE '✅ rollback_document_metadata: 10_rd_source_docs に対応';
    RAISE NOTICE '✅ チラシ関連トリガー: 70_rd_flyer_docs, 70_rd_flyer_items に対応';
    RAISE NOTICE '✅ 再処理キュー関連関数: 99_lg_reprocess_queue に対応';
END $$;

COMMIT;
