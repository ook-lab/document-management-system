# general_name（一般名詞）機能 実装ガイド

## 概要

商品名を一般名詞化してカテゴリ判定に活用する機能を実装しました。

例：「明治おいしい牛乳」→「牛乳」→「食費」

## データベーススキーマ

### 1. MASTER_Product_generalize（一般化マスタ）

商品名→一般名詞のマッピング

```sql
CREATE TABLE "MASTER_Product_generalize" (
  id UUID PRIMARY KEY,
  raw_keyword TEXT NOT NULL,      -- 元の商品名（例：「明治おいしい牛乳」）
  general_name TEXT NOT NULL,     -- 一般名詞（例：「牛乳」）
  confidence_score FLOAT,
  source TEXT,                    -- 'manual', 'gemini_batch', 'gemini_inference'
  notes TEXT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
);
```

### 2. MASTER_Product_classify（分類マスタ）

一般名詞→費目カテゴリのマッピング

```sql
CREATE TABLE "MASTER_Product_classify" (
  id UUID PRIMARY KEY,
  general_name TEXT NOT NULL,              -- 一般名詞（例：「牛乳」）
  category_id UUID REFERENCES "MASTER_Categories_expense"(id),  -- 費目（例：「食費」）
  source_type TEXT,
  workspace TEXT,
  organization TEXT,
  approval_status TEXT DEFAULT 'pending',
  confidence_score FLOAT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
);
```

### 3. Rawdata_RECEIPT_items

トランザクションテーブルに`general_name`カラムを追加

```sql
ALTER TABLE "Rawdata_RECEIPT_items"
  ADD COLUMN IF NOT EXISTS general_name TEXT;

COMMENT ON COLUMN "Rawdata_RECEIPT_items".general_name IS
  '一般名詞（カテゴリ判定用、例：「明治おいしい牛乳」→「牛乳」）';
```

## 実装手順

### Step 1: データベースマイグレーション

```bash
# 1. Rawdata_RECEIPT_itemsにgeneral_nameカラムを追加
database/migrations/add_general_name_to_receipt_items.sql

# 2. サンプルデータを挿入
database/migrations/insert_sample_product_generalize.sql
```

Supabase SQL Editorで実行してください。

### Step 2: コード変更箇所

#### transaction_processor.py

```python
# __init__メソッドでマスタデータをキャッシュ
self.product_generalize = self._load_product_generalize()

# 一般名詞を取得するメソッド
def _get_general_name(self, product_name: str) -> Optional[str]:
    """商品名から一般名詞を取得"""
    # 完全一致または部分一致で検索
    ...

# _normalize_itemメソッドで一般名詞を追加
return {
    "product_name": product_name,
    "general_name": self._get_general_name(product_name),
    "category_id": None,
    ...
}
```

#### kakeibo_db_handler.py

```python
# _insert_transactionメソッドで一般名詞を保存
data.update({
    "official_name": normalized["product_name"],
    "general_name": normalized.get("general_name"),  # 追加
    ...
})
```

## 使用方法

### 1. マスタデータの登録

#### 手動登録

```sql
INSERT INTO "MASTER_Product_generalize" (raw_keyword, general_name, source)
VALUES
  ('明治おいしい牛乳', '牛乳', 'manual'),
  ('コカコーラ', '炭酸飲料', 'manual');
```

#### 一括登録

サンプルデータには以下が含まれています：
- 乳製品：牛乳、ヨーグルト、チーズ、バター
- 飲料：炭酸飲料、お茶、コーヒー、ジュース
- パン・麺類：パン、インスタント麺、パスタ
- 野菜、肉、魚、調味料、お菓子、日用品など

### 2. カテゴリマッピングの登録

```sql
INSERT INTO "MASTER_Product_classify" (general_name, category_id, source_type)
VALUES
  ('牛乳', (SELECT id FROM "MASTER_Categories_expense" WHERE name = '食費'), 'receipt');
```

### 3. 自動分類

トランザクション処理時に自動で一般名詞が設定されます：

```python
processor = TransactionProcessor()
result = processor.process(
    ocr_result={...},
    file_name="receipt.jpg",
    drive_file_id="xxx",
    model_name="gemini-2.5-flash"
)
# → Rawdata_RECEIPT_itemsにgeneral_nameが保存される
```

### 4. カテゴリ自動判定

`review_ui.py`の`auto_classify_transaction()`関数で、`general_name`を使った自動判定が可能：

```python
result = auto_classify_transaction(
    db=db,
    shop_name="スーパーA",
    product_name="明治おいしい牛乳",
    general_name="牛乳"  # ← これを使って分類
)
# → {"category": "食費", "person": "家族", "purpose": "日常"}
```

## データフロー

```
1. OCR読み取り
   「明治おいしい牛乳 ¥200」

2. 正規化（transaction_processor._normalize_item）
   product_name: "明治おいしい牛乳"
   general_name: "牛乳"  ← MASTER_Product_generalizeから取得

3. DB保存（Rawdata_RECEIPT_items）
   product_name: "明治おいしい牛乳"
   general_name: "牛乳"
   category_id: NULL  ← まだ分類されていない

4. カテゴリ判定（オプション）
   general_name: "牛乳" → MASTER_Product_classify → category_id: "食費"
```

## テスト

```bash
cd K_kakeibo
python test_general_name.py
```

テスト内容：
1. 一般名詞の取得テスト
2. 商品正規化時のgeneral_name設定テスト

## 今後の拡張

### AIによる自動クラスタリング

`L_product_classification/`ディレクトリに、Geminiを使った自動クラスタリング機能があります：

```bash
python L_product_classification/daily_auto_classifier.py
```

これにより、新しい商品を自動的に一般名詞化できます。

### 集計クエリ例

```sql
-- 一般名詞ごとの購入回数・金額
SELECT
  general_name,
  COUNT(*) as count,
  SUM(std_amount) as total_amount
FROM "Rawdata_RECEIPT_items"
WHERE general_name IS NOT NULL
GROUP BY general_name
ORDER BY total_amount DESC;
```

## トラブルシューティング

### Q1: general_nameがNULLになる

**A**: `MASTER_Product_generalize`にデータが登録されていない可能性があります。

```sql
SELECT * FROM "MASTER_Product_generalize" WHERE raw_keyword ILIKE '%商品名%';
```

### Q2: 部分一致が効かない

**A**: `_get_general_name()`メソッドは、キーワードが商品名に含まれている場合に部分一致します。

例：
- OK: 「明治おいしい牛乳」に「牛乳」が含まれる
- NG: 「牛乳」に「明治おいしい牛乳」が含まれない

長いキーワードは完全一致のみ対応です。

### Q3: カテゴリが自動設定されない

**A**: 現在、カテゴリ自動設定は手動トリガーです。自動化するには：

1. `MASTER_Product_classify`にマッピングを登録
2. `transaction_processor.py`で自動的にcategory_idを設定するロジックを追加

## まとめ

- ✅ 商品名→一般名詞のマッピング機能を実装
- ✅ トランザクション処理時に自動で一般名詞を設定
- ✅ サンプルデータ（150+商品）を用意
- ✅ カテゴリ自動判定に活用可能
- ✅ テストスクリプトを作成

これにより、「明治おいしい牛乳」「森永のおいしい牛乳」「雪印メグミルク牛乳」などを「牛乳」としてまとめて集計・分析できるようになりました！
