# キーワードベース検索システム実装完了サマリー

## 実装内容

あなたの要望に基づき、以下の新しいアーキテクチャを実装しました:

### ✅ 完了した実装

#### 1. データ構造の変更

**新しいアーキテクチャ:**
- `general_name`: コア概念のみ（例: "食パン", "ボトルコーヒー"）
- `keywords`: 全ての単語を個別に格納する配列（JSONB）

**例:**
```
商品名: "パスコ超熟6枚切り"
→ general_name: "食パン"
→ keywords: ["食パン", "パスコ", "超熟", "6枚切り"]

商品名: "ジョージア無糖1000ml"
→ general_name: "ボトルコーヒー"
→ keywords: ["ボトルコーヒー", "ジョージア", "無糖", "1000ml"]
```

#### 2. AI抽出ロジックの改善

**ファイル:** `K_kakeibo/transaction_processor.py`

**新しいメソッド:**
- `_extract_general_name_with_ai()`: Gemini 2.5 Flashで一般名詞とキーワードを同時抽出
- `_get_general_name_and_keywords()`: ブランド名マッピング → AI抽出 → 正規表現の順で処理

**プロンプトの改善点:**
- JSON形式で`{"general_name": "...", "keywords": [...]}`を返すように指示
- コア概念と個別キーワードを明確に分離
- メーカー名、ブランド名、容量も全てキーワードに含める

#### 3. 同期スクリプトの更新

**ファイル:** `K_kakeibo/sync_netsuper_general_names.py`

**変更内容:**
- `general_name`と`keywords`の両方をデータベースに保存
- キーワードはJSON形式で保存
- ログ出力で両方の値を表示

#### 4. テスト結果

**ファイル:** `K_kakeibo/test_keyword_extraction.py`

全10件のテストケースで期待通りの結果を確認:

```
✅ パスコ 超熟 6枚切り
   → general_name: 食パン
   → keywords: ["食パン", "パスコ", "超熟", "6枚切り"]

✅ ジョージア 無糖 1000ml
   → general_name: ボトルコーヒー
   → keywords: ["ボトルコーヒー", "ジョージア", "無糖", "1000ml"]

✅ 明治おいしい牛乳 1000ml
   → general_name: 牛乳
   → keywords: ["牛乳", "明治おいしい牛乳", "1000ml"]

✅ Mizkan りんご黒酢 カロリーゼロ 1l
   → general_name: りんご黒酢
   → keywords: ["Mizkan", "りんご黒酢", "カロリーゼロ", "1l"]
```

---

## 📋 次に実行すべきこと

### Step 1: データベースにkeywordsカラムを追加

**Supabase Dashboard → SQL Editor で実行:**

```sql
-- keywordsカラムの追加
ALTER TABLE "Rawdata_NETSUPER_items"
ADD COLUMN IF NOT EXISTS keywords JSONB DEFAULT '[]'::jsonb;

-- インデックスの作成
CREATE INDEX IF NOT EXISTS idx_netsuper_items_keywords
ON "Rawdata_NETSUPER_items" USING gin(keywords);
```

### Step 2: 重み付きsearch_vectorの設定

**Supabase Dashboard → SQL Editor で実行:**

```sql
-- ファイルの内容をそのまま実行
-- database/migrations/create_weighted_search_vector.sql
```

このSQLは以下を実行します:
1. トリガー関数の作成（自動的にsearch_vectorを生成）
2. トリガーの作成（INSERT/UPDATE時に自動実行）
3. 既存データのsearch_vector更新

**重み付けの仕組み:**
- Weight A (最重要): `general_name` - "りんご黒酢"
- Weight B (重要): `keywords` - ["Mizkan", "りんご黒酢", "カロリーゼロ", "1l"]
- Weight C (参考): `product_name` - 元の商品名全体

### Step 3: AI分類・Embedding生成の実行

**⚠️ 新システム: 3段階フォールバック分類**

#### 3-1. 既存AI生成データのクリーンアップ（必要な場合）

```bash
# 確認のみ（削除しない）
python K_kakeibo/cleanup_generated_data.py --all --dry-run

# 実際に削除
python K_kakeibo/cleanup_generated_data.py --all
```

#### 3-2. 商品分類（Gemini 2.5 Flash）

**全商品に general_name, small_category, keywords を生成:**

```bash
python -m L_product_classification.daily_auto_classifier
```

**処理内容:**
- Tier 1: 辞書lookup（MASTER_Product_generalize）
- Tier 2: コンテキストlookup（MASTER_Product_classify）
- Tier 3: Gemini Few-shot推論
- コスト: 約11-12円（Gemini 2.5 Flash使用）

#### 3-3. Embedding生成（OpenAI）

**全商品に embedding を生成:**

```bash
python netsuper_search_app/generate_multi_embeddings.py
```

**処理内容:**
- OpenAI text-embedding-3-small (1536次元)
- コスト: 約5-10円

---

**⚠️ 廃止予定スクリプト:**
- `K_kakeibo/sync_netsuper_general_names.py` は general_name と keywords のみ生成するため廃止予定
- 新システムでは small_category も含めた3つすべてを Gemini で生成

---

## 📁 作成されたファイル

### 実装ファイル

1. **`K_kakeibo/transaction_processor.py`** (更新)
   - `_extract_general_name_with_ai()`: AIでgeneral_nameとkeywordsを抽出
   - `_get_general_name_and_keywords()`: ブランド名マッピング + AI抽出

2. **`K_kakeibo/sync_netsuper_general_names.py`** (更新)
   - general_nameとkeywordsの両方をデータベースに保存

3. **`K_kakeibo/test_keyword_extraction.py`** (新規)
   - キーワード抽出のテストスクリプト

### データベース関連

4. **`database/migrations/add_keywords_to_netsuper_items.sql`** (新規)
   - keywordsカラム追加のSQL

5. **`database/migrations/create_weighted_search_vector.sql`** (新規)
   - 重み付きsearch_vector生成のトリガー設定SQL

6. **`database/migrations/PLAN_weighted_search_vector.md`** (新規)
   - 重み付き検索の詳細な実装プラン

7. **`database/apply_keywords_migration.py`** (新規)
   - マイグレーション実行用ヘルパースクリプト

---

## 🔍 検索の動作（実装後）

### 例: "りんご黒酢"で検索

```sql
SELECT
    id,
    product_name,
    general_name,
    keywords,
    ts_rank(search_vector, to_tsquery('japanese', 'りんご & 黒酢')) AS rank
FROM "Rawdata_NETSUPER_items"
WHERE search_vector @@ to_tsquery('japanese', 'りんご & 黒酢')
ORDER BY rank DESC
LIMIT 10;
```

**結果の順位:**

1. **商品A**: "Mizkan りんご黒酢 カロリーゼロ 1l"
   - general_name: "りんご黒酢" (Weight A) → **最高スコア** ⭐⭐⭐
   - keywords: ["Mizkan", "りんご黒酢", "カロリーゼロ", "1l"]

2. **商品B**: "りんごジュース 1000ml"
   - general_name: "りんごジュース" (部分一致のみ) → 低スコア ⭐
   - keywords: ["りんごジュース", "1000ml"]

→ general_nameで完全一致する商品Aが最上位に表示される

---

## ⚠️ 注意事項

### 現在の状態

- ✅ コードの実装: 完了
- ⏳ データベーススキーマ: **未実行**（keywordsカラムが存在しない）
- ⏳ トリガー設定: **未実行**
- ⏳ AI抽出: **未実行**（約108件のみ古いAI処理済み）

### 実行順序

1. **必ず** Step 1 → Step 2 → Step 3 の順で実行してください
2. Step 2のトリガー設定が完了してからStep 3のAI抽出を実行すること
3. AI抽出中は時間がかかるため、バックグラウンドで実行することを推奨

---

## 💰 コスト見積もり

### Gemini 2.5 Flash

- 入力: 150トークン/商品 × 1,159商品 = 約173,850トークン
- 出力: 75トークン/商品 × 1,159商品 = 約86,925トークン

**コスト:**
- 入力: 173,850 × $0.15/1M = $0.026
- 出力: 86,925 × $0.60/1M = $0.052
- **合計: 約$0.078（約11-12円）**

---

## 🎯 期待される効果

1. **検索精度の向上**
   - general_nameによる重み付けで、コア概念での検索が最優先
   - キーワード単位での柔軟な検索が可能

2. **検索体験の改善**
   - "りんご黒酢"で検索 → "りんごジュース"より"りんご黒酢"が上位に
   - ブランド名での検索も可能（"ジョージア"で検索 → ボトルコーヒーが見つかる）

3. **メンテナンス性の向上**
   - AI抽出により手動マッピングの必要性が大幅に減少
   - ブランド名マッピング（30件）のみ手動管理すればOK

---

## 📞 サポート

質問や問題があれば、以下のファイルを参照してください:

- 実装詳細: `database/migrations/PLAN_weighted_search_vector.md`
- テスト方法: `K_kakeibo/test_keyword_extraction.py`
- SQL実行: `database/migrations/create_weighted_search_vector.sql`
