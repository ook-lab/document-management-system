-- すべての言及された日付を保存するフィールドの追加
-- 実行場所: Supabase SQL Editor
-- 目的: 日付検索を最優先事項として、本文中のすべての日付を漏れなく抽出・検索可能にする

BEGIN;

-- 1. all_mentioned_datesカラムを追加（event_datesとは別に保持）
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS all_mentioned_dates DATE[];

-- 2. GINインデックスを追加（配列検索の高速化）
CREATE INDEX IF NOT EXISTS idx_documents_all_mentioned_dates
ON documents USING GIN(all_mentioned_dates);

-- 3. コメントの追加
COMMENT ON COLUMN documents.all_mentioned_dates IS '本文中で言及されているすべての日付（正規表現+AI抽出の統合結果）。日付検索の最優先項目として、漏れなく抽出されている。';

COMMIT;

-- 実行確認クエリ
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'documents'
AND column_name IN ('event_dates', 'all_mentioned_dates', 'document_date', 'classroom_sent_at');
