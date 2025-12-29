-- スクレイピングスケジュール管理テーブル
CREATE TABLE IF NOT EXISTS "99_lg_scraping_schedule" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_name TEXT NOT NULL,
    category_name TEXT NOT NULL,
    url TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    start_date DATE NOT NULL,
    interval_days INTEGER DEFAULT 7,
    last_run DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_store_category UNIQUE (store_name, category_name)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_scraping_schedule_store ON "99_lg_scraping_schedule"(store_name);
CREATE INDEX IF NOT EXISTS idx_scraping_schedule_enabled ON "99_lg_scraping_schedule"(enabled);
CREATE INDEX IF NOT EXISTS idx_scraping_schedule_start_date ON "99_lg_scraping_schedule"(start_date);

-- updated_at自動更新トリガー
CREATE OR REPLACE FUNCTION update_scraping_schedule_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_scraping_schedule_updated_at
    BEFORE UPDATE ON "99_lg_scraping_schedule"
    FOR EACH ROW
    EXECUTE FUNCTION update_scraping_schedule_updated_at();

-- コメント
COMMENT ON TABLE "99_lg_scraping_schedule" IS 'ネットスーパースクレイピングのスケジュール管理';
COMMENT ON COLUMN "99_lg_scraping_schedule".store_name IS '店舗名（例: rakuten_seiyu, tokyu_store, daiei）';
COMMENT ON COLUMN "99_lg_scraping_schedule".category_name IS 'カテゴリー名';
COMMENT ON COLUMN "99_lg_scraping_schedule".enabled IS '有効/無効フラグ';
COMMENT ON COLUMN "99_lg_scraping_schedule".start_date IS '次回実行開始日';
COMMENT ON COLUMN "99_lg_scraping_schedule".interval_days IS '実行間隔（日数）';
COMMENT ON COLUMN "99_lg_scraping_schedule".last_run IS '最終実行日';
