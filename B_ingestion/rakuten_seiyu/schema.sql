-- ====================================================================
-- 楽天西友ネットスーパー データベーススキーマ
-- ====================================================================

-- テーブル1: rakuten_seiyu_products（商品マスタ）
-- 商品の最新情報を保持するマスターテーブル

CREATE TABLE IF NOT EXISTS rakuten_seiyu_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 基本情報
    source_type VARCHAR(50) DEFAULT 'online_shop',
    workspace VARCHAR(50) DEFAULT 'shopping',
    doc_type VARCHAR(50) DEFAULT 'online shop',
    organization VARCHAR(255) DEFAULT '楽天西友ネットスーパー',

    -- 商品基本情報
    product_name VARCHAR(500) NOT NULL,
    product_name_normalized VARCHAR(500),
    jan_code VARCHAR(20),

    -- 現在の価格（最新価格）
    current_price DECIMAL(10, 2),
    current_price_tax_included DECIMAL(10, 2),
    price_text VARCHAR(255),

    -- 分類
    category VARCHAR(100),
    category_id VARCHAR(50),
    tags TEXT[],

    -- 商品詳細
    manufacturer VARCHAR(255),
    image_url TEXT,

    -- 在庫・販売状況
    in_stock BOOLEAN DEFAULT true,
    is_available BOOLEAN DEFAULT true,

    -- メタデータ
    metadata JSONB,

    -- 日付
    document_date DATE,
    last_scraped_at TIMESTAMPTZ DEFAULT NOW(),

    -- 表示用
    display_subject VARCHAR(500),
    display_sender VARCHAR(255),

    -- 検索用
    search_vector tsvector,

    -- ユニーク制約（JANコードで重複防止）
    CONSTRAINT unique_rakuten_seiyu_jan_code UNIQUE(jan_code)
);

-- コメント
COMMENT ON TABLE rakuten_seiyu_products IS '楽天西友ネットスーパーの商品マスタテーブル';
COMMENT ON COLUMN rakuten_seiyu_products.jan_code IS 'JANコード（商品の一意識別子）';
COMMENT ON COLUMN rakuten_seiyu_products.current_price IS '現在の価格（税抜）';
COMMENT ON COLUMN rakuten_seiyu_products.current_price_tax_included IS '現在の価格（税込）';
COMMENT ON COLUMN rakuten_seiyu_products.last_scraped_at IS '最終スクレイピング日時';
COMMENT ON COLUMN rakuten_seiyu_products.search_vector IS '全文検索用ベクトル';

-- インデックス
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_category ON rakuten_seiyu_products(category);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_jan_code ON rakuten_seiyu_products(jan_code);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_price ON rakuten_seiyu_products(current_price);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_name ON rakuten_seiyu_products(product_name);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_scraped ON rakuten_seiyu_products(last_scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_search ON rakuten_seiyu_products USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_date ON rakuten_seiyu_products(document_date DESC);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_workspace ON rakuten_seiyu_products(workspace);

-- 検索ベクトル自動更新トリガー
CREATE OR REPLACE FUNCTION update_rakuten_seiyu_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', COALESCE(NEW.product_name, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(NEW.manufacturer, '')), 'B') ||
        setweight(to_tsvector('simple', COALESCE(NEW.category, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER rakuten_seiyu_search_vector_update
    BEFORE INSERT OR UPDATE ON rakuten_seiyu_products
    FOR EACH ROW
    EXECUTE FUNCTION update_rakuten_seiyu_search_vector();

-- updated_at 自動更新トリガー
CREATE OR REPLACE FUNCTION update_rakuten_seiyu_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER rakuten_seiyu_updated_at_trigger
    BEFORE UPDATE ON rakuten_seiyu_products
    FOR EACH ROW
    EXECUTE FUNCTION update_rakuten_seiyu_updated_at();

-- ====================================================================
-- テーブル2: rakuten_seiyu_price_history（価格履歴）
-- 価格変動を追跡するためのテーブル（Phase 4で使用）
-- ====================================================================

CREATE TABLE IF NOT EXISTS rakuten_seiyu_price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- 商品参照
    product_id UUID REFERENCES rakuten_seiyu_products(id) ON DELETE CASCADE,
    jan_code VARCHAR(20) NOT NULL,
    product_name VARCHAR(500),

    -- 価格情報
    price DECIMAL(10, 2) NOT NULL,
    price_tax_included DECIMAL(10, 2) NOT NULL,
    price_text VARCHAR(255),

    -- 在庫状況
    in_stock BOOLEAN DEFAULT true,

    -- 日付
    scraped_date DATE NOT NULL,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),

    -- メタデータ
    metadata JSONB,

    -- 複合ユニーク制約（1日1レコード）
    CONSTRAINT unique_price_record UNIQUE(jan_code, scraped_date)
);

-- コメント
COMMENT ON TABLE rakuten_seiyu_price_history IS '楽天西友ネットスーパーの価格履歴テーブル';
COMMENT ON COLUMN rakuten_seiyu_price_history.scraped_date IS 'スクレイピング実施日（同一JANコード・同一日は1レコードのみ）';

-- インデックス
CREATE INDEX IF NOT EXISTS idx_price_history_product_id ON rakuten_seiyu_price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_jan_code ON rakuten_seiyu_price_history(jan_code);
CREATE INDEX IF NOT EXISTS idx_price_history_date ON rakuten_seiyu_price_history(scraped_date DESC);
CREATE INDEX IF NOT EXISTS idx_price_history_price ON rakuten_seiyu_price_history(price);

-- ====================================================================
-- Row Level Security (RLS) 設定
-- ====================================================================

-- RLSを有効化
ALTER TABLE rakuten_seiyu_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE rakuten_seiyu_price_history ENABLE ROW LEVEL SECURITY;

-- 認証済みユーザーは全てのデータにアクセス可能
CREATE POLICY "Allow authenticated users full access to rakuten_seiyu_products"
    ON rakuten_seiyu_products
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow authenticated users full access to rakuten_seiyu_price_history"
    ON rakuten_seiyu_price_history
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- サービスロールは全てのデータにアクセス可能（管理用）
CREATE POLICY "Allow service role full access to rakuten_seiyu_products"
    ON rakuten_seiyu_products
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow service role full access to rakuten_seiyu_price_history"
    ON rakuten_seiyu_price_history
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ====================================================================
-- 便利なビュー
-- ====================================================================

-- 最新の価格情報を含む商品一覧ビュー
CREATE OR REPLACE VIEW v_rakuten_seiyu_products_latest AS
SELECT
    p.*,
    ph.price AS latest_history_price,
    ph.scraped_date AS latest_price_date
FROM rakuten_seiyu_products p
LEFT JOIN LATERAL (
    SELECT price, scraped_date
    FROM rakuten_seiyu_price_history
    WHERE jan_code = p.jan_code
    ORDER BY scraped_date DESC
    LIMIT 1
) ph ON true
ORDER BY p.updated_at DESC;

COMMENT ON VIEW v_rakuten_seiyu_products_latest IS '最新の価格履歴を含む商品一覧ビュー';

-- 価格変動が大きい商品を抽出するビュー（Phase 4で使用）
CREATE OR REPLACE VIEW v_rakuten_seiyu_price_changes AS
SELECT
    p.product_name,
    p.jan_code,
    p.current_price,
    ph_old.price AS old_price,
    ph_new.price AS new_price,
    ph_new.scraped_date AS change_date,
    ROUND(((ph_new.price - ph_old.price) / ph_old.price * 100)::numeric, 2) AS price_change_percent
FROM rakuten_seiyu_products p
INNER JOIN rakuten_seiyu_price_history ph_new ON p.jan_code = ph_new.jan_code
INNER JOIN LATERAL (
    SELECT price
    FROM rakuten_seiyu_price_history
    WHERE jan_code = p.jan_code
      AND scraped_date < ph_new.scraped_date
    ORDER BY scraped_date DESC
    LIMIT 1
) ph_old ON true
WHERE ph_new.price <> ph_old.price
ORDER BY ABS((ph_new.price - ph_old.price) / ph_old.price) DESC;

COMMENT ON VIEW v_rakuten_seiyu_price_changes IS '価格変動があった商品の一覧（変動率順）';

-- ====================================================================
-- 初期データの投入（必要に応じて）
-- ====================================================================

-- 特になし（商品データはスクレイピングで取得）
