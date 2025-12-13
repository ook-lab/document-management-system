-- documentsテーブルのclassroom関連カラムの存在確認
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'documents'
AND column_name LIKE 'classroom%'
ORDER BY column_name;
