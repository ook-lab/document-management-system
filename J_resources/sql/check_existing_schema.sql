-- ============================================================
-- 既存テーブルのカラム構造確認
-- 実行場所: Supabase SQL Editor
-- ============================================================

-- documentsテーブルの全カラムを表示
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'documents'
ORDER BY ordinal_position;

-- document_chunksテーブルの全カラムを表示
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'document_chunks'
ORDER BY ordinal_position;
