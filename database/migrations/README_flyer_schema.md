# チラシ管理スキーマ

スーパーやドラッグストアのチラシ情報を管理するための専用スキーマです。

## テーブル構造

### 1. flyer_documents（チラシ基本情報）

チラシの基本情報を管理するメインテーブルです。

**主要フィールド:**
- `organization`: 店舗名（例: "フーディアム 武蔵小杉"、"マルエツ 武蔵小杉駅前店"）
- `flyer_id`: チラシの一意識別子（ページごとにユニーク）
- `flyer_title`: チラシのタイトル
- `flyer_period`: 有効期間（例: "2024/12/18〜2024/12/24"）
- `page_number`: ページ番号
- `attachment_text`: OCRで抽出したテキスト
- `summary`: AIが生成したサマリー
- `tags`: タグ配列（検索・分類用）
- `valid_from`, `valid_until`: 有効期間の日付
- `processing_status`: 処理ステータス（pending, processing, completed, failed）

### 2. flyer_products（商品情報）

チラシから抽出した個別商品の情報を管理するテーブルです。

**主要フィールド:**
- `flyer_document_id`: 関連するチラシのID（外部キー）
- `product_name`: 商品名
- `price`: 価格
- `original_price`: 元の価格（割引前）
- `discount_rate`: 割引率（%）
- `category`: カテゴリ（野菜、肉、魚、日用品など）
- `brand`: ブランド
- `quantity`: 数量・容量
- `is_special_offer`: 特売品フラグ
- `page_number`: 掲載ページ
- `bounding_box`: 画像内の位置情報（JSON）
- `extracted_text`: OCR元テキスト
- `confidence`: 抽出の信頼度

## マイグレーション手順

### 1. Supabase SQLエディタで実行

```bash
# Supabaseダッシュボードにログイン
# SQL Editor を開く
# create_flyer_schema.sql の内容をコピー＆ペースト
# 実行
```

### 2. ローカルで実行（psqlを使用）

```bash
psql -h <your-supabase-host> -U postgres -d postgres -f create_flyer_schema.sql
```

## 使用例

### チラシの検索

```sql
-- 特定店舗のチラシを取得
SELECT * FROM flyer_documents
WHERE organization = 'フーディアム 武蔵小杉'
ORDER BY created_at DESC;

-- 有効期限内のチラシを取得
SELECT * FROM flyer_documents
WHERE valid_until >= CURRENT_DATE
ORDER BY organization, valid_from;

-- 全文検索
SELECT * FROM flyer_documents
WHERE search_vector @@ to_tsquery('simple', 'クリスマス & セール');
```

### 商品の検索

```sql
-- 特定カテゴリの商品を取得
SELECT p.*, f.organization, f.flyer_title
FROM flyer_products p
JOIN flyer_documents f ON p.flyer_document_id = f.id
WHERE p.category = '野菜'
ORDER BY p.price;

-- 特売商品を取得
SELECT p.*, f.organization
FROM flyer_products p
JOIN flyer_documents f ON p.flyer_document_id = f.id
WHERE p.is_special_offer = true
AND f.valid_until >= CURRENT_DATE
ORDER BY p.discount_rate DESC;

-- 商品名で検索
SELECT * FROM flyer_products
WHERE product_name_normalized ILIKE '%トマト%';
```

### 店舗別の統計

```sql
-- 店舗別のチラシ数
SELECT organization, COUNT(*) as flyer_count
FROM flyer_documents
GROUP BY organization
ORDER BY flyer_count DESC;

-- 店舗別の平均商品価格
SELECT f.organization,
       AVG(p.price) as avg_price,
       COUNT(p.id) as product_count
FROM flyer_products p
JOIN flyer_documents f ON p.flyer_document_id = f.id
WHERE p.price IS NOT NULL
GROUP BY f.organization
ORDER BY avg_price;
```

## インデックス

以下のインデックスが自動的に作成されます：

**flyer_documents:**
- organization（店舗名）
- flyer_id（チラシID）
- valid_from, valid_until（有効期間）
- processing_status（処理ステータス）
- tags（GINインデックス）
- search_vector（全文検索）

**flyer_products:**
- flyer_document_id（チラシID）
- category（カテゴリ）
- product_name, product_name_normalized（商品名）
- price（価格）
- is_special_offer（特売フラグ）
- search_vector（全文検索）

## 自動機能

1. **更新日時の自動更新**: `updated_at` フィールドは自動的に更新されます
2. **全文検索ベクトルの自動生成**: `search_vector` フィールドは自動的に生成・更新されます
3. **カスケード削除**: チラシを削除すると、関連する商品データも自動的に削除されます

## 処理フロー

1. **チラシ取得**: `flyer_ingestion.py` がチラシをダウンロードし、`flyer_documents` テーブルに保存（`processing_status='pending'`）
2. **OCR処理**: 別途処理スクリプトがOCRを実行し、`attachment_text` を更新
3. **商品抽出**: OCRテキストから商品情報を抽出し、`flyer_products` テーブルに保存
4. **完了**: `processing_status='completed'` に更新

## 注意事項

- `flyer_id` はページごとにユニークな値（例: `12345_p1`, `12345_p2`）
- 日付フィールドは `DATE` 型、タイムスタンプは `TIMESTAMPTZ` 型
- 価格は `DECIMAL(10, 2)` 型で保存（円単位、小数点以下2桁まで）
- タグ配列は PostgreSQL の配列型を使用
- JSON データは `JSONB` 型で保存（検索可能）
