-- ====================================================================
-- サンプル商品カテゴリマッピングデータ投入 v2
-- ====================================================================
-- 目的: MASTER_Product_category_mapping に初期データを投入
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- 前提条件: add_two_tier_classification_system.sql が実行済み
-- 変更点: 実際のテーブルスキーマに合わせて修正
-- ====================================================================

BEGIN;

-- ====================================================================
-- 前提: 商品カテゴリマスタ（MASTER_Categories_product）の確認と作成
-- ====================================================================

DO $$
DECLARE
    food_category_id UUID;
    daily_goods_category_id UUID;
    beverage_category_id UUID;
BEGIN
    -- 「食材」カテゴリを取得（既存）
    SELECT id INTO food_category_id
    FROM "MASTER_Categories_product"
    WHERE name = '食材'
    LIMIT 1;

    IF food_category_id IS NULL THEN
        -- 食材カテゴリが存在しない場合は作成
        INSERT INTO "MASTER_Categories_product" (name, description)
        VALUES ('食材', '生鮮食品、加工食品など')
        RETURNING id INTO food_category_id;
        RAISE NOTICE '✅ 商品カテゴリ「食材」を作成しました';
    ELSE
        RAISE NOTICE '✅ 商品カテゴリ「食材」は既に存在します (id: %)', food_category_id;
    END IF;

    -- 「日用品」カテゴリチェック
    SELECT id INTO daily_goods_category_id
    FROM "MASTER_Categories_product"
    WHERE name = '日用品'
    LIMIT 1;

    IF daily_goods_category_id IS NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description)
        VALUES ('日用品', 'ティッシュ、洗剤などの日用消耗品')
        RETURNING id INTO daily_goods_category_id;
        RAISE NOTICE '✅ 商品カテゴリ「日用品」を作成しました';
    ELSE
        RAISE NOTICE '✅ 商品カテゴリ「日用品」は既に存在します (id: %)', daily_goods_category_id;
    END IF;

    -- 「飲料」カテゴリチェック
    SELECT id INTO beverage_category_id
    FROM "MASTER_Categories_product"
    WHERE name = '飲料'
    LIMIT 1;

    IF beverage_category_id IS NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description)
        VALUES ('飲料', 'アルコール・ソフトドリンクなど')
        RETURNING id INTO beverage_category_id;
        RAISE NOTICE '✅ 商品カテゴリ「飲料」を作成しました';
    ELSE
        RAISE NOTICE '✅ 商品カテゴリ「飲料」は既に存在します (id: %)', beverage_category_id;
    END IF;
END $$;

-- ====================================================================
-- サンプルデータ投入
-- ====================================================================

-- 食材カテゴリのマッピング
INSERT INTO "MASTER_Product_category_mapping" (general_name, product_category_id, source, notes)
SELECT
    mapping.general_name,
    cat.id as product_category_id,
    'manual' as source,
    mapping.notes
FROM (VALUES
    -- 乳製品
    ('牛乳', '食材', '乳製品全般'),
    ('ヨーグルト', '食材', '発酵乳製品'),
    ('チーズ', '食材', 'チーズ各種'),
    ('バター', '食材', '乳脂肪製品'),

    -- パン・穀物
    ('パン', '食材', 'パン類全般'),
    ('食パン', '食材', '食パン'),
    ('米', '食材', '米・雑穀'),
    ('麺類', '食材', 'うどん、そば、パスタなど'),
    ('うどん', '食材', 'うどん'),
    ('そば', '食材', 'そば'),
    ('パスタ', '食材', 'パスタ'),
    ('ラーメン', '食材', 'ラーメン'),
    ('インスタントラーメン', '食材', '即席麺'),

    -- 肉・魚
    ('牛肉', '食材', '牛肉各部位'),
    ('豚肉', '食材', '豚肉各部位'),
    ('鶏肉', '食材', '鶏肉各部位'),
    ('魚', '食材', '魚介類全般'),
    ('刺身', '食材', '生魚刺身'),
    ('サーモン', '食材', 'サーモン'),
    ('マグロ', '食材', 'マグロ'),

    -- 野菜・果物（既存の「野菜」「果物」カテゴリがあるが、まとめて「食材」として扱う）
    ('野菜', '食材', '野菜全般'),
    ('果物', '食材', '果物全般'),
    ('トマト', '食材', 'トマト'),
    ('玉ねぎ', '食材', '玉ねぎ'),
    ('じゃがいも', '食材', 'じゃがいも'),
    ('にんじん', '食材', 'にんじん'),
    ('キャベツ', '食材', 'キャベツ'),
    ('レタス', '食材', 'レタス'),
    ('小松菜', '食材', '小松菜'),
    ('ほうれん草', '食材', 'ほうれん草'),
    ('りんご', '食材', 'りんご'),
    ('バナナ', '食材', 'バナナ'),
    ('みかん', '食材', 'みかん'),

    -- 調味料
    ('醤油', '食材', '醤油'),
    ('味噌', '食材', '味噌'),
    ('砂糖', '食材', '砂糖'),
    ('塩', '食材', '塩'),
    ('油', '食材', '食用油'),
    ('酢', '食材', '酢'),
    ('みりん', '食材', 'みりん'),
    ('料理酒', '食材', '料理酒'),
    ('マヨネーズ', '食材', 'マヨネーズ'),
    ('ケチャップ', '食材', 'ケチャップ'),
    ('マスタード', '食材', 'マスタード'),

    -- お菓子
    ('お菓子', '食材', '菓子類全般'),
    ('クッキー', '食材', 'ビスケット・クッキー'),
    ('チョコレート', '食材', 'チョコレート菓子'),
    ('アイスクリーム', '食材', '冷菓'),
    ('ケーキ', '食材', '洋菓子'),
    ('ポテトチップス', '食材', 'スナック菓子'),

    -- 惣菜・加工食品
    ('豆腐', '食材', '豆腐'),
    ('納豆', '食材', '納豆'),
    ('卵', '食材', '鶏卵'),
    ('ハム', '食材', 'ハム'),
    ('ベーコン', '食材', 'ベーコン'),
    ('ソーセージ', '食材', 'ソーセージ')
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
    ('緑茶', '飲料', '緑茶'),
    ('麦茶', '飲料', '麦茶'),
    ('コーヒー', '飲料', 'コーヒー'),
    ('紅茶', '飲料', '紅茶'),
    ('炭酸飲料', '飲料', '炭酸飲料'),
    ('コーラ', '飲料', 'コーラ'),
    ('ビール', '飲料', 'ビール・発泡酒'),
    ('ワイン', '飲料', 'ワイン'),
    ('赤ワイン', '飲料', '赤ワイン'),
    ('白ワイン', '飲料', '白ワイン'),
    ('日本酒', '飲料', '日本酒'),
    ('焼酎', '飲料', '焼酎'),
    ('ウイスキー', '飲料', 'ウイスキー'),
    ('酎ハイ', '飲料', '缶チューハイ'),
    ('水', '飲料', 'ミネラルウォーター'),
    ('スポーツドリンク', '飲料', 'スポーツドリンク'),
    ('エナジードリンク', '飲料', 'エナジードリンク')
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
    ('キッチンペーパー', '日用品', 'キッチンペーパー'),
    ('洗濯洗剤', '日用品', '洗濯用洗剤'),
    ('柔軟剤', '日用品', '衣類柔軟剤'),
    ('食器用洗剤', '日用品', '食器用洗剤'),
    ('漂白剤', '日用品', '漂白剤'),
    ('タオル', '日用品', 'タオル'),
    ('スポンジ', '日用品', 'スポンジ')
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
    WHERE cat.name = '食材';

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
    RAISE NOTICE '  食材:       % 件', food_count;
    RAISE NOTICE '  飲料:       % 件', beverage_count;
    RAISE NOTICE '  日用品:     % 件', daily_count;
    RAISE NOTICE '';
    RAISE NOTICE 'サンプルマッピング:';
    RAISE NOTICE '  牛乳 → 食材';
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
