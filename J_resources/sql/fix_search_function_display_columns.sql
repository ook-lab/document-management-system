-- =====================================================
-- 検索関数の修正: classroom_* → display_* カラム名変更対応
-- 作成日: 2025-12-15
-- =====================================================

-- 説明:
-- search_documents_with_chunks関数を更新して、
-- 新しいカラム名（display_*）を返すようにします。

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
    display_subject TEXT,                    -- ✅ 変更: classroom_subject → display_subject
    display_sender VARCHAR(500),             -- ✅ 変更: classroom_sender → display_sender
    classroom_sender_email VARCHAR(500),
    display_sent_at TIMESTAMPTZ,             -- ✅ 変更: classroom_sent_at → display_sent_at
    display_post_text TEXT,                  -- ✅ 変更: classroom_post_text → display_post_text
    display_type VARCHAR(50)                 -- ✅ 変更: classroom_type → display_type
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
        d.attachment_text,
        dbc.chunk_content,
        dbc.chunk_id,
        dbc.chunk_index,
        dbc.chunk_score,
        dbc.chunk_score AS combined_score,
        d.source_type,
        d.source_url,
        d.created_at,
        d.display_subject,              -- ✅ 変更: classroom_subject → display_subject
        d.display_sender,               -- ✅ 変更: classroom_sender → display_sender
        d.classroom_sender_email,
        d.display_sent_at,              -- ✅ 変更: classroom_sent_at → display_sent_at
        d.display_post_text,            -- ✅ 変更: classroom_post_text → display_post_text
        d.display_type                  -- ✅ 変更: classroom_type → display_type
    FROM document_best_chunks dbc
    INNER JOIN source_documents d ON d.id = dbc.document_id
    WHERE
        -- doc_typeフィルタ（指定がある場合のみ）
        (filter_doc_types IS NULL OR d.doc_type = ANY(filter_doc_types))
    ORDER BY dbc.chunk_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- =====================================================
-- 実行後の確認
-- =====================================================
-- SELECT * FROM search_documents_with_chunks(
--     'テスト検索',
--     (SELECT embedding FROM document_chunks LIMIT 1),
--     0.0,
--     5,
--     0.7,
--     0.3,
--     NULL
-- );
