# halfvec変換 - 段階的実行手順

メモリエラーを回避するため、**1つずつ手動で実行**してください。

## 📋 実行手順

### Step 1: インデックス削除（1つずつ）

Supabase SQL Editorで以下を**1行ずつ**実行：

```sql
DROP INDEX IF EXISTS idx_netsuper_general_name_embedding;
```

成功したら次：

```sql
DROP INDEX IF EXISTS idx_netsuper_small_category_embedding;
```

成功したら次：

```sql
DROP INDEX IF EXISTS idx_netsuper_keywords_embedding;
```

---

### Step 2: 型変換（1つずつ）

**重要: 1つずつ実行してください。一度に実行しないこと。**

まず1つ目：

```sql
ALTER TABLE "Rawdata_NETSUPER_items"
  ALTER COLUMN general_name_embedding TYPE halfvec(1536);
```

✅ 成功したら2つ目：

```sql
ALTER TABLE "Rawdata_NETSUPER_items"
  ALTER COLUMN small_category_embedding TYPE halfvec(1536);
```

✅ 成功したら3つ目：

```sql
ALTER TABLE "Rawdata_NETSUPER_items"
  ALTER COLUMN keywords_embedding TYPE halfvec(1536);
```

---

### Step 3: 確認

すべて成功したら、型が変換されたか確認：

```sql
SELECT
  column_name,
  data_type,
  udt_name
FROM information_schema.columns
WHERE table_name = 'Rawdata_NETSUPER_items'
  AND column_name LIKE '%embedding%';
```

**期待される結果:**
- `general_name_embedding` → udt_name = `halfvec`
- `small_category_embedding` → udt_name = `halfvec`
- `keywords_embedding` → udt_name = `halfvec`

---

### Step 4: 検索テスト

型変換が完了したら、検索が動作するかテスト：

```bash
python netsuper_search_app/hybrid_search.py "牛乳"
```

---

## ⚠️ もしエラーが出たら

もし**それでもメモリエラーが出る場合**は、Supabaseのプラン制限の可能性があります。

その場合の代替案：
1. データを一時的にエクスポート
2. 新しいテーブルを作成（halfvec型で）
3. データを再インポート
4. 古いテーブルを削除

この方法が必要な場合は教えてください。
