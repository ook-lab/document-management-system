-- search_documents_with_chunks関数を更新
-- Classroom投稿の表示に必要なフィールドを追加

-- 既存の関数を削除
DROP FUNCTION IF EXISTS public.search_documents_with_chunks(text, vector, double precision, integer, double precision, double precision, text[]);

-- 新しい定義で関数を作成
CREATE OR REPLACE FUNCTION public.search_documents_with_chunks(
    query_text text,
    query_embedding vector,
    match_threshold double precision DEFAULT 0.0,
    match_count integer DEFAULT 10,
    vector_weight double precision DEFAULT 0.7,
    fulltext_weight double precision DEFAULT 0.3,
    filter_doc_types text[] DEFAULT NULL::text[]
)
RETURNS TABLE(
    document_id uuid,
    file_name character varying,
    doc_type character varying,
    workspace character varying,
    document_date date,
    metadata jsonb,
    summary text,
    full_text text,
    chunk_content text,
    chunk_id uuid,
    chunk_index integer,
    chunk_score double precision,
    combined_score double precision,
    source_type character varying,
    source_url text,
    created_at timestamp with time zone,
    -- ✅ Classroom投稿用フィールドを追加
    classroom_subject text,
    classroom_sender character varying,
    classroom_sender_email character varying,
    classroom_sent_at timestamp with time zone,
    classroom_course_id character varying,
    classroom_course_name character varying
)
LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    WITH chunk_scores AS (
        SELECT
            dc.id AS chunk_id,
            dc.document_id AS document_id,
            dc.chunk_index AS chunk_index,
            dc.chunk_text AS chunk_content,
            (1 - (dc.embedding <=> query_embedding)) AS vector_score,
            ts_rank_cd(
                to_tsvector('simple', dc.chunk_text),
                websearch_to_tsquery('simple', query_text)
            ) AS fulltext_score,
            (
                (1 - (dc.embedding <=> query_embedding)) * vector_weight +
                ts_rank_cd(
                    to_tsvector('simple', dc.chunk_text),
                    websearch_to_tsquery('simple', query_text)
                ) * fulltext_weight
            ) AS chunk_score
        FROM document_chunks dc
        WHERE
            dc.embedding IS NOT NULL
            AND dc.chunk_size <= 500
            AND (1 - (dc.embedding <=> query_embedding)) >= match_threshold
    ),
    document_best_chunks AS (
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
        d.full_text,
        dbc.chunk_content,
        dbc.chunk_id,
        dbc.chunk_index,
        dbc.chunk_score,
        dbc.chunk_score AS combined_score,
        d.source_type,
        d.source_url,
        d.created_at,
        -- ✅ Classroom投稿用フィールドを返す
        d.classroom_subject,
        d.classroom_sender,
        d.classroom_sender_email,
        d.classroom_sent_at,
        d.classroom_course_id,
        d.classroom_course_name
    FROM document_best_chunks dbc
    INNER JOIN documents d ON d.id = dbc.document_id
    WHERE
        (filter_doc_types IS NULL
         OR cardinality(filter_doc_types) = 0
         OR d.doc_type = ANY(filter_doc_types))
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$function$;
