-- ============================================================
-- ステップ2: データ移行
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-14
-- 前提: step1_create_tables.sql が実行済みであること
-- ============================================================

BEGIN;

-- ============================================================
-- 1. source_documentsへデータ移行
-- ============================================================
INSERT INTO source_documents (
    id, source_type, source_id, source_url, ingestion_route,
    file_name, file_type,
    workspace, doc_type,
    summary,
    classroom_sender, classroom_sender_email, classroom_sent_at,
    classroom_subject, classroom_post_text, classroom_type,
    metadata, tags, document_date, content_hash,
    created_at, updated_at
)
SELECT
    id, source_type, source_id, source_url, ingestion_route,
    file_name, file_type,
    workspace, doc_type,
    summary,
    classroom_sender,
    classroom_sender_email,
    classroom_sent_at,
    classroom_subject,
    classroom_post_text,
    classroom_type,
    metadata, tags, document_date, content_hash,
    created_at, updated_at
FROM documents
ON CONFLICT (source_id) DO NOTHING;

-- ============================================================
-- 2. process_logsへデータ移行
-- ============================================================
INSERT INTO process_logs (
    document_id, processing_status, processing_stage,
    prompt_version,
    processing_duration_ms, inference_time,
    error_message, version, updated_by,
    processed_at, created_at, updated_at
)
SELECT
    id, processing_status, processing_stage,
    prompt_version,
    processing_duration_ms, inference_time,
    error_message, version, updated_by,
    updated_at, created_at, updated_at
FROM documents;

-- ============================================================
-- 3. search_indexへデータ移行
-- ============================================================
INSERT INTO search_index (
    id, document_id, chunk_index, chunk_content, chunk_size,
    chunk_type, search_weight, embedding,
    page_numbers, section_title,
    created_at, updated_at
)
SELECT
    id, document_id, chunk_index, chunk_text, chunk_size,
    chunk_type, search_weight, embedding,
    page_numbers, section_title,
    created_at, updated_at
FROM document_chunks
ON CONFLICT (document_id, chunk_index) DO NOTHING;

COMMIT;

-- ============================================================
-- 完了メッセージと統計
-- ============================================================
SELECT
    'ステップ2完了: データ移行が成功しました' AS status,
    (SELECT COUNT(*) FROM source_documents) AS source_documents_count,
    (SELECT COUNT(*) FROM process_logs) AS process_logs_count,
    (SELECT COUNT(*) FROM search_index) AS search_index_count;
