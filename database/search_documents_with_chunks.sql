-- 小チャンク検索 + 大チャンク回答のハイブリッド検索関数
--
-- 検索フロー:
-- 1. document_chunksテーブルでベクトル検索 + 全文検索（小チャンクのみ）
-- 2. ドキュメント単位で重複排除（最高スコアのチャンクのみ）
-- 3. documentsテーブルとJOINして大チャンク（全文）を取得

BEGIN;

DROP FUNCTION IF EXISTS search_documents_with_chunks(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, TEXT[]);

CREATE OR REPLACE FUNCTION search_documents_with_chunks(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    filter_doc_types TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    document_id UUID,
    file_name VARCHAR,
    doc_type VARCHAR,
    workspace VARCHAR,
    document_date DATE,
    metadata JSONB,
    summary TEXT,
    full_text TEXT,
    chunk_content TEXT,
    chunk_id UUID,
    chunk_index INTEGER,
    chunk_score FLOAT,
    combined_score FLOAT,
    source_type VARCHAR,
    source_url TEXT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    WITH chunk_scores AS (
        -- 小チャンクでベクトル検索 + 全文検索
        SELECT
            dc.id AS chunk_id,
            dc.document_id AS document_id,
            dc.chunk_index AS chunk_index,
            dc.chunk_text AS chunk_content,
            -- ベクトル類似度スコア (0~1)
            (1 - (dc.embedding <=> query_embedding)) AS vector_score,
            -- 全文検索スコア
            ts_rank_cd(
                to_tsvector('simple', dc.chunk_text),
                websearch_to_tsquery('simple', query_text)
            ) AS fulltext_score,
            -- 統合スコア (ベクトル70% + 全文30%)
            (
                (1 - (dc.embedding <=> query_embedding)) * vector_weight +
                ts_rank_cd(
                    to_tsvector('simple', dc.chunk_text),
                    websearch_to_tsquery('simple', query_text)
                ) * fulltext_weight
            ) AS chunk_score
        FROM document_chunks dc
        WHERE
            -- embeddingが存在するチャンクのみ
            dc.embedding IS NOT NULL
            -- 小チャンクのみ（chunk_sizeで判定、大チャンク=全文を除外）
            AND dc.chunk_size <= 500
            -- 類似度フィルタ
            AND (1 - (dc.embedding <=> query_embedding)) >= match_threshold
    ),
    document_best_chunks AS (
        -- ドキュメントごとに最高スコアのチャンクを選択
        SELECT DISTINCT ON (cs.document_id)
            cs.chunk_id,
            cs.document_id,
            cs.chunk_index,
            cs.chunk_content,
            cs.chunk_score
        FROM chunk_scores cs
        ORDER BY cs.document_id, cs.chunk_score DESC
    )
    SELECT
        d.id AS document_id,
        d.file_name,
        d.doc_type,
        d.workspace,
        d.document_date,
        d.metadata,
        d.summary,
        d.full_text,  -- 大チャンク（全文）for回答生成
        dbc.chunk_content,  -- ヒットした小チャンク
        dbc.chunk_id,
        dbc.chunk_index,
        dbc.chunk_score,
        dbc.chunk_score AS combined_score,
        d.source_type,
        d.source_url,
        d.created_at
    FROM document_best_chunks dbc
    INNER JOIN documents d ON d.id = dbc.document_id
    WHERE
        -- doc_typeフィルタ
        (filter_doc_types IS NULL
         OR cardinality(filter_doc_types) = 0
         OR d.doc_type = ANY(filter_doc_types))
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_documents_with_chunks IS '小チャンク検索+大チャンク回答のハイブリッド検索（重複排除＆Rerank対応）';

COMMIT;
