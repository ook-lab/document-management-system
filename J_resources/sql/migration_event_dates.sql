-- イベント日付配列フィールドの追加
-- 実行場所: Supabase SQL Editor
-- 実行日: 2025-12-10

BEGIN;

-- 1. event_datesカラムを追加
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS event_dates DATE[];

-- 2. インデックスの追加（GIN index for array search）
CREATE INDEX IF NOT EXISTS idx_documents_event_dates ON documents USING GIN(event_dates);

-- 3. コメントの追加（ドキュメント化）
COMMENT ON COLUMN documents.event_dates IS '文書内で言及されているイベントや予定の日付配列。「明後日」などの相対表現も絶対日付に変換されている。';

COMMIT;

-- 実行確認クエリ
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'documents'
AND column_name = 'event_dates';
