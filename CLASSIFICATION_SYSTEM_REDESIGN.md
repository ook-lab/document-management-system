# 分類システムの再設計

**作成日:** 2025-12-26
**目的:** 商品分類の階層構造を適正化し、1次分類（商品分類）と2次分類（費目分類）を明確に分離

---

## 問題点

### 現在の構造（問題あり）

```
商品名 → general_name → 費目カテゴリ（MASTER_Categories_expense）
例: 「明治おいしい牛乳」 → 「牛乳」 → 「食費」
```

**問題:**
- 商品の性質（物としての分類）と費目（使途・会計分類）が混同されている
- 「食料品」（商品分類）と「食費」（費目）が区別されていない
- 同じ商品でも状況によって費目が変わることに対応できない
  - 例: お菓子は「食費」にも「交際費」（手土産）にもなり得る

---

## 提案する解決策

### 新しい階層構造（3層アーキテクチャ）

```
【Tier 0】商品名の正規化（変更なし）
  商品名 → general_name
  テーブル: MASTER_Product_generalize
  例: 「明治おいしい牛乳 1000ml」 → general_name: "牛乳"

  ↓

【Tier 1】1次分類：商品カテゴリ（NEW）
  general_name → product_category
  テーブル: MASTER_Product_category_mapping (新規作成)
  例: general_name: "牛乳" → product_category: "食料品 > 乳製品"
  性質: 客観的・物理的な分類（物としての性質）

  ↓

【Tier 2】2次分類：費目カテゴリ（修正）
  product_category + purpose + person → expense_category
  テーブル: MASTER_Product_classify (カラム追加)
  例: "食料品" + "日常" + NULL → "食費"
      "食料品" + "ビジネス" + NULL → "交際費"
  性質: 主観的・会計的な分類（使途・目的に基づく）
```

---

## 具体例

### ケース1: 牛乳を買った（日常の買い物）

1. **Tier 0:** 「明治おいしい牛乳 1000ml」 → `general_name: "牛乳"`
2. **Tier 1:** general_name: "牛乳" → `product_category: "食料品 > 乳製品"`
3. **Tier 2:**
   - 商品分類: 食料品
   - 用途: 日常
   - 人: NULL
   - → **費目: 食費**

### ケース2: お菓子を買った（手土産）

1. **Tier 0:** 「ヨックモック シガール」 → `general_name: "クッキー"`
2. **Tier 1:** general_name: "クッキー" → `product_category: "食料品 > 菓子"`
3. **Tier 2:**
   - 商品分類: 食料品
   - 用途: ビジネス/交際
   - 人: NULL
   - → **費目: 交際費**

### ケース3: ティッシュを買った

1. **Tier 0:** 「エリエール ティッシュ 5箱」 → `general_name: "ティッシュ"`
2. **Tier 1:** general_name: "ティッシュ" → `product_category: "日用品 > 消耗品"`
3. **Tier 2:**
   - 商品分類: 日用品
   - 用途: 日常
   - 人: NULL
   - → **費目: 日用品費**

---

## 実装計画

### 1. 新規テーブル作成

#### MASTER_Product_category_mapping（1次分類用）

```sql
CREATE TABLE "MASTER_Product_category_mapping" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  general_name TEXT NOT NULL,                    -- 一般名詞（「牛乳」「クッキー」など）
  product_category_id UUID NOT NULL REFERENCES "MASTER_Categories_product"(id),
  confidence_score FLOAT DEFAULT 1.0,
  source TEXT DEFAULT 'manual',                  -- 'manual', 'gemini', 'auto'
  approval_status TEXT DEFAULT 'approved',       -- 'pending', 'approved', 'rejected'
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(general_name)
);

CREATE INDEX idx_MASTER_Product_category_mapping_general ON "MASTER_Product_category_mapping"(general_name);
CREATE INDEX idx_MASTER_Product_category_mapping_category ON "MASTER_Product_category_mapping"(product_category_id);
CREATE INDEX idx_MASTER_Product_category_mapping_approval ON "MASTER_Product_category_mapping"(approval_status) WHERE approval_status = 'pending';

COMMENT ON TABLE "MASTER_Product_category_mapping" IS '1次分類: 一般名詞→商品カテゴリのマッピング';
```

### 2. 既存テーブルの修正

#### MASTER_Product_classify（2次分類用に拡張）

**変更内容:**
- ✅ `general_name` カラムは**保持**（後方互換性）
- ✅ `product_category_id` カラムを**追加**（新しい分類軸）
- ✅ `purpose_id`, `person` カラムを**追加**（コンテキスト情報）

```sql
-- カラム追加
ALTER TABLE "MASTER_Product_classify" ADD COLUMN IF NOT EXISTS product_category_id UUID REFERENCES "MASTER_Categories_product"(id);
ALTER TABLE "MASTER_Product_classify" ADD COLUMN IF NOT EXISTS purpose_id UUID REFERENCES "MASTER_Categories_purpose"(id);
ALTER TABLE "MASTER_Product_classify" ADD COLUMN IF NOT EXISTS person TEXT;

-- インデックス追加
CREATE INDEX IF NOT EXISTS idx_MASTER_Product_classify_product_category ON "MASTER_Product_classify"(product_category_id);
CREATE INDEX IF NOT EXISTS idx_MASTER_Product_classify_purpose ON "MASTER_Product_classify"(purpose_id);

-- コメント更新
COMMENT ON TABLE "MASTER_Product_classify" IS '2次分類: 商品カテゴリ+用途+人→費目カテゴリのマッピング（general_nameは後方互換性のため保持）';
COMMENT ON COLUMN "MASTER_Product_classify".general_name IS '(非推奨) 後方互換性のため保持。新規レコードはproduct_category_idを使用';
COMMENT ON COLUMN "MASTER_Product_classify".product_category_id IS '商品カテゴリID（1次分類結果）';
COMMENT ON COLUMN "MASTER_Product_classify".purpose_id IS '用途・シチュエーション（日常、ビジネス、旅行など）';
COMMENT ON COLUMN "MASTER_Product_classify".person IS '購入者・使用者（夫、妻、子供など）';
```

---

## データフロー

### 新規レシート処理時

```python
# Tier 0: 商品名正規化
product_name = "明治おいしい牛乳 1000ml"
general_name = get_general_name(product_name)  # → "牛乳"

# Tier 1: 商品カテゴリ分類（NEW）
product_category_id = get_product_category(general_name)  # → "食料品 > 乳製品"

# Tier 2: 費目分類
expense_category_id = get_expense_category(
    product_category_id=product_category_id,
    purpose_id=purpose_id,  # 日常
    person=person           # NULL
)  # → "食費"
```

---

## メリット

### ✅ 明確な階層構造
- **1次分類:** 商品の性質（物理的・客観的）
  - 例: 食料品、日用品、衣類、家電
- **2次分類:** 費目（会計・主観的）
  - 例: 食費、交際費、日用品費

### ✅ 柔軟性の向上
- 同じ商品でも用途によって費目を変更可能
- ビジネス/プライベートの区別が容易
- 将来的な拡張が容易

### ✅ 保守性の向上
- 分類ルールが明確で理解しやすい
- AIによる自動分類の精度向上
- デバッグが容易

### ✅ 後方互換性
- `general_name` を保持することで既存機能が動作
- 段階的な移行が可能

---

## 移行手順

### フェーズ1: テーブル作成（本日実施）
1. `MASTER_Product_category_mapping` テーブル作成
2. `MASTER_Product_classify` カラム追加
3. インデックス・制約の設定

### フェーズ2: 初期データ投入
1. 既存の `general_name` から商品カテゴリを推測
2. `MASTER_Product_category_mapping` に初期データ登録
3. 手動レビュー・修正

### フェーズ3: コード修正
1. 分類ロジックを新しいフローに更新
2. UI画面の更新
3. テスト実施

### フェーズ4: 段階的ロールアウト
1. 新規データは新しいフローで処理
2. 既存データは必要に応じて移行
3. モニタリング・調整

---

## 次のステップ

1. ✅ マイグレーションスクリプトの作成
2. ✅ 初期データの準備（商品カテゴリマスタ）
3. ✅ テーブル作成の実行
4. ⏳ コードの更新

---

**作成者:** Claude Sonnet 4.5
**承認:** 2025-12-26
