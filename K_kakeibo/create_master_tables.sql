-- マスターテーブルを作成（空）

-- エイリアステーブル
CREATE TABLE IF NOT EXISTS public."60_ms_ocr_aliases" (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    input_word TEXT NOT NULL,
    correct_word TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 商品辞書
CREATE TABLE IF NOT EXISTS public."60_ms_product_dict" (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    raw_keyword TEXT NOT NULL,
    official_name TEXT NOT NULL,
    category_id UUID,
    tax_rate INTEGER DEFAULT 10,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- シチュエーション
CREATE TABLE IF NOT EXISTS public."60_ms_situations" (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- デフォルトのシチュエーションを挿入
INSERT INTO public."60_ms_situations" (name) VALUES ('日常') ON CONFLICT (name) DO NOTHING;

-- カテゴリ
CREATE TABLE IF NOT EXISTS public."60_ms_categories" (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
