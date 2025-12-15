-- 【実行場所】: Supabase SQL Editor
-- 【対象】: documents テーブルにレビュー状態カラムを追加
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行
-- 【目的】: レビューUI用のステータス管理機能を追加

-- レビューステータス管理
-- 全件レビューを可能にしつつ、チェック済みは非表示、検索で呼び出し可能にする

BEGIN;

-- ============================================================================
-- Step 1: documents テーブルにレビュー状態カラムを追加
-- ============================================================================

-- is_reviewed: レビュー済みかどうか（デフォルト: false）
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS is_reviewed BOOLEAN DEFAULT FALSE;

-- reviewed_at: レビュー完了日時
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

-- reviewed_by: レビュー担当者のメールアドレス（オプション）
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS reviewed_by TEXT;

-- カラムの説明
COMMENT ON COLUMN documents.is_reviewed IS
'レビュー済みフラグ。trueの場合は通常リストに表示されない。';

COMMENT ON COLUMN documents.reviewed_at IS
'レビュー完了日時。レビュー済みにした時刻を記録。';

COMMENT ON COLUMN documents.reviewed_by IS
'レビューを実施した担当者のメールアドレス。';

-- ============================================================================
-- Step 2: インデックスの作成
-- ============================================================================

-- is_reviewed でのフィルタリングを高速化
CREATE INDEX IF NOT EXISTS idx_documents_is_reviewed
ON documents(is_reviewed, updated_at DESC);

-- レビュー済みドキュメントの検索用
CREATE INDEX IF NOT EXISTS idx_documents_reviewed_at
ON documents(reviewed_at DESC)
WHERE reviewed_at IS NOT NULL;

-- ============================================================================
-- Step 3: 既存データの初期化（オプション）
-- ============================================================================

-- 既存のドキュメントはすべて未レビューとして扱う
-- （すでにデフォルト値がFALSEなので、この更新は不要だが念のため実行）
UPDATE documents
SET is_reviewed = FALSE
WHERE is_reviewed IS NULL;

-- ============================================================================
-- Step 4: 統計情報の更新
-- ============================================================================

DO $$
DECLARE
    total_count INTEGER;
    reviewed_count INTEGER;
    unreviewed_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_count FROM documents;
    SELECT COUNT(*) INTO reviewed_count FROM documents WHERE is_reviewed = TRUE;
    SELECT COUNT(*) INTO unreviewed_count FROM documents WHERE is_reviewed = FALSE;

    RAISE NOTICE '============================================';
    RAISE NOTICE 'レビューステータス機能が追加されました';
    RAISE NOTICE '============================================';
    RAISE NOTICE '総ドキュメント数: %', total_count;
    RAISE NOTICE '未レビュー: %', unreviewed_count;
    RAISE NOTICE 'レビュー済み: %', reviewed_count;
    RAISE NOTICE '============================================';
    RAISE NOTICE 'カラム追加完了:';
    RAISE NOTICE '  - is_reviewed (boolean)';
    RAISE NOTICE '  - reviewed_at (timestamptz)';
    RAISE NOTICE '  - reviewed_by (text)';
    RAISE NOTICE 'インデックス作成完了:';
    RAISE NOTICE '  - idx_documents_is_reviewed';
    RAISE NOTICE '  - idx_documents_reviewed_at';
    RAISE NOTICE '============================================';
END $$;

COMMIT;

-- ============================================================================
-- 【確認クエリ】
-- ============================================================================

-- カラム追加確認
-- SELECT
--     column_name,
--     data_type,
--     column_default,
--     is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'documents'
-- AND column_name IN ('is_reviewed', 'reviewed_at', 'reviewed_by')
-- ORDER BY ordinal_position;

-- インデックス確認
-- SELECT
--     indexname,
--     indexdef
-- FROM pg_indexes
-- WHERE tablename = 'documents'
-- AND indexname LIKE '%review%'
-- ORDER BY indexname;

-- レビュー状態別の件数確認
-- SELECT
--     is_reviewed,
--     COUNT(*) as count
-- FROM documents
-- GROUP BY is_reviewed
-- ORDER BY is_reviewed;

-- ============================================================================
-- 【サンプルクエリ】
-- ============================================================================

-- 未レビューのドキュメント一覧（最新50件）
-- SELECT
--     id,
--     file_name,
--     doc_type,
--     confidence,
--     created_at
-- FROM documents
-- WHERE is_reviewed = FALSE
-- ORDER BY updated_at DESC
-- LIMIT 50;

-- レビュー済みのドキュメント検索（file_nameで部分一致）
-- SELECT
--     id,
--     file_name,
--     doc_type,
--     reviewed_at,
--     reviewed_by
-- FROM documents
-- WHERE is_reviewed = TRUE
-- AND file_name ILIKE '%検索ワード%'
-- ORDER BY reviewed_at DESC
-- LIMIT 10;

-- レビュー進捗状況
-- SELECT
--     COUNT(*) FILTER (WHERE is_reviewed = FALSE) as unreviewed,
--     COUNT(*) FILTER (WHERE is_reviewed = TRUE) as reviewed,
--     COUNT(*) as total,
--     ROUND(100.0 * COUNT(*) FILTER (WHERE is_reviewed = TRUE) / COUNT(*), 2) as progress_percent
-- FROM documents;
