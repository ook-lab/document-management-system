-- 60_rd_standardized_itemsテーブルにgeneral_nameカラムを追加
-- AI自動判定の検索キーとして使用

ALTER TABLE "60_rd_standardized_items"
ADD COLUMN IF NOT EXISTS general_name TEXT;

-- コメント追加
COMMENT ON COLUMN "60_rd_standardized_items".general_name IS '一般名詞（AI判定の検索キー）';
