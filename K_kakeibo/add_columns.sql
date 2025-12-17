-- money_transactionsテーブルに新しいカラムを追加

ALTER TABLE money_transactions
ADD COLUMN IF NOT EXISTS official_name TEXT,  -- 正式名
ADD COLUMN IF NOT EXISTS item_name TEXT,      -- 物品名
ADD COLUMN IF NOT EXISTS major_category TEXT, -- 大分類
ADD COLUMN IF NOT EXISTS minor_category TEXT, -- 小分類
ADD COLUMN IF NOT EXISTS person TEXT,         -- 人物
ADD COLUMN IF NOT EXISTS purpose TEXT;        -- 名目

-- インデックス追加（検索高速化）
CREATE INDEX IF NOT EXISTS idx_transactions_major_category ON money_transactions(major_category);
CREATE INDEX IF NOT EXISTS idx_transactions_person ON money_transactions(person);
