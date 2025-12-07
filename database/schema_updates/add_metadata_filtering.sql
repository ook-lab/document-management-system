-- 【実行場所】: Supabase SQL Editor
-- 【対象】: メタデータフィルタリング強化
-- 【目的】: 条件付き検索（「2023年の予算案」など）の高速化

-- メタデータフィルタリングにより、検索前にWHERE句で絞り込むことで
-- 検索精度と速度が大幅に向上します

BEGIN;

-- documents テーブルにフィルタリング用カラムを追加
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS year INTEGER,           -- 文書の年（例：2023）
    ADD COLUMN IF NOT EXISTS month INTEGER,          -- 文書の月（例：12）
    ADD COLUMN IF NOT EXISTS amount NUMERIC,         -- 金額（請求書、契約書など）
    ADD COLUMN IF NOT EXISTS event_dates DATE[],     -- イベント日付の配列（学校行事など）
    ADD COLUMN IF NOT EXISTS grade_level VARCHAR(50), -- 学年（学校関連文書）
    ADD COLUMN IF NOT EXISTS school_name VARCHAR(200); -- 学校名（学校関連文書）

-- インデックス作成（高速フィルタリングのため）
CREATE INDEX IF NOT EXISTS idx_documents_year ON documents(year);
CREATE INDEX IF NOT EXISTS idx_documents_month ON documents(month);
CREATE INDEX IF NOT EXISTS idx_documents_year_month ON documents(year, month); -- 複合インデックス
CREATE INDEX IF NOT EXISTS idx_documents_amount ON documents(amount);
CREATE INDEX IF NOT EXISTS idx_documents_event_dates ON documents USING GIN(event_dates); -- 配列用インデックス
CREATE INDEX IF NOT EXISTS idx_documents_grade_level ON documents(grade_level);
CREATE INDEX IF NOT EXISTS idx_documents_school_name ON documents(school_name);

-- document_chunks テーブルにもフィルタリング用カラムを追加（JOIN不要で高速化）
ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS year INTEGER,
    ADD COLUMN IF NOT EXISTS month INTEGER;

-- チャンク検索関数をフィルタリング対応に更新
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 50,
    filter_year INT DEFAULT NULL,
    filter_month INT DEFAULT NULL,
    filter_doc_type VARCHAR DEFAULT NULL,
    filter_workspace VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    chunk_index INTEGER,
    chunk_text TEXT,
    similarity FLOAT,
    -- 親ドキュメント情報も結合して返す
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
        dc.id AS chunk_id,
        dc.document_id,
        dc.chunk_index,
        dc.chunk_text,
        1 - (dc.embedding <=> query_embedding) AS similarity,
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
        AND (1 - (dc.embedding <=> query_embedding)) > match_threshold
        -- メタデータフィルタリング
        AND (filter_year IS NULL OR d.year = filter_year)
        AND (filter_month IS NULL OR d.month = filter_month)
        AND (filter_doc_type IS NULL OR d.doc_type = filter_doc_type)
        AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- 文書検索関数もフィルタリング対応に更新（後方互換性のため）
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 50,
    filter_year INT DEFAULT NULL,
    filter_month INT DEFAULT NULL,
    filter_doc_type VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    file_name VARCHAR,
    doc_type VARCHAR,
    document_date DATE,
    similarity FLOAT,
    year INTEGER,
    month INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.file_name,
        d.doc_type,
        d.document_date,
        1 - (d.embedding <=> query_embedding) AS similarity,
        d.year,
        d.month
    FROM documents d
    WHERE
        d.processing_status = 'completed'
        AND d.embedding IS NOT NULL
        AND (1 - (d.embedding <=> query_embedding)) > match_threshold
        -- メタデータフィルタリング
        AND (filter_year IS NULL OR d.year = filter_year)
        AND (filter_month IS NULL OR d.month = filter_month)
        AND (filter_doc_type IS NULL OR d.doc_type = filter_doc_type)
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;
