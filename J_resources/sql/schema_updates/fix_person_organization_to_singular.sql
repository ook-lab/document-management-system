-- 【実行場所】: Supabase SQL Editor
-- 【対象ファイル】: 新規SQL実行
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行
-- 【目的】: persons/organizations を person/organization（単数形）に修正

BEGIN;

-- ============================================================
-- 単数形フィールドを追加
-- ============================================================

-- person: システムが指定する単一の人物名（文書の担当者・作成者など）
ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS person TEXT;

-- organization: システムが指定する単一の組織名（文書の所属組織など）
ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS organization TEXT;

COMMENT ON COLUMN source_documents.person IS 'システムが指定する担当者・作成者（単一）';
COMMENT ON COLUMN source_documents.organization IS 'システムが指定する所属組織（単一）';

-- ============================================================
-- 既存データの移行（複数形→単数形）
-- ============================================================

-- persons配列の最初の要素をpersonにコピー
UPDATE source_documents
SET person = persons[1]
WHERE persons IS NOT NULL
  AND array_length(persons, 1) > 0
  AND person IS NULL;

-- organizations配列の最初の要素をorganizationにコピー
UPDATE source_documents
SET organization = organizations[1]
WHERE organizations IS NOT NULL
  AND array_length(organizations, 1) > 0
  AND organization IS NULL;

-- ============================================================
-- 複数形フィールドを削除
-- ============================================================

DROP INDEX IF EXISTS idx_source_documents_persons;
DROP INDEX IF EXISTS idx_source_documents_organizations;

ALTER TABLE source_documents
DROP COLUMN IF EXISTS persons;

ALTER TABLE source_documents
DROP COLUMN IF EXISTS organizations;

-- ============================================================
-- 新しいインデックスを作成
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_source_documents_person
ON source_documents(person)
WHERE person IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_source_documents_organization
ON source_documents(organization)
WHERE organization IS NOT NULL;

COMMIT;

-- ============================================================
-- 検証クエリ（実行後に確認用）
-- ============================================================

-- カラムが修正されたことを確認
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'source_documents'
  AND column_name IN ('person', 'organization', 'people')
ORDER BY column_name;

-- データが移行されたことを確認
SELECT
    COUNT(*) as total_docs,
    COUNT(person) as docs_with_person,
    COUNT(organization) as docs_with_organization,
    COUNT(people) as docs_with_people
FROM source_documents;

-- 移行されたデータの例
SELECT id, file_name, person, organization, people
FROM source_documents
WHERE person IS NOT NULL OR organization IS NOT NULL
LIMIT 5;
