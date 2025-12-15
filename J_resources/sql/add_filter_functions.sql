-- =========================================
-- フィルタ機能用SQL関数
-- 実行場所: Supabase SQL Editor
-- 目的: workspace/doc_type一覧の動的取得と複数選択検索
-- =========================================

BEGIN;

-- ■ 1. workspace一覧を取得する関数
CREATE OR REPLACE FUNCTION get_active_workspaces()
RETURNS TABLE (workspace TEXT) AS $$
BEGIN
  RETURN QUERY
  SELECT DISTINCT d.workspace
  FROM documents d
  WHERE d.workspace IS NOT NULL
    AND d.processing_status = 'completed'  -- 完了済みのみ
  ORDER BY d.workspace;
END;
$$ LANGUAGE plpgsql;

-- ■ 2. doc_type一覧を取得する関数（件数付き）
CREATE OR REPLACE FUNCTION get_active_doc_types(filter_workspace TEXT DEFAULT NULL)
RETURNS TABLE (doc_type TEXT, doc_count BIGINT) AS $$
BEGIN
  RETURN QUERY
  SELECT d.doc_type, COUNT(*)::BIGINT as doc_count
  FROM documents d
  WHERE d.doc_type IS NOT NULL
    AND d.processing_status = 'completed'
    AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
  GROUP BY d.doc_type
  ORDER BY d.doc_type;
END;
$$ LANGUAGE plpgsql;

-- ■ 3. hybrid_search関数を配列対応に修正
DROP FUNCTION IF EXISTS hybrid_search(TEXT, vector(1536), TEXT, TEXT, INT);

CREATE OR REPLACE FUNCTION hybrid_search(
    query_text TEXT,
    query_embedding vector(1536),
    target_workspaces TEXT[] DEFAULT NULL,  -- ✅ 配列に変更
    target_types TEXT[] DEFAULT NULL,        -- ✅ 配列に変更
    limit_results INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    source_type VARCHAR,
    source_url TEXT,
    file_name VARCHAR,
    doc_type VARCHAR,
    workspace VARCHAR,
    summary TEXT,
    full_text TEXT,
    metadata JSONB,
    document_date DATE,
    similarity_score FLOAT,
    text_rank FLOAT,
    combined_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.source_type,
        d.source_url,
        d.file_name,
        d.doc_type,
        d.workspace,
        d.summary,
        d.full_text,
        d.metadata,
        d.document_date,
        (1 - (d.embedding <=> query_embedding))::FLOAT AS similarity_score,
        ts_rank(to_tsvector('japanese', COALESCE(d.full_text, '')), plainto_tsquery('japanese', query_text))::FLOAT AS text_rank,
        ((1 - (d.embedding <=> query_embedding)) * 0.7 +
         ts_rank(to_tsvector('japanese', COALESCE(d.full_text, '')), plainto_tsquery('japanese', query_text)) * 0.3)::FLOAT AS combined_score
    FROM documents d
    WHERE
        -- ✅ 配列が空またはNULLならすべて、指定があれば該当のみ
        (target_workspaces IS NULL OR cardinality(target_workspaces) = 0 OR d.workspace = ANY(target_workspaces))
        AND (target_types IS NULL OR cardinality(target_types) = 0 OR d.doc_type = ANY(target_types))
        AND d.processing_status = 'completed'
    ORDER BY combined_score DESC
    LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- =========================================
-- 実行後の確認クエリ（参考）
-- =========================================
-- SELECT * FROM get_active_workspaces();
-- SELECT * FROM get_active_doc_types();
-- SELECT * FROM get_active_doc_types('ikuya_classroom');
