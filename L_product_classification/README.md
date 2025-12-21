# 商品データ整理・自動分類システム

## 概要

5,000件以上のネットスーパー商品データを効率的に整理・分類するシステムです。

### コアアーキテクチャ

- **2段階辞書**: Tier 1（名寄せ） → Tier 2（分類）
- **文脈判定**: source_type, organization等で「食材」「外食」を自動判別
- **Gemini Flash統合**: バッチクラスタリング + 日次Few-shot推論
- **3つのStreamlit UI**: 一括承認、日次インボックス、カテゴリツリー編集

---

## システム構成

### データベース

**新規作成テーブル:**
- `70_ms_product_normalization`: Tier 1名寄せ辞書（N:1マッピング）
- `70_ms_product_classification`: Tier 2分類辞書（1:1マッピング）
- `99_tmp_gemini_clustering`: Geminiクラスタリング結果（一時）
- `99_lg_gemini_classification_log`: Gemini操作ログ

**既存テーブル拡張:**
- `80_rd_products`: general_name, category_id, needs_approval, classification_confidence カラム追加
- `60_ms_categories`: 「食材」「外食」を「食費」の子カテゴリとして追加

### ファイル構成

```
B_ingestion/
  common/
    base_product_ingestion.py       # 共通基盤クラス（302行）
  tokyu_store/
    product_ingestion.py             # 東急ストア（193行 ← 457行）
  rakuten_seiyu/
    product_ingestion.py             # 楽天西友（189行 ← 430行）
  daiei/
    product_ingestion.py             # ダイエー（125行 ← 388行）

L_product_classification/
  gemini_batch_clustering.py         # Geminiバッチクラスタリング
  daily_auto_classifier.py           # 日次自動分類エンジン
  ui_bulk_clustering.py              # UI-1: 一括承認画面
  ui_daily_inbox.py                  # UI-2: 日次インボックス
  ui_category_tree.py                # UI-3: カテゴリツリー編集
  cron_daily_classification.sh       # Cron実行スクリプト

database/
  migrations/
    create_product_classification_system.sql  # DB schema定義
```

---

## セットアップ手順

### 1. データベースマイグレーション

```bash
cd /Users/ookuboyoshinori/document_management_system

# Supabase CLIの場合
supabase db push

# psqlの場合
psql -h <host> -U <user> -d <database> -f database/migrations/create_product_classification_system.sql
```

### 2. 初期クラスタリング実行

```bash
# 5,000件の既存商品をGeminiでクラスタリング
python L_product_classification/gemini_batch_clustering.py
```

### 3. UI-1で一括承認

```bash
# Streamlit UI起動
streamlit run L_product_classification/ui_bulk_clustering.py
```

ブラウザで `http://localhost:8501` を開き、クラスタを確認・承認します。

### 4. 日次分類エンジンをCronに登録

```bash
# crontab編集
crontab -e

# 以下を追加（毎日3:00 AMに実行）
0 3 * * * /Users/ookuboyoshinori/document_management_system/L_product_classification/cron_daily_classification.sh >> /var/log/product_classification.log 2>&1
```

---

## 運用ワークフロー

### 初回セットアップ（一度のみ）

1. **データベースマイグレーション**
   ```bash
   psql -h <host> -U <user> -d <database> -f database/migrations/create_product_classification_system.sql
   ```

2. **Geminiバッチクラスタリング実行**
   ```bash
   python L_product_classification/gemini_batch_clustering.py
   ```
   - 5,000件の商品を100件ずつバッチ処理
   - `99_tmp_gemini_clustering` にクラスタが保存される

3. **UI-1で一括承認**
   ```bash
   streamlit run L_product_classification/ui_bulk_clustering.py
   ```
   - クラスタを確認し、チェックボックスで選択
   - 「選択を一括承認」をクリック
   - → Tier 1/2辞書に登録され、商品の `general_name` と `category_id` が更新される

### 日次運用

#### 自動処理（Cron）

毎日3:00 AMに `daily_auto_classifier.py` が自動実行され:

1. **Tier 1 lookup**: 商品名 → general_name
2. **Tier 2 lookup**: general_name + context → category_id
3. **Gemini few-shot**: Tier 1/2で見つからない場合、Geminiで推論

#### 手動承認（UI-2）

信頼度90%未満の商品は `needs_approval = True` となり、UI-2で確認:

```bash
streamlit run L_product_classification/ui_daily_inbox.py
```

- 🟢 高信頼度 (≥90%)
- 🟡 中信頼度 (70-90%)
- 🔴 要確認 (<70%)

#### カテゴリ編集（UI-3）

カテゴリの追加・削除・階層管理:

```bash
streamlit run L_product_classification/ui_category_tree.py
```

---

## 実行コマンド一覧

### バッチクラスタリング

```bash
# 5,000件の商品をクラスタリング
python L_product_classification/gemini_batch_clustering.py
```

### 日次分類エンジン

```bash
# 未分類商品を自動分類（最大1,000件）
python L_product_classification/daily_auto_classifier.py
```

### Streamlit UI起動

```bash
# UI-1: 一括クラスタリング承認
streamlit run L_product_classification/ui_bulk_clustering.py

# UI-2: 日次承認インボックス
streamlit run L_product_classification/ui_daily_inbox.py

# UI-3: カテゴリツリー編集
streamlit run L_product_classification/ui_category_tree.py
```

---

## 技術仕様

### 2段階辞書の仕組み

#### Tier 1: 名寄せ辞書（N:1マッピング）

表記ゆれを吸収し、複数の商品名を1つの一般名詞に統合:

```
明治おいしい牛乳 1000ml → 牛乳
メグミルク低脂肪乳 500ml → 牛乳
タカナシ牛乳 900ml → 牛乳
```

**テーブル:** `70_ms_product_normalization`

#### Tier 2: 文脈分類辞書（1:1マッピング）

general_name + 文脈（source_type, workspace, organization）でカテゴリを判定:

```
牛乳 + (source_type=online_shop, workspace=shopping) → 食材
牛乳 + (source_type=receipt, workspace=shopping, organization=スーパー) → 食材
牛乳 + (source_type=receipt, workspace=shopping, organization=レストラン) → 外食
```

**テーブル:** `70_ms_product_classification`

### 3段階フォールバック分類

```
1. Tier 1 lookup: 商品名 → general_name
   ↓ 見つかった？
2. Tier 2 lookup: general_name + context → category_id
   ↓ 見つかった？
3. Gemini few-shot推論: 過去20件の承認済みデータを参考に推論
   ↓
   category_id取得
```

### Geminiモデル使用

- **バッチクラスタリング**: `gemini-2.5-flash`（高精度）
- **日次推論**: `gemini-2.5-flash-lite`（コスト効率）

---

## トラブルシューティング

### クラスタリングが失敗する

**原因**: Gemini APIのレート制限

**対策**: `gemini_batch_clustering.py` の `batch_size` を50に減らす

```python
clustering = GeminiBatchClustering(batch_size=50)  # デフォルト100
```

### 分類信頼度が低い

**原因**: Few-shot例が不足

**対策**: UI-1で承認済みデータを増やす（最低100件推奨）

### カテゴリが見つからない

**原因**: `60_ms_categories` に「食材」カテゴリが存在しない

**対策**: マイグレーション再実行、またはUI-3で手動追加

---

## ログ確認

### Gemini操作ログ

```sql
SELECT
  operation_type,
  model_name,
  confidence_score,
  created_at
FROM "99_lg_gemini_classification_log"
ORDER BY created_at DESC
LIMIT 100;
```

### Cron実行ログ

```bash
tail -f /var/log/product_classification.log
```

---

## パフォーマンス指標

### コード削減実績

- **東急ストア**: 457行 → 193行（58%減）
- **楽天西友**: 430行 → 189行（56%減）
- **ダイエー**: 388行 → 125行（68%減）
- **合計**: 768行の重複コード削除

### 処理速度

- **バッチクラスタリング**: 5,000件 → 約50バッチ × 3秒 ≈ 2.5分
- **日次分類**: 1,000件 × 0.5秒 ≈ 8.3分（Tier 1/2ヒット時は即座）

### コスト試算

- **Gemini Flash**: $0.64/1M入力トークン
- **5,000件クラスタリング**: 約50バッチ × 2,000トークン ≈ $0.064
- **日次1,000件**: Tier 1/2ヒット率80%と仮定 → 200件 × 1,000トークン ≈ $0.013/日

---

## 次のステップ

### 推奨実装順序

1. **Phase 1 → Phase 3 → Phase 4.1**: DB + クラスタリング + UI-1で初期5,000件処理
2. **Phase 5.1 → Phase 4.2**: 日次エンジン + UI-2で運用開始
3. **Phase 4.3**: カテゴリ編集UI（必要に応じて）

### 拡張アイデア

- **レシート分類への対応**: Tier 2に `organization=スーパー/レストラン` を追加
- **定期レポート**: 週次で分類精度レポートを自動生成
- **Slack通知**: 要承認商品が100件を超えたら通知

---

## 技術的な設計判断

### 1. 2段階辞書の分離理由

**再利用性**: 同じgeneral_name（例: 牛乳）でも文脈で異なるカテゴリに分類
- net_super → 食材
- restaurant → 外食

**スケーラビリティ**: 表記ゆれ吸収（Tier 1）と文脈分類（Tier 2）を独立管理

### 2. 文脈判定に使用するメタデータ

- `source_type="online_shop"` → 自動的に「食材」カテゴリ
- `organization`（店名） → 将来のレシート処理で「スーパー」「レストラン」判別

### 3. Geminiモデル選択

- **バッチクラスタリング**: gemini-2.5-flash（高精度）
- **日次推論**: gemini-2.5-flash-lite（コスト効率）

### 4. 既存パターン活用

- **DatabaseClient**: `DatabaseClient(use_service_role=True)` でRLSバイパス
- **LLMClient**: `call_model(tier="...", model_name="...")` で統一API
- **Streamlit UI**: K_kakeibo/review_ui.pyの承認ワークフローパターン踏襲

---

## まとめ

このシステムにより:

✅ **5,000件の商品を効率的に整理**
✅ **表記ゆれを自動吸収**
✅ **文脈に応じた自動分類**
✅ **Gemini Flashによる高精度クラスタリング**
✅ **3つの使いやすいUI**
✅ **完全自動化された日次運用**

これで家計簿システムの商品マスタ整理が完了します！
