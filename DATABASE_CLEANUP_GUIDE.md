# データベース「断捨離」実行ガイド

このガイドは、`documents` テーブルから不要なカラムを安全に削除するための手順書です。

## 概要

以下の不要なカラムを削除し、データを `metadata` JSONB カラムで一元管理します。

### 削除対象カラム

1. **日付関連**: `year`, `month`
2. **金額**: `amount`
3. **学校関連**: `grade_level`, `school_name`
4. **ファイル情報**: `file_size_bytes`
5. **イベント・表データ**: `event_dates`, `extracted_tables`
6. **タイムスタンプ**: `last_edited_at`
7. **Stage1関連**: `stage1_confidence`, `stage1_needs_processing`
8. **レビュー状態**: `reviewed`, `is_reviewed`

## 実行前の確認事項

### 1. バックアップの取得 ✅

**重要**: 本番環境で実行する前に、必ずバックアップを取得してください。

```bash
# pg_dump を使用する場合（例）
pg_dump -h your-host -U your-user -d your-database > backup_$(date +%Y%m%d_%H%M%S).sql

# または Supabase の Backup 機能を使用
```

### 2. Python コードの修正確認 ✅

以下のファイルが修正されていることを確認してください：

- [x] `pipelines/two_stage_ingestion.py` - `extracted_tables`, `event_dates` への参照を削除
- [x] `core/database/client.py` - `filter_year`, `filter_month`, `year`, `month`, `is_reviewed` への参照を削除
- [x] `reprocess_classroom_documents_v2.py` - 修正不要（確認済み）
- [x] `core/utils/metadata_extractor.py` - 使用されていない（今後削除予定）

### 3. 不要なスクリプトの削除 ✅

以下のマイグレーションスクリプトを削除済み：

- [x] `scripts/migrate_metadata_filtering.py`
- [x] `scripts/migrate_tables_to_extracted_tables.py`

## 実行手順

### ステップ1: SQL検索関数の更新

**実行ファイル**: `database/cleanup_remove_columns_step1_update_search_function.sql`

**目的**: `search_documents_final` 関数から `filter_year`, `filter_month`, `year`, `month` への参照を削除

**実行方法**:
1. Supabase Dashboard を開く
2. SQL Editor に移動
3. `cleanup_remove_columns_step1_update_search_function.sql` の内容を貼り付け
4. 実行

**確認**:
```sql
-- 関数が正しく更新されたことを確認
SELECT * FROM search_documents_final(
    'テストクエリ',
    '[0.1, 0.2, ...]'::vector(1536),
    0.0,
    10,
    0.7,
    0.3,
    ARRAY['workspace1']::TEXT[]
);
```

### ステップ2: アプリケーションの動作確認

**重要**: SQL関数を更新した後、アプリケーションが正常に動作することを確認してください。

1. **検索機能のテスト**
   ```bash
   # 検索APIをテスト
   curl -X POST http://localhost:5000/api/search \
     -H "Content-Type: application/json" \
     -d '{"query": "テストクエリ", "doc_types": ["workspace1"]}'
   ```

2. **ドキュメント取得のテスト**
   ```bash
   # レビュー対象ドキュメントを取得
   curl http://localhost:5000/api/documents/review
   ```

3. **エラーログの確認**
   ```bash
   # アプリケーションログを確認
   tail -f logs/app.log
   ```

### ステップ3: カラムの削除

**実行ファイル**: `database/cleanup_remove_columns_step2_drop_columns.sql`

**目的**: 不要なカラムを物理的に削除

**実行方法**:
1. **本番環境の場合**: メンテナンスウィンドウを設定（推奨）
2. Supabase Dashboard を開く
3. SQL Editor に移動
4. `cleanup_remove_columns_step2_drop_columns.sql` の内容を貼り付け
5. **慎重に内容を確認**
6. 実行

**確認**:
```sql
-- カラムが削除されたことを確認
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'documents'
ORDER BY ordinal_position;
```

### ステップ4: 最終確認

1. **アプリケーションの再起動**
   ```bash
   # アプリケーションを再起動
   systemctl restart your-app-service
   ```

2. **全機能のテスト**
   - ドキュメント検索
   - ドキュメント取り込み
   - レビュー機能
   - メタデータ編集

3. **データ整合性の確認**
   ```sql
   -- metadata カラムにデータが含まれていることを確認
   SELECT
       id,
       file_name,
       metadata->>'tables' AS tables,
       metadata->>'event_dates' AS event_dates
   FROM documents
   LIMIT 10;
   ```

## トラブルシューティング

### エラー: カラムが見つからない

**症状**: Python コードで削除済みカラムを参照しようとしてエラーが発生

**対処法**:
1. エラーメッセージから該当するファイルと行番号を特定
2. 該当箇所のコードを修正
3. アプリケーションを再起動

### エラー: SQL関数が見つからない

**症状**: `search_documents_final` 関数が見つからない

**対処法**:
1. `cleanup_remove_columns_step1_update_search_function.sql` を再実行
2. 関数名のタイプミスがないか確認

### ロールバック方法

カラムを削除した後は、データを復元できません。バックアップから復元する必要があります。

```bash
# pg_restore を使用する場合（例）
psql -h your-host -U your-user -d your-database < backup_20250101_120000.sql

# または Supabase の Restore 機能を使用
```

## まとめ

この「断捨離」により、以下のメリットが得られます：

1. **データ一元管理**: すべてのメタデータが `metadata` JSONB カラムに集約
2. **柔軟性の向上**: スキーマ変更なしに新しいメタデータフィールドを追加可能
3. **保守性の向上**: トップレベルカラムとの同期が不要
4. **クエリの簡素化**: `filter_year`, `filter_month` の代わりに `all_mentioned_dates` を使用

## 参考情報

- `metadata` JSONB カラムの構造については、`docs/METADATA_STRUCTURE.md` を参照
- 日付検索機能については、`all_mentioned_dates` 配列を使用
- レビュー状態は `review_status` カラムで管理（`pending`, `reviewed` など）
