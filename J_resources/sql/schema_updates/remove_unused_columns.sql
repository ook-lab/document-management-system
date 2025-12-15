-- Remove unused columns from documents and emails tables
-- これらの列は不要になったため削除します
--
-- 実行方法: Supabase SQL Editor で実行してください
-- 注意: この操作は元に戻せません。実行前にバックアップを取ることを推奨します。
--
-- 削除する列:
-- documents テーブル:
--   1. drive_file_id - source_idで十分なため不要
--   2. embedding - documentsテーブルでは使用しない（document_chunksのみ使用）
--   3. llm_provider - 使用されていない
--   4. stage1_confidence - 不要
--   5. extraction_confidence - 不要
-- emails テーブル:
--   1. stage1_confidence - 不要

BEGIN;

-- documents テーブル
-- 1. drive_file_id 列を削除
ALTER TABLE documents DROP COLUMN IF EXISTS drive_file_id;

-- 2. embedding 列を削除
ALTER TABLE documents DROP COLUMN IF EXISTS embedding;

-- 3. llm_provider 列を削除
ALTER TABLE documents DROP COLUMN IF EXISTS llm_provider;

-- 4. stage1_confidence 列を削除
ALTER TABLE documents DROP COLUMN IF EXISTS stage1_confidence;

-- 5. extraction_confidence 列を削除
ALTER TABLE documents DROP COLUMN IF EXISTS extraction_confidence;

-- 6. embedding関連のインデックスを削除（既に削除済みの場合もあるため IF EXISTS を使用）
DROP INDEX IF EXISTS idx_documents_embedding;

-- emails テーブル
-- 1. stage1_confidence 列を削除
ALTER TABLE emails DROP COLUMN IF EXISTS stage1_confidence;

-- 確認用コメント
COMMENT ON TABLE documents IS 'drive_file_id, embedding, llm_provider, stage1_confidence, extraction_confidence 列を削除しました（不要なため）';
COMMENT ON TABLE emails IS 'stage1_confidence 列を削除しました（不要なため）';

COMMIT;
