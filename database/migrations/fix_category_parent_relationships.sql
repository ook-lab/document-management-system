-- ====================================================================
-- カテゴリ階層の親子関係を修正
-- ====================================================================
-- 目的: 野菜・果物・肉類・魚介類を食品の中分類として再配置
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- ====================================================================
-- 問題: 野菜・果物・肉類・魚介類がparent_id=NULLの大分類として作成されている
-- 解決: これらを食品(parent_id)の中分類に変更し、その下に小分類を作成
-- ====================================================================

BEGIN;

DO $$
DECLARE
    food_large_id UUID;
    vegetables_mid_id UUID;
    fruits_mid_id UUID;
    meat_mid_id UUID;
    seafood_mid_id UUID;
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'ステップ1: 食品(大分類)のIDを取得';
    RAISE NOTICE '====================================================================';

    -- 大分類「食品」のIDを取得
    SELECT id INTO food_large_id
    FROM "MASTER_Categories_product"
    WHERE name IN ('食品', '食材') AND parent_id IS NULL
    ORDER BY created_at DESC
    LIMIT 1;

    IF food_large_id IS NULL THEN
        RAISE EXCEPTION '食品(大分類)が見つかりません';
    END IF;

    RAISE NOTICE '✅ 食品ID: %', food_large_id;
    RAISE NOTICE '';

    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'ステップ2: 野菜・果物・肉類・魚介類の親IDを食品に変更';
    RAISE NOTICE '====================================================================';

    -- 野菜を中分類に変更
    UPDATE "MASTER_Categories_product"
    SET parent_id = food_large_id,
        description = COALESCE(description, '野菜類'),
        updated_at = NOW()
    WHERE name = '野菜' AND parent_id IS NULL
    RETURNING id INTO vegetables_mid_id;

    IF vegetables_mid_id IS NOT NULL THEN
        RAISE NOTICE '✅ 野菜を中分類に変更: %', vegetables_mid_id;
    ELSE
        RAISE NOTICE '⚠️ 野菜が見つかりませんでした';
    END IF;

    -- 果物を中分類に変更
    UPDATE "MASTER_Categories_product"
    SET parent_id = food_large_id,
        description = COALESCE(description, '果物類'),
        updated_at = NOW()
    WHERE name = '果物' AND parent_id IS NULL
    RETURNING id INTO fruits_mid_id;

    IF fruits_mid_id IS NOT NULL THEN
        RAISE NOTICE '✅ 果物を中分類に変更: %', fruits_mid_id;
    ELSE
        RAISE NOTICE '⚠️ 果物が見つかりませんでした';
    END IF;

    -- 肉類を中分類に変更
    UPDATE "MASTER_Categories_product"
    SET parent_id = food_large_id,
        description = COALESCE(description, '精肉'),
        updated_at = NOW()
    WHERE name = '肉類' AND parent_id IS NULL
    RETURNING id INTO meat_mid_id;

    IF meat_mid_id IS NOT NULL THEN
        RAISE NOTICE '✅ 肉類を中分類に変更: %', meat_mid_id;
    ELSE
        RAISE NOTICE '⚠️ 肉類が見つかりませんでした';
    END IF;

    -- 魚介類を中分類に変更
    UPDATE "MASTER_Categories_product"
    SET parent_id = food_large_id,
        description = COALESCE(description, '鮮魚・水産加工品'),
        updated_at = NOW()
    WHERE name = '魚介類' AND parent_id IS NULL
    RETURNING id INTO seafood_mid_id;

    IF seafood_mid_id IS NOT NULL THEN
        RAISE NOTICE '✅ 魚介類を中分類に変更: %', seafood_mid_id;
    ELSE
        RAISE NOTICE '⚠️ 魚介類が見つかりませんでした';
    END IF;

    RAISE NOTICE '';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'ステップ3: 小分類の作成';
    RAISE NOTICE '====================================================================';

    -- 野菜の小分類
    IF vegetables_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('根菜類', '大根・にんじん・じゃがいもなど', vegetables_mid_id),
        ('葉物野菜', 'キャベツ・レタス・ほうれん草など', vegetables_mid_id),
        ('果菜類', 'トマト・きゅうり・なすなど', vegetables_mid_id),
        ('きのこ類', 'しいたけ・えのきなど', vegetables_mid_id),
        ('香味野菜', 'ねぎ・にんにく・しょうがなど', vegetables_mid_id),
        ('豆類', '枝豆・大豆など', vegetables_mid_id)
        ON CONFLICT DO NOTHING;
        RAISE NOTICE '✅ 野菜の小分類 6件 作成';
    END IF;

    -- 果物の小分類
    IF fruits_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('柑橘類', 'みかん・オレンジ・レモンなど', fruits_mid_id),
        ('りんご・なし', 'りんご・なし', fruits_mid_id),
        ('ベリー類', 'いちご・ブルーベリーなど', fruits_mid_id),
        ('バナナ', 'バナナ', fruits_mid_id),
        ('その他果物', 'その他の果物', fruits_mid_id)
        ON CONFLICT DO NOTHING;
        RAISE NOTICE '✅ 果物の小分類 5件 作成';
    END IF;

    -- 肉類の小分類
    IF meat_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('牛肉', '牛肉各部位', meat_mid_id),
        ('豚肉', '豚肉各部位', meat_mid_id),
        ('鶏肉', '鶏肉各部位', meat_mid_id),
        ('挽肉', '合挽き・牛挽き・豚挽き', meat_mid_id),
        ('加工肉', 'ハム・ベーコン・ソーセージ', meat_mid_id)
        ON CONFLICT DO NOTHING;
        RAISE NOTICE '✅ 肉類の小分類 5件 作成';
    END IF;

    -- 魚介類の小分類
    IF seafood_mid_id IS NOT NULL THEN
        INSERT INTO "MASTER_Categories_product" (name, description, parent_id) VALUES
        ('鮮魚', '生鮮魚介', seafood_mid_id),
        ('刺身', '刺身・寿司用', seafood_mid_id),
        ('練り物', 'かまぼこ・ちくわ・はんぺん', seafood_mid_id),
        ('干物・塩干', '干物・塩干魚', seafood_mid_id),
        ('貝類', '貝類', seafood_mid_id),
        ('エビ・カニ', 'エビ・カニ', seafood_mid_id)
        ON CONFLICT DO NOTHING;
        RAISE NOTICE '✅ 魚介類の小分類 6件 作成';
    END IF;

    RAISE NOTICE '';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '完了';
    RAISE NOTICE '====================================================================';

END $$;

-- 最終確認
DO $$
DECLARE
    large_count INTEGER;
    medium_count INTEGER;
    small_count INTEGER;
BEGIN
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

    RAISE NOTICE '';
    RAISE NOTICE '最終統計:';
    RAISE NOTICE '  大分類: % 件', large_count;
    RAISE NOTICE '  中分類: % 件', medium_count;
    RAISE NOTICE '  小分類: % 件', small_count;
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ: update_mappings_to_small_categories.sql を実行';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;
