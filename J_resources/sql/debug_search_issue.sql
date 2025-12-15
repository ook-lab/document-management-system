-- 検索がヒットしない原因を調査するSQL

-- ========================================
-- 1. documentsテーブルの確認
-- ========================================

-- documentsテーブルにデータが存在するか
SELECT
    COUNT(*) as total_documents,
    COUNT(attachment_text) as docs_with_attachment_text,
    COUNT(summary) as docs_with_summary
FROM documents;

-- 最新5件のドキュメント情報
SELECT
    id,
    file_name,
    doc_type,
    workspace,
    LENGTH(attachment_text) as attachment_text_length,
    LENGTH(summary) as summary_length,
    created_at
FROM documents
ORDER BY created_at DESC
LIMIT 5;

-- ========================================
-- 2. document_chunksテーブルの確認
-- ========================================

-- チャンクが存在するか
SELECT
    COUNT(*) as total_chunks,
    COUNT(embedding) as chunks_with_embedding,
    COUNT(CASE WHEN chunk_size <= 500 THEN 1 END) as searchable_chunks,
    MIN(chunk_size) as min_chunk_size,
    MAX(chunk_size) as max_chunk_size,
    AVG(chunk_size) as avg_chunk_size
FROM document_chunks;

-- チャンク種別ごとの数
SELECT
    chunk_type,
    COUNT(*) as count,
    COUNT(embedding) as with_embedding,
    AVG(chunk_size) as avg_size
FROM document_chunks
GROUP BY chunk_type
ORDER BY count DESC;

-- 最新のチャンク5件
SELECT
    dc.id,
    dc.document_id,
    dc.chunk_type,
    dc.chunk_size,
    LEFT(dc.chunk_text, 100) as chunk_preview,
    dc.embedding IS NOT NULL as has_embedding,
    d.file_name,
    dc.created_at
FROM document_chunks dc
LEFT JOIN documents d ON d.id = dc.document_id
ORDER BY dc.created_at DESC
LIMIT 5;

-- ========================================
-- 3. 検索関数が正しく動作するかテスト
-- ========================================

-- テスト用のベクトル（ダミー）を生成
-- 注意: 実際の検索では正しいembeddingが必要
SELECT
    'Testing search function with dummy vector' as test_name,
    COUNT(*) as matching_chunks
FROM document_chunks dc
WHERE
    dc.embedding IS NOT NULL
    AND dc.chunk_size <= 500;

-- ========================================
-- 4. カラム存在確認
-- ========================================

-- documentsテーブルにattachment_textカラムが存在するか
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'documents'
    AND column_name IN ('attachment_text', 'full_text', 'summary')
ORDER BY column_name;

-- document_chunksテーブルのカラム確認
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'document_chunks'
    AND column_name IN ('chunk_text', 'embedding', 'chunk_size', 'chunk_type')
ORDER BY column_name;

-- ========================================
-- 5. 検索関数の存在確認
-- ========================================

SELECT
    routine_name,
    routine_type,
    data_type as return_type
FROM information_schema.routines
WHERE routine_name = 'search_documents_with_chunks';
