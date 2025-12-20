# テーブル統合・リネーム マイグレーション実行手順

## 📋 概要

このマイグレーションは以下を実行します：

1. **ダイエーと楽天西友の商品テーブルを統合可能な構造に変更**
   - `daiei_products` + `rakuten_seiyu_products` → `80_rd_products`（統合テーブル）
   - `rakuten_seiyu_price_history` → `80_rd_price_history`

2. **全テーブルを新命名規則でリネーム**
   - 10番台: ドキュメント処理
   - 60番台: 家計簿
   - 70番台: チラシ
   - 80番台: ネットスーパー
   - 99番台: ログ・システム

3. **不要テーブルの削除**
   - `money_events`（purpose カラムで代用）
   - `daiei_products`（統合後削除）
   - `rakuten_seiyu_products`（統合後削除）
   - `v_rakuten_seiyu_products_latest`（不要ビュー）

## ⚠️ 注意事項

- **既存データは消滅します**（新テーブルは空の状態で作成）
- **ロールバック機能はありません**
- Supabaseのバックアップ機能でスナップショットを取得しておくことを推奨

## 🚀 実行手順

### Step 1: メインマイグレーションの実行

Supabase SQL Editorで以下を実行：

```bash
database/migrations/table_consolidation_and_rename.sql
```

このSQLは以下を実行します：
- 新テーブル `80_rd_products`, `80_rd_price_history` の作成
- 全テーブルのリネーム
- ビューの再作成
- 不要テーブルの削除

### Step 2: 関数・トリガーの更新

続けて以下を実行：

```bash
database/migrations/update_functions_and_triggers.sql
```

このSQLは以下を実行します：
- `rollback_document_metadata` 関数の更新
- チラシ関連のトリガー・関数の更新
- 再処理キュー関連の関数の更新

### Step 3: 確認

以下のクエリで新しいテーブル構成を確認：

```sql
SELECT
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
  AND (
    table_name LIKE '10\_%' OR
    table_name LIKE '60\_%' OR
    table_name LIKE '70\_%' OR
    table_name LIKE '80\_%' OR
    table_name LIKE '99\_%'
  )
ORDER BY table_name;
```

## 📊 マイグレーション後のテーブル構成

### 10. ドキュメント処理（2テーブル）
- `10_rd_source_docs` - 原本ドキュメント
- `10_ix_search_index` - 検索インデックス

### 60. 家計簿（7テーブル）
- `60_rd_transactions` - 取引データ
- `60_ms_categories` - 費目マスタ
- `60_ms_situations` - シチュエーションマスタ
- `60_ms_product_dict` - 商品名辞書
- `60_ms_ocr_aliases` - OCR誤読修正
- `60_ag_daily_summary` - [View] 日次集計
- `60_ag_monthly_summary` - [View] 月次集計

### 70. チラシ（2テーブル）
- `70_rd_flyer_docs` - チラシドキュメント
- `70_rd_flyer_items` - チラシ商品

### 80. ネットスーパー（3テーブル）
- `80_rd_products` - 統合商品マスタ（ダイエー + 楽天西友）
- `80_rd_price_history` - 価格履歴
- `80_ag_price_changes` - [View] 価格変動

### 99. ログ・システム（4テーブル）
- `99_lg_correction_history` - 修正履歴
- `99_lg_process_logs` - 処理ログ
- `99_lg_reprocess_queue` - 再処理キュー
- `99_lg_image_proc_log` - 画像処理ログ

**合計: 18テーブル（ビュー含む）**

## 🔄 今後のデータ取り込み

### ネットスーパーのスクレイピング

新しい `80_rd_products` テーブルにデータを挿入する際は、`organization` カラムで識別：

```sql
-- ダイエーの商品
INSERT INTO "80_rd_products" (
    organization,
    product_name,
    jan_code,
    current_price,
    ...
) VALUES (
    'ダイエーネットスーパー',
    '商品名',
    '4901234567890',
    298,
    ...
);

-- 楽天西友の商品
INSERT INTO "80_rd_products" (
    organization,
    product_name,
    jan_code,
    current_price,
    category_id,  -- 楽天西友のみ
    tags,         -- 楽天西友のみ
    ...
) VALUES (
    '楽天西友ネットスーパー',
    '商品名',
    '4901234567890',
    298,
    'category_123',
    ARRAY['セール', '人気'],
    ...
);
```

### 既存スクレイピングスクリプトの修正

以下のファイルを新テーブル名に対応させる必要があります：

1. `B_ingestion/daiei/` 配下のスクレイピングスクリプト
   - テーブル名: `daiei_products` → `80_rd_products`

2. `B_ingestion/rakuten_seiyu/` 配下のスクレイピングスクリプト
   - テーブル名: `rakuten_seiyu_products` → `80_rd_products`
   - テーブル名: `rakuten_seiyu_price_history` → `80_rd_price_history`

3. 家計簿関連のスクリプト
   - `money_transactions` → `60_rd_transactions`
   - `money_*` → `60_ms_*` または `60_rd_*`

4. チラシ関連のスクリプト
   - `flyer_documents` → `70_rd_flyer_docs`
   - `flyer_products` → `70_rd_flyer_items`

## 📝 命名規則

### プレフィックスの意味

- `rd` (Raw Data) - 生データ、トランザクションデータ
- `ms` (Master) - マスタデータ
- `ag` (Aggregate) - 集計ビュー
- `ix` (Index) - インデックステーブル
- `lg` (Log) - ログ、システムテーブル

### 番号の意味

- **10番台**: データの入り口（ドキュメント処理）
- **60番台**: メイン機能（家計簿）
- **70番台**: サブ機能（チラシ）
- **80番台**: サブ機能（ネットスーパー）
- **99番台**: 裏方（ログ・システム）

番号を飛ばしているのは、将来の拡張性のため（20番台にユーザー管理、40番台に分析など追加可能）

## ❓ トラブルシューティング

### エラー: テーブル名に引用符が必要

PostgreSQLでは数字で始まるテーブル名は二重引用符で囲む必要があります：

```sql
-- ❌ エラー
SELECT * FROM 80_rd_products;

-- ✅ 正しい
SELECT * FROM "80_rd_products";
```

Supabaseクライアントから操作する場合も同様です。

### 外部キー制約エラー

マイグレーション実行前に既存データが存在する場合、外部キー制約でエラーが発生することがあります。
その場合は、該当テーブルのデータを手動で削除してから再実行してください。

## 🎉 完了

マイグレーション完了後、Supabase Studioの「Table Editor」で新しいテーブル構成が確認できます。
番号順に整理されているため、目的のテーブルが見つけやすくなっています。
