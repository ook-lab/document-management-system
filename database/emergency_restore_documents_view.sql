-- 緊急復旧: documentsビューを再作成
-- デプロイ済みアプリが古いコードのため、ビューが必要

-- documentsビューを作成（source_documentsの完全なエイリアス）
CREATE OR REPLACE VIEW documents AS
SELECT
    id,
    file_name,
    file_type,
    source_type,
    source_id,
    drive_file_id,
    workspace,
    doc_type,
    confidence,
    summary,
    full_text,
    document_date,
    tags,
    metadata,
    processing_status,
    error_message,
    attachment_text,
    embedding,
    created_at,
    updated_at
FROM source_documents;

-- 確認
SELECT
    CASE
        WHEN EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'public' AND viewname = 'documents')
        THEN '✅ documents view restored successfully'
        ELSE '❌ Failed to restore documents view'
    END as status;

-- データ確認
SELECT COUNT(*) as document_count FROM documents;
