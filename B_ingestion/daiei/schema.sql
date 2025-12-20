-- ダイエーネットスーパー商品テーブル
CREATE TABLE IF NOT EXISTS daiei_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- 基本情報
    source_type TEXT DEFAULT 'online_shop',
    workspace TEXT DEFAULT 'shopping',
    doc_type TEXT DEFAULT 'online shop',
    organization TEXT DEFAULT 'ダイエーネットスーパー',

    -- 商品基本情報
    product_name TEXT NOT NULL,
    product_name_normalized TEXT,
    jan_code TEXT UNIQUE,  -- JANコードで重複チェック

    -- 価格
    current_price NUMERIC,
    current_price_tax_included NUMERIC,
    price_text TEXT,

    -- 分類
    category TEXT,
    manufacturer TEXT,

    -- 商品詳細
    image_url TEXT,

    -- 在庫・販売状況
    in_stock BOOLEAN DEFAULT true,
    is_available BOOLEAN DEFAULT true,

    -- メタデータ
    metadata JSONB,

    -- 日付
    document_date DATE,
    last_scraped_at TIMESTAMP WITH TIME ZONE,

    -- 表示用
    display_subject TEXT,
    display_sender TEXT,

    -- タイムスタンプ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_daiei_jan_code ON daiei_products(jan_code);
CREATE INDEX IF NOT EXISTS idx_daiei_category ON daiei_products(category);
CREATE INDEX IF NOT EXISTS idx_daiei_product_name ON daiei_products(product_name);
CREATE INDEX IF NOT EXISTS idx_daiei_document_date ON daiei_products(document_date);
CREATE INDEX IF NOT EXISTS idx_daiei_last_scraped_at ON daiei_products(last_scraped_at);

-- 全文検索用インデックス（シンプル設定）
CREATE INDEX IF NOT EXISTS idx_daiei_product_name_gin ON daiei_products USING gin(to_tsvector('simple', product_name));

-- RLS（Row Level Security）ポリシー
ALTER TABLE daiei_products ENABLE ROW LEVEL SECURITY;

-- すべてのユーザーが読み取り可能
CREATE POLICY "Enable read access for all users" ON daiei_products
    FOR SELECT USING (true);

-- Service Role のみが挿入・更新・削除可能（バックエンド処理用）
CREATE POLICY "Enable insert for service role only" ON daiei_products
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update for service role only" ON daiei_products
    FOR UPDATE USING (true);

CREATE POLICY "Enable delete for service role only" ON daiei_products
    FOR DELETE USING (true);
