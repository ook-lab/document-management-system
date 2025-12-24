-- ========================================
-- 2次分類（費目）システムの構築
-- ========================================
--
-- 設計思想:
-- - 1次分類: 商品の物理的カテゴリー（文房具、ゲームソフト、交通費など）
-- - 2次分類: 家計簿の費目（食費、教育費、娯楽費など）
-- - 決定ロジック: 優先順位 = 名目 > 人物 > 1次分類
--
-- 例:
-- - 交通費（1次）+ 旅行（名目）→ 行楽費（2次）
-- - 交通費（1次）+ 学校行事（名目）→ 教育費（2次）
-- - ゲームソフト（1次）+ 育哉 + 教育（名目）→ 教育費（2次）
-- ========================================

-- 1. 1次分類マスタ（商品の物理的カテゴリー）
CREATE TABLE IF NOT EXISTS "MASTER_Categories_product" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    parent_id UUID REFERENCES "MASTER_Categories_product"(id) ON DELETE SET NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_categories_parent ON "MASTER_Categories_product"(parent_id);

COMMENT ON TABLE "MASTER_Categories_product" IS '1次分類: 商品の物理的カテゴリー（文房具、ゲームソフト、食材など）';
COMMENT ON COLUMN "MASTER_Categories_product".parent_id IS '親カテゴリ（階層構造: 野菜 > 根菜）';

-- 2. 2次分類マスタ（費目）
CREATE TABLE IF NOT EXISTS "MASTER_Categories_expense" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    display_order INTEGER DEFAULT 100,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE "MASTER_Categories_expense" IS '2次分類: 家計簿の費目（食費、教育費、娯楽費など）';
COMMENT ON COLUMN "MASTER_Categories_expense".display_order IS '表示順（小さいほど上）';

-- 3. 名目マスタ（拡張可能）
CREATE TABLE IF NOT EXISTS "MASTER_Categories_purpose" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    display_order INTEGER DEFAULT 100,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE "MASTER_Categories_purpose" IS '名目マスタ（日常、旅行、学校行事など。状況に応じて拡張）';

-- 4. 2次分類決定ルール（優先順位: 名目 > 人物 > 1次分類）
CREATE TABLE IF NOT EXISTS "MASTER_Rules_expense_mapping" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 条件（優先順位順）
    purpose_id UUID REFERENCES "MASTER_Categories_purpose"(id) ON DELETE CASCADE,
    person TEXT,  -- 家族、パパ、ママ、絵麻、育哉
    product_category_id UUID REFERENCES "MASTER_Categories_product"(id) ON DELETE CASCADE,

    -- 結果
    expense_category_id UUID REFERENCES "MASTER_Categories_expense"(id) ON DELETE CASCADE NOT NULL,

    -- 優先度（自動計算）
    -- 100: 名目のみ
    -- 90: 名目 + 人物 または 名目 + 1次分類
    -- 80: 名目 + 人物 + 1次分類
    -- 50: 人物 + 1次分類
    -- 30: 1次分類のみ
    priority INTEGER DEFAULT 50,

    -- メタデータ
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by TEXT,  -- ユーザー手動 or システム自動

    -- ユニーク制約（NULL値も考慮）
    UNIQUE NULLS NOT DISTINCT (purpose_id, person, product_category_id)
);

CREATE INDEX IF NOT EXISTS idx_expense_rules_purpose ON "MASTER_Rules_expense_mapping"(purpose_id);
CREATE INDEX IF NOT EXISTS idx_expense_rules_product ON "MASTER_Rules_expense_mapping"(product_category_id);
CREATE INDEX IF NOT EXISTS idx_expense_rules_priority ON "MASTER_Rules_expense_mapping"(priority DESC);

COMMENT ON TABLE "MASTER_Rules_expense_mapping" IS '2次分類決定ルール（優先順位: 名目 > 人物 > 1次分類）';
COMMENT ON COLUMN "MASTER_Rules_expense_mapping".priority IS '優先度（大きいほど優先。名目のみ=100、名目+人物=90など）';

-- ========================================
-- 初期データ投入
-- ========================================

-- 2次分類（費目）の初期データ
INSERT INTO "MASTER_Categories_expense" (name, description, display_order) VALUES
    ('食費', '食料品、外食など', 10),
    ('日用品費', '日用品、消耗品など', 20),
    ('教育費', '書籍、教材、習い事など', 30),
    ('娯楽費', 'ゲーム、趣味、レジャーなど', 40),
    ('交通費', '交通機関、ガソリンなど', 50),
    ('医療費', '病院、薬など', 60),
    ('行楽費', '旅行、観光など', 70),
    ('その他', 'その他の支出', 100)
ON CONFLICT (name) DO NOTHING;

-- 名目の初期データ
INSERT INTO "MASTER_Categories_purpose" (name, description, display_order) VALUES
    ('日常', '日常的な支出', 10),
    ('教育', '教育目的の支出', 20),
    ('学校行事', '学校関連のイベント', 30),
    ('旅行', '旅行・観光', 40),
    ('医療', '医療・健康関連', 50)
ON CONFLICT (name) DO NOTHING;

-- 1次分類の初期データ（よく使われるカテゴリー）
INSERT INTO "MASTER_Categories_product" (name, parent_id, description) VALUES
    ('食材', NULL, '生鮮食品、加工食品など'),
    ('野菜', (SELECT id FROM "MASTER_Categories_product" WHERE name = '食材'), NULL),
    ('果物', (SELECT id FROM "MASTER_Categories_product" WHERE name = '食材'), NULL),
    ('肉類', (SELECT id FROM "MASTER_Categories_product" WHERE name = '食材'), NULL),
    ('魚介類', (SELECT id FROM "MASTER_Categories_product" WHERE name = '食材'), NULL),
    ('外食', NULL, 'レストラン、ファストフードなど'),
    ('文房具', NULL, 'ペン、ノートなど'),
    ('ゲームソフト', NULL, 'ゲームソフト、アプリなど'),
    ('書籍', NULL, '本、雑誌など'),
    ('交通', NULL, '電車、バス、タクシーなど'),
    ('日用品', NULL, '洗剤、ティッシュなど')
ON CONFLICT (name) DO NOTHING;

-- デフォルトルールの投入
DO $$
DECLARE
    purpose_daily_id UUID;
    purpose_education_id UUID;
    purpose_school_id UUID;
    purpose_travel_id UUID;

    cat_food_id UUID;
    cat_dining_id UUID;
    cat_education_id UUID;
    cat_entertainment_id UUID;
    cat_travel_id UUID;

    prod_food_id UUID;
    prod_dining_id UUID;
    prod_stationery_id UUID;
    prod_game_id UUID;
    prod_book_id UUID;
    prod_transport_id UUID;
BEGIN
    -- 名目IDを取得
    SELECT id INTO purpose_daily_id FROM "MASTER_Categories_purpose" WHERE name = '日常';
    SELECT id INTO purpose_education_id FROM "MASTER_Categories_purpose" WHERE name = '教育';
    SELECT id INTO purpose_school_id FROM "MASTER_Categories_purpose" WHERE name = '学校行事';
    SELECT id INTO purpose_travel_id FROM "MASTER_Categories_purpose" WHERE name = '旅行';

    -- 2次分類IDを取得
    SELECT id INTO cat_food_id FROM "MASTER_Categories_expense" WHERE name = '食費';
    SELECT id INTO cat_education_id FROM "MASTER_Categories_expense" WHERE name = '教育費';
    SELECT id INTO cat_entertainment_id FROM "MASTER_Categories_expense" WHERE name = '娯楽費';
    SELECT id INTO cat_travel_id FROM "MASTER_Categories_expense" WHERE name = '行楽費';

    -- 1次分類IDを取得
    SELECT id INTO prod_food_id FROM "MASTER_Categories_product" WHERE name = '食材';
    SELECT id INTO prod_dining_id FROM "MASTER_Categories_product" WHERE name = '外食';
    SELECT id INTO prod_stationery_id FROM "MASTER_Categories_product" WHERE name = '文房具';
    SELECT id INTO prod_game_id FROM "MASTER_Categories_product" WHERE name = 'ゲームソフト';
    SELECT id INTO prod_book_id FROM "MASTER_Categories_product" WHERE name = '書籍';
    SELECT id INTO prod_transport_id FROM "MASTER_Categories_product" WHERE name = '交通';

    -- ルールを投入
    INSERT INTO "MASTER_Rules_expense_mapping"
        (purpose_id, person, product_category_id, expense_category_id, priority, created_by)
    VALUES
        -- 名目優先ルール（priority=100）
        (purpose_travel_id, NULL, NULL, cat_travel_id, 100, 'system'),
        (purpose_school_id, NULL, NULL, cat_education_id, 100, 'system'),

        -- 名目 + 1次分類（priority=90）
        (purpose_education_id, NULL, prod_game_id, cat_education_id, 90, 'system'),
        (purpose_education_id, NULL, prod_book_id, cat_education_id, 90, 'system'),
        (purpose_daily_id, NULL, prod_game_id, cat_entertainment_id, 90, 'system'),

        -- 1次分類のみ（priority=30）
        (NULL, NULL, prod_food_id, cat_food_id, 30, 'system'),
        (NULL, NULL, prod_dining_id, cat_food_id, 30, 'system'),
        (NULL, NULL, prod_stationery_id, cat_education_id, 30, 'system'),
        (NULL, NULL, prod_book_id, cat_education_id, 30, 'system')
    ON CONFLICT DO NOTHING;
END $$;

-- ========================================
-- ビュー: ルール一覧（見やすく）
-- ========================================
CREATE OR REPLACE VIEW v_expense_category_rules AS
SELECT
    r.id,
    p.name AS purpose,
    r.person,
    pc.name AS product_category,
    ec.name AS expense_category,
    r.priority,
    r.created_by,
    r.created_at
FROM "MASTER_Rules_expense_mapping" r
LEFT JOIN "MASTER_Categories_purpose" p ON r.purpose_id = p.id
LEFT JOIN "MASTER_Categories_product" pc ON r.product_category_id = pc.id
LEFT JOIN "MASTER_Categories_expense" ec ON r.expense_category_id = ec.id
ORDER BY r.priority DESC, r.created_at DESC;

COMMENT ON VIEW v_expense_category_rules IS '2次分類決定ルールの見やすいビュー';
