-- =====================================================
-- データベース構造の診断
-- =====================================================

-- 1. すべてのテーブル名を表示
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- 2. source_documentsテーブルのカラムを確認
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'source_documents'
ORDER BY ordinal_position;

-- 3. chunksに関連するテーブルを検索
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name LIKE '%chunk%'
ORDER BY table_name;

-- 4. 検索関数の存在確認
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_name LIKE '%search%'
ORDER BY routine_name;
