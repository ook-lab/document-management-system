-- doc_type列を削除し、workspaceを意味的な分類のメイン軸として使用
--
-- 変更内容:
-- 1. source_type: 技術的な出所（gmail, drive）
-- 2. file_type: ファイル形式（pdf, excel, email）
-- 3. workspace: 意味的な分類（★メインの分類軸）
-- 4. doc_type: 削除
--
-- workspace値:
-- - IKUYA_SCHOOL, IKUYA_JUKU, IKUYA_EXAM
-- - EMA_SCHOOL
-- - HOME_LIVING, HOME_COOKING
-- - YOSHINORI_PRIVATE_FOLDER
-- - BUSINESS_WORK
-- - IKUYA_MAIL, EMA_MAIL, WORK_MAIL, DM_MAIL, JOB_MAIL, MONEY_MAIL

-- 1. doc_type列を削除（存在する場合）
ALTER TABLE documents DROP COLUMN IF EXISTS doc_type;

-- 2. stage1_doc_type列も削除（もう使わない）
ALTER TABLE documents DROP COLUMN IF EXISTS stage1_doc_type;

-- 3. workspaceにインデックスを追加（検索高速化）
CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace);

-- 4. source_type + workspace の複合インデックス（よく使う組み合わせ）
CREATE INDEX IF NOT EXISTS idx_documents_source_workspace ON documents(source_type, workspace);

-- 5. file_type + workspace の複合インデックス
CREATE INDEX IF NOT EXISTS idx_documents_filetype_workspace ON documents(file_type, workspace);

-- 確認用コメント
COMMENT ON COLUMN documents.source_type IS '技術的な出所: gmail, drive';
COMMENT ON COLUMN documents.file_type IS 'ファイル形式: pdf, excel, email';
COMMENT ON COLUMN documents.workspace IS '意味的な分類（メイン軸）: IKUYA_SCHOOL, WORK_MAIL, など';
