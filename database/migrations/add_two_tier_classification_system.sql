-- ====================================================================
-- 2層分類システムの実装
-- ====================================================================
-- 目的: 1次分類（商品カテゴリ）と2次分類（費目）を明確に分離
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- 参照: CLASSIFICATION_SYSTEM_REDESIGN.md
-- ====================================================================

BEGIN;

-- ====================================================================
-- フェーズ1: 新規テーブル作成
-- ====================================================================

-- Tier 1: 商品カテゴリマッピング（一般名詞 → 商品カテゴリ）
CREATE TABLE IF NOT EXISTS "MASTER_Product_category_mapping" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  general_name TEXT NOT NULL,                    -- 一般名詞（「牛乳」「クッキー」など）
  product_category_id UUID NOT NULL REFERENCES "MASTER_Categories_product"(id) ON DELETE CASCADE,
  confidence_score FLOAT DEFAULT 1.0,            -- 分類の信頼度（0.0-1.0）
  source TEXT DEFAULT 'manual',                  -- 'manual', 'gemini', 'auto'
  approval_status TEXT DEFAULT 'approved',       -- 'pending', 'approved', 'rejected'
  notes TEXT,                                    -- メモ・備考
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(general_name)                           -- 一般名詞は一意
);

-- インデックス作成
CREATE INDEX idx_MASTER_Product_category_mapping_general
  ON "MASTER_Product_category_mapping"(general_name);

CREATE INDEX idx_MASTER_Product_category_mapping_category
  ON "MASTER_Product_category_mapping"(product_category_id);

CREATE INDEX idx_MASTER_Product_category_mapping_approval
  ON "MASTER_Product_category_mapping"(approval_status)
  WHERE approval_status = 'pending';

CREATE INDEX idx_MASTER_Product_category_mapping_source
  ON "MASTER_Product_category_mapping"(source);

-- テーブルコメント
COMMENT ON TABLE "MASTER_Product_category_mapping" IS
  '1次分類: 一般名詞→商品カテゴリのマッピング（例: 牛乳→食料品）';

COMMENT ON COLUMN "MASTER_Product_category_mapping".general_name IS
  '一般名詞（MASTER_Product_generalizeで正規化された名前）';

COMMENT ON COLUMN "MASTER_Product_category_mapping".product_category_id IS
  '商品カテゴリID（MASTER_Categories_product）';

COMMENT ON COLUMN "MASTER_Product_category_mapping".confidence_score IS
  '分類の信頼度（0.0-1.0）。AIによる分類の場合に使用';

COMMENT ON COLUMN "MASTER_Product_category_mapping".source IS
  '分類の情報源（manual: 手動, gemini: AI, auto: 自動推測）';

-- ====================================================================
-- フェーズ2: 既存テーブルの拡張
-- ====================================================================

-- MASTER_Product_classify に新しいカラムを追加
ALTER TABLE "MASTER_Product_classify"
  ADD COLUMN IF NOT EXISTS product_category_id UUID REFERENCES "MASTER_Categories_product"(id) ON DELETE SET NULL;

ALTER TABLE "MASTER_Product_classify"
  ADD COLUMN IF NOT EXISTS purpose_id UUID REFERENCES "MASTER_Categories_purpose"(id) ON DELETE SET NULL;

ALTER TABLE "MASTER_Product_classify"
  ADD COLUMN IF NOT EXISTS person TEXT;

-- インデックス追加
CREATE INDEX IF NOT EXISTS idx_MASTER_Product_classify_product_category
  ON "MASTER_Product_classify"(product_category_id);

CREATE INDEX IF NOT EXISTS idx_MASTER_Product_classify_purpose
  ON "MASTER_Product_classify"(purpose_id);

CREATE INDEX IF NOT EXISTS idx_MASTER_Product_classify_person
  ON "MASTER_Product_classify"(person);

-- カラムコメント更新
COMMENT ON TABLE "MASTER_Product_classify" IS
  '2次分類: 商品カテゴリ+用途+人→費目カテゴリのマッピング（general_nameは後方互換性のため保持）';

COMMENT ON COLUMN "MASTER_Product_classify".general_name IS
  '(非推奨) 後方互換性のため保持。新規レコードはproduct_category_idを使用すること';

COMMENT ON COLUMN "MASTER_Product_classify".product_category_id IS
  '商品カテゴリID（1次分類結果）。新しい分類システムで使用';

COMMENT ON COLUMN "MASTER_Product_classify".purpose_id IS
  '用途・シチュエーション（日常、ビジネス、旅行など）';

COMMENT ON COLUMN "MASTER_Product_classify".person IS
  '購入者・使用者（夫、妻、子供など）。NULLの場合は共通';

-- ====================================================================
-- フェーズ3: RLSポリシー設定
-- ====================================================================

-- MASTER_Product_category_mapping のRLS
ALTER TABLE "MASTER_Product_category_mapping" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users full access to product category mapping"
  ON "MASTER_Product_category_mapping"
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow service role full access to product category mapping"
  ON "MASTER_Product_category_mapping"
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- ====================================================================
-- 完了メッセージ
-- ====================================================================

DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ 2層分類システムの実装が完了しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '作成されたテーブル:';
    RAISE NOTICE '  - MASTER_Product_category_mapping (新規)';
    RAISE NOTICE '';
    RAISE NOTICE '拡張されたテーブル:';
    RAISE NOTICE '  - MASTER_Product_classify (カラム追加)';
    RAISE NOTICE '    - product_category_id';
    RAISE NOTICE '    - purpose_id';
    RAISE NOTICE '    - person';
    RAISE NOTICE '';
    RAISE NOTICE '分類フロー:';
    RAISE NOTICE '  [Tier 0] 商品名 → general_name (MASTER_Product_generalize)';
    RAISE NOTICE '  [Tier 1] general_name → product_category (MASTER_Product_category_mapping)';
    RAISE NOTICE '  [Tier 2] product_category + context → expense_category (MASTER_Product_classify)';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. 初期データの投入（サンプル商品カテゴリマッピング）';
    RAISE NOTICE '  2. コードの更新（分類ロジック）';
    RAISE NOTICE '  3. テストの実施';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;

-- ====================================================================
-- 実行後の確認クエリ
-- ====================================================================

-- テーブル作成確認
-- SELECT table_name, table_type
-- FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name = 'MASTER_Product_category_mapping';

-- カラム追加確認
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'MASTER_Product_classify'
-- AND column_name IN ('product_category_id', 'purpose_id', 'person')
-- ORDER BY column_name;

-- インデックス確認
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename IN ('MASTER_Product_category_mapping', 'MASTER_Product_classify')
-- ORDER BY tablename, indexname;
