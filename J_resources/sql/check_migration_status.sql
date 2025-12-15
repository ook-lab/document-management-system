-- ============================================================
-- マイグレーション状態確認
-- 実行場所: Supabase SQL Editor
-- ============================================================

-- 既存テーブルの確認
SELECT
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
    AND table_name IN (
        'documents',
        'documents_legacy',
        'document_chunks',
        'document_chunks_legacy',
        'source_documents',
        'process_logs',
        'search_index'
    )
ORDER BY table_name;

-- 結果の解釈:
-- - documents (BASE TABLE) → 既存の実テーブルが残っている
-- - documents (VIEW) → ビューに置き換わっている
-- - source_documents (BASE TABLE) → 新テーブルが作成されている
