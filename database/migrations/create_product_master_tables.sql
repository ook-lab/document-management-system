-- ====================================================================
-- 商品マスターテーブル作成スクリプト
-- ====================================================================
-- 目的: 商品の名寄せ・分類システムのテーブルを作成
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-25
-- ====================================================================

BEGIN;

-- ====================================================================
-- Tier 1: 商品名の一般化マスタ（名寄せ辞書）
-- ====================================================================
-- 例: 「サッポロ一番 塩ラーメン 5個パック」→「インスタントラーメン」

CREATE TABLE IF NOT EXISTS "MASTER_Product_generalize" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_keyword TEXT NOT NULL,              -- 元の商品名
  general_name TEXT NOT NULL,             -- 一般名詞化した名前
  confidence_score FLOAT DEFAULT 1.0,
  source TEXT DEFAULT 'manual',           -- 'manual', 'gemini_batch', 'gemini_inference'
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(raw_keyword, general_name)
);

CREATE INDEX idx_MASTER_Product_generalize_raw ON "MASTER_Product_generalize"(raw_keyword);
CREATE INDEX idx_MASTER_Product_generalize_general ON "MASTER_Product_generalize"(general_name);

COMMENT ON TABLE "MASTER_Product_generalize" IS '商品名の一般化辞書 - 商品名→一般名詞のマッピング';

-- ====================================================================
-- Tier 2: 商品分類マスタ（一般名詞→費目）
-- ====================================================================
-- 例: 「インスタントラーメン」→ 費目「食費」

CREATE TABLE IF NOT EXISTS "MASTER_Product_classify" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  general_name TEXT NOT NULL,             -- 一般名詞
  source_type TEXT,                       -- 'receipt', 'netsuper', 'flyer'
  workspace TEXT,                         -- ワークスペース（任意）
  doc_type TEXT,                          -- 文書タイプ（任意）
  organization TEXT,                      -- 組織名（任意）
  category_id UUID NOT NULL REFERENCES "MASTER_Categories_expense"(id) ON DELETE CASCADE,
  approval_status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
  confidence_score FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(general_name, source_type, workspace, doc_type, organization)
);

CREATE INDEX idx_MASTER_Product_classify_general ON "MASTER_Product_classify"(general_name);
CREATE INDEX idx_MASTER_Product_classify_category ON "MASTER_Product_classify"(category_id);
CREATE INDEX idx_MASTER_Product_classify_context ON "MASTER_Product_classify"(source_type, workspace, organization);

COMMENT ON TABLE "MASTER_Product_classify" IS '商品分類辞書 - 一般名詞→費目カテゴリのマッピング';

-- ====================================================================
-- 一時テーブル: Geminiクラスタリング結果
-- ====================================================================

CREATE TABLE IF NOT EXISTS "99_tmp_gemini_clustering" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id UUID NOT NULL,
  general_name TEXT NOT NULL,
  category_name TEXT,
  product_ids UUID[] NOT NULL,            -- Rawdata_NETSUPER_items.id配列
  product_names TEXT[] NOT NULL,
  confidence_avg FLOAT,
  approval_status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_99_tmp_gemini_clustering_batch_id ON "99_tmp_gemini_clustering"(batch_id);
CREATE INDEX idx_99_tmp_gemini_clustering_approval_status ON "99_tmp_gemini_clustering"(approval_status);

COMMENT ON TABLE "99_tmp_gemini_clustering" IS 'Gemini商品クラスタリング一時結果';

-- ====================================================================
-- ログテーブル: Gemini分類ログ
-- ====================================================================

CREATE TABLE IF NOT EXISTS "99_lg_gemini_classification_log" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES "Rawdata_NETSUPER_items"(id),
  operation_type TEXT NOT NULL,           -- 'batch_clustering', 'daily_classification'
  model_name TEXT,
  prompt TEXT,
  response TEXT,
  confidence_score FLOAT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_99_lg_gemini_classification_log_product_id ON "99_lg_gemini_classification_log"(product_id);
CREATE INDEX idx_99_lg_gemini_classification_log_created_at ON "99_lg_gemini_classification_log"(created_at);

COMMENT ON TABLE "99_lg_gemini_classification_log" IS 'Gemini商品分類処理ログ';

-- ====================================================================
-- 既存テーブルへのカラム追加
-- ====================================================================

-- Rawdata_NETSUPER_items: 商品マスタに一般名詞と分類結果を追加
ALTER TABLE "Rawdata_NETSUPER_items" ADD COLUMN IF NOT EXISTS general_name TEXT;
ALTER TABLE "Rawdata_NETSUPER_items" ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES "MASTER_Categories_expense"(id);
ALTER TABLE "Rawdata_NETSUPER_items" ADD COLUMN IF NOT EXISTS needs_approval BOOLEAN DEFAULT TRUE;
ALTER TABLE "Rawdata_NETSUPER_items" ADD COLUMN IF NOT EXISTS classification_confidence FLOAT;

CREATE INDEX IF NOT EXISTS idx_Rawdata_NETSUPER_items_general_name ON "Rawdata_NETSUPER_items"(general_name);
CREATE INDEX IF NOT EXISTS idx_Rawdata_NETSUPER_items_category_id ON "Rawdata_NETSUPER_items"(category_id);
CREATE INDEX IF NOT EXISTS idx_Rawdata_NETSUPER_items_needs_approval ON "Rawdata_NETSUPER_items"(needs_approval) WHERE needs_approval = TRUE;

COMMIT;

-- ====================================================================
-- 実行後の確認クエリ
-- ====================================================================

-- テーブル作成確認
-- SELECT table_name
-- FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name IN ('MASTER_Product_generalize', 'MASTER_Product_classify', '99_tmp_gemini_clustering', '99_lg_gemini_classification_log')
-- ORDER BY table_name;

-- カラム追加確認
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'Rawdata_NETSUPER_items'
-- AND column_name IN ('general_name', 'category_id', 'needs_approval', 'classification_confidence');
