-- ========================================
-- 税額自動計算機能のためのスキーマ追加
-- ========================================

-- 1. money_transactionsテーブルに税額関連フィールドを追加
ALTER TABLE money_transactions
ADD COLUMN IF NOT EXISTS tax_rate INTEGER,           -- 適用税率（8 or 10）
ADD COLUMN IF NOT EXISTS tax_amount INTEGER,         -- 内税額
ADD COLUMN IF NOT EXISTS needs_tax_review BOOLEAN DEFAULT FALSE;  -- 税額要確認フラグ

-- 2. レシート全体の税額サマリーテーブルを作成
CREATE TABLE IF NOT EXISTS money_receipt_tax_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 処理ログとの紐付け
    processing_log_id UUID REFERENCES money_image_processing_log(id) ON DELETE CASCADE,

    -- レシート記載の税額情報（実際の値）
    tax_8_subtotal INTEGER,      -- 8%対象額（税抜）
    tax_8_amount INTEGER,         -- 8%税額
    tax_10_subtotal INTEGER,      -- 10%対象額（税抜）
    tax_10_amount INTEGER,        -- 10%税額
    total_amount INTEGER,         -- 総合計

    -- 計算結果との照合
    calculated_tax_8_amount INTEGER,   -- 計算した8%税額
    calculated_tax_10_amount INTEGER,  -- 計算した10%税額
    calculated_matches_actual BOOLEAN DEFAULT TRUE,  -- 整合性フラグ

    -- 誤差情報
    tax_8_diff INTEGER,           -- 8%税額の差分
    tax_10_diff INTEGER,          -- 10%税額の差分

    created_at TIMESTAMP DEFAULT NOW(),

    -- ユニーク制約（1つの処理ログに1つのサマリー）
    UNIQUE(processing_log_id)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_receipt_tax_summary_log ON money_receipt_tax_summary(processing_log_id);
CREATE INDEX IF NOT EXISTS idx_transactions_tax_rate ON money_transactions(tax_rate);
CREATE INDEX IF NOT EXISTS idx_transactions_needs_review ON money_transactions(needs_tax_review) WHERE needs_tax_review = TRUE;

-- コメント追加
COMMENT ON COLUMN money_transactions.tax_rate IS '適用税率（8% or 10%）';
COMMENT ON COLUMN money_transactions.tax_amount IS '内税額（税込価格から逆算）';
COMMENT ON COLUMN money_transactions.needs_tax_review IS '税額の手動確認が必要かどうか';
COMMENT ON TABLE money_receipt_tax_summary IS 'レシート全体の税額サマリーと整合性チェック結果';
