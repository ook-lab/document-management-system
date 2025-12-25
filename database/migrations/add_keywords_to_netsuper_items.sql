-- Add keywords JSONB column to Rawdata_NETSUPER_items table
-- keywords: 商品名から抽出された個別のキーワードの配列
-- 例: ["パスコ", "超熟", "6枚切り", "食パン"]

ALTER TABLE "Rawdata_NETSUPER_items"
ADD COLUMN IF NOT EXISTS keywords JSONB DEFAULT '[]'::jsonb;

-- Add index for keyword searches
CREATE INDEX IF NOT EXISTS idx_netsuper_items_keywords
ON "Rawdata_NETSUPER_items" USING gin(keywords);

-- Add comment
COMMENT ON COLUMN "Rawdata_NETSUPER_items".keywords IS '商品名から抽出された個別キーワードの配列（検索用）';
