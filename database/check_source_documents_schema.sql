-- source_documentsテーブルの実際のスキーマを確認

-- 1. テーブルのカラム一覧を確認
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
    AND table_name = 'source_documents'
ORDER BY ordinal_position;

-- 2. データ件数確認（シンプル版）
SELECT COUNT(*) as total_count FROM source_documents;

-- 3. 最初の1行を取得してカラムを確認
SELECT * FROM source_documents LIMIT 1;
