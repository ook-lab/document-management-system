-- search_documents_with_chunks を3-tier構造に更新
-- document_chunks → search_index
-- documents → source_documents

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
    file_name VARCHAR(500),
    doc_type VARCHAR(100),
    workspace VARCHAR(50),
    document_date DATE,
    metadata JSONB,
    summary TEXT,
    attachment_text TEXT,
    chunk_content TEXT,
    chunk_id UUID,
    chunk_index INTEGER,
    chunk_score FLOAT,
    combined_score FLOAT,
    source_type VARCHAR(50),
    source_url TEXT,
    created_at TIMESTAMPTZ,
    classroom_subject TEXT,
    classroom_sender VARCHAR(500),
    classroom_sender_email VARCHAR(500),
    classroom_sent_at TIMESTAMPTZ,
    classroom_post_text TEXT,
    classroom_type VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    WITH chunk_scores AS (
        -- 小チャンクでベクトル検索 + 全文検索
        SELECT
            si.id AS chunk_id,
            si.document_id AS document_id,
            si.chunk_index AS chunk_index,
            si.chunk_content AS chunk_content,  -- ✅ chunk_text → chunk_content
            -- ベクトル類似度スコア (0~1)
            (1 - (si.embedding <=> query_embedding)) AS vector_score,
            -- 全文検索スコア
            ts_rank_cd(
                to_tsvector('simple', si.chunk_content),
                websearch_to_tsquery('simple', query_text)
            ) AS fulltext_score,
            -- 統合スコア (ベクトル70% + 全文30%)
            (
                (1 - (si.embedding <=> query_embedding)) * vector_weight +
                ts_rank_cd(
                    to_tsvector('simple', si.chunk_content),
                    websearch_to_tsquery('simple', query_text)
                ) * fulltext_weight
            ) AS chunk_score
        FROM search_index si  -- ✅ document_chunks → search_index
        WHERE
            -- embeddingが存在するチャンクのみ
            si.embedding IS NOT NULL
            -- 小チャンクのみ（chunk_sizeで判定、大チャンク=全文を除外）
            AND si.chunk_size <= 500
            -- 類似度フィルタ
            AND (1 - (si.embedding <=> query_embedding)) >= match_threshold
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
        COALESCE(d.full_text, d.summary, '') AS attachment_text,  -- ✅ attachment_text → full_text
        dbc.chunk_content,  -- ヒットした小チャンク
        dbc.chunk_id,
        dbc.chunk_index,
        dbc.chunk_score,
        dbc.chunk_score AS combined_score,
        d.source_type,
        d.source_url,
        d.created_at,
        d.classroom_subject,
        d.classroom_sender,
        d.classroom_sender_email,
        d.classroom_sent_at,
        d.classroom_post_text,
        d.classroom_type
    FROM document_best_chunks dbc
    INNER JOIN source_documents d ON d.id = dbc.document_id  -- ✅ documents → source_documents
    INNER JOIN process_logs pl ON d.id = pl.document_id      -- ✅ processing_status確認のため追加
    WHERE
        -- processing_status確認
        pl.processing_status = 'completed'  -- ✅ 処理完了済みのみ
        -- doc_typeフィルタ
        AND (filter_doc_types IS NULL
         OR cardinality(filter_doc_types) = 0
         OR d.doc_type = ANY(filter_doc_types))
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_documents_with_chunks IS '小チャンク検索+大チャンク回答のハイブリッド検索（3-tier構造対応）';

COMMIT;

-- 確認
SELECT '✅ search_documents_with_chunks updated for 3-tier architecture' as status;
