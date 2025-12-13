-- 【実行場所】: Supabase SQL Editor
-- 【対象ファイル】: 新規SQL実行
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行
-- 【目的】: documentsとemailsテーブルにperson, organization, peopleカラムを追加

BEGIN;

-- ============================================================
-- documentsテーブルにカラムを追加
-- ============================================================

-- person: システムが指定する単一の人物名（文書の担当者・作成者など）
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS person TEXT;

-- organization: システムが指定する単一の組織名（文書の所属組織など）
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS organization TEXT;

-- people: AIが抽出した複数の人物名（文書内に記載された人物）
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS people TEXT[];

-- カラムへのコメント追加
COMMENT ON COLUMN documents.person IS 'システムが指定する担当者・作成者など（単一）';
COMMENT ON COLUMN documents.organization IS 'システムが指定する所属組織など（単一）';
COMMENT ON COLUMN documents.people IS 'AIが抽出した文書内に記載された人物名（複数）';

-- ============================================================
-- emailsテーブルにカラムを追加
-- ============================================================

-- person: システムが指定する単一の人物名（メールの担当者など）
ALTER TABLE emails
ADD COLUMN IF NOT EXISTS person TEXT;

-- organization: システムが指定する単一の組織名（メールの所属組織など）
ALTER TABLE emails
ADD COLUMN IF NOT EXISTS organization TEXT;

-- people: AIが抽出した複数の人物名（メール本文内に記載された人物）
ALTER TABLE emails
ADD COLUMN IF NOT EXISTS people TEXT[];

-- カラムへのコメント追加
COMMENT ON COLUMN emails.person IS 'システムが指定する担当者など（単一）';
COMMENT ON COLUMN emails.organization IS 'システムが指定する所属組織など（単一）';
COMMENT ON COLUMN emails.people IS 'AIが抽出したメール本文内に記載された人物名（複数）';

-- ============================================================
-- インデックス作成（検索パフォーマンス向上）
-- ============================================================

-- documents用インデックス
CREATE INDEX IF NOT EXISTS idx_documents_person ON documents(person) WHERE person IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documents_organization ON documents(organization) WHERE organization IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documents_people ON documents USING GIN(people) WHERE people IS NOT NULL;

-- emails用インデックス
CREATE INDEX IF NOT EXISTS idx_emails_person ON emails(person) WHERE person IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_emails_organization ON emails(organization) WHERE organization IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_emails_people ON emails USING GIN(people) WHERE people IS NOT NULL;

COMMIT;

-- ============================================================
-- 検証クエリ（実行後に確認用）
-- ============================================================

-- カラムが追加されたことを確認
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'documents'
  AND column_name IN ('person', 'organization', 'people')
ORDER BY column_name;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'emails'
  AND column_name IN ('person', 'organization', 'people')
ORDER BY column_name;
