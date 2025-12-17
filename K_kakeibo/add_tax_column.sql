-- 内税額カラムを追加
ALTER TABLE money_transactions
ADD COLUMN IF NOT EXISTS tax_included_amount INTEGER;  -- 内税額

COMMENT ON COLUMN money_transactions.tax_included_amount IS '内税額（外税の場合に税込み換算した金額）';
