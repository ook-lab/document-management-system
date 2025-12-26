-- ====================================================================
-- 商品カテゴリマッピングを小分類に更新
-- ====================================================================
-- 目的: MASTER_Product_category_mapping を詳細な小分類に更新
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- ====================================================================

BEGIN;

-- ====================================================================
-- 既存マッピングを削除（大分類レベルのものをクリア）
-- ====================================================================

-- 旧マッピングを一旦削除して、新しい小分類で再作成
DELETE FROM "MASTER_Product_category_mapping";

-- ====================================================================
-- 小分類へのマッピングを作成
-- ====================================================================

DO $$
DECLARE
    -- 小分類ID変数
    root_veg_id UUID;
    leaf_veg_id UUID;
    fruit_veg_id UUID;
    mushroom_id UUID;
    herb_veg_id UUID;
    beans_id UUID;

    citrus_id UUID;
    apple_pear_id UUID;
    berry_id UUID;
    banana_id UUID;
    other_fruit_id UUID;

    beef_id UUID;
    pork_id UUID;
    chicken_id UUID;
    ground_meat_id UUID;
    processed_meat_id UUID;

    fresh_fish_id UUID;
    sashimi_id UUID;
    kamaboko_id UUID;
    dried_fish_id UUID;
    shellfish_id UUID;
    shrimp_crab_id UUID;

    milk_id UUID;
    yogurt_id UUID;
    cheese_id UUID;
    butter_id UUID;
    cream_id UUID;

    rice_id UUID;
    bread_id UUID;
    noodles_id UUID;
    cereal_id UUID;
    flour_id UUID;

    basic_seasoning_id UUID;
    oil_id UUID;
    sauce_id UUID;
    soup_id UUID;
    spice_id UUID;

    snack_id UUID;
    chocolate_id UUID;
    cookie_id UUID;
    wagashi_id UUID;
    ice_cream_id UUID;
    cake_id UUID;
    candy_id UUID;

    tofu_natto_id UUID;
    egg_id UUID;
    pickle_id UUID;
    canned_id UUID;
    retort_id UUID;

    tissue_id UUID;
    toilet_paper_id UUID;
    mask_id UUID;

    laundry_detergent_id UUID;
    dish_detergent_id UUID;

    wrap_id UUID;
    garbage_bag_id UUID;
    kitchen_id UUID;

    shampoo_id UUID;
    body_soap_id UUID;
    tooth_id UUID;

    tea_id UUID;
    juice_id UUID;
    soda_id UUID;
    sports_drink_id UUID;

    beer_id UUID;
    wine_id UUID;
    sake_id UUID;
    shochu_id UUID;
    chuhai_id UUID;
    whiskey_id UUID;

    coffee_id UUID;
    black_tea_id UUID;
BEGIN
    -- 小分類IDを取得
    -- 野菜の小分類
    SELECT id INTO root_veg_id FROM "MASTER_Categories_product" WHERE name = '根菜類' AND parent_id IS NOT NULL;
    SELECT id INTO leaf_veg_id FROM "MASTER_Categories_product" WHERE name = '葉物野菜' AND parent_id IS NOT NULL;
    SELECT id INTO fruit_veg_id FROM "MASTER_Categories_product" WHERE name = '果菜類' AND parent_id IS NOT NULL;
    SELECT id INTO mushroom_id FROM "MASTER_Categories_product" WHERE name = 'きのこ類' AND parent_id IS NOT NULL;
    SELECT id INTO herb_veg_id FROM "MASTER_Categories_product" WHERE name = '香味野菜' AND parent_id IS NOT NULL;
    SELECT id INTO beans_id FROM "MASTER_Categories_product" WHERE name = '豆類' AND parent_id IS NOT NULL;

    -- 果物の小分類
    SELECT id INTO citrus_id FROM "MASTER_Categories_product" WHERE name = '柑橘類' AND parent_id IS NOT NULL;
    SELECT id INTO apple_pear_id FROM "MASTER_Categories_product" WHERE name = 'りんご・なし' AND parent_id IS NOT NULL;
    SELECT id INTO berry_id FROM "MASTER_Categories_product" WHERE name = 'ベリー類' AND parent_id IS NOT NULL;
    SELECT id INTO banana_id FROM "MASTER_Categories_product" WHERE name = 'バナナ' AND parent_id IS NOT NULL;
    SELECT id INTO other_fruit_id FROM "MASTER_Categories_product" WHERE name = 'その他果物' AND parent_id IS NOT NULL;

    -- 肉類の小分類
    SELECT id INTO beef_id FROM "MASTER_Categories_product" WHERE name = '牛肉' AND parent_id IS NOT NULL;
    SELECT id INTO pork_id FROM "MASTER_Categories_product" WHERE name = '豚肉' AND parent_id IS NOT NULL;
    SELECT id INTO chicken_id FROM "MASTER_Categories_product" WHERE name = '鶏肉' AND parent_id IS NOT NULL;
    SELECT id INTO ground_meat_id FROM "MASTER_Categories_product" WHERE name = '挽肉' AND parent_id IS NOT NULL;
    SELECT id INTO processed_meat_id FROM "MASTER_Categories_product" WHERE name = '加工肉' AND parent_id IS NOT NULL;

    -- 魚介類の小分類
    SELECT id INTO fresh_fish_id FROM "MASTER_Categories_product" WHERE name = '鮮魚' AND parent_id IS NOT NULL;
    SELECT id INTO sashimi_id FROM "MASTER_Categories_product" WHERE name = '刺身' AND parent_id IS NOT NULL;
    SELECT id INTO kamaboko_id FROM "MASTER_Categories_product" WHERE name = '練り物' AND parent_id IS NOT NULL;
    SELECT id INTO dried_fish_id FROM "MASTER_Categories_product" WHERE name = '干物・塩干' AND parent_id IS NOT NULL;
    SELECT id INTO shellfish_id FROM "MASTER_Categories_product" WHERE name = '貝類' AND parent_id IS NOT NULL;
    SELECT id INTO shrimp_crab_id FROM "MASTER_Categories_product" WHERE name = 'エビ・カニ' AND parent_id IS NOT NULL;

    -- 乳製品の小分類
    SELECT id INTO milk_id FROM "MASTER_Categories_product" WHERE name = '牛乳' AND parent_id IS NOT NULL;
    SELECT id INTO yogurt_id FROM "MASTER_Categories_product" WHERE name = 'ヨーグルト' AND parent_id IS NOT NULL;
    SELECT id INTO cheese_id FROM "MASTER_Categories_product" WHERE name = 'チーズ' AND parent_id IS NOT NULL;
    SELECT id INTO butter_id FROM "MASTER_Categories_product" WHERE name = 'バター・マーガリン' AND parent_id IS NOT NULL;
    SELECT id INTO cream_id FROM "MASTER_Categories_product" WHERE name = '生クリーム' AND parent_id IS NOT NULL;

    -- 穀類の小分類
    SELECT id INTO rice_id FROM "MASTER_Categories_product" WHERE name = '米' AND parent_id IS NOT NULL;
    SELECT id INTO bread_id FROM "MASTER_Categories_product" WHERE name = 'パン' AND parent_id IS NOT NULL;
    SELECT id INTO noodles_id FROM "MASTER_Categories_product" WHERE name = '麺類' AND parent_id IS NOT NULL;
    SELECT id INTO cereal_id FROM "MASTER_Categories_product" WHERE name = 'シリアル' AND parent_id IS NOT NULL;
    SELECT id INTO flour_id FROM "MASTER_Categories_product" WHERE name = '粉類' AND parent_id IS NOT NULL;

    -- 調味料の小分類
    SELECT id INTO basic_seasoning_id FROM "MASTER_Categories_product" WHERE name = '基本調味料' AND parent_id IS NOT NULL;
    SELECT id INTO oil_id FROM "MASTER_Categories_product" WHERE name = '油類' AND parent_id IS NOT NULL;
    SELECT id INTO sauce_id FROM "MASTER_Categories_product" WHERE name = 'ソース類' AND parent_id IS NOT NULL;
    SELECT id INTO soup_id FROM "MASTER_Categories_product" WHERE name = 'だし・スープ' AND parent_id IS NOT NULL;
    SELECT id INTO spice_id FROM "MASTER_Categories_product" WHERE name = '香辛料' AND parent_id IS NOT NULL;

    -- 菓子の小分類
    SELECT id INTO snack_id FROM "MASTER_Categories_product" WHERE name = 'スナック菓子' AND parent_id IS NOT NULL;
    SELECT id INTO chocolate_id FROM "MASTER_Categories_product" WHERE name = 'チョコレート菓子' AND parent_id IS NOT NULL;
    SELECT id INTO cookie_id FROM "MASTER_Categories_product" WHERE name = 'クッキー・ビスケット' AND parent_id IS NOT NULL;
    SELECT id INTO wagashi_id FROM "MASTER_Categories_product" WHERE name = '和菓子' AND parent_id IS NOT NULL;
    SELECT id INTO ice_cream_id FROM "MASTER_Categories_product" WHERE name = 'アイス・冷菓' AND parent_id IS NOT NULL;
    SELECT id INTO cake_id FROM "MASTER_Categories_product" WHERE name = 'ケーキ・洋菓子' AND parent_id IS NOT NULL;
    SELECT id INTO candy_id FROM "MASTER_Categories_product" WHERE name = 'ガム・キャンディ' AND parent_id IS NOT NULL;

    -- 加工食品の小分類
    SELECT id INTO tofu_natto_id FROM "MASTER_Categories_product" WHERE name = '豆腐・納豆' AND parent_id IS NOT NULL;
    SELECT id INTO egg_id FROM "MASTER_Categories_product" WHERE name = '卵' AND parent_id IS NOT NULL;
    SELECT id INTO pickle_id FROM "MASTER_Categories_product" WHERE name = '漬物' AND parent_id IS NOT NULL;
    SELECT id INTO canned_id FROM "MASTER_Categories_product" WHERE name = '缶詰' AND parent_id IS NOT NULL;
    SELECT id INTO retort_id FROM "MASTER_Categories_product" WHERE name = 'レトルト食品' AND parent_id IS NOT NULL;

    -- 衛生用品の小分類
    SELECT id INTO tissue_id FROM "MASTER_Categories_product" WHERE name = 'ティッシュ' AND parent_id IS NOT NULL;
    SELECT id INTO toilet_paper_id FROM "MASTER_Categories_product" WHERE name = 'トイレットペーパー' AND parent_id IS NOT NULL;
    SELECT id INTO mask_id FROM "MASTER_Categories_product" WHERE name = 'マスク' AND parent_id IS NOT NULL;

    -- 洗剤類の小分類
    SELECT id INTO laundry_detergent_id FROM "MASTER_Categories_product" WHERE name = '洗濯用洗剤' AND parent_id IS NOT NULL;
    SELECT id INTO dish_detergent_id FROM "MASTER_Categories_product" WHERE name = '食器用洗剤' AND parent_id IS NOT NULL;

    -- 日用消耗品の小分類
    SELECT id INTO wrap_id FROM "MASTER_Categories_product" WHERE name = 'ラップ・ホイル' AND parent_id IS NOT NULL;
    SELECT id INTO garbage_bag_id FROM "MASTER_Categories_product" WHERE name = 'ゴミ袋' AND parent_id IS NOT NULL;
    SELECT id INTO kitchen_id FROM "MASTER_Categories_product" WHERE name = 'キッチン用品' AND parent_id IS NOT NULL;

    -- バス・トイレ用品の小分類
    SELECT id INTO shampoo_id FROM "MASTER_Categories_product" WHERE name = 'シャンプー・リンス' AND parent_id IS NOT NULL;
    SELECT id INTO body_soap_id FROM "MASTER_Categories_product" WHERE name = 'ボディソープ' AND parent_id IS NOT NULL;
    SELECT id INTO tooth_id FROM "MASTER_Categories_product" WHERE name = '歯磨き用品' AND parent_id IS NOT NULL;

    -- ソフトドリンクの小分類
    SELECT id INTO tea_id FROM "MASTER_Categories_product" WHERE name = 'お茶' AND parent_id IS NOT NULL;
    SELECT id INTO juice_id FROM "MASTER_Categories_product" WHERE name = 'ジュース' AND parent_id IS NOT NULL;
    SELECT id INTO soda_id FROM "MASTER_Categories_product" WHERE name = '炭酸飲料' AND parent_id IS NOT NULL;
    SELECT id INTO sports_drink_id FROM "MASTER_Categories_product" WHERE name = 'スポーツドリンク' AND parent_id IS NOT NULL;

    -- アルコールの小分類
    SELECT id INTO beer_id FROM "MASTER_Categories_product" WHERE name = 'ビール・発泡酒' AND parent_id IS NOT NULL;
    SELECT id INTO wine_id FROM "MASTER_Categories_product" WHERE name = 'ワイン' AND parent_id IS NOT NULL;
    SELECT id INTO sake_id FROM "MASTER_Categories_product" WHERE name = '日本酒' AND parent_id IS NOT NULL;
    SELECT id INTO shochu_id FROM "MASTER_Categories_product" WHERE name = '焼酎' AND parent_id IS NOT NULL;
    SELECT id INTO chuhai_id FROM "MASTER_Categories_product" WHERE name = 'チューハイ' AND parent_id IS NOT NULL;
    SELECT id INTO whiskey_id FROM "MASTER_Categories_product" WHERE name = 'ウイスキー・洋酒' AND parent_id IS NOT NULL;

    -- コーヒー・紅茶の小分類
    SELECT id INTO coffee_id FROM "MASTER_Categories_product" WHERE name = 'コーヒー' AND parent_id IS NOT NULL;
    SELECT id INTO black_tea_id FROM "MASTER_Categories_product" WHERE name = '紅茶' AND parent_id IS NOT NULL;

    -- マッピングデータ投入（小分類を使用）
    INSERT INTO "MASTER_Product_category_mapping" (general_name, product_category_id, source, notes) VALUES
    -- 野菜
    ('大根', root_veg_id, 'manual', '根菜'),
    ('にんじん', root_veg_id, 'manual', '根菜'),
    ('じゃがいも', root_veg_id, 'manual', '根菜'),
    ('玉ねぎ', root_veg_id, 'manual', '根菜'),
    ('さつまいも', root_veg_id, 'manual', '根菜'),
    ('ごぼう', root_veg_id, 'manual', '根菜'),
    ('れんこん', root_veg_id, 'manual', '根菜'),

    ('キャベツ', leaf_veg_id, 'manual', '葉物'),
    ('レタス', leaf_veg_id, 'manual', '葉物'),
    ('ほうれん草', leaf_veg_id, 'manual', '葉物'),
    ('小松菜', leaf_veg_id, 'manual', '葉物'),
    ('白菜', leaf_veg_id, 'manual', '葉物'),
    ('水菜', leaf_veg_id, 'manual', '葉物'),
    ('チンゲン菜', leaf_veg_id, 'manual', '葉物'),

    ('トマト', fruit_veg_id, 'manual', '果菜'),
    ('きゅうり', fruit_veg_id, 'manual', '果菜'),
    ('なす', fruit_veg_id, 'manual', '果菜'),
    ('ピーマン', fruit_veg_id, 'manual', '果菜'),
    ('パプリカ', fruit_veg_id, 'manual', '果菜'),
    ('かぼちゃ', fruit_veg_id, 'manual', '果菜'),

    ('しいたけ', mushroom_id, 'manual', 'きのこ'),
    ('えのき', mushroom_id, 'manual', 'きのこ'),
    ('しめじ', mushroom_id, 'manual', 'きのこ'),
    ('まいたけ', mushroom_id, 'manual', 'きのこ'),
    ('エリンギ', mushroom_id, 'manual', 'きのこ'),

    ('ねぎ', herb_veg_id, 'manual', '香味野菜'),
    ('にんにく', herb_veg_id, 'manual', '香味野菜'),
    ('しょうが', herb_veg_id, 'manual', '香味野菜'),
    ('生姜', herb_veg_id, 'manual', '香味野菜'),
    ('みょうが', herb_veg_id, 'manual', '香味野菜'),

    -- 果物
    ('みかん', citrus_id, 'manual', '柑橘'),
    ('オレンジ', citrus_id, 'manual', '柑橘'),
    ('レモン', citrus_id, 'manual', '柑橘'),
    ('グレープフルーツ', citrus_id, 'manual', '柑橘'),

    ('りんご', apple_pear_id, 'manual', 'りんご・なし'),
    ('なし', apple_pear_id, 'manual', 'りんご・なし'),

    ('いちご', berry_id, 'manual', 'ベリー'),
    ('ブルーベリー', berry_id, 'manual', 'ベリー'),

    ('バナナ', banana_id, 'manual', 'バナナ'),

    -- 肉類
    ('牛肉', beef_id, 'manual', '牛肉'),
    ('豚肉', pork_id, 'manual', '豚肉'),
    ('鶏肉', chicken_id, 'manual', '鶏肉'),
    ('挽肉', ground_meat_id, 'manual', '挽肉'),
    ('ハム', processed_meat_id, 'manual', '加工肉'),
    ('ベーコン', processed_meat_id, 'manual', '加工肉'),
    ('ソーセージ', processed_meat_id, 'manual', '加工肉'),

    -- 魚介類
    ('魚', fresh_fish_id, 'manual', '鮮魚'),
    ('サーモン', fresh_fish_id, 'manual', '鮮魚'),
    ('マグロ', fresh_fish_id, 'manual', '鮮魚'),
    ('刺身', sashimi_id, 'manual', '刺身'),
    ('かまぼこ', kamaboko_id, 'manual', '練り物'),
    ('ちくわ', kamaboko_id, 'manual', '練り物'),
    ('はんぺん', kamaboko_id, 'manual', '練り物'),

    -- 乳製品
    ('牛乳', milk_id, 'manual', '牛乳'),
    ('ヨーグルト', yogurt_id, 'manual', 'ヨーグルト'),
    ('チーズ', cheese_id, 'manual', 'チーズ'),
    ('バター', butter_id, 'manual', 'バター'),

    -- 穀類
    ('米', rice_id, 'manual', '米'),
    ('パン', bread_id, 'manual', 'パン'),
    ('食パン', bread_id, 'manual', 'パン'),
    ('うどん', noodles_id, 'manual', '麺'),
    ('そば', noodles_id, 'manual', '麺'),
    ('パスタ', noodles_id, 'manual', '麺'),
    ('ラーメン', noodles_id, 'manual', '麺'),
    ('インスタントラーメン', retort_id, 'manual', 'インスタント'),

    -- 調味料
    ('醤油', basic_seasoning_id, 'manual', '基本調味料'),
    ('味噌', basic_seasoning_id, 'manual', '基本調味料'),
    ('砂糖', basic_seasoning_id, 'manual', '基本調味料'),
    ('塩', basic_seasoning_id, 'manual', '基本調味料'),
    ('油', oil_id, 'manual', '油'),
    ('マヨネーズ', sauce_id, 'manual', 'ソース'),
    ('ケチャップ', sauce_id, 'manual', 'ソース'),
    ('マスタード', sauce_id, 'manual', 'ソース'),

    -- 菓子
    ('ポテトチップス', snack_id, 'manual', 'スナック'),
    ('お菓子', snack_id, 'manual', 'スナック'),
    ('チョコレート', chocolate_id, 'manual', 'チョコ'),
    ('クッキー', cookie_id, 'manual', 'クッキー'),
    ('アイスクリーム', ice_cream_id, 'manual', 'アイス'),
    ('ケーキ', cake_id, 'manual', 'ケーキ'),

    -- 加工食品
    ('豆腐', tofu_natto_id, 'manual', '豆腐'),
    ('納豆', tofu_natto_id, 'manual', '納豆'),
    ('卵', egg_id, 'manual', '卵'),

    -- 日用品
    ('ティッシュ', tissue_id, 'manual', 'ティッシュ'),
    ('トイレットペーパー', toilet_paper_id, 'manual', 'トイレットペーパー'),
    ('マスク', mask_id, 'manual', 'マスク'),
    ('洗剤', laundry_detergent_id, 'manual', '洗剤'),
    ('洗濯洗剤', laundry_detergent_id, 'manual', '洗濯洗剤'),
    ('食器用洗剤', dish_detergent_id, 'manual', '食器用洗剤'),
    ('ラップ', wrap_id, 'manual', 'ラップ'),
    ('ゴミ袋', garbage_bag_id, 'manual', 'ゴミ袋'),
    ('シャンプー', shampoo_id, 'manual', 'シャンプー'),
    ('石鹸', body_soap_id, 'manual', '石鹸'),
    ('歯磨き粉', tooth_id, 'manual', '歯磨き'),
    ('歯ブラシ', tooth_id, 'manual', '歯ブラシ'),

    -- 飲料
    ('お茶', tea_id, 'manual', 'お茶'),
    ('緑茶', tea_id, 'manual', '緑茶'),
    ('麦茶', tea_id, 'manual', '麦茶'),
    ('ジュース', juice_id, 'manual', 'ジュース'),
    ('炭酸飲料', soda_id, 'manual', '炭酸'),
    ('コーラ', soda_id, 'manual', 'コーラ'),
    ('ビール', beer_id, 'manual', 'ビール'),
    ('ワイン', wine_id, 'manual', 'ワイン'),
    ('赤ワイン', wine_id, 'manual', '赤ワイン'),
    ('白ワイン', wine_id, 'manual', '白ワイン'),
    ('日本酒', sake_id, 'manual', '日本酒'),
    ('焼酎', shochu_id, 'manual', '焼酎'),
    ('酎ハイ', chuhai_id, 'manual', 'チューハイ'),
    ('水', sports_drink_id, 'manual', '水'),
    ('コーヒー', coffee_id, 'manual', 'コーヒー'),
    ('紅茶', black_tea_id, 'manual', '紅茶')
    ON CONFLICT (general_name) DO NOTHING;

    RAISE NOTICE '✅ 商品カテゴリマッピングを小分類で作成しました';
END $$;

COMMIT;

-- 実行後の確認
-- SELECT
--     pcm.general_name,
--     small.name as small_category,
--     mid.name as mid_category,
--     large.name as large_category
-- FROM "MASTER_Product_category_mapping" pcm
-- JOIN "MASTER_Categories_product" small ON pcm.product_category_id = small.id
-- LEFT JOIN "MASTER_Categories_product" mid ON small.parent_id = mid.id
-- LEFT JOIN "MASTER_Categories_product" large ON mid.parent_id = large.id
-- ORDER BY large.name, mid.name, small.name, pcm.general_name
-- LIMIT 50;
