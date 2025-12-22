-- 取引明細の辞書テーブル
-- 店舗名と商品名から分類・人物・名目を自動判定するための辞書

CREATE TABLE IF NOT EXISTS "60_ms_transaction_dictionary" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 検索キー（優先順位順）
    shop_name TEXT,         -- 店舗名（最優先）
    product_name TEXT,      -- 商品名（レシート記載）
    official_name TEXT,     -- 正式名
    general_name TEXT,      -- 一般名詞

    -- 判定結果
    category TEXT,          -- 分類（最下層）
    person TEXT,            -- 人物（家族、パパ、ママ、絵麻、育哉）
    purpose TEXT,           -- 名目（日常、など）

    -- メタデータ
    rule_type TEXT NOT NULL,  -- ルールタイプ: 'shop_only', 'shop_product', 'product', 'official', 'general'
    priority INTEGER DEFAULT 100,  -- 優先度（小さいほど優先）
    usage_count INTEGER DEFAULT 1, -- 使用回数（信頼度の指標）

    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- 制約: 少なくとも1つの検索キーが必要
    CHECK (shop_name IS NOT NULL OR product_name IS NOT NULL OR official_name IS NOT NULL OR general_name IS NOT NULL)
);

-- インデックス（高速検索用）
CREATE INDEX IF NOT EXISTS idx_dict_shop ON "60_ms_transaction_dictionary"(shop_name) WHERE shop_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dict_product ON "60_ms_transaction_dictionary"(product_name) WHERE product_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dict_official ON "60_ms_transaction_dictionary"(official_name) WHERE official_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dict_general ON "60_ms_transaction_dictionary"(general_name) WHERE general_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dict_priority ON "60_ms_transaction_dictionary"(priority);

-- 複合インデックス（店舗名 + 商品名の組み合わせ検索用）
CREATE INDEX IF NOT EXISTS idx_dict_shop_product ON "60_ms_transaction_dictionary"(shop_name, product_name)
WHERE shop_name IS NOT NULL AND product_name IS NOT NULL;

-- コメント
COMMENT ON TABLE "60_ms_transaction_dictionary" IS '取引明細の自動判定用辞書テーブル';
COMMENT ON COLUMN "60_ms_transaction_dictionary".shop_name IS '店舗名（最優先の検索キー）';
COMMENT ON COLUMN "60_ms_transaction_dictionary".product_name IS '商品名（レシート記載）';
COMMENT ON COLUMN "60_ms_transaction_dictionary".official_name IS '正式名';
COMMENT ON COLUMN "60_ms_transaction_dictionary".general_name IS '一般名詞';
COMMENT ON COLUMN "60_ms_transaction_dictionary".rule_type IS 'ルールタイプ（shop_only: 店舗のみ、shop_product: 店舗+商品、product: 商品のみ、など）';
COMMENT ON COLUMN "60_ms_transaction_dictionary".priority IS '優先度（小さいほど優先。1=最優先、100=デフォルト）';
COMMENT ON COLUMN "60_ms_transaction_dictionary".usage_count IS '使用回数（信頼度の指標）';

-- 初期データ例（サイゼリヤのような店舗全体のルール）
INSERT INTO "60_ms_transaction_dictionary" (shop_name, category, person, purpose, rule_type, priority)
VALUES
    ('サイゼリヤ', '外食', '家族', '日常', 'shop_only', 1),
    ('すき家', '外食', '家族', '日常', 'shop_only', 1),
    ('松屋', '外食', '家族', '日常', 'shop_only', 1),
    ('吉野家', '外食', '家族', '日常', 'shop_only', 1),
    ('マクドナルド', '外食', '家族', '日常', 'shop_only', 1),
    ('スターバックス', '外食', '家族', '日常', 'shop_only', 1)
ON CONFLICT DO NOTHING;
