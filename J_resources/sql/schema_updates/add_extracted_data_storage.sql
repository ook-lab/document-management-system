-- ===================================================================
-- リアクティブ編集システム用のスキーマ拡張
-- extracted_tables と レビューステータスカラムを追加
--
-- 注意: extracted_text は既存の full_text カラムを使用
-- ===================================================================

BEGIN;

-- extracted_tables と レビュー関連カラムを追加
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS extracted_tables JSONB,
    ADD COLUMN IF NOT EXISTS last_edited_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS reviewed BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS review_status VARCHAR(20) DEFAULT 'pending';

-- インデックス追加
CREATE INDEX IF NOT EXISTS idx_documents_review_status
    ON documents(review_status);

CREATE INDEX IF NOT EXISTS idx_documents_reviewed
    ON documents(reviewed);

-- コメント追加
COMMENT ON COLUMN documents.full_text IS 'PDF抽出元テキスト（編集可能・Source of Truth）';
COMMENT ON COLUMN documents.extracted_tables IS 'PDF抽出テーブルデータ（編集可能・JSONB形式）';
COMMENT ON COLUMN documents.last_edited_at IS '最終編集日時';
COMMENT ON COLUMN documents.reviewed IS 'レビュー完了フラグ';
COMMENT ON COLUMN documents.review_status IS 'レビュー状態: pending/in_progress/completed/error';

COMMIT;
