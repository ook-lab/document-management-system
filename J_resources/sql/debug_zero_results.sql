-- =========================================
-- 検索結果が0件になる原因を調査
-- =========================================

-- 1. process_logsのステータス確認
SELECT
    processing_status,
    COUNT(*) as count
FROM process_logs
GROUP BY processing_status
ORDER BY count DESC;

-- 2. 3テーブルのJOIN結果確認
SELECT
    COUNT(DISTINCT sd.id) as total_in_source,
    COUNT(DISTINCT CASE WHEN si.id IS NOT NULL THEN sd.id END) as with_search_index,
    COUNT(DISTINCT CASE WHEN pl.id IS NOT NULL THEN sd.id END) as with_process_logs,
    COUNT(DISTINCT CASE WHEN si.id IS NOT NULL AND pl.id IS NOT NULL THEN sd.id END) as in_both
FROM source_documents sd
LEFT JOIN search_index si ON sd.id = si.document_id
LEFT JOIN process_logs pl ON sd.id = pl.document_id;

-- 3. 検索可能なドキュメント（processing_status = 'completed'）
SELECT
    COUNT(DISTINCT sd.id) as searchable_count
FROM source_documents sd
INNER JOIN search_index si ON sd.id = si.document_id
INNER JOIN process_logs pl ON sd.id = pl.document_id
WHERE pl.processing_status = 'completed';

-- 4. processing_status別のドキュメント数
SELECT
    COALESCE(pl.processing_status, 'status_missing') as status,
    COUNT(DISTINCT sd.id) as doc_count,
    COUNT(si.id) as chunk_count
FROM source_documents sd
LEFT JOIN process_logs pl ON sd.id = pl.document_id
LEFT JOIN search_index si ON sd.id = si.document_id
GROUP BY pl.processing_status
ORDER BY doc_count DESC;

-- 5. search_indexがあるがprocess_logsが無いドキュメント
SELECT
    sd.id,
    sd.file_name,
    sd.doc_type,
    COUNT(si.id) as chunk_count
FROM source_documents sd
INNER JOIN search_index si ON sd.id = si.document_id
LEFT JOIN process_logs pl ON sd.id = pl.document_id
WHERE pl.id IS NULL
GROUP BY sd.id, sd.file_name, sd.doc_type
LIMIT 5;

-- 6. process_logsがあるがsearch_indexが無いドキュメント
SELECT
    sd.id,
    sd.file_name,
    sd.doc_type,
    pl.processing_status
FROM source_documents sd
INNER JOIN process_logs pl ON sd.id = pl.document_id
LEFT JOIN search_index si ON sd.id = si.document_id
WHERE si.id IS NULL
LIMIT 5;
