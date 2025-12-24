-- レシートテーブルに税額カラムを追加
ALTER TABLE public."Rawdata_RECEIPT_shops"
ADD COLUMN IF NOT EXISTS tax_8_amount INTEGER,
ADD COLUMN IF NOT EXISTS tax_10_amount INTEGER;

-- トランザクションテーブルに表示額カラムを追加
ALTER TABLE public."Rawdata_RECEIPT_items"
ADD COLUMN IF NOT EXISTS displayed_amount INTEGER;

-- コメント追加
COMMENT ON COLUMN public."Rawdata_RECEIPT_shops".tax_8_amount IS '8%消費税額（レシート記載値）';
COMMENT ON COLUMN public."Rawdata_RECEIPT_shops".tax_10_amount IS '10%消費税額（レシート記載値）';
COMMENT ON COLUMN public."Rawdata_RECEIPT_items".displayed_amount IS 'レシート記載の表示金額（割引前の元金額、割引行はマイナス値）';
