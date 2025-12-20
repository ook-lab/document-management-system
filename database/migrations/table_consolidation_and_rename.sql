-- ====================================================================
-- テーブル統合・リネーム マイグレーション
-- ====================================================================
-- 実行前提: 既存データは消滅してもOK
-- 実行場所: Supabase SQL Editor
-- ====================================================================

BEGIN;

-- ====================================================================
-- STEP 0: 古いテーブルの削除（制約名の重複を避けるため先に削除）
-- ====================================================================

DROP TABLE IF EXISTS rakuten_seiyu_price_history CASCADE;
DROP TABLE IF EXISTS daiei_products CASCADE;
DROP TABLE IF EXISTS rakuten_seiyu_products CASCADE;
DROP TABLE IF EXISTS money_events CASCADE;

-- ====================================================================
-- STEP 1: 統合テーブル 80_rd_products の作成
-- ====================================================================

CREATE TABLE IF NOT EXISTS "80_rd_products" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- メタ情報
    source_type VARCHAR(50) DEFAULT 'online_shop',
    workspace VARCHAR(50) DEFAULT 'shopping',
    doc_type VARCHAR(50) DEFAULT 'online shop',
    organization VARCHAR(255) NOT NULL,

    -- 商品基本情報
    product_name VARCHAR(500) NOT NULL,
    product_name_normalized VARCHAR(500),
    jan_code VARCHAR(20),

    -- 価格情報
    current_price DECIMAL(10, 2),
    current_price_tax_included DECIMAL(10, 2),
    price_text VARCHAR(255),

    -- 分類
    category VARCHAR(100),
    category_id VARCHAR(50),
    tags TEXT[],
    manufacturer VARCHAR(255),

    -- 商品詳細
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

    -- 複合ユニーク制約
    CONSTRAINT unique_products_jan_org UNIQUE(jan_code, organization)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_80_rd_products_category ON "80_rd_products"(category);
CREATE INDEX IF NOT EXISTS idx_80_rd_products_jan_code ON "80_rd_products"(jan_code);
CREATE INDEX IF NOT EXISTS idx_80_rd_products_price ON "80_rd_products"(current_price);
CREATE INDEX IF NOT EXISTS idx_80_rd_products_name ON "80_rd_products"(product_name);
CREATE INDEX IF NOT EXISTS idx_80_rd_products_scraped ON "80_rd_products"(last_scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_80_rd_products_search ON "80_rd_products" USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_80_rd_products_date ON "80_rd_products"(document_date DESC);
CREATE INDEX IF NOT EXISTS idx_80_rd_products_workspace ON "80_rd_products"(workspace);
CREATE INDEX IF NOT EXISTS idx_80_rd_products_organization ON "80_rd_products"(organization);

-- 検索ベクトル自動更新トリガー
CREATE OR REPLACE FUNCTION update_80_rd_products_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', COALESCE(NEW.product_name, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(NEW.manufacturer, '')), 'B') ||
        setweight(to_tsvector('simple', COALESCE(NEW.category, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_80_rd_products_search_vector_update
    BEFORE INSERT OR UPDATE ON "80_rd_products"
    FOR EACH ROW
    EXECUTE FUNCTION update_80_rd_products_search_vector();

-- updated_at 自動更新トリガー
CREATE OR REPLACE FUNCTION update_80_rd_products_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_80_rd_products_updated_at
    BEFORE UPDATE ON "80_rd_products"
    FOR EACH ROW
    EXECUTE FUNCTION update_80_rd_products_updated_at();

-- ====================================================================
-- STEP 2: 価格履歴テーブル 80_rd_price_history の作成
-- ====================================================================

CREATE TABLE IF NOT EXISTS "80_rd_price_history" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- 商品参照
    product_id UUID REFERENCES "80_rd_products"(id) ON DELETE CASCADE,
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

    -- 複合ユニーク制約
    CONSTRAINT unique_80_rd_price_record UNIQUE(jan_code, scraped_date)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_80_rd_price_history_product_id ON "80_rd_price_history"(product_id);
CREATE INDEX IF NOT EXISTS idx_80_rd_price_history_jan_code ON "80_rd_price_history"(jan_code);
CREATE INDEX IF NOT EXISTS idx_80_rd_price_history_date ON "80_rd_price_history"(scraped_date DESC);
CREATE INDEX IF NOT EXISTS idx_80_rd_price_history_price ON "80_rd_price_history"(price);

-- ====================================================================
-- STEP 3: テーブルリネーム
-- ====================================================================

-- 10. ドキュメント処理
ALTER TABLE IF EXISTS source_documents RENAME TO "10_rd_source_docs";
ALTER TABLE IF EXISTS search_index RENAME TO "10_ix_search_index";

-- 60. 家計簿
ALTER TABLE IF EXISTS money_transactions RENAME TO "60_rd_transactions";
ALTER TABLE IF EXISTS money_categories RENAME TO "60_ms_categories";
ALTER TABLE IF EXISTS money_situations RENAME TO "60_ms_situations";
ALTER TABLE IF EXISTS money_product_dictionary RENAME TO "60_ms_product_dict";
ALTER TABLE IF EXISTS money_aliases RENAME TO "60_ms_ocr_aliases";

-- 70. チラシ
ALTER TABLE IF EXISTS flyer_documents RENAME TO "70_rd_flyer_docs";
ALTER TABLE IF EXISTS flyer_products RENAME TO "70_rd_flyer_items";

-- 99. ログ・システム
ALTER TABLE IF EXISTS correction_history RENAME TO "99_lg_correction_history";
ALTER TABLE IF EXISTS process_logs RENAME TO "99_lg_process_logs";
ALTER TABLE IF EXISTS document_reprocessing_queue RENAME TO "99_lg_reprocess_queue";
ALTER TABLE IF EXISTS money_image_processing_log RENAME TO "99_lg_image_proc_log";

-- ====================================================================
-- STEP 4: ビュー再作成
-- ====================================================================

-- 古いビュー削除
DROP VIEW IF EXISTS v_daily_summary;
DROP VIEW IF EXISTS v_monthly_summary;
DROP VIEW IF EXISTS v_rakuten_seiyu_products_latest;
DROP VIEW IF EXISTS v_rakuten_seiyu_price_changes;

-- 60_ag_daily_summary
CREATE OR REPLACE VIEW "60_ag_daily_summary" AS
SELECT
    transaction_date,
    s.name AS situation,
    c.name AS category,
    COUNT(*) AS item_count,
    SUM(total_amount) AS total
FROM "60_rd_transactions" t
LEFT JOIN "60_ms_situations" s ON t.situation_id = s.id
LEFT JOIN "60_ms_categories" c ON t.category_id = c.id
WHERE c.is_expense = TRUE
GROUP BY transaction_date, s.name, c.name
ORDER BY transaction_date DESC;

-- 60_ag_monthly_summary
CREATE OR REPLACE VIEW "60_ag_monthly_summary" AS
SELECT
    DATE_TRUNC('month', transaction_date) AS month,
    s.name AS situation,
    c.name AS category,
    COUNT(*) AS item_count,
    SUM(total_amount) AS total
FROM "60_rd_transactions" t
LEFT JOIN "60_ms_situations" s ON t.situation_id = s.id
LEFT JOIN "60_ms_categories" c ON t.category_id = c.id
WHERE c.is_expense = TRUE
GROUP BY month, s.name, c.name
ORDER BY month DESC;

-- 80_ag_price_changes
CREATE OR REPLACE VIEW "80_ag_price_changes" AS
SELECT
    p.product_name,
    p.jan_code,
    p.current_price,
    ph_old.price AS old_price,
    ph_new.price AS new_price,
    ph_new.scraped_date AS change_date,
    ROUND(((ph_new.price - ph_old.price) / ph_old.price * 100)::numeric, 2) AS price_change_percent
FROM "80_rd_products" p
INNER JOIN "80_rd_price_history" ph_new ON p.jan_code = ph_new.jan_code
INNER JOIN LATERAL (
    SELECT price
    FROM "80_rd_price_history"
    WHERE jan_code = p.jan_code
      AND scraped_date < ph_new.scraped_date
    ORDER BY scraped_date DESC
    LIMIT 1
) ph_old ON true
WHERE ph_new.price <> ph_old.price
ORDER BY ABS((ph_new.price - ph_old.price) / ph_old.price) DESC;

-- ====================================================================
-- STEP 5: 不要ビュー削除
-- ====================================================================

-- 古いビューは既にSTEP 4で削除済み

-- ====================================================================
-- STEP 6: RLSポリシー設定（80番台のみ）
-- ====================================================================

ALTER TABLE "80_rd_products" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "80_rd_price_history" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users full access to 80_rd_products"
    ON "80_rd_products"
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow service role full access to 80_rd_products"
    ON "80_rd_products"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow authenticated users full access to 80_rd_price_history"
    ON "80_rd_price_history"
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow service role full access to 80_rd_price_history"
    ON "80_rd_price_history"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ====================================================================
-- 完了メッセージ
-- ====================================================================

DO $$
BEGIN
    RAISE NOTICE '✅ テーブル統合・リネームが完了しました';
    RAISE NOTICE '✅ 80_rd_products: ダイエーと楽天西友を統合可能な構造を作成';
    RAISE NOTICE '✅ 80_rd_price_history: 価格履歴テーブルを作成';
    RAISE NOTICE '✅ 全テーブルを新命名規則でリネーム完了';
    RAISE NOTICE '✅ ビューを新テーブル名で再作成完了';
    RAISE NOTICE '✅ 不要テーブル削除完了（money_events, daiei_products, rakuten_seiyu_products）';
END $$;

COMMIT;

-- ====================================================================
-- 確認クエリ（実行後に確認）
-- ====================================================================

-- テーブル一覧確認
SELECT
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE '%\_rd\_%'
   OR table_name LIKE '%\_ms\_%'
   OR table_name LIKE '%\_ag\_%'
   OR table_name LIKE '%\_lg\_%'
   OR table_name LIKE '%\_ix\_%'
ORDER BY table_name;
