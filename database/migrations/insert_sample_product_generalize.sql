-- ====================================================================
-- MASTER_Product_generalizeテーブルにサンプルデータを挿入
-- ====================================================================
-- 目的: よく使う商品の一般名詞をマスタに登録
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- ====================================================================

BEGIN;

-- 乳製品
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('明治おいしい牛乳', '牛乳', 'manual', '一般的な牛乳'),
('メグミルク', '牛乳', 'manual', '一般的な牛乳'),
('雪印メグミルク', '牛乳', 'manual', '一般的な牛乳'),
('低脂肪牛乳', '牛乳', 'manual', '低脂肪牛乳も牛乳カテゴリ'),
('ヨーグルト', 'ヨーグルト', 'manual', '発酵乳製品'),
('ブルガリアヨーグルト', 'ヨーグルト', 'manual', '明治のヨーグルト'),
('ビヒダスヨーグルト', 'ヨーグルト', 'manual', '森永のヨーグルト'),
('チーズ', 'チーズ', 'manual', 'チーズ全般'),
('とろけるチーズ', 'チーズ', 'manual', '調理用チーズ'),
('バター', 'バター', 'manual', 'バター全般')
ON CONFLICT (raw_keyword, general_name) DO NOTHING;

-- 飲料
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('コカコーラ', '炭酸飲料', 'manual', '炭酸飲料'),
('ペプシ', '炭酸飲料', 'manual', '炭酸飲料'),
('三ツ矢サイダー', '炭酸飲料', 'manual', '炭酸飲料'),
('お茶', 'お茶', 'manual', 'お茶全般'),
('緑茶', 'お茶', 'manual', '緑茶'),
('麦茶', 'お茶', 'manual', '麦茶'),
('ウーロン茶', 'お茶', 'manual', 'ウーロン茶'),
('コーヒー', 'コーヒー', 'manual', 'コーヒー全般'),
('ジュース', 'ジュース', 'manual', 'ジュース全般'),
('オレンジジュース', 'ジュース', 'manual', 'オレンジジュース'),
('アップルジュース', 'ジュース', 'manual', 'アップルジュース'),
('ミネラルウォーター', '水', 'manual', 'ミネラルウォーター')
ON CONFLICT (raw_keyword, general_name) DO NOTHING;

-- パン・麺類
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('食パン', 'パン', 'manual', '食パン'),
('ロールパン', 'パン', 'manual', 'ロールパン'),
('フランスパン', 'パン', 'manual', 'フランスパン'),
('菓子パン', 'パン', 'manual', '菓子パン'),
('うどん', '麺類', 'manual', 'うどん'),
('そば', '麺類', 'manual', 'そば'),
('スパゲティ', '麺類', 'manual', 'スパゲティ'),
('パスタ', '麺類', 'manual', 'パスタ'),
('ラーメン', 'インスタント麺', 'manual', 'インスタントラーメン'),
('カップラーメン', 'インスタント麺', 'manual', 'カップラーメン'),
('サッポロ一番', 'インスタント麺', 'manual', 'サッポロ一番'),
('チキンラーメン', 'インスタント麺', 'manual', 'チキンラーメン')
ON CONFLICT (raw_keyword, general_name) DO NOTHING;

-- 米・穀物
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('米', '米', 'manual', '米全般'),
('コシヒカリ', '米', 'manual', 'コシヒカリ'),
('あきたこまち', '米', 'manual', 'あきたこまち'),
('ひとめぼれ', '米', 'manual', 'ひとめぼれ')
ON CONFLICT (raw_keyword, general_name) DO NOTHING;

-- 野菜
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('キャベツ', '野菜', 'manual', 'キャベツ'),
('レタス', '野菜', 'manual', 'レタス'),
('白菜', '野菜', 'manual', '白菜'),
('玉ねぎ', '野菜', 'manual', '玉ねぎ'),
('じゃがいも', '野菜', 'manual', 'じゃがいも'),
('にんじん', '野菜', 'manual', 'にんじん'),
('大根', '野菜', 'manual', '大根'),
('トマト', '野菜', 'manual', 'トマト'),
('きゅうり', '野菜', 'manual', 'きゅうり'),
('なす', '野菜', 'manual', 'なす'),
('ピーマン', '野菜', 'manual', 'ピーマン'),
('もやし', '野菜', 'manual', 'もやし')
ON CONFLICT (raw_keyword, general_name) DO NOTHING;

-- 肉類
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('豚肉', '肉', 'manual', '豚肉'),
('牛肉', '肉', 'manual', '牛肉'),
('鶏肉', '肉', 'manual', '鶏肉'),
('ひき肉', '肉', 'manual', 'ひき肉'),
('ソーセージ', '加工肉', 'manual', 'ソーセージ'),
('ハム', '加工肉', 'manual', 'ハム'),
('ベーコン', '加工肉', 'manual', 'ベーコン')
ON CONFLICT (raw_keyword, general_name) DO NOTHING;

-- 魚介類
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('鮭', '魚', 'manual', '鮭'),
('サバ', '魚', 'manual', 'サバ'),
('アジ', '魚', 'manual', 'アジ'),
('マグロ', '魚', 'manual', 'マグロ'),
('イワシ', '魚', 'manual', 'イワシ'),
('刺身', '魚', 'manual', '刺身'),
('エビ', '海産物', 'manual', 'エビ'),
('イカ', '海産物', 'manual', 'イカ'),
('タコ', '海産物', 'manual', 'タコ')
ON CONFLICT (raw_keyword, general_name) DO NOTHING;

-- 調味料
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('醤油', '調味料', 'manual', '醤油'),
('味噌', '調味料', 'manual', '味噌'),
('砂糖', '調味料', 'manual', '砂糖'),
('塩', '調味料', 'manual', '塩'),
('酢', '調味料', 'manual', '酢'),
('みりん', '調味料', 'manual', 'みりん'),
('料理酒', '調味料', 'manual', '料理酒'),
('油', '調味料', 'manual', '食用油'),
('サラダ油', '調味料', 'manual', 'サラダ油'),
('ごま油', '調味料', 'manual', 'ごま油'),
('マヨネーズ', '調味料', 'manual', 'マヨネーズ'),
('ケチャップ', '調味料', 'manual', 'ケチャップ'),
('ソース', '調味料', 'manual', 'ソース')
ON CONFLICT (raw_keyword, general_name) DO NOTHING;

-- お菓子
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('ポテトチップス', 'スナック菓子', 'manual', 'ポテトチップス'),
('せんべい', 'スナック菓子', 'manual', 'せんべい'),
('チョコレート', 'お菓子', 'manual', 'チョコレート'),
('ガム', 'お菓子', 'manual', 'ガム'),
('キャンディ', 'お菓子', 'manual', 'キャンディ'),
('アイス', 'アイス', 'manual', 'アイスクリーム'),
('アイスクリーム', 'アイス', 'manual', 'アイスクリーム')
ON CONFLICT (raw_keyword, general_name) DO NOTHING;

-- 日用品
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('ティッシュ', '日用品', 'manual', 'ティッシュペーパー'),
('トイレットペーパー', '日用品', 'manual', 'トイレットペーパー'),
('洗剤', '日用品', 'manual', '洗剤全般'),
('食器用洗剤', '日用品', 'manual', '食器用洗剤'),
('洗濯洗剤', '日用品', 'manual', '洗濯洗剤'),
('シャンプー', '日用品', 'manual', 'シャンプー'),
('ボディソープ', '日用品', 'manual', 'ボディソープ'),
('歯磨き粉', '日用品', 'manual', '歯磨き粉'),
('ラップ', '日用品', 'manual', 'ラップフィルム'),
('アルミホイル', '日用品', 'manual', 'アルミホイル')
ON CONFLICT (raw_keyword, general_name) DO NOTHING;

COMMIT;

-- ====================================================================
-- 確認クエリ
-- ====================================================================
-- SELECT general_name, COUNT(*) as count
-- FROM "MASTER_Product_generalize"
-- GROUP BY general_name
-- ORDER BY count DESC;
