-- トランザクションテーブルに7要素カラムを追加
-- 7要素: 数量、表示額、外or内、税率、本体価、税額、税込価

ALTER TABLE public."60_rd_transactions"
ADD COLUMN IF NOT EXISTS base_price INTEGER,
ADD COLUMN IF NOT EXISTS tax_amount INTEGER,
ADD COLUMN IF NOT EXISTS tax_included_amount INTEGER,
ADD COLUMN IF NOT EXISTS tax_display_type TEXT,
ADD COLUMN IF NOT EXISTS tax_rate INTEGER;

-- コメント追加
COMMENT ON COLUMN public."60_rd_transactions".base_price IS '本体価（税抜額）';
COMMENT ON COLUMN public."60_rd_transactions".tax_amount IS '消費税額';
COMMENT ON COLUMN public."60_rd_transactions".tax_included_amount IS '税込価（割引後の最終金額）';
COMMENT ON COLUMN public."60_rd_transactions".tax_display_type IS '外税 or 内税（"excluded" or "included"）';
COMMENT ON COLUMN public."60_rd_transactions".tax_rate IS '税率（8 or 10）';
