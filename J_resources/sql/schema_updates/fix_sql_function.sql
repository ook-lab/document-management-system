-- Fix hybrid_search_2tier_final to work without chunk_type column
-- This function searches small chunks and returns large chunks for answers

DROP FUNCTION IF EXISTS hybrid_search_2tier_final(
    query_text text,
    query_embedding vector,
    match_threshold float8,
    match_count int,
    vector_weight float8,
    fulltext_weight float8,
    filter_year int,
    filter_month int,
    filter_workspace text
);

CREATE OR REPLACE FUNCTION hybrid_search_2tier_final(
    query_text text,
    query_embedding vector,
    match_threshold float8,
    match_count int,
    vector_weight float8,
    fulltext_weight float8,
    filter_year int,
    filter_month int,
    filter_workspace text
)
RETURNS TABLE (
    id uuid,
    document_id uuid,
    file_name text,
    doc_type text,
    content text,
    full_text text,
    similarity float8,
    metadata jsonb,
    extracted_tables jsonb,
    workspace text,
    combined_score float8
) AS $$
BEGIN
    RETURN QUERY
    WITH small_search AS (
        -- Step 1: Small chunk search (vector + fulltext hybrid)
        SELECT 
            dc.id,
            dc.document_id,
            doc.file_name,
            doc.doc_type,
            dc.chunk_text,
            doc.full_text,
            (1 - (dc.embedding <=> query_embedding))::double precision AS vector_score,
            doc.metadata,
            doc.extracted_tables,
            doc.workspace,
            (
                vector_weight * (1 - (dc.embedding <=> query_embedding)) +
                fulltext_weight * (
                    CASE 
                        WHEN dc.chunk_text @@ plainto_tsquery(query_text) THEN 1.0
                        ELSE 0.0
                    END
                )
            )::double precision AS combined_score
        FROM document_chunks dc
        JOIN documents doc ON dc.document_id = doc.id
        WHERE 
            (1 - (dc.embedding <=> query_embedding)) > match_threshold
            AND (filter_workspace IS NULL OR doc.workspace = filter_workspace)
        ORDER BY combined_score DESC
        LIMIT match_count * 2  -- Get more candidates for deduplication
    ),
    deduped AS (
        -- Step 2: Deduplication - keep highest scoring chunk per document
        SELECT DISTINCT ON (document_id)
            *
        FROM small_search
        ORDER BY document_id, combined_score DESC
        LIMIT match_count
    )
    SELECT 
        deduped.id,
        deduped.document_id,
        deduped.file_name,
        deduped.doc_type,
        deduped.chunk_text,
        deduped.full_text,
        deduped.vector_score,
        deduped.metadata,
        deduped.extracted_tables,
        deduped.workspace,
        deduped.combined_score
    FROM deduped
    ORDER BY deduped.combined_score DESC;
END
$$ LANGUAGE plpgsql;
