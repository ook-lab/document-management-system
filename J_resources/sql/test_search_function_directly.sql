-- =========================================
-- 検索関数を直接テスト
-- =========================================

-- 1. 検索可能なドキュメントを確認（再確認）
SELECT
    sd.id,
    sd.file_name,
    sd.doc_type,
    pl.processing_status,
    COUNT(si.id) as chunk_count
FROM source_documents sd
INNER JOIN search_index si ON sd.id = si.document_id
INNER JOIN process_logs pl ON sd.id = pl.document_id
WHERE pl.processing_status = 'completed'
GROUP BY sd.id, sd.file_name, sd.doc_type, pl.processing_status
LIMIT 10;

-- 2. search_indexの最初のembeddingを取得してテスト検索
DO $$
DECLARE
    test_embedding vector(1536);
BEGIN
    -- 最初のembeddingを取得
    SELECT embedding INTO test_embedding
    FROM search_index
    LIMIT 1;

    -- そのembeddingで検索してみる
    RAISE NOTICE 'Testing search with embedding from search_index...';

    -- 結果を表示（DO内ではSELECTの結果は表示されないので、後で別途実行）
END $$;

-- 3. 実際に検索関数を呼び出してテスト（ダミーembedding使用）
SELECT
    document_id,
    file_name,
    doc_type,
    combined_score
FROM search_documents_final(
    'test',  -- query_text
    (SELECT embedding FROM search_index LIMIT 1),  -- 実際のembeddingを使用
    0.0,  -- match_threshold (0にして全件取得)
    10,   -- match_count
    0.7,  -- vector_weight
    0.3,  -- fulltext_weight
    NULL, -- filter_year
    NULL, -- filter_month
    NULL  -- filter_doc_types
);

-- 4. もしくは、類似度0でも全件取得するテスト
SELECT
    document_id,
    file_name,
    doc_type,
    workspace,
    combined_score
FROM search_documents_final(
    '図書',  -- 実際のキーワード
    (SELECT embedding FROM search_index WHERE chunk_content LIKE '%図書%' LIMIT 1),
    -1.0,  -- match_threshold を-1にして全件取得
    50,
    0.7,
    0.3,
    NULL,
    NULL,
    NULL
);
