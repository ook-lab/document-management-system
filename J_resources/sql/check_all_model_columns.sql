-- documentsテーブルの全カラムを確認
-- 実行場所: Supabase SQL Editor

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'documents'
AND column_name LIKE '%model%'
ORDER BY column_name;
