-- documentsビューとテーブルの存在確認

-- Step 1: ビューの確認
SELECT
    'View exists' as status,
    viewname as name
FROM pg_views
WHERE schemaname = 'public' AND viewname = 'documents'
UNION ALL
-- Step 2: テーブルの確認
SELECT
    'Table exists' as status,
    tablename as name
FROM pg_tables
WHERE schemaname = 'public' AND tablename IN ('documents', 'source_documents')
ORDER BY status, name;

-- Step 3: 詳細確認
SELECT
    CASE
        WHEN EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'public' AND viewname = 'documents')
        THEN '✅ documents VIEW exists'
        WHEN EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'documents')
        THEN '⚠️  documents TABLE exists (not view)'
        ELSE '❌ documents does not exist (CRITICAL!)'
    END as documents_status,
    CASE
        WHEN EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'source_documents')
        THEN '✅ source_documents exists'
        ELSE '❌ source_documents does not exist'
    END as source_documents_status;
