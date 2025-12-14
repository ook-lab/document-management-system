-- ============================================================
-- 未使用テーブルのクリーンアップ
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-14
--
-- 削除対象: データが0件のテーブル（6個）
-- 安全性: すべて外部参照なし、データなしを確認済み
-- ============================================================

DO $$
DECLARE
    attachments_count INT;
    corrections_count INT;
    small_chunks_count INT;
    correction_history_count INT;
    emails_count INT;
    hypothetical_questions_count INT;
BEGIN
    -- ============================================================
    -- 削除前の安全性チェック
    -- ============================================================
    SELECT COUNT(*) INTO attachments_count FROM attachments;
    SELECT COUNT(*) INTO corrections_count FROM corrections;
    SELECT COUNT(*) INTO small_chunks_count FROM small_chunks;
    SELECT COUNT(*) INTO correction_history_count FROM correction_history;
    SELECT COUNT(*) INTO emails_count FROM emails;
    SELECT COUNT(*) INTO hypothetical_questions_count FROM hypothetical_questions;

    -- データがあるテーブルがあれば中止
    IF attachments_count > 0 OR
       corrections_count > 0 OR
       small_chunks_count > 0 OR
       correction_history_count > 0 OR
       emails_count > 0 OR
       hypothetical_questions_count > 0 THEN
        RAISE EXCEPTION 'データが存在するテーブルがあります。削除を中止します。';
    END IF;

    RAISE NOTICE '安全性チェック完了: すべてのテーブルのデータ件数は0です';

    -- ============================================================
    -- テーブル削除
    -- ============================================================

    -- 1. attachments テーブル削除
    DROP TABLE IF EXISTS attachments CASCADE;
    RAISE NOTICE '✓ attachments テーブルを削除しました';

    -- 2. corrections テーブル削除
    DROP TABLE IF EXISTS corrections CASCADE;
    RAISE NOTICE '✓ corrections テーブルを削除しました';

    -- 3. small_chunks テーブル削除
    DROP TABLE IF EXISTS small_chunks CASCADE;
    RAISE NOTICE '✓ small_chunks テーブルを削除しました';

    -- 4. correction_history テーブル削除
    DROP TABLE IF EXISTS correction_history CASCADE;
    RAISE NOTICE '✓ correction_history テーブルを削除しました';

    -- 5. emails テーブル削除
    DROP TABLE IF EXISTS emails CASCADE;
    RAISE NOTICE '✓ emails テーブルを削除しました';

    -- 6. hypothetical_questions テーブル削除
    DROP TABLE IF EXISTS hypothetical_questions CASCADE;
    RAISE NOTICE '✓ hypothetical_questions テーブルを削除しました';

    RAISE NOTICE '完了: 6個のテーブルを削除しました';
END $$;

-- ============================================================
-- 完了メッセージ
-- ============================================================
SELECT
    '未使用テーブルのクリーンアップが完了しました' AS status,
    '削除されたテーブル: 6個' AS deleted_tables,
    '残りのテーブル: source_documents, process_logs, search_index, document_reprocessing_queue, documents_legacy, document_chunks_legacy' AS remaining_tables;
