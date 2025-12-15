-- ============================================================
-- document_chunks 互換性ビューの作成
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-14
--
-- 目的: 既存アプリケーションが document_chunks を参照できるようにする
-- search_index → document_chunks のビューとして作成
-- ============================================================

-- document_chunks ビューを作成
CREATE OR REPLACE VIEW document_chunks AS
SELECT
    id,
    document_id,
    chunk_index,
    chunk_content AS chunk_text,  -- search_index.chunk_content → document_chunks.chunk_text
    chunk_size,
    chunk_type,
    search_weight,
    embedding,
    page_numbers,
    section_title,
    created_at,
    updated_at
FROM search_index;

COMMENT ON VIEW document_chunks IS
'互換性ビュー: 既存アプリケーションのためにsearch_indexをdocument_chunksとして公開';

-- 確認
SELECT
    'document_chunks ビューが作成されました' AS status,
    COUNT(*) AS chunk_count
FROM document_chunks;
