-- ====================================================================
-- 商品カテゴリ階層構造の作成（大・中・小分類）
-- ====================================================================
-- 目的: 詳細な商品分類階層を構築
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- ====================================================================

BEGIN;

-- ====================================================================
-- 既存の分類を整理
-- ====================================================================
-- 現在の「食材」「野菜」などを中分類として再構成

-- まず、大分類を作成
DO $$
DECLARE
    food_large_id UUID;
    goods_large_id UUID;
    beverage_large_id UUID;
    other_large_id UUID;
BEGIN
    -- 大分類: 食品
    INSERT INTO "MASTER_Categories_product" (name, description, parent_id)
    VALUES ('食品', '食材・食料品全般', NULL)
    ON CONFLICT DO NOTHING
    RETURNING id INTO food_large_id;

    -- 既存の「食材」を取得（なければ上で作成したIDを使用）
    IF food_large_id IS NULL THEN
        SELECT id INTO food_large_id
        FROM "MASTER_Categories_product"
        WHERE name IN ('食品', '食材') AND parent_id IS NULL
        LIMIT 1;
    END IF;

    -- 大分類: 日用品
    SELECT id INTO goods_large_id
    FROM "MASTER_Categories_product"
    WHERE name = '日用品' AND parent_id IS NULL
    LIMIT 1;

    IF goods_large_id IS NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id)
        VALUES ('日用品', '日用消耗品・生活雑貨', NULL)
        RETURNING id INTO goods_large_id;
    END IF;

    -- 大分類: 飲料
    SELECT id INTO beverage_large_id
    FROM "MASTER_Categories_product"
    WHERE name = '飲料' AND parent_id IS NULL
    LIMIT 1;

    IF beverage_large_id IS NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id)
        VALUES ('飲料', 'アルコール・ソフトドリンク', NULL)
        RETURNING id INTO beverage_large_id;
    END IF;

    -- 大分類: その他
    SELECT id INTO other_large_id
    FROM "MASTER_Categories_product"
    WHERE name = 'その他' AND parent_id IS NULL
    LIMIT 1;

    IF other_large_id IS NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id)
        VALUES ('その他', 'その他の商品', NULL)
        RETURNING id INTO other_large_id;
    END IF;

    RAISE NOTICE '✅ 大分類を作成しました';
    RAISE NOTICE '   - 食品: %', food_large_id;
    RAISE NOTICE '   - 日用品: %', goods_large_id;
    RAISE NOTICE '   - 飲料: %', beverage_large_id;
    RAISE NOTICE '   - その他: %', other_large_id;
END $$;

-- ====================================================================
-- 中分類の作成
-- ====================================================================

DO $$
DECLARE
    food_large_id UUID;
    goods_large_id UUID;
    beverage_large_id UUID;

    vegetables_mid_id UUID;
    fruits_mid_id UUID;
    meat_mid_id UUID;
    seafood_mid_id UUID;
    dairy_mid_id UUID;
    grains_mid_id UUID;
    seasoning_mid_id UUID;
    snacks_mid_id UUID;
    processed_mid_id UUID;
BEGIN
    -- 大分類IDを取得
    SELECT id INTO food_large_id FROM "MASTER_Categories_product" WHERE name IN ('食品', '食材') AND parent_id IS NULL LIMIT 1;
    SELECT id INTO goods_large_id FROM "MASTER_Categories_product" WHERE name = '日用品' AND parent_id IS NULL LIMIT 1;
    SELECT id INTO beverage_large_id FROM "MASTER_Categories_product" WHERE name = '飲料' AND parent_id IS NULL LIMIT 1;

    -- 【食品】の中分類
    INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
    ('野菜', '野菜類', food_large_id),
    ('果物', '果物類', food_large_id),
    ('肉類', '精肉', food_large_id),
    ('魚介類', '鮮魚・水産加工品', food_large_id),
    ('乳製品', '牛乳・乳製品', food_large_id),
    ('穀類', '米・パン・麺類', food_large_id),
    ('調味料', '調味料・香辛料', food_large_id),
    ('菓子', 'お菓子・デザート', food_large_id),
    ('加工食品', '惣菜・加工品', food_large_id),
    ('冷凍食品', '冷凍食品', food_large_id)
    ON CONFLICT DO NOTHING;

    RAISE NOTICE '✅ 食品の中分類を作成しました';

    -- 【日用品】の中分類
    INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
    ('衛生用品', 'ティッシュ・トイレ用品', goods_large_id),
    ('洗剤類', '洗濯・掃除用洗剤', goods_large_id),
    ('日用消耗品', 'ラップ・ゴミ袋など', goods_large_id),
    ('バス・トイレ用品', 'シャンプー・石鹸など', goods_large_id)
    ON CONFLICT DO NOTHING;

    RAISE NOTICE '✅ 日用品の中分類を作成しました';

    -- 【飲料】の中分類
    INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
    ('ソフトドリンク', 'お茶・ジュースなど', beverage_large_id),
    ('アルコール', 'ビール・ワイン・日本酒など', beverage_large_id),
    ('水', 'ミネラルウォーター', beverage_large_id),
    ('コーヒー・紅茶', 'コーヒー・紅茶', beverage_large_id)
    ON CONFLICT DO NOTHING;

    RAISE NOTICE '✅ 飲料の中分類を作成しました';
END $$;

-- ====================================================================
-- 小分類の作成（詳細分類）
-- ====================================================================

DO $$
DECLARE
    vegetables_mid_id UUID;
    fruits_mid_id UUID;
    meat_mid_id UUID;
    seafood_mid_id UUID;
    dairy_mid_id UUID;
    grains_mid_id UUID;
    seasoning_mid_id UUID;
    snacks_mid_id UUID;
    processed_mid_id UUID;
    frozen_mid_id UUID;

    hygiene_mid_id UUID;
    detergent_mid_id UUID;
    consumables_mid_id UUID;
    bath_mid_id UUID;

    soft_drink_mid_id UUID;
    alcohol_mid_id UUID;
    water_mid_id UUID;
    coffee_mid_id UUID;
BEGIN
    -- 中分類IDを取得
    SELECT id INTO vegetables_mid_id FROM "MASTER_Categories_product" WHERE name = '野菜' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO fruits_mid_id FROM "MASTER_Categories_product" WHERE name = '果物' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO meat_mid_id FROM "MASTER_Categories_product" WHERE name = '肉類' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO seafood_mid_id FROM "MASTER_Categories_product" WHERE name = '魚介類' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO dairy_mid_id FROM "MASTER_Categories_product" WHERE name = '乳製品' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO grains_mid_id FROM "MASTER_Categories_product" WHERE name = '穀類' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO seasoning_mid_id FROM "MASTER_Categories_product" WHERE name = '調味料' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO snacks_mid_id FROM "MASTER_Categories_product" WHERE name = '菓子' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO processed_mid_id FROM "MASTER_Categories_product" WHERE name = '加工食品' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO frozen_mid_id FROM "MASTER_Categories_product" WHERE name = '冷凍食品' AND parent_id IS NOT NULL LIMIT 1;

    SELECT id INTO hygiene_mid_id FROM "MASTER_Categories_product" WHERE name = '衛生用品' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO detergent_mid_id FROM "MASTER_Categories_product" WHERE name = '洗剤類' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO consumables_mid_id FROM "MASTER_Categories_product" WHERE name = '日用消耗品' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO bath_mid_id FROM "MASTER_Categories_product" WHERE name = 'バス・トイレ用品' AND parent_id IS NOT NULL LIMIT 1;

    SELECT id INTO soft_drink_mid_id FROM "MASTER_Categories_product" WHERE name = 'ソフトドリンク' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO alcohol_mid_id FROM "MASTER_Categories_product" WHERE name = 'アルコール' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO water_mid_id FROM "MASTER_Categories_product" WHERE name = '水' AND parent_id IS NOT NULL LIMIT 1;
    SELECT id INTO coffee_mid_id FROM "MASTER_Categories_product" WHERE name = 'コーヒー・紅茶' AND parent_id IS NOT NULL LIMIT 1;

    -- 【野菜】の小分類
    IF vegetables_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('根菜類', '大根・にんじん・じゃがいもなど', vegetables_mid_id),
        ('葉物野菜', 'キャベツ・レタス・ほうれん草など', vegetables_mid_id),
        ('果菜類', 'トマト・きゅうり・なすなど', vegetables_mid_id),
        ('きのこ類', 'しいたけ・えのきなど', vegetables_mid_id),
        ('香味野菜', 'ねぎ・にんにく・しょうがなど', vegetables_mid_id),
        ('豆類', '枝豆・大豆など', vegetables_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【果物】の小分類
    IF fruits_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('柑橘類', 'みかん・オレンジ・レモンなど', fruits_mid_id),
        ('りんご・なし', 'りんご・なし', fruits_mid_id),
        ('ベリー類', 'いちご・ブルーベリーなど', fruits_mid_id),
        ('バナナ', 'バナナ', fruits_mid_id),
        ('その他果物', 'その他の果物', fruits_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【肉類】の小分類
    IF meat_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('牛肉', '牛肉各部位', meat_mid_id),
        ('豚肉', '豚肉各部位', meat_mid_id),
        ('鶏肉', '鶏肉各部位', meat_mid_id),
        ('挽肉', '合挽き・牛挽き・豚挽き', meat_mid_id),
        ('加工肉', 'ハム・ベーコン・ソーセージ', meat_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【魚介類】の小分類
    IF seafood_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('鮮魚', '生鮮魚介', seafood_mid_id),
        ('刺身', '刺身・寿司用', seafood_mid_id),
        ('練り物', 'かまぼこ・ちくわ・はんぺん', seafood_mid_id),
        ('干物・塩干', '干物・塩干魚', seafood_mid_id),
        ('貝類', '貝類', seafood_mid_id),
        ('エビ・カニ', 'エビ・カニ', seafood_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【乳製品】の小分類
    IF dairy_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('牛乳', '牛乳', dairy_mid_id),
        ('ヨーグルト', 'ヨーグルト', dairy_mid_id),
        ('チーズ', 'チーズ', dairy_mid_id),
        ('バター・マーガリン', 'バター・マーガリン', dairy_mid_id),
        ('生クリーム', '生クリーム', dairy_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【穀類】の小分類
    IF grains_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('米', '米・雑穀', grains_mid_id),
        ('パン', 'パン類', grains_mid_id),
        ('麺類', 'うどん・そば・パスタ', grains_mid_id),
        ('シリアル', 'シリアル', grains_mid_id),
        ('粉類', '小麦粉・片栗粉など', grains_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【調味料】の小分類
    IF seasoning_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('基本調味料', '醤油・味噌・塩・砂糖', seasoning_mid_id),
        ('油類', 'サラダ油・ごま油など', seasoning_mid_id),
        ('ソース類', 'ソース・ケチャップ・マヨネーズ', seasoning_mid_id),
        ('だし・スープ', 'だし・スープの素', seasoning_mid_id),
        ('香辛料', '香辛料・スパイス', seasoning_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【菓子】の小分類
    IF snacks_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('スナック菓子', 'ポテトチップスなど', snacks_mid_id),
        ('チョコレート菓子', 'チョコレート', snacks_mid_id),
        ('クッキー・ビスケット', 'クッキー・ビスケット', snacks_mid_id),
        ('和菓子', '和菓子', snacks_mid_id),
        ('アイス・冷菓', 'アイスクリーム', snacks_mid_id),
        ('ケーキ・洋菓子', 'ケーキ・洋菓子', snacks_mid_id),
        ('ガム・キャンディ', 'ガム・キャンディ', snacks_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【加工食品】の小分類
    IF processed_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('豆腐・納豆', '豆腐・納豆・豆製品', processed_mid_id),
        ('卵', '鶏卵', processed_mid_id),
        ('漬物', '漬物', processed_mid_id),
        ('缶詰', '缶詰', processed_mid_id),
        ('レトルト食品', 'レトルト・インスタント', processed_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【衛生用品】の小分類
    IF hygiene_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('ティッシュ', 'ティッシュペーパー', hygiene_mid_id),
        ('トイレットペーパー', 'トイレットペーパー', hygiene_mid_id),
        ('マスク', 'マスク', hygiene_mid_id),
        ('生理用品', '生理用品', hygiene_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【洗剤類】の小分類
    IF detergent_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('洗濯用洗剤', '洗濯用洗剤・柔軟剤', detergent_mid_id),
        ('食器用洗剤', '食器用洗剤', detergent_mid_id),
        ('住居用洗剤', '掃除用洗剤', detergent_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【日用消耗品】の小分類
    IF consumables_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('ラップ・ホイル', 'ラップ・アルミホイル', consumables_mid_id),
        ('ゴミ袋', 'ゴミ袋', consumables_mid_id),
        ('キッチン用品', 'キッチンペーパー・スポンジ', consumables_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【バス・トイレ用品】の小分類
    IF bath_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('シャンプー・リンス', 'シャンプー・コンディショナー', bath_mid_id),
        ('ボディソープ', 'ボディソープ・石鹸', bath_mid_id),
        ('歯磨き用品', '歯磨き粉・歯ブラシ', bath_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【ソフトドリンク】の小分類
    IF soft_drink_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('お茶', '緑茶・麦茶など', soft_drink_mid_id),
        ('ジュース', '果汁飲料', soft_drink_mid_id),
        ('炭酸飲料', 'コーラ・サイダーなど', soft_drink_mid_id),
        ('スポーツドリンク', 'スポーツドリンク', soft_drink_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【アルコール】の小分類
    IF alcohol_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('ビール・発泡酒', 'ビール・発泡酒', alcohol_mid_id),
        ('ワイン', 'ワイン', alcohol_mid_id),
        ('日本酒', '日本酒', alcohol_mid_id),
        ('焼酎', '焼酎', alcohol_mid_id),
        ('チューハイ', '缶チューハイ', alcohol_mid_id),
        ('ウイスキー・洋酒', 'ウイスキー・洋酒', alcohol_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 【コーヒー・紅茶】の小分類
    IF coffee_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('コーヒー', 'コーヒー', coffee_mid_id),
        ('紅茶', '紅茶', coffee_mid_id)
        ON CONFLICT DO NOTHING;
    END IF;

    RAISE NOTICE '✅ 小分類を作成しました';
END $$;

COMMIT;

-- ====================================================================
-- 完了メッセージ
-- ====================================================================

DO $$
DECLARE
    large_count INTEGER;
    medium_count INTEGER;
    small_count INTEGER;
BEGIN
    -- 階層別カウント
    SELECT COUNT(*) INTO large_count
    FROM "MASTER_Categories_product"
    WHERE parent_id IS NULL;

    SELECT COUNT(*) INTO medium_count
    FROM "MASTER_Categories_product" mid
    WHERE mid.parent_id IN (SELECT id FROM "MASTER_Categories_product" WHERE parent_id IS NULL);

    SELECT COUNT(*) INTO small_count
    FROM "MASTER_Categories_product" small
    WHERE small.parent_id IN (
        SELECT mid.id FROM "MASTER_Categories_product" mid
        WHERE mid.parent_id IS NOT NULL
    );

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ 商品カテゴリ階層構造を作成しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '階層構造:';
    RAISE NOTICE '  大分類: % 件', large_count;
    RAISE NOTICE '  中分類: % 件', medium_count;
    RAISE NOTICE '  小分類: % 件', small_count;
    RAISE NOTICE '  総計:   % 件', large_count + medium_count + small_count;
    RAISE NOTICE '';
    RAISE NOTICE '例:';
    RAISE NOTICE '  食品 → 野菜 → 根菜類';
    RAISE NOTICE '  食品 → 魚介類 → 練り物';
    RAISE NOTICE '  日用品 → 衛生用品 → ティッシュ';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. 商品カテゴリマッピングの更新';
    RAISE NOTICE '  2. Rawdata_NETSUPER_items への反映';
    RAISE NOTICE '====================================================================';
END $$;
