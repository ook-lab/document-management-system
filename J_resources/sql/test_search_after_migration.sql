-- =========================================
-- 検索関数のテスト
-- =========================================

-- 1. データ確認
SELECT
    (SELECT COUNT(*) FROM source_documents) as total_documents,
    (SELECT COUNT(DISTINCT document_id) FROM search_index) as documents_in_search_index,
    (SELECT COUNT(*) FROM search_index) as total_chunks,
    (SELECT COUNT(*) FROM process_logs) as total_process_logs;

-- 2. 検索可能なドキュメント確認（process_logsと結合）
SELECT
    COUNT(DISTINCT sd.id) as searchable_documents
FROM source_documents sd
INNER JOIN search_index si ON sd.id = si.document_id
INNER JOIN process_logs pl ON sd.id = pl.document_id
WHERE pl.processing_status = 'completed';

-- 3. ワークスペース一覧のテスト
SELECT * FROM get_active_workspaces();

-- 4. ドキュメントタイプ一覧のテスト
SELECT * FROM get_active_doc_types();

-- 5. サンプルドキュメント（最新5件）
SELECT
    sd.id,
    sd.file_name,
    sd.doc_type,
    sd.workspace,
    pl.processing_status,
    COUNT(si.id) as chunk_count
FROM source_documents sd
LEFT JOIN process_logs pl ON sd.id = pl.document_id
LEFT JOIN search_index si ON sd.id = si.document_id
GROUP BY sd.id, sd.file_name, sd.doc_type, sd.workspace, pl.processing_status
ORDER BY sd.created_at DESC
LIMIT 5;
