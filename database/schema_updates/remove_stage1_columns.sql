-- Remove stage1_workspace and stage1_doc_type columns
-- これらの列は不要になったため削除します
--
-- 実行方法: Supabase SQL Editor で実行してください
-- 注意: この操作は元に戻せません。実行前にバックアップを取ることを推奨します。

BEGIN;

-- 1. stage1_doc_type 列を削除
ALTER TABLE documents DROP COLUMN IF EXISTS stage1_doc_type;

-- 2. stage1_workspace 列を削除
ALTER TABLE documents DROP COLUMN IF EXISTS stage1_workspace;

-- 確認用コメント
COMMENT ON TABLE documents IS 'stage1_doc_type と stage1_workspace 列を削除しました（不要なため）';

COMMIT;
