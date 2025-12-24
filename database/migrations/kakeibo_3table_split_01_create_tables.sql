-- ====================================================================
-- フェーズ1: 家計簿3分割テーブル - スキーマ作成
-- ====================================================================
-- 目的: 新しい3層構造のテーブルを作成（既存テーブルは維持）
-- 実行場所: Supabase SQL Editor
-- 前提条件: 既存の Rawdata_RECEIPT_items テーブルが存在すること
-- ====================================================================

BEGIN;

-- ====================================================================
-- 1. 親テーブル: Rawdata_RECEIPT_shops (レシート管理台帳)
-- ====================================================================
-- 役割: レシート1枚単位の「管理属性」と「正解データ」を保持

CREATE TABLE IF NOT EXISTS "Rawdata_RECEIPT_shops" (
    -- ID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- レシート基本情報（修正後の正解）
    transaction_date DATE NOT NULL,
    shop_name TEXT NOT NULL,
    total_amount_check INTEGER NOT NULL,  -- レシート印字の合計金額（検算用）
    subtotal_amount INTEGER,              -- 小計（割引計算の基準）

    -- ファイル管理
    image_path TEXT,
    drive_file_id TEXT,
    source_folder TEXT,                   -- INBOX_EASY / INBOX_HARD

    -- OCR処理情報
    ocr_model TEXT,                       -- gemini-2.5-flash / gemini-2.5-flash-lite

    -- 分類・管理
    person TEXT,                          -- 支払担当者（夫、妻、会社など）
    workspace TEXT DEFAULT 'household',   -- マルチテナント用

    -- 状態管理
    is_verified BOOLEAN DEFAULT FALSE,    -- 人間による確認完了
    notes TEXT,                           -- レシート全体に対するメモ

    -- タイムスタンプ
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_shops_date
    ON "Rawdata_RECEIPT_shops"(transaction_date DESC);

CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_shops_shop
    ON "Rawdata_RECEIPT_shops" USING gin(shop_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_shops_drive_id
    ON "Rawdata_RECEIPT_shops"(drive_file_id);

CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_shops_unverified
    ON "Rawdata_RECEIPT_shops"(is_verified) WHERE is_verified = FALSE;

CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_shops_workspace
    ON "Rawdata_RECEIPT_shops"(workspace);

-- コメント
COMMENT ON TABLE "Rawdata_RECEIPT_shops" IS 'レシート管理台帳 - レシート1枚単位の管理情報';
COMMENT ON COLUMN "Rawdata_RECEIPT_shops".total_amount_check IS 'レシート印字の合計金額（検算用）';
COMMENT ON COLUMN "Rawdata_RECEIPT_shops".subtotal_amount IS '小計（割引計算の基準）';
COMMENT ON COLUMN "Rawdata_RECEIPT_shops".is_verified IS '人間による確認完了フラグ';

-- ====================================================================
-- 2. 子テーブル: Rawdata_RECEIPT_items_new (OCRテキスト正規化)
-- ====================================================================
-- 役割: OCRの読み取り結果と、人間が読める文字への修正を保持
-- 注意: 既存のRawdata_RECEIPT_itemsと名前が衝突するため、一旦 _new サフィックスで作成

CREATE TABLE IF NOT EXISTS "Rawdata_RECEIPT_items_new" (
    -- ID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id UUID NOT NULL REFERENCES "Rawdata_RECEIPT_shops"(id) ON DELETE CASCADE,

    -- 行メタ情報
    line_number INTEGER NOT NULL,         -- レシート内の行番号（文脈解析用）
    line_type TEXT NOT NULL DEFAULT 'ITEM',  -- ITEM, DISCOUNT, SUB_TOTAL, TAX, etc.

    -- OCR原文（証拠保全）
    ocr_raw_text TEXT,                    -- AIが見たままの文字列
    ocr_confidence DECIMAL(5,4),          -- AIの読み取り自信度 (0.0000-1.0000)

    -- テキスト正規化結果（「4乳」→「牛乳」）
    product_name TEXT NOT NULL,           -- 正規化後の商品名
    item_name TEXT,                       -- 補足名称・型番
    unit_price INTEGER,                   -- 正規化後の単価
    quantity INTEGER DEFAULT 1,           -- 正規化後の数量

    -- 記号・マーク
    marks_text TEXT,                      -- 税マーク等（「※」「軽」など）
    discount_text TEXT,                   -- 割引記載（「2割引」「半額」など）

    -- タイムスタンプ
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 複合ユニーク制約
    CONSTRAINT unique_receipt_line UNIQUE(receipt_id, line_number)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_60_rd_trans_new_receipt
    ON "Rawdata_RECEIPT_items_new"(receipt_id);

CREATE INDEX IF NOT EXISTS idx_60_rd_trans_new_line
    ON "Rawdata_RECEIPT_items_new"(receipt_id, line_number);

CREATE INDEX IF NOT EXISTS idx_60_rd_trans_new_type
    ON "Rawdata_RECEIPT_items_new"(line_type);

CREATE INDEX IF NOT EXISTS idx_60_rd_trans_new_low_confidence
    ON "Rawdata_RECEIPT_items_new"(ocr_confidence) WHERE ocr_confidence < 0.8;

CREATE INDEX IF NOT EXISTS idx_60_rd_trans_new_created
    ON "Rawdata_RECEIPT_items_new"(created_at DESC);

-- コメント
COMMENT ON TABLE "Rawdata_RECEIPT_items_new" IS 'OCRテキスト正規化 - 読み取り結果の文字修正';
COMMENT ON COLUMN "Rawdata_RECEIPT_items_new".ocr_raw_text IS 'AIが見たままの文字列（証拠保全）';
COMMENT ON COLUMN "Rawdata_RECEIPT_items_new".ocr_confidence IS 'AIの読み取り自信度 (0.0000-1.0000)';
COMMENT ON COLUMN "Rawdata_RECEIPT_items_new".line_number IS 'レシート内の行番号（文脈解析用）';
COMMENT ON COLUMN "Rawdata_RECEIPT_items_new".line_type IS '行の種類（ITEM, DISCOUNT, SUB_TOTAL, TAX等）';

-- ====================================================================
-- 3. 孫テーブル: 60_rd_standardized_items (家計簿・情報正規化)
-- ====================================================================
-- 役割: 家計簿としての意味・分類・最終金額を保持（集計用）

CREATE TABLE IF NOT EXISTS "60_rd_standardized_items" (
    -- ID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES "Rawdata_RECEIPT_items_new"(id) ON DELETE CASCADE,
    receipt_id UUID NOT NULL REFERENCES "Rawdata_RECEIPT_shops"(id) ON DELETE CASCADE,  -- 冗長化（JOIN削減）

    -- 正規化された商品情報
    official_name TEXT,                   -- マスタ辞書から引いた正式名称

    -- 家計簿分類
    category_id UUID REFERENCES "MASTER_Categories_expense"(id),     -- 費目（食費、日用品など）
    situation_id UUID REFERENCES "MASTER_Categories_purpose"(id),    -- シチュエーション（日常、旅行など）
    major_category TEXT,                  -- 大分類（自由記入）
    minor_category TEXT,                  -- 小分類（自由記入）
    purpose TEXT,                         -- 購入目的（より詳細なタグ）
    person TEXT,                          -- 使用者（誰が使うか）

    -- 税計算結果
    tax_rate INTEGER NOT NULL DEFAULT 10, -- 適用税率 (8 or 10)
    std_unit_price INTEGER,               -- 割引適用後の実質単価（税込）
    std_amount INTEGER NOT NULL,          -- 最終支払金額（税込） ← これをSUMすれば家計簿
    tax_amount INTEGER,                   -- 内税額

    -- 計算ロジックのトレーサビリティ
    calc_logic_log TEXT,                  -- 「3行目の20円引を適用」「外税計算」などの根拠
    needs_review BOOLEAN DEFAULT FALSE,   -- 手動確認が必要

    -- メタ情報
    notes TEXT,                           -- 明細ごとのメモ

    -- タイムスタンプ
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_60_rd_std_transaction
    ON "60_rd_standardized_items"(transaction_id);

CREATE INDEX IF NOT EXISTS idx_60_rd_std_receipt
    ON "60_rd_standardized_items"(receipt_id);

CREATE INDEX IF NOT EXISTS idx_60_rd_std_category
    ON "60_rd_standardized_items"(category_id);

CREATE INDEX IF NOT EXISTS idx_60_rd_std_situation
    ON "60_rd_standardized_items"(situation_id);

CREATE INDEX IF NOT EXISTS idx_60_rd_std_tax_rate
    ON "60_rd_standardized_items"(tax_rate);

CREATE INDEX IF NOT EXISTS idx_60_rd_std_needs_review
    ON "60_rd_standardized_items"(needs_review) WHERE needs_review = TRUE;

CREATE INDEX IF NOT EXISTS idx_60_rd_std_created
    ON "60_rd_standardized_items"(created_at DESC);

-- コメント
COMMENT ON TABLE "60_rd_standardized_items" IS '家計簿・情報正規化 - 分類と最終金額（集計用）';
COMMENT ON COLUMN "60_rd_standardized_items".std_amount IS '最終支払金額（税込） - これをSUMすれば家計簿';
COMMENT ON COLUMN "60_rd_standardized_items".calc_logic_log IS '計算ロジックの根拠（トレーサビリティ）';
COMMENT ON COLUMN "60_rd_standardized_items".needs_review IS '手動確認が必要かどうか';

-- ====================================================================
-- 4. RLSポリシー設定
-- ====================================================================

-- 親テーブル
ALTER TABLE "Rawdata_RECEIPT_shops" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users full access to receipts"
    ON "Rawdata_RECEIPT_shops"
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow service role full access to receipts"
    ON "Rawdata_RECEIPT_shops"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- 子テーブル
ALTER TABLE "Rawdata_RECEIPT_items_new" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users full access to transactions_new"
    ON "Rawdata_RECEIPT_items_new"
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow service role full access to transactions_new"
    ON "Rawdata_RECEIPT_items_new"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- 孫テーブル
ALTER TABLE "60_rd_standardized_items" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users full access to standardized_items"
    ON "60_rd_standardized_items"
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow service role full access to standardized_items"
    ON "60_rd_standardized_items"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ====================================================================
-- 完了メッセージ
-- ====================================================================

DO $$
BEGIN
    RAISE NOTICE '✅ フェーズ1完了: 3テーブルのスキーマ作成完了';
    RAISE NOTICE '✅ 作成されたテーブル:';
    RAISE NOTICE '   - Rawdata_RECEIPT_shops (親: レシート管理台帳)';
    RAISE NOTICE '   - Rawdata_RECEIPT_items_new (子: OCRテキスト正規化)';
    RAISE NOTICE '   - 60_rd_standardized_items (孫: 家計簿・情報正規化)';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ: フェーズ2（データ移行）を実行してください';
END $$;

COMMIT;

-- ====================================================================
-- 確認クエリ（実行後に確認）
-- ====================================================================

-- 作成されたテーブルの確認
SELECT
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('Rawdata_RECEIPT_shops', 'Rawdata_RECEIPT_items_new', '60_rd_standardized_items')
ORDER BY table_name;

-- 各テーブルのカラム数確認
SELECT
    table_name,
    COUNT(*) AS column_count
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('Rawdata_RECEIPT_shops', 'Rawdata_RECEIPT_items_new', '60_rd_standardized_items')
GROUP BY table_name
ORDER BY table_name;
