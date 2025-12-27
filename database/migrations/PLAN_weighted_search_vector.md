# Weighted Search Vector Implementation Plan

## 目的

商品検索において、重要度に応じた重み付けを行い、検索精度を向上させる。

### 検索の優先順位

"Mizkan りんご黒酢 カロリーゼロ 1l" の場合:
1. **最重要** (Weight A): `general_name` = "りんご黒酢"
2. **重要** (Weight B): `keywords` = ["Mizkan", "りんご黒酢", "カロリーゼロ", "1l"]
3. **参考** (Weight C): `product_name` = 元の商品名全体

---

## PostgreSQL setweight() の使い方

PostgreSQLの全文検索では、4段階の重み付けが可能:
- **A**: 最重要（general_name用）
- **B**: 重要（keywords用）
- **C**: 普通（product_name用）
- **D**: 参考

### 重み付けの構文

```sql
setweight(to_tsvector('config', 'text'), 'A')
```

---

## 実装方針

### 1. search_vectorカラムの生成ロジック

```sql
UPDATE "Rawdata_NETSUPER_items"
SET search_vector =
    -- Weight A: general_name (最重要)
    setweight(to_tsvector('japanese', COALESCE(general_name, '')), 'A') ||

    -- Weight B: keywords (重要)
    setweight(to_tsvector('japanese',
        COALESCE(array_to_string(keywords, ' '), '')), 'B') ||

    -- Weight C: product_name (参考)
    setweight(to_tsvector('japanese', COALESCE(product_name, '')), 'C');
```

### 説明
- `COALESCE(general_name, '')`: NULLの場合は空文字列に変換
- `array_to_string(keywords, ' ')`: JSON配列を空白区切りの文字列に変換
- `||`: ベクトルの連結演算子

---

## 実装ステップ

### Step 1: keywordsカラムの追加（完了）

```sql
ALTER TABLE "Rawdata_NETSUPER_items"
ADD COLUMN IF NOT EXISTS keywords JSONB DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_netsuper_items_keywords
ON "Rawdata_NETSUPER_items" USING gin(keywords);
```

### Step 2: search_vectorカラムの存在確認

既存の `search_vector` カラムを確認:

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'Rawdata_NETSUPER_items'
AND column_name = 'search_vector';
```

### Step 3: 重み付きsearch_vectorの生成

```sql
-- 既存データの更新
UPDATE "Rawdata_NETSUPER_items"
SET search_vector =
    setweight(to_tsvector('japanese', COALESCE(general_name, '')), 'A') ||
    setweight(to_tsvector('japanese',
        COALESCE(
            (SELECT string_agg(value::text, ' ')
             FROM jsonb_array_elements_text(keywords)),
            ''
        )), 'B') ||
    setweight(to_tsvector('japanese', COALESCE(product_name, '')), 'C')
WHERE general_name IS NOT NULL OR keywords IS NOT NULL OR product_name IS NOT NULL;
```

### Step 4: トリガーの作成（自動更新）

商品データが挿入・更新されたときに自動的にsearch_vectorを更新:

```sql
CREATE OR REPLACE FUNCTION update_netsuper_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('japanese', COALESCE(NEW.general_name, '')), 'A') ||
        setweight(to_tsvector('japanese',
            COALESCE(
                (SELECT string_agg(value::text, ' ')
                 FROM jsonb_array_elements_text(NEW.keywords)),
                ''
            )), 'B') ||
        setweight(to_tsvector('japanese', COALESCE(NEW.product_name, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER netsuper_search_vector_update
    BEFORE INSERT OR UPDATE OF general_name, keywords, product_name
    ON "Rawdata_NETSUPER_items"
    FOR EACH ROW
    EXECUTE FUNCTION update_netsuper_search_vector();
```

### Step 5: 検索クエリの例

```sql
-- 重み付き検索（general_nameが最も重要）
SELECT
    id,
    product_name,
    general_name,
    keywords,
    ts_rank(search_vector, to_tsquery('japanese', 'りんご & 黒酢')) AS rank
FROM "Rawdata_NETSUPER_items"
WHERE search_vector @@ to_tsquery('japanese', 'りんご & 黒酢')
ORDER BY rank DESC
LIMIT 10;
```

---

## 検索の動作

### 例: "りんご黒酢"で検索

#### 商品A: "Mizkan りんご黒酢 カロリーゼロ 1l"
- general_name: "りんご黒酢" (Weight A) → **最高スコア**
- keywords: ["Mizkan", "りんご黒酢", "カロリーゼロ", "1l"] (Weight B)
- product_name: "Mizkan りんご黒酢 カロリーゼロ 1l" (Weight C)

→ general_nameで完全一致するため、最も高いランクになる

#### 商品B: "りんごジュース 1000ml"
- general_name: "りんごジュース" (Weight A) → 部分一致
- keywords: ["りんごジュース", "1000ml"] (Weight B)
- product_name: "りんごジュース 1000ml" (Weight C)

→ "りんご"のみ一致、スコアは低い

---

## 注意事項

1. **JSON配列の扱い**
   - PostgreSQLのJSONB配列から文字列に変換が必要
   - `jsonb_array_elements_text()` を使用

2. **日本語トークナイザー**
   - `'japanese'` 設定を使用
   - Supabaseではデフォルトで利用可能

3. **パフォーマンス**
   - GINインデックスが必要（既存のsearch_vectorインデックスを活用）
   - 大量データの一括更新は時間がかかる可能性あり

4. **NULL対策**
   - 全てのカラムで `COALESCE()` を使用してNULLエラーを防ぐ

---

## 次のステップ

1. ✅ keywordsカラムの追加（完了）
2. ⏳ 重み付きsearch_vectorの生成SQLをSupabase Dashboardで実行
3. ⏳ トリガーの作成（自動更新用）
4. ⏳ AI分類・Embedding生成の実行
   - `python -m L_product_classification.daily_auto_classifier` で general_name, small_category, keywords を生成
   - `python netsuper_search_app/generate_multi_embeddings.py` で embedding を生成
   - ⚠️ `sync_netsuper_general_names.py` は廃止予定（small_category を生成しないため）
5. ⏳ 検索機能の実装・テスト

---

## Supabaseでの実行方法

Supabase DashboardのSQL Editorで以下を順番に実行:

```sql
-- 1. keywordsカラムの追加（既に実行済みの可能性あり）
ALTER TABLE "Rawdata_NETSUPER_items"
ADD COLUMN IF NOT EXISTS keywords JSONB DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_netsuper_items_keywords
ON "Rawdata_NETSUPER_items" USING gin(keywords);

-- 2. search_vectorの更新関数作成
CREATE OR REPLACE FUNCTION update_netsuper_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('japanese', COALESCE(NEW.general_name, '')), 'A') ||
        setweight(to_tsvector('japanese',
            COALESCE(
                (SELECT string_agg(value::text, ' ')
                 FROM jsonb_array_elements_text(NEW.keywords)),
                ''
            )), 'B') ||
        setweight(to_tsvector('japanese', COALESCE(NEW.product_name, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. トリガーの作成
DROP TRIGGER IF EXISTS netsuper_search_vector_update ON "Rawdata_NETSUPER_items";
CREATE TRIGGER netsuper_search_vector_update
    BEFORE INSERT OR UPDATE OF general_name, keywords, product_name
    ON "Rawdata_NETSUPER_items"
    FOR EACH ROW
    EXECUTE FUNCTION update_netsuper_search_vector();

-- 4. 既存データのsearch_vector更新（時間がかかる可能性あり）
UPDATE "Rawdata_NETSUPER_items"
SET search_vector =
    setweight(to_tsvector('japanese', COALESCE(general_name, '')), 'A') ||
    setweight(to_tsvector('japanese',
        COALESCE(
            (SELECT string_agg(value::text, ' ')
             FROM jsonb_array_elements_text(keywords)),
            ''
        )), 'B') ||
    setweight(to_tsvector('japanese', COALESCE(product_name, '')), 'C')
WHERE product_name IS NOT NULL;
```
