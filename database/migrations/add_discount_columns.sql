-- ====================================================================
-- 値引き情報カラムの追加
-- ====================================================================
-- 目的: Rawdata_RECEIPT_items テーブルに値引き関連カラムを追加
-- 実行場所: Supabase SQL Editor
-- ====================================================================

BEGIN;

-- 値引き金額カラムを追加
ALTER TABLE "Rawdata_RECEIPT_items"
ADD COLUMN IF NOT EXISTS discount_amount INTEGER DEFAULT 0;

-- 値引き適用先カラムを追加（この値引きがどの商品に適用されるか）
ALTER TABLE "Rawdata_RECEIPT_items"
ADD COLUMN IF NOT EXISTS discount_applied_to UUID REFERENCES "Rawdata_RECEIPT_items"(id) ON DELETE SET NULL;

-- コメント追加
COMMENT ON COLUMN "Rawdata_RECEIPT_items".discount_amount IS '値引き額（通常は負の値、例: -100）';
COMMENT ON COLUMN "Rawdata_RECEIPT_items".discount_applied_to IS 'この値引きが適用される transaction_id（値引き行の場合のみ）';

-- インデックス追加
CREATE INDEX IF NOT EXISTS idx_60_rd_trans_discount_applied
    ON "Rawdata_RECEIPT_items"(discount_applied_to) WHERE discount_applied_to IS NOT NULL;

-- 完了メッセージ
DO $$
BEGIN
    RAISE NOTICE '✅ 値引き関連カラムの追加完了';
    RAISE NOTICE '   - discount_amount: 値引き額';
    RAISE NOTICE '   - discount_applied_to: 値引き適用先のtransaction_id';
END $$;

COMMIT;
