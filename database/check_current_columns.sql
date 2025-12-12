-- 現在のdocumentsテーブルのカラム一覧を確認
-- 実行場所: Supabase SQL Editor

SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_name = 'documents'
ORDER BY ordinal_position;
