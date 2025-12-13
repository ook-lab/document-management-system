-- 不要なClassroom関連カラムの削除
-- 実行場所: Supabase SQL Editor
-- 実行日: 2025-12-13

BEGIN;

-- 1. 不要なカラムを削除
ALTER TABLE documents
DROP COLUMN IF EXISTS classroom_course_id,
DROP COLUMN IF EXISTS classroom_course_name,
DROP COLUMN IF EXISTS text_extraction_model;

-- 2. 削除されたことを確認するクエリ
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'documents'
AND column_name IN (
    'classroom_course_id',
    'classroom_course_name',
    'text_extraction_model'
)
ORDER BY column_name;

-- 3. 残っているclassroom関連カラムを確認
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'documents'
AND column_name LIKE '%classroom%'
ORDER BY column_name;

COMMIT;

-- 期待される結果:
-- - classroom_course_id, classroom_course_name, text_extraction_model は削除される
-- - classroom_sender, classroom_sender_email, classroom_sent_at, classroom_subject, classroom_post_text は残る
