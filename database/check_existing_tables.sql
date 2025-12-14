-- =========================================
-- 存在するテーブルを確認
-- =========================================

-- 1. 全てのテーブル一覧
SELECT
    tablename,
    schemaname
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- 2. 3-tierテーブルのデータ件数
SELECT
    'source_documents' as table_name,
    CASE
        WHEN EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'source_documents')
        THEN (SELECT COUNT(*)::text FROM source_documents)
        ELSE 'テーブルなし'
    END as count
UNION ALL
SELECT
    'process_logs' as table_name,
    CASE
        WHEN EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'process_logs')
        THEN (SELECT COUNT(*)::text FROM process_logs)
        ELSE 'テーブルなし'
    END as count
UNION ALL
SELECT
    'search_index' as table_name,
    CASE
        WHEN EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'search_index')
        THEN (SELECT COUNT(*)::text FROM search_index)
        ELSE 'テーブルなし'
    END as count;

-- 3. レガシーテーブルの確認
SELECT
    'documents' as table_name,
    CASE
        WHEN EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'documents')
        THEN 'テーブル存在'
        WHEN EXISTS (SELECT 1 FROM pg_views WHERE viewname = 'documents')
        THEN 'ビュー存在'
        ELSE 'なし'
    END as status
UNION ALL
SELECT
    'document_chunks' as table_name,
    CASE
        WHEN EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'document_chunks')
        THEN 'テーブル存在'
        WHEN EXISTS (SELECT 1 FROM pg_views WHERE viewname = 'document_chunks')
        THEN 'ビュー存在'
        ELSE 'なし'
    END as status
UNION ALL
SELECT
    'documents_legacy' as table_name,
    CASE
        WHEN EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'documents_legacy')
        THEN 'テーブル存在'
        ELSE 'なし'
    END as status
UNION ALL
SELECT
    'document_chunks_legacy' as table_name,
    CASE
        WHEN EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'document_chunks_legacy')
        THEN 'テーブル存在'
        ELSE 'なし'
    END as status;
