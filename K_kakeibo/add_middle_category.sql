-- 60_rd_standardized_itemsテーブルに中分類カラムを追加
-- 分類の3階層構造: major_category (大分類) -> middle_category (中分類) -> minor_category (小分類)

ALTER TABLE "60_rd_standardized_items"
ADD COLUMN IF NOT EXISTS middle_category TEXT;

-- コメント追加
COMMENT ON COLUMN "60_rd_standardized_items".major_category IS '大分類（例: 食料品）';
COMMENT ON COLUMN "60_rd_standardized_items".middle_category IS '中分類（例: 野菜）';
COMMENT ON COLUMN "60_rd_standardized_items".minor_category IS '小分類（例: 根菜）';
