-- MASTER_Categories_productに大中小分類カラムを追加

ALTER TABLE "MASTER_Categories_product"
ADD COLUMN IF NOT EXISTS large_category TEXT,
ADD COLUMN IF NOT EXISTS medium_category TEXT,
ADD COLUMN IF NOT EXISTS small_category TEXT;

-- 既存データのマイグレーション（name を > で分割）
UPDATE "MASTER_Categories_product"
SET
  large_category = SPLIT_PART(name, '>', 1),
  medium_category = SPLIT_PART(name, '>', 2),
  small_category = SPLIT_PART(name, '>', 3)
WHERE name LIKE '%>%';

-- インデックス追加（検索高速化）
CREATE INDEX IF NOT EXISTS idx_categories_name ON "MASTER_Categories_product"(name);
CREATE INDEX IF NOT EXISTS idx_categories_large ON "MASTER_Categories_product"(large_category);
CREATE INDEX IF NOT EXISTS idx_categories_medium ON "MASTER_Categories_product"(medium_category);
CREATE INDEX IF NOT EXISTS idx_categories_small ON "MASTER_Categories_product"(small_category);
