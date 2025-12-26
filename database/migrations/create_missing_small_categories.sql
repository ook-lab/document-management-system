-- ====================================================================
-- 不足している小分類を追加
-- ====================================================================
-- 目的: 野菜、果物、肉類、魚介類の小分類を確実に作成
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- ====================================================================

BEGIN;

DO $$
DECLARE
    -- 中分類ID（食品配下）
    vegetables_mid_id UUID;
    fruits_mid_id UUID;
    meat_mid_id UUID;
    seafood_mid_id UUID;
BEGIN
    -- 中分類IDを取得（食品配下の野菜、果物、肉類、魚介類）
    SELECT id INTO vegetables_mid_id
    FROM "MASTER_Categories_product"
    WHERE name = '野菜' AND parent_id IS NOT NULL
    LIMIT 1;

    SELECT id INTO fruits_mid_id
    FROM "MASTER_Categories_product"
    WHERE name = '果物' AND parent_id IS NOT NULL
    LIMIT 1;

    SELECT id INTO meat_mid_id
    FROM "MASTER_Categories_product"
    WHERE name = '肉類' AND parent_id IS NOT NULL
    LIMIT 1;

    SELECT id INTO seafood_mid_id
    FROM "MASTER_Categories_product"
    WHERE name = '魚介類' AND parent_id IS NOT NULL
    LIMIT 1;

    RAISE NOTICE '中分類ID確認:';
    RAISE NOTICE '  野菜: %', vegetables_mid_id;
    RAISE NOTICE '  果物: %', fruits_mid_id;
    RAISE NOTICE '  肉類: %', meat_mid_id;
    RAISE NOTICE '  魚介類: %', seafood_mid_id;

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
        RAISE NOTICE '✅ 野菜の小分類を作成しました';
    ELSE
        RAISE NOTICE '❌ 野菜の中分類が見つかりません';
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
        RAISE NOTICE '✅ 果物の小分類を作成しました';
    ELSE
        RAISE NOTICE '❌ 果物の中分類が見つかりません';
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
        RAISE NOTICE '✅ 肉類の小分類を作成しました';
    ELSE
        RAISE NOTICE '❌ 肉類の中分類が見つかりません';
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
        RAISE NOTICE '✅ 魚介類の小分類を作成しました';
    ELSE
        RAISE NOTICE '❌ 魚介類の中分類が見つかりません';
    END IF;

END $$;

COMMIT;

-- 確認
DO $$
DECLARE
    total_small INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_small
    FROM "MASTER_Categories_product" small
    WHERE small.parent_id IN (
        SELECT mid.id FROM "MASTER_Categories_product" mid
        WHERE mid.parent_id IS NOT NULL
    );

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ 小分類の作成完了';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '  小分類総数: % 件', total_small;
    RAISE NOTICE '====================================================================';
END $$;
