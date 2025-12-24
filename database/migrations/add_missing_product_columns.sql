-- ============================================
-- Rawdata_NETSUPER_items に不足しているカラムを追加
-- ============================================

-- general_name（一般名詞）
ALTER TABLE "Rawdata_NETSUPER_items" ADD COLUMN IF NOT EXISTS general_name TEXT;

-- category_id（カテゴリID）
ALTER TABLE "Rawdata_NETSUPER_items" ADD COLUMN IF NOT EXISTS category_id UUID;

-- needs_approval（承認待ちフラグ）
ALTER TABLE "Rawdata_NETSUPER_items" ADD COLUMN IF NOT EXISTS needs_approval BOOLEAN DEFAULT TRUE;

-- classification_confidence（分類信頼度）
ALTER TABLE "Rawdata_NETSUPER_items" ADD COLUMN IF NOT EXISTS classification_confidence FLOAT;

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_Rawdata_NETSUPER_items_general_name ON "Rawdata_NETSUPER_items"(general_name);
CREATE INDEX IF NOT EXISTS idx_Rawdata_NETSUPER_items_category_id ON "Rawdata_NETSUPER_items"(category_id);
CREATE INDEX IF NOT EXISTS idx_Rawdata_NETSUPER_items_needs_approval ON "Rawdata_NETSUPER_items"(needs_approval) WHERE needs_approval = TRUE;

-- 確認
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'Rawdata_NETSUPER_items'
AND column_name IN ('general_name', 'category_id', 'needs_approval', 'classification_confidence')
ORDER BY column_name;
