-- documents ビューを削除
-- これで3-tier構造への移行が完全に完了します

-- Step 1: documentsビューが存在するか確認
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_views
        WHERE schemaname = 'public' AND viewname = 'documents'
    ) THEN
        RAISE NOTICE 'documents view exists - will be dropped';
    ELSE
        RAISE NOTICE 'documents view does not exist';
    END IF;
END $$;

-- Step 2: documentsビューを削除
DROP VIEW IF EXISTS documents;

-- Step 3: 削除確認
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_views
        WHERE schemaname = 'public' AND viewname = 'documents'
    ) THEN
        RAISE NOTICE '✅ documents view has been successfully dropped';
    ELSE
        RAISE NOTICE '❌ documents view still exists';
    END IF;
END $$;

-- 最終確認: 現在のテーブルとビューのリスト
SELECT
    'Table' as type,
    tablename as name
FROM pg_tables
WHERE schemaname = 'public'
    AND tablename IN ('source_documents', 'process_logs', 'search_index', 'documents')
UNION ALL
SELECT
    'View' as type,
    viewname as name
FROM pg_views
WHERE schemaname = 'public'
    AND viewname IN ('source_documents', 'process_logs', 'search_index', 'documents')
ORDER BY type, name;
