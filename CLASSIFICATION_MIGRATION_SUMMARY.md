# 分類システム改善 - 実装完了サマリー

**実施日:** 2025-12-26
**ステータス:** マイグレーションスクリプト作成完了

---

## 実施した作業

### ✅ タスク1: 混在データのクリーンアップ

#### 問題
- `Rawdata_NETSUPER_items` に146件のレシートデータが混入
- `sync_receipt_products_to_master.py` が誤ってレシートデータをネットスーパーテーブルに挿入

#### 実施内容
1. **混入データの削除:** 146件のレシート由来データを削除
2. **スクリプト削除:** `sync_receipt_products_to_master.py` を削除
3. **検証:** クリーンアップ後、レシート由来データが0件であることを確認

#### 結果
```
削除前: 1,159件（うちレシート由来 146件 = 12.6%）
削除後: 1,013件（レシート由来 0件）
```

---

### ✅ タスク2: 分類システムの適正化

#### 問題
- 商品の性質（物としての分類）と費目（使途・会計分類）が混同
- 「食料品」（商品カテゴリ）と「食費」（費目）の区別がない
- 同じ商品でも状況によって費目が変わることに対応できない

#### 設計した解決策

**3層アーキテクチャ:**

```
【Tier 0】商品名の正規化（既存）
  商品名 → general_name
  テーブル: MASTER_Product_generalize
  例: 「明治おいしい牛乳 1000ml」 → "牛乳"

  ↓

【Tier 1】1次分類：商品カテゴリ（NEW）
  general_name → product_category
  テーブル: MASTER_Product_category_mapping ← 新規作成
  例: "牛乳" → "食料品"
  性質: 客観的・物理的

  ↓

【Tier 2】2次分類：費目カテゴリ（修正）
  product_category + purpose + person → expense_category
  テーブル: MASTER_Product_classify ← カラム追加
  例: "食料品" + "日常" + NULL → "食費"
       "食料品" + "ビジネス" + NULL → "交際費"
  性質: 主観的・会計的
```

#### 作成したファイル

1. **設計ドキュメント**
   - `CLASSIFICATION_SYSTEM_REDESIGN.md`
   - 分類システムの全体設計と移行計画

2. **マイグレーションスクリプト**
   - `database/migrations/add_two_tier_classification_system.sql`
   - 新規テーブル作成と既存テーブル拡張

3. **初期データ投入スクリプト**
   - `database/migrations/insert_sample_product_category_mappings.sql`
   - サンプル商品カテゴリマッピング（約70件）

---

## 次のステップ

### 1. マイグレーションの実行

#### ステップ1: テーブル作成
```sql
-- Supabase SQL Editor で実行
-- ファイル: database/migrations/add_two_tier_classification_system.sql
```

**実行内容:**
- `MASTER_Product_category_mapping` テーブル作成
- `MASTER_Product_classify` テーブルにカラム追加
  - `product_category_id`
  - `purpose_id`
  - `person`

#### ステップ2: 初期データ投入
```sql
-- Supabase SQL Editor で実行
-- ファイル: database/migrations/insert_sample_product_category_mappings.sql
```

**実行内容:**
- 商品カテゴリマスタの確認・作成（食料品、飲料、日用品）
- サンプル商品カテゴリマッピング投入（約70件）
  - 食料品: 牛乳、パン、肉、魚、野菜など
  - 飲料: ジュース、ビール、ワインなど
  - 日用品: ティッシュ、洗剤、マスクなど

### 2. コードの更新（後日実施）

更新が必要なファイル:
- `L_product_classification/` - 商品分類処理
- `K_kakeibo/transaction_processor.py` - レシート処理
- 家計簿UI

### 3. テストの実施

1. 新しい商品の分類テスト
2. 既存データとの互換性確認
3. UI動作確認

---

## 技術的な詳細

### 新規テーブル: MASTER_Product_category_mapping

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | UUID | 主キー |
| general_name | TEXT | 一般名詞（「牛乳」など）|
| product_category_id | UUID | 商品カテゴリID |
| confidence_score | FLOAT | 分類の信頼度（0.0-1.0）|
| source | TEXT | 情報源（manual, gemini, auto）|
| approval_status | TEXT | 承認状態 |
| notes | TEXT | メモ |
| created_at | TIMESTAMPTZ | 作成日時 |
| updated_at | TIMESTAMPTZ | 更新日時 |

**制約:**
- `general_name` は UNIQUE
- `product_category_id` は `MASTER_Categories_product` への外部キー

### 拡張テーブル: MASTER_Product_classify

**追加カラム:**
- `product_category_id` - 商品カテゴリID（1次分類結果）
- `purpose_id` - 用途・シチュエーション
- `person` - 購入者・使用者

**重要:** `general_name` カラムは後方互換性のため保持。新規レコードは `product_category_id` を使用すること。

---

## メリット

### ✅ 明確な階層構造
- 1次分類: 商品の性質（食料品、日用品など）
- 2次分類: 費目（食費、交際費など）

### ✅ 柔軟性の向上
- 同じ商品でも用途によって費目を変更可能
- 例: お菓子 → 日常なら「食費」、手土産なら「交際費」

### ✅ 保守性の向上
- 分類ルールが明確
- AIによる自動分類の精度向上

### ✅ 後方互換性
- 既存の `general_name` ベースの分類も継続動作
- 段階的な移行が可能

---

## 実行確認事項

マイグレーション実行前のチェックリスト:

- [ ] バックアップの取得
- [ ] `MASTER_Categories_product` テーブルが存在することを確認
- [ ] `MASTER_Categories_purpose` テーブルが存在することを確認
- [ ] Supabase SQL Editor へのアクセス確認

マイグレーション実行後の確認:

- [ ] `MASTER_Product_category_mapping` テーブルが作成されたか
- [ ] `MASTER_Product_classify` に新しいカラムが追加されたか
- [ ] サンプルデータが投入されたか（約70件）
- [ ] インデックスが作成されたか
- [ ] RLSポリシーが設定されたか

---

**作成者:** Claude Sonnet 4.5
**レビュー:** 2025-12-26
**承認:** ユーザー承認待ち
