-- ============================================
-- 商品データ整理・自動分類システム
-- データベースマイグレーション
-- ============================================

-- ============================================
-- Tier 1: 名寄せ辞書（N:1マッピング）
-- ============================================
CREATE TABLE IF NOT EXISTS "70_ms_product_normalization" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_keyword TEXT NOT NULL,
  general_name TEXT NOT NULL,
  confidence_score FLOAT DEFAULT 1.0,
  source TEXT DEFAULT 'manual',  -- 'manual', 'gemini_batch', 'gemini_inference'
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(raw_keyword, general_name)
);

CREATE INDEX idx_70_ms_product_normalization_raw_keyword ON "70_ms_product_normalization"(raw_keyword);
CREATE INDEX idx_70_ms_product_normalization_general_name ON "70_ms_product_normalization"(general_name);

-- ============================================
-- Tier 2: 文脈分類辞書（1:1マッピング）
-- ============================================
CREATE TABLE IF NOT EXISTS "70_ms_product_classification" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  general_name TEXT NOT NULL,
  source_type TEXT,
  workspace TEXT,
  doc_type TEXT,
  organization TEXT,
  category_id UUID NOT NULL REFERENCES "60_ms_categories"(id) ON DELETE CASCADE,
  approval_status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
  confidence_score FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(general_name, source_type, workspace, doc_type, organization)
);

CREATE INDEX idx_70_ms_product_classification_general_name ON "70_ms_product_classification"(general_name);
CREATE INDEX idx_70_ms_product_classification_category_id ON "70_ms_product_classification"(category_id);
CREATE INDEX idx_70_ms_product_classification_context ON "70_ms_product_classification"(source_type, workspace, organization);

-- ============================================
-- 一時テーブル: Geminiクラスタリング結果
-- ============================================
CREATE TABLE IF NOT EXISTS "99_tmp_gemini_clustering" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id UUID NOT NULL,
  general_name TEXT NOT NULL,
  category_name TEXT,
  product_ids UUID[] NOT NULL,  -- 80_rd_products.id配列
  product_names TEXT[] NOT NULL,
  confidence_avg FLOAT,
  approval_status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_99_tmp_gemini_clustering_batch_id ON "99_tmp_gemini_clustering"(batch_id);
CREATE INDEX idx_99_tmp_gemini_clustering_approval_status ON "99_tmp_gemini_clustering"(approval_status);

-- ============================================
-- ログテーブル: Gemini分類ログ
-- ============================================
CREATE TABLE IF NOT EXISTS "99_lg_gemini_classification_log" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES "80_rd_products"(id),
  operation_type TEXT NOT NULL,  -- 'batch_clustering', 'daily_classification'
  model_name TEXT,
  prompt TEXT,
  response TEXT,
  confidence_score FLOAT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_99_lg_gemini_classification_log_product_id ON "99_lg_gemini_classification_log"(product_id);
CREATE INDEX idx_99_lg_gemini_classification_log_created_at ON "99_lg_gemini_classification_log"(created_at);

-- ============================================
-- 既存テーブルへのカラム追加
-- ============================================

-- 80_rd_products: 商品マスタ
ALTER TABLE "80_rd_products" ADD COLUMN IF NOT EXISTS general_name TEXT;
ALTER TABLE "80_rd_products" ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES "60_ms_categories"(id);
ALTER TABLE "80_rd_products" ADD COLUMN IF NOT EXISTS needs_approval BOOLEAN DEFAULT TRUE;
ALTER TABLE "80_rd_products" ADD COLUMN IF NOT EXISTS classification_confidence FLOAT;

CREATE INDEX IF NOT EXISTS idx_80_rd_products_general_name ON "80_rd_products"(general_name);
CREATE INDEX IF NOT EXISTS idx_80_rd_products_category_id ON "80_rd_products"(category_id);
CREATE INDEX IF NOT EXISTS idx_80_rd_products_needs_approval ON "80_rd_products"(needs_approval) WHERE needs_approval = TRUE;

-- ============================================
-- カテゴリマスタへの階層データ追加
-- ============================================

-- 「食費」カテゴリのIDを取得して、その下に「食材」「外食」を追加
DO $$
DECLARE
  food_category_id UUID;
BEGIN
  -- 「食費」カテゴリのIDを取得
  SELECT id INTO food_category_id FROM "60_ms_categories" WHERE name = '食費' LIMIT 1;

  -- food_category_idがNULLでない場合のみ実行
  IF food_category_id IS NOT NULL THEN
    -- 「食材」カテゴリを追加（parent_id = 食費）
    INSERT INTO "60_ms_categories" (name, is_expense, parent_id)
    VALUES ('食材', TRUE, food_category_id)
    ON CONFLICT (name) DO NOTHING;

    -- 「外食」カテゴリを追加（parent_id = 食費）
    INSERT INTO "60_ms_categories" (name, is_expense, parent_id)
    VALUES ('外食', TRUE, food_category_id)
    ON CONFLICT (name) DO NOTHING;
  ELSE
    RAISE NOTICE '「食費」カテゴリが見つかりませんでした。手動で作成してください。';
  END IF;
END $$;
