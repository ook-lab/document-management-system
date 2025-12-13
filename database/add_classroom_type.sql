-- classroom_type カラムの追加
-- 実行場所: Supabase SQL Editor
-- 実行日: 2025-12-13

BEGIN;

-- classroom_type カラムを追加
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS classroom_type VARCHAR(50);

-- インデックスを追加（検索パフォーマンス向上）
CREATE INDEX IF NOT EXISTS idx_documents_classroom_type ON documents(classroom_type);

-- コメントの追加
COMMENT ON COLUMN documents.classroom_type IS 'Google Classroom投稿の種別（お知らせ、課題、資料）';

-- 確認クエリ
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'documents'
AND column_name = 'classroom_type';

COMMIT;
