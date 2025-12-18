-- チラシ管理用のスキーマ作成

-- 1. flyer_documents テーブル（チラシ基本情報）
CREATE TABLE IF NOT EXISTS flyer_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 基本情報
    source_type VARCHAR(50) DEFAULT 'flyer',
    workspace VARCHAR(50) DEFAULT 'shopping',
    doc_type VARCHAR(50) DEFAULT 'physical shop',
    organization VARCHAR(255) NOT NULL,  -- 店舗名

    -- チラシ固有情報
    flyer_id VARCHAR(255) UNIQUE,  -- トクバイのチラシID
    flyer_title VARCHAR(500),  -- チラシのタイトル
    flyer_period VARCHAR(255),  -- 有効期間（例: "2024/12/18〜2024/12/24"）
    flyer_url TEXT,  -- チラシの元URL
    page_number INTEGER,  -- ページ番号
    total_pages INTEGER,  -- 総ページ数

    -- ファイル情報
    source_id VARCHAR(255),  -- Google DriveファイルID
    source_url TEXT,  -- Drive URL
    file_name VARCHAR(500),
    file_type VARCHAR(50) DEFAULT 'image',
    content_hash VARCHAR(64),  -- SHA-256ハッシュ

    -- OCR・テキスト情報
    attachment_text TEXT,  -- OCRで抽出したテキスト
    summary TEXT,  -- AIが生成したサマリー

    -- 分類・タグ
    tags TEXT[],  -- タグ配列
    category VARCHAR(100),  -- カテゴリ（食品、日用品、衣料品など）

    -- 日付
    document_date DATE,  -- チラシの日付
    valid_from DATE,  -- 有効期間開始
    valid_until DATE,  -- 有効期間終了

    -- 処理ステータス
    processing_status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed
    processing_stage VARCHAR(100),
    processing_error TEXT,

    -- 表示用フィールド
    display_subject VARCHAR(500),
    display_sender VARCHAR(255),
    display_sent_at TIMESTAMPTZ,
    display_post_text TEXT,

    -- メタデータ（JSON）
    metadata JSONB,

    -- インデックス用
    person VARCHAR(100),

    -- 検索用
    search_vector tsvector
);

-- 2. flyer_products テーブル（商品情報）
CREATE TABLE IF NOT EXISTS flyer_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 関連するチラシ
    flyer_document_id UUID REFERENCES flyer_documents(id) ON DELETE CASCADE,

    -- 商品基本情報
    product_name VARCHAR(500) NOT NULL,  -- 商品名
    product_name_normalized VARCHAR(500),  -- 正規化された商品名（検索用）

    -- 価格情報
    price DECIMAL(10, 2),  -- 価格
    original_price DECIMAL(10, 2),  -- 元の価格（割引前）
    discount_rate DECIMAL(5, 2),  -- 割引率（%）
    price_unit VARCHAR(50),  -- 単位（円、円/100g など）
    price_text VARCHAR(255),  -- 価格のテキスト表記（"298円"、"特価"など）

    -- 分類
    category VARCHAR(100),  -- カテゴリ（野菜、肉、魚、日用品など）
    subcategory VARCHAR(100),  -- サブカテゴリ
    tags TEXT[],  -- タグ配列

    -- 商品詳細
    brand VARCHAR(255),  -- ブランド
    quantity VARCHAR(100),  -- 数量・容量（"100g"、"1パック"など）
    origin VARCHAR(255),  -- 産地

    -- 特売情報
    is_special_offer BOOLEAN DEFAULT false,  -- 特売品かどうか
    offer_type VARCHAR(50),  -- 特売タイプ（タイムセール、日替わりなど）

    -- 画像内の位置情報
    page_number INTEGER,  -- 掲載ページ
    bounding_box JSONB,  -- 画像内の位置（{x, y, width, height}）

    -- OCR元テキスト
    extracted_text TEXT,  -- OCRで抽出した元のテキスト
    confidence DECIMAL(5, 4),  -- 抽出の信頼度（0-1）

    -- メタデータ
    metadata JSONB,

    -- 検索用
    search_vector tsvector
);

-- 3. インデックス作成

-- flyer_documents用インデックス
CREATE INDEX IF NOT EXISTS idx_flyer_documents_organization ON flyer_documents(organization);
CREATE INDEX IF NOT EXISTS idx_flyer_documents_flyer_id ON flyer_documents(flyer_id);
CREATE INDEX IF NOT EXISTS idx_flyer_documents_workspace ON flyer_documents(workspace);
CREATE INDEX IF NOT EXISTS idx_flyer_documents_doc_type ON flyer_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_flyer_documents_valid_from ON flyer_documents(valid_from);
CREATE INDEX IF NOT EXISTS idx_flyer_documents_valid_until ON flyer_documents(valid_until);
CREATE INDEX IF NOT EXISTS idx_flyer_documents_processing_status ON flyer_documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_flyer_documents_created_at ON flyer_documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_flyer_documents_tags ON flyer_documents USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_flyer_documents_metadata ON flyer_documents USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_flyer_documents_search ON flyer_documents USING GIN(search_vector);

-- flyer_products用インデックス
CREATE INDEX IF NOT EXISTS idx_flyer_products_flyer_id ON flyer_products(flyer_document_id);
CREATE INDEX IF NOT EXISTS idx_flyer_products_category ON flyer_products(category);
CREATE INDEX IF NOT EXISTS idx_flyer_products_product_name ON flyer_products(product_name);
CREATE INDEX IF NOT EXISTS idx_flyer_products_product_name_normalized ON flyer_products(product_name_normalized);
CREATE INDEX IF NOT EXISTS idx_flyer_products_price ON flyer_products(price);
CREATE INDEX IF NOT EXISTS idx_flyer_products_is_special_offer ON flyer_products(is_special_offer);
CREATE INDEX IF NOT EXISTS idx_flyer_products_tags ON flyer_products USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_flyer_products_search ON flyer_products USING GIN(search_vector);

-- 4. 更新日時の自動更新トリガー
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_flyer_documents_updated_at BEFORE UPDATE ON flyer_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_flyer_products_updated_at BEFORE UPDATE ON flyer_products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 5. 全文検索用のトリガー（日本語対応）
CREATE OR REPLACE FUNCTION flyer_documents_search_vector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', coalesce(NEW.flyer_title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.organization, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(NEW.attachment_text, '')), 'C') ||
        setweight(to_tsvector('simple', coalesce(NEW.summary, '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvector_update_flyer_documents BEFORE INSERT OR UPDATE ON flyer_documents
    FOR EACH ROW EXECUTE FUNCTION flyer_documents_search_vector_update();

CREATE OR REPLACE FUNCTION flyer_products_search_vector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', coalesce(NEW.product_name, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.brand, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(NEW.category, '')), 'C') ||
        setweight(to_tsvector('simple', coalesce(NEW.extracted_text, '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvector_update_flyer_products BEFORE INSERT OR UPDATE ON flyer_products
    FOR EACH ROW EXECUTE FUNCTION flyer_products_search_vector_update();

-- 6. RLS (Row Level Security) ポリシー（必要に応じて設定）
-- ALTER TABLE flyer_documents ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE flyer_products ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE flyer_documents IS 'スーパーやドラッグストアのチラシ基本情報を管理';
COMMENT ON TABLE flyer_products IS 'チラシから抽出した個別商品情報を管理';
