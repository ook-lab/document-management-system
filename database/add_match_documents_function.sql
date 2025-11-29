-- match_documents関数の追加
-- Supabase SQL Editorで実行してください
--
-- この関数は、ベクトル検索（cosine類似度）でdocumentsテーブルから関連文書を検索します

CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.2,
    match_count int DEFAULT 10,
    filter_workspace text DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    source_type varchar,
    source_id varchar,
    title text,
    content text,
    doc_type varchar,
    workspace varchar,
    document_date date,
    file_name varchar,
    similarity float,
    metadata jsonb,
    created_at timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.source_type,
        d.source_id,
        COALESCE(d.file_name, '無題') as title,
        COALESCE(d.summary, d.full_text, '') as content,
        d.doc_type,
        d.workspace,
        d.document_date,
        d.file_name,
        1 - (d.embedding <=> query_embedding) as similarity,
        d.metadata,
        d.created_at
    FROM documents d
    WHERE
        d.embedding IS NOT NULL
        AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
        AND (1 - (d.embedding <=> query_embedding)) >= match_threshold
        AND d.processing_status = 'completed'
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- インデックスが既に存在する場合はスキップ
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops);

-- 関数の説明
COMMENT ON FUNCTION match_documents IS 'ベクトル検索（cosine類似度）でdocumentsテーブルから関連文書を検索';
