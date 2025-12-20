# 家計簿テーブル3分割マイグレーション実装計画書

## 📋 概要

**目的**: 現在の `60_rd_transactions` テーブルを、情報の「蒸留プロセス」に基づいて3層構造に分割し、データの正規化と処理フローの明確化を実現する。

**コンセプト**: 情報の「蒸留」プロセス
1. **親 (Receipts)**: 「管理情報」の正規化 - レシート1枚の事実と管理属性
2. **子 (Transactions)**: 「テキスト」の正規化 - OCR読み取り結果の文字修正
3. **孫 (Standardized)**: 「意味・数値」の正規化 - 家計簿としての分類と最終金額

---

## 🔍 現状分析

### 現在の `60_rd_transactions` テーブル構造

```
現在のレコード数: 26件
テーブル名: 60_rd_transactions (旧: money_transactions)
```

**カラム一覧** (27カラム):

| カテゴリ | カラム名 | 型 | 説明 |
|---------|---------|-----|------|
| **基本** | id | UUID | PK |
| | transaction_date | DATE | 購入日 |
| | shop_name | TEXT | 店名 |
| **商品情報** | product_name | TEXT | 商品名 |
| | item_name | TEXT | 物品名 |
| | official_name | TEXT | 正式名称 |
| | quantity | INTEGER | 数量 |
| | unit_price | INTEGER | 単価 |
| | total_amount | INTEGER | 合計金額 |
| **税金** | tax_rate | INTEGER | 税率 (8 or 10) |
| | tax_amount | INTEGER | 税額 |
| | tax_included_amount | INTEGER | 税込金額 |
| | needs_tax_review | BOOLEAN | 税額要確認 |
| **分類** | category_id | UUID | カテゴリID (FK) |
| | situation_id | UUID | シチュエーションID (FK) |
| | major_category | TEXT | 大分類 |
| | minor_category | TEXT | 小分類 |
| | person | TEXT | 支払担当者 |
| | purpose | TEXT | 購入目的 |
| **ファイル管理** | image_path | TEXT | 画像パス |
| | drive_file_id | TEXT | Google Drive ID |
| | ocr_model | TEXT | 使用OCRモデル |
| | source_folder | TEXT | ソースフォルダ |
| **その他** | notes | TEXT | メモ |
| | is_verified | BOOLEAN | 確認済み |
| | created_at | TIMESTAMP | 作成日時 |
| | updated_at | TIMESTAMP | 更新日時 |

### 現在の問題点

1. **責務の混在**: 1つのテーブルに「管理情報」「テキスト情報」「分析情報」が混在
2. **OCR原文の喪失**: 修正前のOCR結果が保存されていない（トレーサビリティの欠如）
3. **レシート単位の情報欠如**: レシートの合計金額などの「枠」情報が保存されていない
4. **計算ロジックの不透明性**: 税額計算の根拠が記録されていない
5. **重複データ**: 同一レシートの複数明細に同じ管理情報（image_path, drive_file_idなど）が重複

### 依存コード

**データ書き込み**:
- `K_kakeibo/transaction_processor.py` - OCR結果をDBに登録

**データ読み取り**:
- `K_kakeibo/review_ui.py` - レビューUI
- 集計ビュー: `60_ag_daily_summary`, `60_ag_monthly_summary`

---

## 🎯 目標設計

### 1. 親テーブル: `60_rd_receipts` (レシート管理台帳)

**役割**: レシート1枚単位の「管理属性」と「正解データ」を保持

```sql
CREATE TABLE "60_rd_receipts" (
    -- ID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- レシート基本情報（修正後の正解）
    transaction_date DATE NOT NULL,
    shop_name TEXT NOT NULL,
    total_amount_check INTEGER NOT NULL,  -- レシート印字の合計金額（検算用）
    subtotal_amount INTEGER,              -- 小計（割引計算の基準）

    -- ファイル管理
    image_path TEXT,
    drive_file_id TEXT,
    source_folder TEXT,                   -- INBOX_EASY / INBOX_HARD

    -- OCR処理情報
    ocr_model TEXT,                       -- gemini-2.5-flash / gemini-2.5-flash-lite

    -- 分類・管理
    person TEXT,                          -- 支払担当者（夫、妻、会社など）
    workspace TEXT DEFAULT 'household',   -- マルチテナント用

    -- 状態管理
    is_verified BOOLEAN DEFAULT FALSE,    -- 人間による確認完了
    notes TEXT,                           -- レシート全体に対するメモ

    -- タイムスタンプ
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックス
CREATE INDEX idx_60_rd_receipts_date ON "60_rd_receipts"(transaction_date DESC);
CREATE INDEX idx_60_rd_receipts_shop ON "60_rd_receipts" USING gin(shop_name gin_trgm_ops);
CREATE INDEX idx_60_rd_receipts_drive_id ON "60_rd_receipts"(drive_file_id);
CREATE INDEX idx_60_rd_receipts_unverified ON "60_rd_receipts"(is_verified) WHERE is_verified = FALSE;
```

### 2. 子テーブル: `60_rd_transactions` (OCRテキスト正規化)

**役割**: OCRの読み取り結果と、人間が読める文字への修正を保持

```sql
CREATE TABLE "60_rd_transactions" (
    -- ID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id UUID NOT NULL REFERENCES "60_rd_receipts"(id) ON DELETE CASCADE,

    -- 行メタ情報
    line_number INTEGER NOT NULL,         -- レシート内の行番号（文脈解析用）
    line_type TEXT NOT NULL,              -- ITEM, DISCOUNT, SUB_TOTAL, TAX, etc.

    -- OCR原文（証拠保全）
    ocr_raw_text TEXT,                    -- AIが見たままの文字列
    ocr_confidence DECIMAL(5,4),          -- AIの読み取り自信度 (0.0000-1.0000)

    -- テキスト正規化結果（「4乳」→「牛乳」）
    product_name TEXT NOT NULL,           -- 正規化後の商品名
    item_name TEXT,                       -- 補足名称・型番
    unit_price INTEGER,                   -- 正規化後の単価
    quantity INTEGER DEFAULT 1,           -- 正規化後の数量

    -- 記号・マーク
    marks_text TEXT,                      -- 税マーク等（「※」「軽」など）
    discount_text TEXT,                   -- 割引記載（「2割引」「半額」など）

    -- タイムスタンプ
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 複合ユニーク制約
    UNIQUE(receipt_id, line_number)
);

-- インデックス
CREATE INDEX idx_60_rd_transactions_receipt ON "60_rd_transactions"(receipt_id);
CREATE INDEX idx_60_rd_transactions_line ON "60_rd_transactions"(receipt_id, line_number);
CREATE INDEX idx_60_rd_transactions_type ON "60_rd_transactions"(line_type);
CREATE INDEX idx_60_rd_transactions_low_confidence
    ON "60_rd_transactions"(ocr_confidence) WHERE ocr_confidence < 0.8;
```

### 3. 孫テーブル: `60_rd_standardized_items` (家計簿・情報正規化)

**役割**: 家計簿としての意味・分類・最終金額を保持（集計用）

```sql
CREATE TABLE "60_rd_standardized_items" (
    -- ID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES "60_rd_transactions"(id) ON DELETE CASCADE,
    receipt_id UUID NOT NULL REFERENCES "60_rd_receipts"(id) ON DELETE CASCADE,  -- 冗長化（JOIN削減）

    -- 正規化された商品情報
    official_name TEXT,                   -- マスタ辞書から引いた正式名称

    -- 家計簿分類
    category_id UUID REFERENCES "60_ms_categories"(id),     -- 費目（食費、日用品など）
    situation_id UUID REFERENCES "60_ms_situations"(id),    -- シチュエーション（日常、旅行など）
    major_category TEXT,                  -- 大分類（自由記入）
    minor_category TEXT,                  -- 小分類（自由記入）
    purpose TEXT,                         -- 購入目的（より詳細なタグ）
    person TEXT,                          -- 使用者（誰が使うか）

    -- 税計算結果
    tax_rate INTEGER NOT NULL,            -- 適用税率 (8 or 10)
    std_unit_price INTEGER,               -- 割引適用後の実質単価（税込）
    std_amount INTEGER NOT NULL,          -- 最終支払金額（税込） ← これをSUMすれば家計簿
    tax_amount INTEGER,                   -- 内税額

    -- 計算ロジックのトレーサビリティ
    calc_logic_log TEXT,                  -- 「3行目の20円引を適用」「外税計算」などの根拠
    needs_review BOOLEAN DEFAULT FALSE,   -- 手動確認が必要

    -- メタ情報
    notes TEXT,                           -- 明細ごとのメモ

    -- タイムスタンプ
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックス
CREATE INDEX idx_60_rd_std_transaction ON "60_rd_standardized_items"(transaction_id);
CREATE INDEX idx_60_rd_std_receipt ON "60_rd_standardized_items"(receipt_id);
CREATE INDEX idx_60_rd_std_category ON "60_rd_standardized_items"(category_id);
CREATE INDEX idx_60_rd_std_situation ON "60_rd_standardized_items"(situation_id);
CREATE INDEX idx_60_rd_std_tax_rate ON "60_rd_standardized_items"(tax_rate);
CREATE INDEX idx_60_rd_std_needs_review ON "60_rd_standardized_items"(needs_review) WHERE needs_review = TRUE;
```

---

## 🔄 データマッピング

### 現在のカラム → 新テーブルへの配置

| 現在のカラム | 移行先テーブル | 新カラム名 | 備考 |
|------------|--------------|-----------|------|
| id | ❌ 削除 | - | 新しいIDを生成 |
| transaction_date | 親 Receipts | transaction_date | レシート単位に集約 |
| shop_name | 親 Receipts | shop_name | レシート単位に集約 |
| product_name | 子 Transactions | product_name | OCR修正後のテキスト |
| item_name | 子 Transactions | item_name | |
| official_name | 孫 Standardized | official_name | |
| quantity | 子 Transactions | quantity | |
| unit_price | 子 Transactions | unit_price | |
| total_amount | 孫 Standardized | std_amount | 最終金額 |
| tax_rate | 孫 Standardized | tax_rate | |
| tax_amount | 孫 Standardized | tax_amount | |
| tax_included_amount | ❌ 削除 | - | std_amountに統合 |
| needs_tax_review | 孫 Standardized | needs_review | |
| category_id | 孫 Standardized | category_id | |
| situation_id | 孫 Standardized | situation_id | |
| major_category | 孫 Standardized | major_category | |
| minor_category | 孫 Standardized | minor_category | |
| person | 親 Receipts + 孫 | person | 支払者は親、使用者は孫 |
| purpose | 孫 Standardized | purpose | |
| image_path | 親 Receipts | image_path | レシート単位に集約 |
| drive_file_id | 親 Receipts | drive_file_id | レシート単位に集約 |
| ocr_model | 親 Receipts | ocr_model | レシート単位に集約 |
| source_folder | 親 Receipts | source_folder | レシート単位に集約 |
| notes | 親 Receipts + 孫 | notes | レシート全体と明細ごと |
| is_verified | 親 Receipts | is_verified | レシート単位に集約 |
| created_at | 全テーブル | created_at | |
| updated_at | 全テーブル | updated_at | |

**新規追加カラム**:
- 子 Transactions: `line_number`, `line_type`, `ocr_raw_text`, `ocr_confidence`, `marks_text`, `discount_text`
- 孫 Standardized: `calc_logic_log`, `std_unit_price`
- 親 Receipts: `total_amount_check`, `subtotal_amount`, `workspace`

---

## ⚠️ マイグレーションの課題と対応

### 課題1: レシート単位の情報が欠落している

**問題**: 現在のデータには「レシート単位のID」が存在しない

**対応策**:
1. `drive_file_id` をレシートIDの代理キーとして使用
2. 同じ `drive_file_id` + `transaction_date` + `shop_name` の組み合わせで1つのレシートとみなす
3. 欠落データは NULL または デフォルト値で補完:
   - `total_amount_check`: 同一レシートの `total_amount` の合計値
   - `subtotal_amount`: NULL
   - `workspace`: 'household'

### 課題2: OCR原文が存在しない

**問題**: 既存データには `ocr_raw_text` が保存されていない

**対応策**:
1. 既存データの `ocr_raw_text` は `product_name` をコピー（修正後と同じ）
2. `ocr_confidence`: NULL（未記録）
3. 今後の新規データでは必ず保存する

### 課題3: 行番号・行タイプが存在しない

**問題**: レシート内の行順序や行の種類が記録されていない

**対応策**:
1. 既存データの `line_number`: 連番を自動採番 (1, 2, 3, ...)
2. 既存データの `line_type`: すべて 'ITEM' とする
3. 今後の新規データでは OCR 時に判定して保存

### 課題4: 税額計算ロジックが記録されていない

**問題**: `calc_logic_log` に記録する情報が存在しない

**対応策**:
1. 既存データの `calc_logic_log`: NULL または 'Migrated from old schema'
2. 今後の新規データでは計算ロジックを記録

---

## 🚀 実装手順

### フェーズ1: スキーマ作成（データ影響なし）

**目的**: 新しい3テーブルを作成（既存テーブルは維持）

**実施内容**:
1. 新テーブル作成SQL実行:
   - `60_rd_receipts`
   - `60_rd_transactions` (新構造)
   - `60_rd_standardized_items`

2. インデックス・制約の作成

**SQLファイル**: `kakeibo_3table_split_01_create_tables.sql`

**リスク**: なし（新規テーブル作成のみ）

---

### フェーズ2: データ移行（既存データを新テーブルにコピー）

**目的**: 現在の `60_rd_transactions` のデータを新3テーブルに変換・移行

**実施内容**:

#### ステップ2-1: 親テーブルへのデータ移行

```sql
-- レシート単位にグループ化して親テーブルに挿入
INSERT INTO "60_rd_receipts" (
    transaction_date,
    shop_name,
    total_amount_check,
    image_path,
    drive_file_id,
    source_folder,
    ocr_model,
    person,
    is_verified,
    notes,
    created_at
)
SELECT
    transaction_date,
    shop_name,
    SUM(total_amount) AS total_amount_check,
    MAX(image_path) AS image_path,          -- 同一レシート内で同じはず
    drive_file_id,
    MAX(source_folder) AS source_folder,
    MAX(ocr_model) AS ocr_model,
    MAX(person) AS person,
    BOOL_AND(is_verified) AS is_verified,   -- 全明細が確認済みの場合のみTRUE
    MAX(notes) AS notes,
    MIN(created_at) AS created_at
FROM "60_rd_transactions_OLD"
GROUP BY drive_file_id, transaction_date, shop_name;
```

#### ステップ2-2: 子テーブルへのデータ移行

```sql
-- 旧トランザクションデータを子テーブルに挿入
INSERT INTO "60_rd_transactions" (
    receipt_id,
    line_number,
    line_type,
    ocr_raw_text,
    product_name,
    item_name,
    unit_price,
    quantity,
    created_at
)
SELECT
    r.id AS receipt_id,
    ROW_NUMBER() OVER (PARTITION BY r.id ORDER BY t.created_at) AS line_number,
    'ITEM' AS line_type,
    t.product_name AS ocr_raw_text,         -- OCR原文がないので product_name をコピー
    t.product_name,
    t.item_name,
    t.unit_price,
    t.quantity,
    t.created_at
FROM "60_rd_transactions_OLD" t
INNER JOIN "60_rd_receipts" r
    ON r.drive_file_id = t.drive_file_id
    AND r.transaction_date = t.transaction_date
    AND r.shop_name = t.shop_name;
```

#### ステップ2-3: 孫テーブルへのデータ移行

```sql
-- 正規化された家計簿データを孫テーブルに挿入
INSERT INTO "60_rd_standardized_items" (
    transaction_id,
    receipt_id,
    official_name,
    category_id,
    situation_id,
    major_category,
    minor_category,
    purpose,
    person,
    tax_rate,
    std_amount,
    tax_amount,
    calc_logic_log,
    needs_review,
    notes,
    created_at
)
SELECT
    tr.id AS transaction_id,
    tr.receipt_id,
    t.official_name,
    t.category_id,
    t.situation_id,
    t.major_category,
    t.minor_category,
    t.purpose,
    t.person,
    COALESCE(t.tax_rate, 10) AS tax_rate,  -- デフォルト10%
    t.total_amount AS std_amount,
    t.tax_amount,
    'Migrated from old schema' AS calc_logic_log,
    t.needs_tax_review AS needs_review,
    t.notes,
    t.created_at
FROM "60_rd_transactions_OLD" t
INNER JOIN "60_rd_receipts" r
    ON r.drive_file_id = t.drive_file_id
    AND r.transaction_date = t.transaction_date
    AND r.shop_name = t.shop_name
INNER JOIN "60_rd_transactions" tr
    ON tr.receipt_id = r.id
    AND tr.product_name = t.product_name
    AND tr.created_at = t.created_at;
```

**SQLファイル**: `kakeibo_3table_split_02_migrate_data.sql`

**リスク**: 中（データ変換ロジックにバグがある可能性）

**対策**:
- 移行前にデータ件数を記録
- 移行後に件数が一致することを確認
- サンプルデータを目視確認

---

### フェーズ3: データ検証

**目的**: 移行されたデータが正しいことを確認

**検証項目**:

1. **件数チェック**:
   ```sql
   -- 親テーブル: レシート数（drive_file_idのユニーク数と一致すること）
   SELECT COUNT(*) FROM "60_rd_receipts";

   -- 子テーブル: 旧トランザクション数と一致すること
   SELECT COUNT(*) FROM "60_rd_transactions";

   -- 孫テーブル: 旧トランザクション数と一致すること
   SELECT COUNT(*) FROM "60_rd_standardized_items";
   ```

2. **金額合計チェック**:
   ```sql
   -- 旧テーブルの合計
   SELECT SUM(total_amount) FROM "60_rd_transactions_OLD";

   -- 新テーブルの合計（孫テーブル）
   SELECT SUM(std_amount) FROM "60_rd_standardized_items";
   ```

3. **外部キー整合性チェック**:
   ```sql
   -- 孤立レコードがないことを確認
   SELECT COUNT(*) FROM "60_rd_transactions" t
   LEFT JOIN "60_rd_receipts" r ON t.receipt_id = r.id
   WHERE r.id IS NULL;  -- 0件であること

   SELECT COUNT(*) FROM "60_rd_standardized_items" s
   LEFT JOIN "60_rd_transactions" t ON s.transaction_id = t.id
   WHERE t.id IS NULL;  -- 0件であること
   ```

4. **サンプルデータ目視確認**:
   ```sql
   -- レシート単位でデータが正しく分割されているか確認
   SELECT
       r.transaction_date,
       r.shop_name,
       r.total_amount_check,
       COUNT(t.id) AS item_count,
       SUM(s.std_amount) AS calculated_total
   FROM "60_rd_receipts" r
   LEFT JOIN "60_rd_transactions" t ON t.receipt_id = r.id
   LEFT JOIN "60_rd_standardized_items" s ON s.receipt_id = r.id
   GROUP BY r.id, r.transaction_date, r.shop_name, r.total_amount_check
   ORDER BY r.transaction_date DESC
   LIMIT 10;
   ```

**SQLファイル**: `kakeibo_3table_split_03_validate.sql`

---

### フェーズ4: ビュー・関数の更新

**目的**: 集計ビューを新テーブル構造に対応させる

**更新対象**:

1. **日次集計ビュー**:
   ```sql
   CREATE OR REPLACE VIEW "60_ag_daily_summary" AS
   SELECT
       r.transaction_date,
       sit.name AS situation,
       cat.name AS category,
       COUNT(*) AS item_count,
       SUM(s.std_amount) AS total
   FROM "60_rd_receipts" r
   INNER JOIN "60_rd_standardized_items" s ON s.receipt_id = r.id
   LEFT JOIN "60_ms_situations" sit ON s.situation_id = sit.id
   LEFT JOIN "60_ms_categories" cat ON s.category_id = cat.id
   WHERE cat.is_expense = TRUE
   GROUP BY r.transaction_date, sit.name, cat.name
   ORDER BY r.transaction_date DESC;
   ```

2. **月次集計ビュー**:
   ```sql
   CREATE OR REPLACE VIEW "60_ag_monthly_summary" AS
   SELECT
       DATE_TRUNC('month', r.transaction_date) AS month,
       sit.name AS situation,
       cat.name AS category,
       COUNT(*) AS item_count,
       SUM(s.std_amount) AS total
   FROM "60_rd_receipts" r
   INNER JOIN "60_rd_standardized_items" s ON s.receipt_id = r.id
   LEFT JOIN "60_ms_situations" sit ON s.situation_id = sit.id
   LEFT JOIN "60_ms_categories" cat ON s.category_id = cat.id
   WHERE cat.is_expense = TRUE
   GROUP BY month, sit.name, cat.name
   ORDER BY month DESC;
   ```

**SQLファイル**: `kakeibo_3table_split_04_update_views.sql`

---

### フェーズ5: Pythonコードの更新

**目的**: アプリケーションコードを新テーブル構造に対応させる

#### 5-1. `K_kakeibo/transaction_processor.py` の更新

**変更内容**:

1. **レシート情報の挿入** (新規処理):
   ```python
   def _insert_receipt(self, ocr_result: Dict, file_name: str, drive_file_id: str, model_name: str, source_folder: str) -> str:
       """レシート情報をDBに登録"""
       receipt_data = {
           "transaction_date": ocr_result["transaction_date"],
           "shop_name": ocr_result["shop_name"],
           "total_amount_check": ocr_result.get("total_amount", 0),
           "subtotal_amount": ocr_result.get("subtotal", None),
           "image_path": f"99_Archive/{datetime.strptime(ocr_result['transaction_date'], '%Y-%m-%d').strftime('%Y-%m')}/{file_name}",
           "drive_file_id": drive_file_id,
           "source_folder": source_folder,
           "ocr_model": model_name,
           "workspace": "household",
           "is_verified": False
       }

       result = self.db.table("60_rd_receipts").insert(receipt_data).execute()
       return result.data[0]["id"]
   ```

2. **トランザクション情報の挿入** (構造変更):
   ```python
   def _insert_transaction(self, receipt_id: str, item: Dict, line_number: int) -> str:
       """トランザクション（明細行）をDBに登録"""
       trans_data = {
           "receipt_id": receipt_id,
           "line_number": line_number,
           "line_type": "ITEM",  # 将来的にはOCRで判定
           "ocr_raw_text": item.get("ocr_raw", item["product_name"]),  # OCR原文
           "product_name": item["product_name"],
           "unit_price": item.get("unit_price"),
           "quantity": item.get("quantity", 1),
           "ocr_confidence": item.get("confidence", None)
       }

       result = self.db.table("60_rd_transactions").insert(trans_data).execute()
       return result.data[0]["id"]
   ```

3. **正規化データの挿入** (新規処理):
   ```python
   def _insert_standardized_item(self, transaction_id: str, receipt_id: str, normalized: Dict, situation_id: str) -> str:
       """正規化された家計簿アイテムをDBに登録"""
       std_data = {
           "transaction_id": transaction_id,
           "receipt_id": receipt_id,
           "official_name": normalized.get("official_name"),
           "category_id": normalized.get("category_id"),
           "situation_id": situation_id,
           "tax_rate": normalized["tax_rate"],
           "std_amount": normalized["total_amount"],
           "tax_amount": normalized["tax_amount"],
           "calc_logic_log": normalized.get("calc_log", ""),
           "needs_review": normalized.get("needs_review", False)
       }

       result = self.db.table("60_rd_standardized_items").insert(std_data).execute()
       return result.data[0]["id"]
   ```

4. **メイン処理フローの変更**:
   ```python
   def process(self, ocr_result: Dict, file_name: str, drive_file_id: str, ...) -> Dict:
       # 1. レシート情報を登録
       receipt_id = self._insert_receipt(ocr_result, file_name, drive_file_id, model_name, source_folder)

       # 2. シチュエーション判定
       situation_id = self._determine_situation(trans_date)

       # 3. 各商品を正規化
       normalized_items = []
       for item in ocr_result["items"]:
           normalized = self._normalize_item(item, ocr_result["shop_name"])
           normalized_items.append(...)

       # 4. 税額按分計算
       items_with_tax = self._calculate_and_distribute_tax(normalized_items, ocr_result.get("tax_summary"))

       # 5. 各明細を3層に分けて登録
       transaction_ids = []
       standardized_ids = []
       for line_num, item_data in enumerate(items_with_tax, start=1):
           # 子テーブル: トランザクション
           trans_id = self._insert_transaction(receipt_id, item_data["raw_item"], line_num)
           transaction_ids.append(trans_id)

           # 孫テーブル: 正規化データ
           std_id = self._insert_standardized_item(trans_id, receipt_id, item_data["normalized"], situation_id)
           standardized_ids.append(std_id)

       # 6. 処理ログ記録（receipt_idも保存）
       self._log_processing_success(file_name, drive_file_id, receipt_id, transaction_ids, model_name)

       return {"success": True, "receipt_id": receipt_id, "transaction_ids": transaction_ids}
   ```

#### 5-2. `K_kakeibo/review_ui.py` の更新

**変更内容**:

1. **レシート単位での表示に変更**:
   ```python
   # 処理ログからレシートIDを取得
   logs = db.table("99_lg_image_proc_log").select("*, receipt_id").order(...).execute()

   # レシート情報を取得
   receipt = db.table("60_rd_receipts").select("*").eq("id", log["receipt_id"]).single().execute()

   # 明細を取得（3テーブルJOIN）
   items = db.table("60_rd_transactions") \
       .select("""
           *,
           standardized:60_rd_standardized_items(
               official_name,
               category_id,
               situation_id,
               std_amount,
               tax_amount,
               tax_rate,
               major_category,
               minor_category,
               person,
               purpose,
               needs_review
           ),
           categories:60_ms_categories(name),
           situations:60_ms_situations(name)
       """) \
       .eq("receipt_id", receipt_id) \
       .order("line_number") \
       .execute()
   ```

2. **表示データの整形**:
   ```python
   df_data = []
   for t in items.data:
       std = t["standardized"]
       df_data.append({
           "商品名": t["product_name"],
           "数量": t["quantity"],
           "単価": t["unit_price"],
           "金額": std["std_amount"],
           "税率": f"{std['tax_rate']}%",
           "税額": std["tax_amount"],
           "正式名": std.get("official_name") or "",
           "カテゴリ": t.get("categories", {}).get("name") or "",
           ...
       })
   ```

3. **更新処理の変更**:
   ```python
   # 子テーブル（テキスト）の更新
   db.table("60_rd_transactions").update({
       "product_name": new_product,
       "unit_price": new_price,
       "quantity": new_qty
   }).eq("id", trans_id).execute()

   # 孫テーブル（分類・金額）の更新
   db.table("60_rd_standardized_items").update({
       "official_name": new_official_name,
       "std_amount": new_amount,
       "major_category": new_major,
       ...
   }).eq("transaction_id", trans_id).execute()

   # 親テーブル（レシート全体）の確認状態更新
   db.table("60_rd_receipts").update({
       "is_verified": True
   }).eq("id", receipt_id).execute()
   ```

#### 5-3. 処理ログテーブルの更新

**変更内容**:

`99_lg_image_proc_log` テーブルに `receipt_id` カラムを追加:

```sql
ALTER TABLE "99_lg_image_proc_log"
ADD COLUMN IF NOT EXISTS receipt_id UUID REFERENCES "60_rd_receipts"(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_image_proc_log_receipt ON "99_lg_image_proc_log"(receipt_id);
```

**SQLファイル**: `kakeibo_3table_split_05_update_log_table.sql`

---

### フェーズ6: 旧テーブルのリネーム・削除

**目的**: 新テーブルへの移行を完了し、旧テーブルを削除

**実施内容**:

1. **旧テーブルのバックアップリネーム**:
   ```sql
   ALTER TABLE "60_rd_transactions" RENAME TO "60_rd_transactions_OLD_BACKUP";
   ```

2. **動作確認期間**:
   - 1週間〜1ヶ月程度、新テーブルで運用
   - 問題がないことを確認

3. **バックアップテーブルの削除**:
   ```sql
   DROP TABLE "60_rd_transactions_OLD_BACKUP" CASCADE;
   ```

**SQLファイル**: `kakeibo_3table_split_06_cleanup.sql`

---

## 🔙 ロールバック戦略

### ロールバック手順

各フェーズでの失敗時の対応:

| フェーズ | 失敗時の対応 |
|---------|------------|
| フェーズ1 | 新テーブルをDROP |
| フェーズ2 | 新テーブルのデータをTRUNCATE |
| フェーズ3 | データ修正後、フェーズ2を再実行 |
| フェーズ4 | ビューをDROP、旧定義を再作成 |
| フェーズ5 | Pythonコードをgit revert |
| フェーズ6 | バックアップテーブルをリネームで戻す |

### バックアップ方針

1. **SQLマイグレーション実行前**:
   - Supabase管理画面でスナップショット取得
   - または `pg_dump` でバックアップ

2. **Pythonコード変更前**:
   - Gitでコミット
   - 新ブランチで作業

---

## ✅ チェックリスト

### 実装前

- [ ] Supabaseのバックアップ取得
- [ ] Gitブランチ作成 (`feature/kakeibo-3table-split`)
- [ ] 現在のデータ件数を記録

### フェーズ1: スキーマ作成

- [ ] SQL実行: `kakeibo_3table_split_01_create_tables.sql`
- [ ] テーブル作成確認 (3テーブル)
- [ ] インデックス作成確認

### フェーズ2: データ移行

- [ ] SQL実行: `kakeibo_3table_split_02_migrate_data.sql`
- [ ] 親テーブルのレコード数確認
- [ ] 子テーブルのレコード数確認
- [ ] 孫テーブルのレコード数確認

### フェーズ3: データ検証

- [ ] SQL実行: `kakeibo_3table_split_03_validate.sql`
- [ ] 件数チェック合格
- [ ] 金額合計チェック合格
- [ ] 外部キー整合性チェック合格
- [ ] サンプルデータ目視確認合格

### フェーズ4: ビュー更新

- [ ] SQL実行: `kakeibo_3table_split_04_update_views.sql`
- [ ] ビュー動作確認

### フェーズ5: Pythonコード更新

- [ ] `transaction_processor.py` 更新
- [ ] `review_ui.py` 更新
- [ ] ローカルテスト実行
- [ ] 新規レシート登録テスト
- [ ] レビューUI動作確認

### フェーズ6: クリーンアップ

- [ ] 1週間の運用確認
- [ ] 旧テーブル削除
- [ ] Git merge

---

## 📊 期待される効果

### 1. データ品質の向上

- **OCR原文の保全**: トレーサビリティ確保
- **計算ロジックの記録**: デバッグ・監査が容易

### 2. 処理フローの明確化

- **責務の分離**: 「管理」「テキスト」「意味」の3層が明確
- **UI設計の改善**: 修正フェーズごとに適切なUIを提供可能

### 3. パフォーマンスの向上

- **インデックス最適化**: 各テーブルの用途に応じたインデックス
- **冗長化によるJOIN削減**: 孫テーブルに `receipt_id` を持たせることで集計が高速化

### 4. 拡張性の確保

- **レシート全体の情報**: 割引・ポイントなどの追加が容易
- **行タイプの拡張**: DISCOUNT, SUB_TOTAL, TAXなど多様な行に対応可能

---

## 🎯 次のステップ

マイグレーション完了後、以下の機能を追加実装する予定:

1. **レシート全体の割引対応**:
   - 親テーブルに `discount_amount` カラムを追加
   - 割引の按分計算ロジック実装

2. **OCR信頼度に基づくハイライト**:
   - `ocr_confidence < 0.8` の行を自動マークアップ
   - レビューUIで優先的に確認

3. **行タイプの自動判定**:
   - OCR時に `line_type` を判定（ITEM / DISCOUNT / TAX / SUB_TOTAL）
   - 割引行と商品行の関連付け

4. **計算ロジックの詳細化**:
   - `calc_logic_log` に具体的な計算式を記録
   - 税額の誤差を検出して自動調整

---

## 📝 備考

### データベース命名規則

- `rd` (Raw Data): 生データ・トランザクションデータ
- `ms` (Master): マスタデータ
- `ag` (Aggregate): 集計ビュー
- `lg` (Log): ログ・システムテーブル

### トランザクション管理

全SQLマイグレーションは `BEGIN; ... COMMIT;` で囲み、エラー時は自動ロールバックされるようにする。

### テスト環境

本番環境への適用前に、開発環境（ローカルPostgreSQL または Supabase開発プロジェクト）でテスト実行すること。

---

**作成日**: 2025-12-20
**対象プロジェクト**: document_management_system
**影響範囲**: 家計簿機能 (60番台テーブル)
**推定所要時間**: 実装 2-3日、テスト 1-2日
