-- 【実行場所】: Supabase SQL Editor
-- 【対象ファイル】: 新規SQL実行
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行
-- 【目的】: source_documentsテーブルにpeopleカラムを追加（将来使用予定）

BEGIN;

-- ============================================================
-- source_documentsテーブルにpeopleカラムを追加
-- ============================================================

-- people: 将来、AIが抽出した複数の人物名を格納する予定（文書内に記載された人物）
ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS people TEXT[];

-- カラムへのコメント追加
COMMENT ON COLUMN source_documents.people IS 'AIが抽出した文書内に記載された人物名（複数）- 将来使用予定';

-- ============================================================
-- インデックス作成（検索パフォーマンス向上）
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_source_documents_people
ON source_documents USING GIN(people)
WHERE people IS NOT NULL;

COMMIT;

-- ============================================================
-- 検証クエリ（実行後に確認用）
-- ============================================================

-- カラムが追加されたことを確認
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'source_documents'
  AND column_name IN ('persons', 'people', 'organizations')
ORDER BY column_name;
