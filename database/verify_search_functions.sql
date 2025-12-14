-- =========================================
-- 検索関数の定義を確認
-- =========================================

-- 1. 関数が存在するか
SELECT
    routine_name,
    routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
    AND routine_name IN (
        'search_documents_final',
        'get_active_workspaces',
        'get_active_doc_types',
        'hybrid_search'
    )
ORDER BY routine_name;

-- 2. search_documents_final関数がどのテーブルを参照しているか
SELECT
    p.proname as function_name,
    CASE
        WHEN pg_get_functiondef(p.oid) LIKE '%FROM search_index%'
            AND pg_get_functiondef(p.oid) LIKE '%JOIN source_documents%'
        THEN '✅ 3-tier構造（search_index + source_documents）'
        WHEN pg_get_functiondef(p.oid) LIKE '%FROM source_documents%'
        THEN '⚠️  source_documentsのみ（embeddingなし）'
        WHEN pg_get_functiondef(p.oid) LIKE '%FROM documents%'
        THEN '❌ 古いdocumentsテーブル参照'
        ELSE '❓ 不明'
    END as status
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public'
    AND p.proname = 'search_documents_final';
