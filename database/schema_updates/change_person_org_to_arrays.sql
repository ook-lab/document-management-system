-- 【実行場所】: Supabase SQL Editor
-- 【対象ファイル】: 新規SQL実行
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行
-- 【目的】: person/organizationを単数形から複数形（配列）に変更
-- 【前提】: add_person_organization_people.sqlを先に実行していること

BEGIN;

-- ============================================================
-- documentsテーブル: person → persons, organization → organizations
-- ============================================================

-- 1. 新しい配列カラムを追加
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS persons TEXT[];

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS organizations TEXT[];

-- 2. 既存のpersonデータをpersons配列に移行（NULLでない場合のみ）
UPDATE documents
SET persons = ARRAY[person]
WHERE person IS NOT NULL AND person != '';

-- 3. 既存のorganizationデータをorganizations配列に移行（NULLでない場合のみ）
UPDATE documents
SET organizations = ARRAY[organization]
WHERE organization IS NOT NULL AND organization != '';

-- 4. 古いカラムを削除
ALTER TABLE documents
DROP COLUMN IF EXISTS person;

ALTER TABLE documents
DROP COLUMN IF EXISTS organization;

-- カラムへのコメント追加
COMMENT ON COLUMN documents.persons IS 'システムが指定する担当者・作成者など（複数）';
COMMENT ON COLUMN documents.organizations IS 'システムが指定する所属組織など（複数）';

-- ============================================================
-- emailsテーブル: person → persons, organization → organizations
-- ============================================================

-- 1. 新しい配列カラムを追加
ALTER TABLE emails
ADD COLUMN IF NOT EXISTS persons TEXT[];

ALTER TABLE emails
ADD COLUMN IF NOT EXISTS organizations TEXT[];

-- 2. 既存のpersonデータをpersons配列に移行（NULLでない場合のみ）
UPDATE emails
SET persons = ARRAY[person]
WHERE person IS NOT NULL AND person != '';

-- 3. 既存のorganizationデータをorganizations配列に移行（NULLでない場合のみ）
UPDATE emails
SET organizations = ARRAY[organization]
WHERE organization IS NOT NULL AND organization != '';

-- 4. 古いカラムを削除
ALTER TABLE emails
DROP COLUMN IF EXISTS person;

ALTER TABLE emails
DROP COLUMN IF EXISTS organization;

-- カラムへのコメント追加
COMMENT ON COLUMN emails.persons IS 'システムが指定する担当者など（複数）';
COMMENT ON COLUMN emails.organizations IS 'システムが指定する所属組織など（複数）';

-- ============================================================
-- インデックスの再作成
-- ============================================================

-- 古いインデックスを削除
DROP INDEX IF EXISTS idx_documents_person;
DROP INDEX IF EXISTS idx_documents_organization;
DROP INDEX IF EXISTS idx_emails_person;
DROP INDEX IF EXISTS idx_emails_organization;

-- 新しい配列用インデックスを作成
CREATE INDEX IF NOT EXISTS idx_documents_persons ON documents USING GIN(persons) WHERE persons IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documents_organizations ON documents USING GIN(organizations) WHERE organizations IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_emails_persons ON emails USING GIN(persons) WHERE persons IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_emails_organizations ON emails USING GIN(organizations) WHERE organizations IS NOT NULL;

COMMIT;

-- ============================================================
-- 検証クエリ（実行後に確認用）
-- ============================================================

-- カラムが正しく変更されたことを確認
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'documents'
  AND column_name IN ('persons', 'organizations', 'people')
ORDER BY column_name;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'emails'
  AND column_name IN ('persons', 'organizations', 'people')
ORDER BY column_name;

-- データが移行されたか確認（サンプル）
SELECT id, persons, organizations, people
FROM documents
WHERE persons IS NOT NULL OR organizations IS NOT NULL
LIMIT 5;
