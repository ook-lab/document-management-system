-- SQL関数の状態を確認

-- 1. 関数が存在するか確認
SELECT
    routine_name as "関数名",
    routine_type as "タイプ"
FROM information_schema.routines
WHERE routine_schema = 'public'
    AND routine_name IN (
        'search_documents_final',
        'get_active_workspaces',
        'get_active_doc_types',
        'hybrid_search'
    )
ORDER BY routine_name;

-- 2. search_documents_final関数の定義を確認（source_documentsを使っているか）
SELECT
    routine_name,
    CASE
        WHEN routine_definition LIKE '%source_documents%' THEN '✅ source_documentsを使用'
        WHEN routine_definition LIKE '%documents%' THEN '❌ 古いdocumentsを使用'
        ELSE '⚠️  不明'
    END as status
FROM information_schema.routines
WHERE routine_schema = 'public'
    AND routine_name = 'search_documents_final';

-- 3. source_documentsテーブルのデータ件数確認
SELECT
    COUNT(*) as total_documents,
    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_documents,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as documents_with_embedding
FROM source_documents;
