-- source_documentsテーブルにchunk_countカラムを追加
-- 実行場所: Supabase SQL Editor

BEGIN;

ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS chunk_count INTEGER DEFAULT 0;

-- 既存ドキュメントのchunk_countを初期化（必要に応じて）
UPDATE source_documents
SET chunk_count = 0
WHERE chunk_count IS NULL;

COMMIT;

-- 確認クエリ
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'source_documents' AND column_name = 'chunk_count';
