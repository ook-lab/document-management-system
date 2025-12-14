-- ============================================================
-- Legacyテーブルのクリーンアップ
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-14
--
-- 【重要】
-- このSQLは新システムが安定稼働したことを確認してから実行してください
-- 推奨: マイグレーション後1〜2週間経過してから実行
--
-- 削除対象:
-- - documents_legacy (バックアップ)
-- - document_chunks_legacy (バックアップ)
-- ============================================================

DO $$
DECLARE
    source_docs_count INT;
    search_index_count INT;
BEGIN
    -- ============================================================
    -- 削除前の安全性チェック
    -- ============================================================

    -- 新テーブルにデータがあることを確認
    SELECT COUNT(*) INTO source_docs_count FROM source_documents;
    SELECT COUNT(*) INTO search_index_count FROM search_index;

    IF source_docs_count = 0 OR search_index_count = 0 THEN
        RAISE EXCEPTION '新テーブルにデータがありません。削除を中止します。';
    END IF;

    RAISE NOTICE '安全性チェック完了: 新テーブルにデータが存在します';
    RAISE NOTICE 'source_documents: % 件', source_docs_count;
    RAISE NOTICE 'search_index: % 件', search_index_count;

    -- ============================================================
    -- Legacyテーブル削除
    -- ============================================================

    -- 1. documents_legacy テーブル削除
    DROP TABLE IF EXISTS documents_legacy CASCADE;
    RAISE NOTICE '✓ documents_legacy テーブルを削除しました';

    -- 2. document_chunks_legacy テーブル削除
    DROP TABLE IF EXISTS document_chunks_legacy CASCADE;
    RAISE NOTICE '✓ document_chunks_legacy テーブルを削除しました';

    RAISE NOTICE '完了: 2個のLegacyテーブルを削除しました';
END $$;

-- ============================================================
-- 完了メッセージ
-- ============================================================
SELECT
    'Legacyテーブルのクリーンアップが完了しました' AS status,
    '削除されたテーブル: 2個' AS deleted_tables,
    '最終的なテーブル構成: source_documents, process_logs, search_index, document_reprocessing_queue' AS final_tables;
