-- =====================================================
-- 検索データの診断クエリ
-- =====================================================

-- 1. source_documentsテーブルのデータ確認
SELECT
    COUNT(*) as total_documents,
    COUNT(DISTINCT workspace) as workspaces,
    COUNT(DISTINCT doc_type) as doc_types
FROM source_documents;

-- 2. document_chunksテーブルのデータ確認
SELECT
    COUNT(*) as total_chunks,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as chunks_with_embedding,
    COUNT(CASE WHEN embedding IS NULL THEN 1 END) as chunks_without_embedding,
    AVG(chunk_size) as avg_chunk_size,
    MIN(chunk_size) as min_chunk_size,
    MAX(chunk_size) as max_chunk_size
FROM document_chunks;

-- 3. 小チャンク（chunk_size <= 500）の確認
SELECT
    COUNT(*) as small_chunks,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as small_chunks_with_embedding
FROM document_chunks
WHERE chunk_size <= 500;

-- 4. サンプルデータの確認（最初の3件）
SELECT
    id,
    file_name,
    doc_type,
    workspace,
    display_subject,
    display_sender,
    display_type,
    created_at
FROM source_documents
ORDER BY created_at DESC
LIMIT 3;

-- 5. チャンクのサンプル確認
SELECT
    dc.id,
    dc.document_id,
    dc.chunk_index,
    dc.chunk_type,
    dc.chunk_size,
    LEFT(dc.chunk_text, 50) as chunk_preview,
    CASE WHEN dc.embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_embedding
FROM document_chunks dc
ORDER BY dc.created_at DESC
LIMIT 5;
