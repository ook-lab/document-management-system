-- 【実行場所】: Supabase SQL Editor
-- 【対象】: Hypothetical Questions（仮想質問生成）
-- 【目的】: 文書保存時にLLMで質問を事前生成し、検索精度を向上

-- Hypothetical Questionsにより：
-- - ユーザーの質問パターンを事前に予測
-- - 質問ベースの検索で精度が向上
-- - 自然言語クエリに強くなる

BEGIN;

-- hypothetical_questions テーブルを作成
CREATE TABLE IF NOT EXISTS hypothetical_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id UUID REFERENCES document_chunks(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_embedding vector(1536) NOT NULL,
    confidence_score FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- インデックス
    CONSTRAINT unique_question_per_chunk UNIQUE (chunk_id, question_text)
);

-- インデックス作成（高速検索のため）
CREATE INDEX IF NOT EXISTS idx_hypothetical_questions_document_id
    ON hypothetical_questions(document_id);

CREATE INDEX IF NOT EXISTS idx_hypothetical_questions_chunk_id
    ON hypothetical_questions(chunk_id);

-- ベクトル検索用インデックス（cosine distance）
CREATE INDEX IF NOT EXISTS idx_hypothetical_questions_embedding
    ON hypothetical_questions
    USING ivfflat (question_embedding vector_cosine_ops)
    WITH (lists = 100);

COMMENT ON TABLE hypothetical_questions IS '文書保存時に生成された仮想質問';
COMMENT ON COLUMN hypothetical_questions.question_text IS 'LLMが生成した質問';
COMMENT ON COLUMN hypothetical_questions.question_embedding IS '質問のembeddingベクトル';
COMMENT ON COLUMN hypothetical_questions.confidence_score IS '質問の信頼度（0.0-1.0）';

-- 仮想質問を使った検索関数
CREATE OR REPLACE FUNCTION search_hypothetical_questions(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 20,
    -- メタデータフィルタ
    filter_year INT DEFAULT NULL,
    filter_month INT DEFAULT NULL,
    filter_doc_type VARCHAR DEFAULT NULL,
    filter_workspace VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    question_id UUID,
    question_text TEXT,
    chunk_id UUID,
    document_id UUID,
    chunk_text TEXT,
    similarity FLOAT,
    confidence_score FLOAT,
    combined_score FLOAT,
    -- 親ドキュメント情報
    file_name VARCHAR,
    doc_type VARCHAR,
    document_date DATE,
    metadata JSONB,
    summary TEXT,
    year INTEGER,
    month INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        hq.id AS question_id,
        hq.question_text,
        hq.chunk_id,
        dc.document_id,
        dc.chunk_text,
        1 - (hq.question_embedding <=> query_embedding) AS similarity,
        hq.confidence_score,
        -- 質問の類似度とconfidenceを掛け合わせたスコア
        (1 - (hq.question_embedding <=> query_embedding)) * hq.confidence_score AS combined_score,
        d.file_name,
        d.doc_type,
        d.document_date,
        d.metadata,
        d.summary,
        d.year,
        d.month
    FROM hypothetical_questions hq
    JOIN document_chunks dc ON hq.chunk_id = dc.id
    JOIN documents d ON dc.document_id = d.id
    WHERE
        d.processing_status = 'completed'
        -- 類似度が閾値以上
        AND (1 - (hq.question_embedding <=> query_embedding)) > match_threshold
        -- メタデータフィルタリング
        AND (filter_year IS NULL OR d.year = filter_year)
        AND (filter_month IS NULL OR d.month = filter_month)
        AND (filter_doc_type IS NULL OR d.doc_type = filter_doc_type)
        AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- ハイブリッド検索（通常検索 + 質問検索）
CREATE OR REPLACE FUNCTION hybrid_search_with_questions(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 50,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    question_weight FLOAT DEFAULT 0.5,
    -- メタデータフィルタ
    filter_year INT DEFAULT NULL,
    filter_month INT DEFAULT NULL,
    filter_doc_type VARCHAR DEFAULT NULL,
    filter_workspace VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    chunk_text TEXT,
    similarity FLOAT,
    question_match BOOLEAN,
    matched_question TEXT,
    combined_score FLOAT,
    -- 親ドキュメント情報
    file_name VARCHAR,
    doc_type VARCHAR,
    document_date DATE,
    metadata JSONB,
    summary TEXT,
    year INTEGER,
    month INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH
    -- 通常のチャンク検索
    chunk_search AS (
        SELECT
            dc.id AS chunk_id,
            dc.document_id,
            dc.chunk_text,
            1 - (dc.embedding <=> query_embedding) AS similarity,
            false AS question_match,
            NULL::TEXT AS matched_question,
            (1 - (dc.embedding <=> query_embedding)) * vector_weight +
            ts_rank(dc.chunk_text_tsv, plainto_tsquery('simple', query_text)) * fulltext_weight AS combined_score,
            d.file_name,
            d.doc_type,
            d.document_date,
            d.metadata,
            d.summary,
            d.year,
            d.month
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE
            d.processing_status = 'completed'
            AND dc.is_parent = false
            AND (
                (1 - (dc.embedding <=> query_embedding)) > match_threshold
                OR
                dc.chunk_text_tsv @@ plainto_tsquery('simple', query_text)
            )
            AND (filter_year IS NULL OR d.year = filter_year)
            AND (filter_month IS NULL OR d.month = filter_month)
            AND (filter_doc_type IS NULL OR d.doc_type = filter_doc_type)
            AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
    ),
    -- 質問検索
    question_search AS (
        SELECT
            dc.id AS chunk_id,
            dc.document_id,
            dc.chunk_text,
            1 - (hq.question_embedding <=> query_embedding) AS similarity,
            true AS question_match,
            hq.question_text AS matched_question,
            (1 - (hq.question_embedding <=> query_embedding)) * hq.confidence_score * question_weight AS combined_score,
            d.file_name,
            d.doc_type,
            d.document_date,
            d.metadata,
            d.summary,
            d.year,
            d.month
        FROM hypothetical_questions hq
        JOIN document_chunks dc ON hq.chunk_id = dc.id
        JOIN documents d ON dc.document_id = d.id
        WHERE
            d.processing_status = 'completed'
            AND (1 - (hq.question_embedding <=> query_embedding)) > 0.7
            AND (filter_year IS NULL OR d.year = filter_year)
            AND (filter_month IS NULL OR d.month = filter_month)
            AND (filter_doc_type IS NULL OR d.doc_type = filter_doc_type)
            AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
    )
    -- 両方の結果を統合
    SELECT * FROM (
        SELECT * FROM chunk_search
        UNION ALL
        SELECT * FROM question_search
    ) AS combined
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;
