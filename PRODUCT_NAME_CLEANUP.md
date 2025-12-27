# product_name_normalized 削除・整理ガイド

## 概要

`Rawdata_NETSUPER_items` と `Rawdata_FLYER_items` テーブルの商品名カラムを整理しました。

### Before（整理前）
```
product_name            → サイト表記の商品名
product_name_normalized → 正規化された商品名（空白処理のみ）
general_name            → 一般名詞（未実装）
```

### After（整理後）
```
product_name    → サイト表記の商品名（そのまま保存）
general_name    → 一般名詞（分析・集計用）
```

**削除理由**:
- `product_name_normalized` は単なる空白正規化で有用性が低い
- 検索は `search_vector`（全文検索）と `embedding`（ベクトル検索）で対応
- `general_name` で一般名詞化した方が分析に有用

---

## 変更内容

### 1. データベーススキーマ

#### マイグレーションファイル
```sql
-- database/migrations/cleanup_product_name_normalized.sql

-- Rawdata_NETSUPER_items から product_name_normalized を削除
ALTER TABLE "Rawdata_NETSUPER_items"
  DROP COLUMN IF EXISTS product_name_normalized;

-- Rawdata_FLYER_items から product_name_normalized を削除
ALTER TABLE "Rawdata_FLYER_items"
  DROP COLUMN IF EXISTS product_name_normalized;
```

### 2. コード変更

#### 修正したファイル（8ファイル）

1. **B_ingestion/common/base_product_ingestion.py**
   - `product_name_normalized` の生成処理を削除
   - `product_name` のみを保存

2. **B_ingestion/tokubai/flyer_processor.py**
   - `product_name_normalized` の生成処理を削除

3. **sync_receipt_products_to_master.py**
   - `product_name_normalized` のDB挿入を削除

4. **K_kakeibo/review_ui.py**
   - UI表示から `product_name_normalized` カラムを削除
   - SELECTクエリから削除

5. **netsuper_search_app/inspect_embedding_content.py**
   - `product_name_normalized` の参照を削除

6. **netsuper_search_app/reverse_engineer_embedding.py**
   - `product_name_normalized` の参照を削除

7. **L_product_classification/gemini_batch_clustering.py**
   - SELECTクエリから `product_name_normalized` を削除

8. **process_queued_flyers.py**
   - `product_name_normalized` の生成・保存処理を削除

---

## 実装手順

### Step 1: データベースマイグレーション

Supabase SQL Editorで以下を実行：

```bash
database/migrations/cleanup_product_name_normalized.sql
```

### Step 2: 動作確認

```sql
-- カラムが削除されたことを確認
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name IN ('Rawdata_NETSUPER_items', 'Rawdata_FLYER_items')
AND column_name LIKE '%product_name%'
ORDER BY table_name, ordinal_position;
```

期待される結果：
```
Rawdata_NETSUPER_items | product_name  | character varying
Rawdata_NETSUPER_items | general_name  | text
Rawdata_FLYER_items    | product_name  | character varying
```

---

## 新しい商品名の構造

### Rawdata_NETSUPER_items

```
product_name  → サイト表記（例：「明治おいしい牛乳 1000ml」）
general_name  → 一般名詞（例：「牛乳」）- MASTER_Product_generalizeから取得
```

### Rawdata_RECEIPT_items

```
ocr_raw_text  → OCR生データ（例：「ｷﾞｭｳﾆｭｳ 外8」）
product_name  → 正規化後の名前（例：「明治おいしい牛乳」）
general_name  → 一般名詞（例：「牛乳」）
```

### Rawdata_FLYER_items

```
product_name  → チラシ記載の商品名（例：「国産豚肉 特売」）
```

---

## 検索機能について

`product_name_normalized` 削除後も、以下の検索機能は影響を受けません：

### 1. 全文検索（PostgreSQL）

```sql
-- search_vector を使った全文検索
SELECT *
FROM "Rawdata_NETSUPER_items"
WHERE search_vector @@ to_tsquery('japanese', '牛乳');
```

### 2. ベクトル検索（OpenAI Embedding）

```sql
-- embedding を使ったセマンティック検索
SELECT *
FROM "Rawdata_NETSUPER_items"
ORDER BY embedding <-> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

### 3. 一般名詞検索

```sql
-- general_name を使った集計
SELECT
  general_name,
  COUNT(*) as 商品数,
  AVG(current_price_tax_included) as 平均価格
FROM "Rawdata_NETSUPER_items"
WHERE general_name IS NOT NULL
GROUP BY general_name
ORDER BY 商品数 DESC;
```

---

## 共通関数の活用

`Rawdata_RECEIPT_items` と `Rawdata_NETSUPER_items` で商品名構造が統一されたため、以下の共通関数が使用可能：

### general_name 取得関数

```python
# K_kakeibo/transaction_processor.py

class TransactionProcessor:
    def _get_general_name(self, product_name: str) -> Optional[str]:
        """
        商品名から一般名詞を取得

        MASTER_Product_generalize テーブルから検索
        完全一致 → 部分一致の順で検索
        """
        # 完全一致
        general_name = self.product_generalize.get(product_name.lower())
        if general_name:
            return general_name

        # 部分一致
        for keyword, gen_name in self.product_generalize.items():
            if keyword in product_name.lower():
                return gen_name

        return None
```

この関数は `Rawdata_RECEIPT_items` と `Rawdata_NETSUPER_items` の両方で使用できます。

---

## ✅ 完了: general_name の自動設定

`Rawdata_NETSUPER_items` の既存商品に `general_name`, `small_category`, `keywords` を一括設定するシステムを構築しました。

### ⚠️ 新システム: 3段階フォールバック分類

**現在の推奨スクリプト:**

```bash
# 1. 既存AI生成データのクリーンアップ（必要な場合）
python K_kakeibo/cleanup_generated_data.py --all

# 2. 全商品を分類（general_name, small_category, keywords を生成）
python -m L_product_classification.daily_auto_classifier

# 3. Embedding生成
python netsuper_search_app/generate_multi_embeddings.py
```

**処理内容:**
- Tier 1: 辞書lookup（MASTER_Product_generalize）
- Tier 2: コンテキストlookup（MASTER_Product_classify）
- Tier 3: Gemini Few-shot推論

---

**⚠️ 廃止予定スクリプト:**

`K_kakeibo/sync_netsuper_general_names.py` は general_name と keywords のみ生成するため廃止予定です。

```bash
# 【使用非推奨】旧スクリプト
./venv/bin/python K_kakeibo/sync_netsuper_general_names.py         # 全件処理
./venv/bin/python K_kakeibo/sync_netsuper_general_names.py --limit=100  # 件数指定
./venv/bin/python K_kakeibo/sync_netsuper_general_names.py --dry-run    # 確認のみ
```

**過去の実行結果（2025-12-26）:**
- 総商品数: 1,159件
- general_name設定済: 660件 (57%)
- general_name未設定: 499件 (43%)

**現在のシステム:**
- 全商品に general_name, small_category, keywords を自動生成
- 辞書ヒット時も small_category と keywords は Gemini で生成
- UI（https://netsuper-classification.streamlit.app/）で手動修正可能
- 修正内容は AI学習に反映

**設定例:**
```
明治おいしい牛乳 1000ml                        → 牛乳
明治 ブルガリアヨーグルトLB81 プレーン 180g     → ヨーグルト
クラフト 切れてるチーズ 134g                    → チーズ
カゴメ トマトジュース 食塩無添加 200ml          → ジュース
```

### 2. AI自動クラスタリング

新しい商品を自動的に一般名詞化：

```bash
python L_product_classification/daily_auto_classifier.py
```

---

## トラブルシューティング

### Q1: 既存データの `product_name_normalized` はどうなる？

**A**: マイグレーション実行時にカラムごと削除されます。データは失われますが、`product_name` で代替可能です。

### Q2: 検索が遅くなる？

**A**: `search_vector`（全文検索インデックス）と `embedding`（ベクトル検索）があるため、影響ありません。

### Q3: 商品名の正規化が必要な場合は？

**A**: 検索時にクエリ側で正規化してください：

```sql
-- 検索クエリで正規化
SELECT * FROM "Rawdata_NETSUPER_items"
WHERE LOWER(REPLACE(product_name, '　', ' ')) LIKE '%牛乳%';
```

または `general_name` を活用：

```sql
-- 一般名詞で検索
SELECT * FROM "Rawdata_NETSUPER_items"
WHERE general_name = '牛乳';
```

---

## まとめ

✅ `product_name_normalized` を削除してスキーマをシンプル化
✅ `product_name`（サイト表記）+ `general_name`（一般名詞）の2層構造に統一
✅ `Rawdata_RECEIPT_items` と `Rawdata_NETSUPER_items` で共通関数が使用可能
✅ 検索機能は `search_vector` と `embedding` で継続サポート
✅ 8ファイルのコードを修正済み

これにより、データ管理がシンプルになり、分析がしやすくなりました！
