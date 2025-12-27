# データベース設定の実行手順

## ⚠️ 重要: 実行順序を守ってください

以下のSQLファイルを **Supabase Dashboard → SQL Editor** で順番に実行してください。

---

## Step 1: keywordsカラムの追加

**ファイル:** `add_keywords_to_netsuper_items.sql`

```sql
-- keywordsカラムの追加
ALTER TABLE "Rawdata_NETSUPER_items"
ADD COLUMN IF NOT EXISTS keywords JSONB DEFAULT '[]'::jsonb;

-- インデックスの作成
CREATE INDEX IF NOT EXISTS idx_netsuper_items_keywords
ON "Rawdata_NETSUPER_items" USING gin(keywords);

-- コメント追加
COMMENT ON COLUMN "Rawdata_NETSUPER_items".keywords IS '商品名から抽出された個別キーワードの配列（検索用）';
```

**実行方法:**
1. Supabase Dashboardにログイン
2. SQL Editorを開く
3. 上記のSQLをコピー&ペースト
4. 「Run」をクリック

---

## Step 2: 重み付きsearch_vectorトリガーの設定

**ファイル:** `create_weighted_search_vector.sql`

このファイルの **全内容** をSupabase SQL Editorで実行してください。

**重み付け:**
- **Weight A（最重要）**: 小分類 + general_name
- **Weight B（重要）**: keywords
- **Weight C（参考）**: product_name

**実行方法:**
1. `create_weighted_search_vector.sql` ファイルを開く
2. 全内容をコピー
3. Supabase Dashboard → SQL Editorにペースト
4. 「Run」をクリック

**処理内容:**
1. トリガー関数の作成（自動的にsearch_vectorを生成）
2. トリガーの作成（INSERT/UPDATE時に自動実行）
3. 既存データのsearch_vector更新（約1,159件）

---

## Step 3: AI分類・Embedding生成の実行

データベース設定が完了したら、以下の手順で商品分類とembedding生成を実行してください。

### 3-1. 既存AI生成データのクリーンアップ（必要な場合）

既存のAI生成データ（general_name, small_category, keywords, embedding）をリセットする場合：

```bash
# 確認のみ（削除しない）
python K_kakeibo/cleanup_generated_data.py --all --dry-run

# 実際に削除
python K_kakeibo/cleanup_generated_data.py --all
```

### 3-2. 商品分類（Gemini 2.5 Flash）

全商品に対して general_name, small_category, keywords を生成：

```bash
python -m L_product_classification.daily_auto_classifier
```

**処理内容:**
- 3段階フォールバック分類システム
  - Tier 1: 辞書lookup（MASTER_Product_generalize）
  - Tier 2: コンテキストlookup（MASTER_Product_classify）
  - Tier 3: Gemini Few-shot推論
- 各商品名から general_name, small_category, keywords を生成
- データベースに保存
- 自動的にsearch_vectorが生成される（トリガーにより）

**コスト:** 約11-12円（Gemini 2.5 Flash使用）

### 3-3. Embedding生成（OpenAI）

全商品に対して text-embedding-3-small で embedding を生成：

```bash
python netsuper_search_app/generate_multi_embeddings.py
```

**処理内容:**
- general_name, small_category, keywords から embedding テキストを生成
- OpenAI text-embedding-3-small (1536次元) で embedding 生成
- データベースに保存

**コスト:** 約5-10円（OpenAI Embedding API使用）

---

## トラブルシューティング

### エラー: "text search configuration 'japanese' does not exist"

→ 修正済みです。現在のSQLファイルは`'simple'`設定を使用しています。

### エラー: "syntax error at or near '#'"

→ マークダウンファイル（.md）ではなく、SQLファイル（.sql）を実行してください。
- ❌ `PLAN_weighted_search_vector.md` - これは説明文書
- ✅ `create_weighted_search_vector.sql` - これを実行

### エラー: "column keywords does not exist"

→ Step 1を先に実行してください。

---

## 検証方法

全て完了したら、以下のSQLで動作確認：

```sql
-- サンプルデータを確認
SELECT
    id,
    product_name,
    general_name,
    keywords,
    search_vector
FROM "Rawdata_NETSUPER_items"
WHERE general_name IS NOT NULL
LIMIT 5;

-- 検索テスト
SELECT
    product_name,
    general_name,
    keywords,
    ts_rank(search_vector, to_tsquery('simple', 'りんご & 黒酢')) AS rank
FROM "Rawdata_NETSUPER_items"
WHERE search_vector @@ to_tsquery('simple', 'りんご & 黒酢')
ORDER BY rank DESC
LIMIT 10;
```

---

## 完了チェックリスト

- [ ] Step 1: keywordsカラムの追加（SQL実行）
- [ ] Step 2: 重み付きsearch_vectorトリガーの設定（SQL実行）
- [ ] Step 3: AI抽出のテスト実行（10件）
- [ ] Step 4: AI抽出の本番実行（全件）
- [ ] 検証: 検索テストの実行

全て完了したら、キーワードベース検索システムの実装は完了です！
