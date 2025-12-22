-- ====================================================================
-- 値引き情報カラムの追加
-- ====================================================================
-- 目的: 60_rd_transactions テーブルに値引き関連カラムを追加
-- 実行場所: Supabase SQL Editor
-- ====================================================================

BEGIN;

-- 値引き金額カラムを追加
ALTER TABLE "60_rd_transactions"
ADD COLUMN IF NOT EXISTS discount_amount INTEGER DEFAULT 0;

-- 値引き適用先カラムを追加（この値引きがどの商品に適用されるか）
ALTER TABLE "60_rd_transactions"
ADD COLUMN IF NOT EXISTS discount_applied_to UUID REFERENCES "60_rd_transactions"(id) ON DELETE SET NULL;

-- コメント追加
COMMENT ON COLUMN "60_rd_transactions".discount_amount IS '値引き額（通常は負の値、例: -100）';
COMMENT ON COLUMN "60_rd_transactions".discount_applied_to IS 'この値引きが適用される transaction_id（値引き行の場合のみ）';

-- インデックス追加
CREATE INDEX IF NOT EXISTS idx_60_rd_trans_discount_applied
    ON "60_rd_transactions"(discount_applied_to) WHERE discount_applied_to IS NOT NULL;

-- 完了メッセージ
DO $$
BEGIN
    RAISE NOTICE '✅ 値引き関連カラムの追加完了';
    RAISE NOTICE '   - discount_amount: 値引き額';
    RAISE NOTICE '   - discount_applied_to: 値引き適用先のtransaction_id';
END $$;

COMMIT;
