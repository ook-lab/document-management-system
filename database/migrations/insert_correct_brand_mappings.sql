-- 正しいブランド名→一般名詞マッピング
-- カテゴリーではなく、ブランド名を一般名詞に変換するためのマッピング

-- 削除して再作成
TRUNCATE TABLE "MASTER_Product_generalize";

-- 乳製品のブランド名
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('明治おいしい牛乳', '牛乳', 'manual', 'ブランド名→一般名詞'),
('おいしい牛乳', '牛乳', 'manual', 'ブランド名→一般名詞'),
('メグミルク', '牛乳', 'manual', 'ブランド名→一般名詞'),
('ブルガリアヨーグルト', 'ヨーグルト', 'manual', 'ブランド名→一般名詞'),
('ビヒダスヨーグルト', 'ヨーグルト', 'manual', 'ブランド名→一般名詞'),
('明治プロビオヨーグルト', 'ヨーグルト', 'manual', 'ブランド名→一般名詞'),
('恵 megumi', 'ヨーグルト', 'manual', 'ブランド名→一般名詞'),
('ナチュレ恵', 'ヨーグルト', 'manual', 'ブランド名→一般名詞');

-- 飲料のブランド名
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('コカコーラ', 'コーラ', 'manual', 'ブランド名→一般名詞'),
('コカ・コーラ', 'コーラ', 'manual', 'ブランド名→一般名詞'),
('ペプシ', 'コーラ', 'manual', 'ブランド名→一般名詞'),
('ペプシコーラ', 'コーラ', 'manual', 'ブランド名→一般名詞'),
('三ツ矢サイダー', 'サイダー', 'manual', 'ブランド名→一般名詞'),
('CCレモン', 'レモンソーダ', 'manual', 'ブランド名→一般名詞');

-- 米の品種名
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('コシヒカリ', '米', 'manual', '品種名→一般名詞'),
('あきたこまち', '米', 'manual', '品種名→一般名詞'),
('ひとめぼれ', '米', 'manual', '品種名→一般名詞'),
('ゆめぴりか', '米', 'manual', '品種名→一般名詞'),
('ななつぼし', '米', 'manual', '品種名→一般名詞');

-- インスタント食品のブランド名
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('サッポロ一番', 'ラーメン', 'manual', 'ブランド名→一般名詞'),
('チキンラーメン', 'ラーメン', 'manual', 'ブランド名→一般名詞'),
('マルちゃん', 'ラーメン', 'manual', 'ブランド名→一般名詞'),
('日清焼そば', '焼きそば', 'manual', 'ブランド名→一般名詞'),
('一平ちゃん', '焼きそば', 'manual', 'ブランド名→一般名詞'),
('ペヤング', '焼きそば', 'manual', 'ブランド名→一般名詞');

-- パンのブランド名
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('ヤマザキ', 'パン', 'manual', 'メーカー名（パン専業）'),
('Pasco', 'パン', 'manual', 'メーカー名（パン専業）'),
('フジパン', 'パン', 'manual', 'メーカー名（パン専業）');

-- その他の特殊なブランド名
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source, notes) VALUES
('いろはす', '水', 'manual', 'ブランド名→一般名詞'),
('南アルプスの天然水', '水', 'manual', 'ブランド名→一般名詞'),
('クリスタルガイザー', '水', 'manual', 'ブランド名→一般名詞'),
('エビアン', '水', 'manual', 'ブランド名→一般名詞'),
('ボルヴィック', '水', 'manual', 'ブランド名→一般名詞');

-- 注意: 以下のようなマッピングは登録しない（すでに一般名詞のため）
-- ❌ ハム → 加工肉（これはカテゴリー）
-- ❌ ベーコン → 加工肉（これはカテゴリー）
-- ❌ 豚肉 → 肉（これはカテゴリー）
-- ❌ トマト → 野菜（これはカテゴリー）
-- ❌ 醤油 → 調味料（これはカテゴリー）
--
-- これらは正規表現で自動的にメーカー名・容量を除去することで対応
