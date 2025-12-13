-- 【実行場所】: Supabase SQL Editor
-- 【対象ファイル】: 新規SQL実行
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行
-- 【目的】: confidence関連のカラムとインデックスを削除
-- 【理由】: confidenceスコアは使用していないため削除

BEGIN;

-- ============================================================
-- documentsテーブルからconfidence関連カラムを削除
-- ============================================================

-- インデックスを削除
DROP INDEX IF EXISTS idx_documents_total_confidence;

-- total_confidenceカラムを削除
ALTER TABLE documents
DROP COLUMN IF EXISTS total_confidence;

-- その他のconfidence関連カラムがあれば削除
-- （念のため確認）
DO $$
BEGIN
    -- confidenceカラムが存在する場合は削除
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'confidence'
    ) THEN
        ALTER TABLE documents DROP COLUMN confidence;
        RAISE NOTICE 'confidenceカラムを削除しました';
    END IF;
END $$;

-- ============================================================
-- hypothetical_questionsテーブルからconfidence_scoreカラムを削除
-- ============================================================

-- confidence_scoreカラムを削除
ALTER TABLE hypothetical_questions
DROP COLUMN IF EXISTS confidence_score;

-- 既存の検索関数を削除（戻り値の型を変更するため必須）
DROP FUNCTION IF EXISTS search_hypothetical_questions(vector,double precision,integer,integer,integer,character varying,character varying);

-- 検索関数を新しい戻り値の型で再作成（confidence_score削除版）
CREATE FUNCTION search_hypothetical_questions(
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
        (1 - (hq.question_embedding <=> query_embedding))::FLOAT AS similarity,
        -- 親ドキュメント情報
        d.file_name,
        d.doc_type,
        d.document_date,
        d.metadata,
        d.summary,
        EXTRACT(YEAR FROM d.document_date)::INTEGER AS year,
        EXTRACT(MONTH FROM d.document_date)::INTEGER AS month
    FROM hypothetical_questions hq
    JOIN document_chunks dc ON hq.chunk_id = dc.id
    JOIN documents d ON dc.document_id = d.id
    WHERE
        (1 - (hq.question_embedding <=> query_embedding)) > match_threshold
        AND (filter_year IS NULL OR EXTRACT(YEAR FROM d.document_date) = filter_year)
        AND (filter_month IS NULL OR EXTRACT(MONTH FROM d.document_date) = filter_month)
        AND (filter_doc_type IS NULL OR d.doc_type = filter_doc_type)
        AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
        AND d.processing_status = 'completed'
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_hypothetical_questions IS '仮想質問ベースのベクトル検索（confidence_score削除版）';

COMMIT;

-- ============================================================
-- 検証クエリ（実行後に確認用）
-- ============================================================

-- confidence関連カラムが削除されたことを確認
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'documents'
  AND column_name LIKE '%confidence%';
-- → 結果が0件であればOK

-- confidence関連インデックスが削除されたことを確認
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'documents'
  AND indexname LIKE '%confidence%';
-- → 結果が0件であればOK
