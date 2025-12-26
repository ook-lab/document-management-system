-- ====================================================================
-- サンプル商品カテゴリマッピングデータ投入
-- ====================================================================
-- 目的: MASTER_Product_category_mapping に初期データを投入
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- 前提条件: add_two_tier_classification_system.sql が実行済み
-- ====================================================================

BEGIN;

-- ====================================================================
-- 前提: 商品カテゴリマスタ（MASTER_Categories_product）の確認
-- ====================================================================
-- 注意: 以下のカテゴリが既に存在することを前提としています
-- 存在しない場合は、先に MASTER_Categories_product にデータを投入してください

DO $$
DECLARE
    food_category_id UUID;
    daily_goods_category_id UUID;
    beverage_category_id UUID;
BEGIN
    -- 商品カテゴリIDを取得（存在チェック）
    SELECT id INTO food_category_id
    FROM "MASTER_Categories_product"
    WHERE name = '食料品'
    LIMIT 1;

    IF food_category_id IS NULL THEN
        -- 食料品カテゴリが存在しない場合は作成
        INSERT INTO "MASTER_Categories_product" (name, description, display_order)
        VALUES ('食料品', '食品・飲料などの食料品全般', 10)
        RETURNING id INTO food_category_id;
        RAISE NOTICE '✅ 商品カテゴリ「食料品」を作成しました';
    END IF;

    -- 日用品カテゴリチェック
    SELECT id INTO daily_goods_category_id
    FROM "MASTER_Categories_product"
    WHERE name = '日用品'
    LIMIT 1;

    IF daily_goods_category_id IS NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, display_order)
        VALUES ('日用品', 'ティッシュ、洗剤などの日用消耗品', 20)
        RETURNING id INTO daily_goods_category_id;
        RAISE NOTICE '✅ 商品カテゴリ「日用品」を作成しました';
    END IF;

    -- 飲料カテゴリチェック
    SELECT id INTO beverage_category_id
    FROM "MASTER_Categories_product"
    WHERE name = '飲料'
    LIMIT 1;

    IF beverage_category_id IS NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, display_order)
        VALUES ('飲料', 'アルコール・ソフトドリンクなど', 15)
        RETURNING id INTO beverage_category_id;
        RAISE NOTICE '✅ 商品カテゴリ「飲料」を作成しました';
    END IF;
END $$;

-- ====================================================================
-- サンプルデータ投入
-- ====================================================================

-- 食料品カテゴリのマッピング
INSERT INTO "MASTER_Product_category_mapping" (general_name, product_category_id, source, notes)
SELECT
    mapping.general_name,
    cat.id as product_category_id,
    'manual' as source,
    mapping.notes
FROM (VALUES
    -- 乳製品
    ('牛乳', '食料品', '乳製品全般'),
    ('ヨーグルト', '食料品', '発酵乳製品'),
    ('チーズ', '食料品', 'チーズ各種'),
    ('バター', '食料品', '乳脂肪製品'),

    -- パン・穀物
    ('パン', '食料品', 'パン類全般'),
    ('食パン', '食料品', '食パン'),
    ('米', '食料品', '米・雑穀'),
    ('麺類', '食料品', 'うどん、そば、パスタなど'),
    ('インスタントラーメン', '食料品', '即席麺'),

    -- 肉・魚
    ('牛肉', '食料品', '牛肉各部位'),
    ('豚肉', '食料品', '豚肉各部位'),
    ('鶏肉', '食料品', '鶏肉各部位'),
    ('魚', '食料品', '魚介類全般'),
    ('刺身', '食料品', '生魚刺身'),

    -- 野菜・果物
    ('野菜', '食料品', '野菜全般'),
    ('果物', '食料品', '果物全般'),
    ('トマト', '食料品', 'トマト'),
    ('玉ねぎ', '食料品', '玉ねぎ'),
    ('じゃがいも', '食料品', 'じゃがいも'),

    -- 調味料
    ('醤油', '食料品', '醤油'),
    ('味噌', '食料品', '味噌'),
    ('砂糖', '食料品', '砂糖'),
    ('塩', '食料品', '塩'),
    ('油', '食料品', '食用油'),

    -- お菓子
    ('お菓子', '食料品', '菓子類全般'),
    ('クッキー', '食料品', 'ビスケット・クッキー'),
    ('チョコレート', '食料品', 'チョコレート菓子'),
    ('アイスクリーム', '食料品', '冷菓'),
    ('ケーキ', '食料品', '洋菓子')
) AS mapping(general_name, category_name, notes)
JOIN "MASTER_Categories_product" cat ON cat.name = mapping.category_name
ON CONFLICT (general_name) DO NOTHING;

-- 飲料カテゴリのマッピング
INSERT INTO "MASTER_Product_category_mapping" (general_name, product_category_id, source, notes)
SELECT
    mapping.general_name,
    cat.id as product_category_id,
    'manual' as source,
    mapping.notes
FROM (VALUES
    ('ジュース', '飲料', '果汁飲料'),
    ('お茶', '飲料', '緑茶・麦茶など'),
    ('コーヒー', '飲料', 'コーヒー'),
    ('紅茶', '飲料', '紅茶'),
    ('炭酸飲料', '飲料', '炭酸飲料'),
    ('ビール', '飲料', 'ビール・発泡酒'),
    ('ワイン', '飲料', 'ワイン'),
    ('日本酒', '飲料', '日本酒'),
    ('焼酎', '飲料', '焼酎'),
    ('ウイスキー', '飲料', 'ウイスキー'),
    ('酎ハイ', '飲料', '缶チューハイ'),
    ('水', '飲料', 'ミネラルウォーター')
) AS mapping(general_name, category_name, notes)
JOIN "MASTER_Categories_product" cat ON cat.name = mapping.category_name
ON CONFLICT (general_name) DO NOTHING;

-- 日用品カテゴリのマッピング
INSERT INTO "MASTER_Product_category_mapping" (general_name, product_category_id, source, notes)
SELECT
    mapping.general_name,
    cat.id as product_category_id,
    'manual' as source,
    mapping.notes
FROM (VALUES
    ('ティッシュ', '日用品', 'ティッシュペーパー'),
    ('トイレットペーパー', '日用品', 'トイレットペーパー'),
    ('洗剤', '日用品', '洗濯・食器用洗剤'),
    ('シャンプー', '日用品', 'シャンプー'),
    ('石鹸', '日用品', '石鹸・ボディソープ'),
    ('歯磨き粉', '日用品', '歯磨き粉'),
    ('歯ブラシ', '日用品', '歯ブラシ'),
    ('マスク', '日用品', 'マスク'),
    ('ゴミ袋', '日用品', 'ゴミ袋'),
    ('ラップ', '日用品', '食品用ラップ'),
    ('アルミホイル', '日用品', 'アルミホイル'),
    ('キッチンペーパー', '日用品', 'キッチンペーパー')
) AS mapping(general_name, category_name, notes)
JOIN "MASTER_Categories_product" cat ON cat.name = mapping.category_name
ON CONFLICT (general_name) DO NOTHING;

-- ====================================================================
-- 統計情報の表示
-- ====================================================================

DO $$
DECLARE
    total_count INTEGER;
    food_count INTEGER;
    beverage_count INTEGER;
    daily_count INTEGER;
BEGIN
    -- 総件数
    SELECT COUNT(*) INTO total_count
    FROM "MASTER_Product_category_mapping";

    -- カテゴリ別件数
    SELECT COUNT(*) INTO food_count
    FROM "MASTER_Product_category_mapping" pcm
    JOIN "MASTER_Categories_product" cat ON pcm.product_category_id = cat.id
    WHERE cat.name = '食料品';

    SELECT COUNT(*) INTO beverage_count
    FROM "MASTER_Product_category_mapping" pcm
    JOIN "MASTER_Categories_product" cat ON pcm.product_category_id = cat.id
    WHERE cat.name = '飲料';

    SELECT COUNT(*) INTO daily_count
    FROM "MASTER_Product_category_mapping" pcm
    JOIN "MASTER_Categories_product" cat ON pcm.product_category_id = cat.id
    WHERE cat.name = '日用品';

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ サンプルデータの投入が完了しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '投入件数:';
    RAISE NOTICE '  総件数:     % 件', total_count;
    RAISE NOTICE '  食料品:     % 件', food_count;
    RAISE NOTICE '  飲料:       % 件', beverage_count;
    RAISE NOTICE '  日用品:     % 件', daily_count;
    RAISE NOTICE '';
    RAISE NOTICE 'サンプルマッピング:';
    RAISE NOTICE '  牛乳 → 食料品';
    RAISE NOTICE '  ビール → 飲料';
    RAISE NOTICE '  ティッシュ → 日用品';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. 不足している商品カテゴリマッピングを追加';
    RAISE NOTICE '  2. コードの更新（分類ロジック）';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;

-- ====================================================================
-- 実行後の確認クエリ
-- ====================================================================

-- 投入されたデータの確認
-- SELECT
--     pcm.general_name,
--     cat.name as product_category,
--     pcm.source,
--     pcm.notes
-- FROM "MASTER_Product_category_mapping" pcm
-- JOIN "MASTER_Categories_product" cat ON pcm.product_category_id = cat.id
-- ORDER BY cat.name, pcm.general_name;

-- カテゴリ別の集計
-- SELECT
--     cat.name as category,
--     COUNT(*) as mapping_count
-- FROM "MASTER_Product_category_mapping" pcm
-- JOIN "MASTER_Categories_product" cat ON pcm.product_category_id = cat.id
-- GROUP BY cat.name
-- ORDER BY cat.name;
