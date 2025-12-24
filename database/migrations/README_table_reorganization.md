# Supabaseテーブル再編成 完了レポート

## 実行日
2025-12-25

## 1. Rawdataテーブルの再編成

### 変更内容
| 旧テーブル名 | 新テーブル名 | 内容 |
|------------|------------|------|
| `10_rd_source_docs` | `Rawdata_FILE_AND_MAIL` | PDFファイル・メール情報 |
| `60_rd_receipts` | `Rawdata_RECEIPT_shops` | レシート店舗情報 |
| `60_rd_transactions` | `Rawdata_RECEIPT_items` | レシート明細 |
| `70_rd_flyer_docs` | `Rawdata_FLYER_shops` | チラシ店舗情報 |
| `70_rd_flyer_items` | `Rawdata_FLYER_items` | チラシ商品情報 |
| `80_rd_products` | `Rawdata_NETSUPER_items` | ネットスーパー商品情報 |

### マイグレーションスクリプト
- `database/migrations/rename_rawdata_tables.sql`
- `database/migrations/rollback_rename_rawdata_tables.sql`

## 2. Masterテーブルの再編成

### 変更内容

#### MASTER_Categories グループ（静的参照データ）
| 旧テーブル名 | 新テーブル名 | 内容 |
|------------|------------|------|
| `60_ms_expense_categories` | `MASTER_Categories_expense` | 費目カテゴリ（食費、日用品など） |
| `60_ms_purposes` | `MASTER_Categories_purpose` | 用途・シチュエーション |
| `60_ms_product_categories` | `MASTER_Categories_product` | 商品カテゴリ |

#### MASTER_Rules グループ（動的ルール・辞書）
| 旧テーブル名 | 新テーブル名 | 内容 |
|------------|------------|------|
| `60_ms_expense_category_rules` | `MASTER_Rules_expense_mapping` | 費目自動割当ルール |
| `60_ms_transaction_dictionary` | `MASTER_Rules_transaction_dict` | 取引名辞書 |

#### Aggregate グループ（集計テーブル）
| 旧テーブル名 | 新テーブル名 | 内容 |
|------------|------------|------|
| `60_ag_items_needs_review` | `Aggregate_items_needs_review` | レビュー必要明細 |

#### 削除されたテーブル
- `60_ms_categories` - `MASTER_Categories_expense`に統合済み
- `60_ms_situations` - `MASTER_Categories_purpose`に統合済み
- `60_ms_product_dict` - 未使用のため削除
- `60_ms_ocr_aliases` - 未使用のため削除

### マイグレーションスクリプト
- `database/migrations/reorganize_master_tables.sql`
- `database/migrations/rollback_reorganize_master_tables.sql`

## 3. コード修正範囲

### 修正されたファイル数
- **Python ファイル**: 全プロジェクト内の関連ファイル
- **SQL ファイル**: 6つのマイグレーションファイル
- **総参照数**: 143箇所を新テーブル名に更新

### 主な影響範囲
- `K_kakeibo/` - 家計簿関連処理（18ファイル）
- `L_product_classification/` - 商品分類処理（7ファイル）
- `B_ingestion/` - データ取込処理（4ファイル）
- `netsuper_search_app/` - ネットスーパー検索（11ファイル）
- `database/migrations/` - 過去のマイグレーションスクリプト

## 4. 検証結果

### データベース状態
- ✅ 全テーブル名が正常に変更されました
- ✅ 外部キー制約は自動更新されました
- ✅ 不要なテーブルは削除されました

### コード検証
- ✅ 新テーブル名への参照: 143箇所
- ✅ 旧テーブル名の残存: 0箇所（マイグレーションスクリプト除く）
- ✅ すべてのPython/SQLファイルが更新されました

## 5. 注意事項

### ロールバック方法
問題が発生した場合は、以下のロールバックスクリプトを実行してください：

```sql
-- Masterテーブルのロールバック
-- database/migrations/rollback_reorganize_master_tables.sql

-- Rawdataテーブルのロールバック
-- database/migrations/rollback_rename_rawdata_tables.sql
```

**重要**: ロールバック後は、アプリケーションコードも元に戻す必要があります。

### 今後のテーブル命名規則

| プレフィックス | 用途 | 例 |
|------------|------|-----|
| `Rawdata_` | ソース生データ | `Rawdata_RECEIPT_items` |
| `MASTER_Categories_` | 静的参照データ | `MASTER_Categories_expense` |
| `MASTER_Rules_` | 動的ルール・辞書 | `MASTER_Rules_expense_mapping` |
| `Aggregate_` | 集計テーブル・ビュー | `Aggregate_items_needs_review` |
| `99_lg_` | ログテーブル | `99_lg_processing_log` |
| `10_ix_` | インデックステーブル | `10_ix_document_index` |

## 6. 次のステップ

1. ✅ データベースマイグレーション実行
2. ✅ アプリケーションコード更新
3. ⏳ 動作テストの実施
4. ⏳ 本番環境への適用検討

---

**作成日**: 2025-12-25
**最終更新**: 2025-12-25
