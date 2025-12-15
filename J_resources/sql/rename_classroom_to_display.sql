-- =====================================================
-- カラム名変更マイグレーション
-- classroom_* → display_* へのリネーム
-- 作成日: 2025-12-15
-- =====================================================

-- 説明:
-- Classroom関連のカラム名を、より汎用的な「display_」プレフィックスに変更します。
-- これにより、将来的に他のソース（Gmail、Slack等）からのデータも
-- 同じカラムに統一して表示できるようになります。

BEGIN;

-- 1. classroom_subject → display_subject（件名/タイトル）
ALTER TABLE source_documents
RENAME COLUMN classroom_subject TO display_subject;

-- 2. classroom_sender → display_sender（送信者名）
ALTER TABLE source_documents
RENAME COLUMN classroom_sender TO display_sender;

-- 3. classroom_post_text → display_post_text（投稿本文）
ALTER TABLE source_documents
RENAME COLUMN classroom_post_text TO display_post_text;

-- 4. classroom_sent_at → display_sent_at（送信日時）
ALTER TABLE source_documents
RENAME COLUMN classroom_sent_at TO display_sent_at;

-- 5. classroom_type → display_type（投稿種別）
ALTER TABLE source_documents
RENAME COLUMN classroom_type TO display_type;

-- インデックスも再作成（もし存在する場合）
-- 注意: 既存のインデックスがある場合は、DROP後にCREATEする必要があります
-- DROP INDEX IF EXISTS idx_classroom_sent_at;
-- CREATE INDEX idx_display_sent_at ON source_documents(display_sent_at);

COMMIT;

-- =====================================================
-- マイグレーション実行後の確認
-- =====================================================
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'source_documents'
-- AND column_name LIKE 'display_%'
-- ORDER BY column_name;
