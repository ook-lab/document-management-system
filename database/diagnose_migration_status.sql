-- =========================================
-- データ移行状況の診断
-- =========================================

-- 1. 各テーブルのデータ件数
SELECT
    'source_documents' as table_name,
    COUNT(*) as count
FROM source_documents
UNION ALL
SELECT
    'process_logs' as table_name,
    COUNT(*) as count
FROM process_logs
UNION ALL
SELECT
    'search_index' as table_name,
    COUNT(*) as count
FROM search_index
ORDER BY table_name;

-- 2. process_logsのステータス別件数
SELECT
    processing_status,
    COUNT(*) as count
FROM process_logs
GROUP BY processing_status
ORDER BY count DESC;

-- 3. search_indexのドキュメント別件数（上位10件）
SELECT
    document_id,
    COUNT(*) as chunk_count
FROM search_index
GROUP BY document_id
ORDER BY chunk_count DESC
LIMIT 10;

-- 4. source_documentsとprocess_logsの結合確認
SELECT
    COUNT(DISTINCT sd.id) as docs_in_source,
    COUNT(DISTINCT pl.document_id) as docs_in_process_logs,
    COUNT(DISTINCT si.document_id) as docs_in_search_index
FROM source_documents sd
LEFT JOIN process_logs pl ON sd.id = pl.document_id
LEFT JOIN search_index si ON sd.id = si.document_id;

-- 5. 検索可能なドキュメント数（completed + embeddingあり）
SELECT
    COUNT(DISTINCT sd.id) as searchable_documents
FROM source_documents sd
INNER JOIN process_logs pl ON sd.id = pl.document_id
INNER JOIN search_index si ON sd.id = si.document_id
WHERE pl.processing_status = 'completed';

-- 6. 古いテーブルの確認
SELECT
    'documents (old)' as table_name,
    COUNT(*) as count
FROM documents
WHERE EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'documents')
UNION ALL
SELECT
    'document_chunks (old)' as table_name,
    COUNT(*) as count
FROM document_chunks
WHERE EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'document_chunks');
