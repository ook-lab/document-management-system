-- 【実行場所】: Supabase SQL Editor
-- 【対象】: correction_history テーブル作成, documents テーブル拡張
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行
-- 【目的】: ユーザーによるメタデータ修正履歴を記録し、ロールバック機能を提供

-- Phase 2 (Track 1) - トランザクション管理・ロールバック
-- AUTO_INBOX_COMPLETE_v3.0.md の「2.1.3 トランザクション管理・ロールバック」に準拠

BEGIN;

-- ============================================================================
-- Step 1: correction_history テーブルの作成
-- ============================================================================

CREATE TABLE IF NOT EXISTS correction_history (
    id BIGSERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    old_metadata JSONB NOT NULL,  -- 修正前のメタデータ
    new_metadata JSONB NOT NULL,  -- 修正後のメタデータ
    corrector_email TEXT,  -- 修正者のメールアドレス
    corrected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- インデックス用の追加情報
    correction_type TEXT DEFAULT 'manual',  -- 'manual' or 'automatic'
    notes TEXT  -- 修正に関するメモ
);

-- テーブルの説明
COMMENT ON TABLE correction_history IS
'ユーザーがReview UIで行ったメタデータ修正の履歴を記録。Phase 2で追加。';

COMMENT ON COLUMN correction_history.old_metadata IS
'修正前のメタデータ（ロールバック時にこの値を復元）';

COMMENT ON COLUMN correction_history.new_metadata IS
'修正後のメタデータ（現在の値）';

COMMENT ON COLUMN correction_history.corrector_email IS
'修正を行ったユーザーのメールアドレス';

COMMENT ON COLUMN correction_history.correction_type IS
'修正の種類: manual（手動）, automatic（自動）';

-- ============================================================================
-- Step 2: インデックスの作成
-- ============================================================================

-- document_id でのソート・検索を高速化
CREATE INDEX IF NOT EXISTS idx_correction_history_document_id
ON correction_history(document_id, corrected_at DESC);

-- 修正者別の検索を高速化
CREATE INDEX IF NOT EXISTS idx_correction_history_corrector
ON correction_history(corrector_email)
WHERE corrector_email IS NOT NULL;

-- 日付範囲での検索を高速化
CREATE INDEX IF NOT EXISTS idx_correction_history_corrected_at
ON correction_history(corrected_at DESC);

-- ============================================================================
-- Step 3: documents テーブルに latest_correction_id カラムを追加
-- ============================================================================

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS latest_correction_id BIGINT REFERENCES correction_history(id);

COMMENT ON COLUMN documents.latest_correction_id IS
'最新の修正履歴レコードへの参照。ロールバック時に使用。';

-- インデックス作成（NULL許容）
CREATE INDEX IF NOT EXISTS idx_documents_latest_correction_id
ON documents(latest_correction_id)
WHERE latest_correction_id IS NOT NULL;

-- ============================================================================
-- Step 4: ロールバック用のヘルパー関数（オプション）
-- ============================================================================

CREATE OR REPLACE FUNCTION rollback_document_metadata(p_document_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_latest_correction_id BIGINT;
    v_old_metadata JSONB;
BEGIN
    -- 最新の修正履歴IDを取得
    SELECT latest_correction_id INTO v_latest_correction_id
    FROM documents
    WHERE id = p_document_id;

    -- 修正履歴が存在しない場合
    IF v_latest_correction_id IS NULL THEN
        RAISE EXCEPTION '修正履歴が存在しません: document_id=%', p_document_id;
    END IF;

    -- 修正前のメタデータを取得
    SELECT old_metadata INTO v_old_metadata
    FROM correction_history
    WHERE id = v_latest_correction_id;

    -- documentsテーブルを更新（ロールバック）
    UPDATE documents
    SET metadata = v_old_metadata,
        latest_correction_id = NULL  -- ロールバック後は修正履歴をクリア
    WHERE id = p_document_id;

    -- ロールバック後のメタデータを返す
    RETURN v_old_metadata;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION rollback_document_metadata IS
'指定されたドキュメントのメタデータを最新の修正前の状態にロールバック';

-- ============================================================================
-- Step 5: 統計情報の更新
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'テーブル correction_history が正常に作成されました';
    RAISE NOTICE 'documents.latest_correction_id カラムが追加されました';
    RAISE NOTICE 'インデックスが作成されました';
    RAISE NOTICE 'ロールバック関数 rollback_document_metadata() が作成されました';
    RAISE NOTICE 'トランザクション管理・ロールバック機能の準備が完了しました';
END $$;

COMMIT;

-- ============================================================================
-- 【確認クエリ】
-- ============================================================================

-- テーブル作成確認
-- SELECT
--     table_name,
--     table_type
-- FROM information_schema.tables
-- WHERE table_name IN ('correction_history', 'documents')
-- ORDER BY table_name;

-- カラム確認
-- SELECT
--     column_name,
--     data_type,
--     is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'correction_history'
-- ORDER BY ordinal_position;

-- インデックス確認
-- SELECT
--     indexname,
--     indexdef
-- FROM pg_indexes
-- WHERE tablename IN ('correction_history', 'documents')
-- AND indexname LIKE '%correction%'
-- ORDER BY tablename, indexname;

-- 関数確認
-- SELECT
--     routine_name,
--     routine_type
-- FROM information_schema.routines
-- WHERE routine_name = 'rollback_document_metadata';

-- ============================================================================
-- 【サンプルクエリ】
-- ============================================================================

-- 修正履歴の一覧（最新10件）
-- SELECT
--     ch.id,
--     d.file_name,
--     d.doc_type,
--     ch.corrector_email,
--     ch.corrected_at,
--     ch.correction_type
-- FROM correction_history ch
-- JOIN documents d ON ch.document_id = d.id
-- ORDER BY ch.corrected_at DESC
-- LIMIT 10;

-- ドキュメント別の修正回数
-- SELECT
--     d.id,
--     d.file_name,
--     d.doc_type,
--     COUNT(ch.id) as correction_count,
--     MAX(ch.corrected_at) as last_corrected_at
-- FROM documents d
-- LEFT JOIN correction_history ch ON d.id = ch.document_id
-- GROUP BY d.id, d.file_name, d.doc_type
-- HAVING COUNT(ch.id) > 0
-- ORDER BY correction_count DESC
-- LIMIT 20;

-- 修正者別の統計
-- SELECT
--     corrector_email,
--     COUNT(*) as correction_count,
--     MIN(corrected_at) as first_correction,
--     MAX(corrected_at) as last_correction
-- FROM correction_history
-- WHERE corrector_email IS NOT NULL
-- GROUP BY corrector_email
-- ORDER BY correction_count DESC;

-- ロールバック可能なドキュメント
-- SELECT
--     d.id,
--     d.file_name,
--     d.doc_type,
--     d.latest_correction_id,
--     ch.corrected_at as can_rollback_to
-- FROM documents d
-- JOIN correction_history ch ON d.latest_correction_id = ch.id
-- ORDER BY ch.corrected_at DESC
-- LIMIT 10;
