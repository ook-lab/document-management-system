# チラシ処理パイプライン

スーパーマーケットのチラシ画像から商品情報を抽出し、検索可能にするパイプライン

## 処理フロー

```
1. チラシ取得 (flyer_ingestion.py)
   ↓
   flyer_documents (processing_status='pending')
   ↓
2. チラシ処理 (process_queued_flyers.py)
   ├─ Pre-processing: 画像ダウンロード
   ├─ Stage B (Gemini Vision 2段階):
   │  ├─ Step 1: OCR + レイアウト解析
   │  └─ Step 2: 商品情報の構造化抽出
   ├─ Stage C (Haiku): 構造化データの最終整理
   ├─ Stage A (Gemini): 要約生成
   └─ チャンク化・ベクトル化
   ↓
   flyer_documents (processing_status='completed')
   flyer_products (商品情報)
   search_index (検索用チャンク)
```

## ファイル構成

```
document-management-system/
├── B_ingestion/tokubai/
│   ├── flyer_ingestion.py           # チラシ取得スクリプト
│   ├── tokubai_scraper.py           # トクバイスクレイパー
│   └── stores_config.json           # 店舗設定
├── E_stage_b_vision/
│   └── flyer_vision_processor.py    # Stage B: Gemini Vision 2段階処理
├── process_queued_flyers.py         # チラシ処理メインスクリプト
└── database/migrations/
    └── create_flyer_schema.sql      # スキーマ定義
```

## 使い方

### 1. Supabaseでスキーマを作成

```bash
# Supabaseダッシュボードで create_flyer_schema.sql を実行
```

### 2. 環境変数を設定

`.env` に以下を追加：

```env
# トクバイ設定
TOKUBAI_STORE_URL=https://tokubai.co.jp/フーディアム/7978
TOKUBAI_FLYER_FOLDER_ID=1uQEJbV94mBC2y0D0FQztDGrzy6UNgEhv
TOKUBAI_STORE_NAME=フーディアム 武蔵小杉

# AI API キー
GOOGLE_AI_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_claude_api_key
```

### 3. チラシを取得

```bash
# 全店舗のチラシを取得
python B_ingestion/tokubai/flyer_ingestion.py

# 結果: flyer_documents テーブルに processing_status='pending' で保存される
```

### 4. チラシを処理

```bash
# 処理待ちチラシを10件処理
python process_queued_flyers.py

# 処理件数を指定
python process_queued_flyers.py --limit=50

# 特定の店舗のみ処理
python process_queued_flyers.py --store="フーディアム 武蔵小杉"

# ドライラン（確認のみ）
python process_queued_flyers.py --dry-run
```

## 処理の詳細

### Stage B: Gemini Vision（2段階処理）

#### Step 1: OCR + レイアウト解析

```python
# プロンプトスキーマ: E_stage_b_vision/flyer_vision_processor.py

出力:
{
  "full_text": "チラシ全体のテキスト",
  "sections": [
    {
      "section_name": "野菜・果物",
      "position": "上部",
      "items_text": "このセクションのテキスト"
    }
  ],
  "flyer_info": {
    "valid_period": "12/18〜12/24",
    "special_offers": ["タイムセール"],
    "catchphrases": ["年末大感謝祭"]
  }
}
```

#### Step 2: 商品情報の構造化抽出

```python
出力:
{
  "products": [
    {
      "product_name": "国産キャベツ",
      "price": 98,
      "price_unit": "円",
      "price_text": "98円",
      "category": "野菜",
      "quantity": "1玉",
      "origin": "国産",
      "is_special_offer": true,
      "offer_type": "日替わり",
      "extracted_text": "国産キャベツ 1玉 98円",
      "confidence": 0.95
    }
  ],
  "total_products": 1
}
```

### Stage C: Haiku構造化

- `attachment_text` の整理
- `metadata` の抽出
- `tags` の生成

### Stage A: Gemini要約

- チラシ全体のサマリー生成

### チャンク化・ベクトル化

- メタデータチャンク（店舗名、商品カテゴリなど）
- OpenAI Embedding生成
- `search_index` テーブルに保存

## データベーススキーマ

### flyer_documents テーブル

チラシ基本情報を管理

```sql
SELECT
  organization,        -- 店舗名
  flyer_title,         -- チラシタイトル
  flyer_period,        -- 有効期間
  page_number,         -- ページ番号
  attachment_text,     -- OCR抽出テキスト
  summary,             -- AI生成サマリー
  processing_status    -- pending/completed/failed
FROM flyer_documents;
```

### flyer_products テーブル

商品情報を管理

```sql
SELECT
  p.product_name,
  p.price,
  p.category,
  p.is_special_offer,
  f.organization
FROM flyer_products p
JOIN flyer_documents f ON p.flyer_document_id = f.id
WHERE p.category = '野菜'
ORDER BY p.price;
```

### search_index テーブル

検索用チャンクを管理

```sql
SELECT
  chunk_content,
  chunk_type,
  search_weight
FROM search_index
WHERE document_id = 'flyer_doc_id';
```

## 検索例

### 店舗別のチラシを検索

```sql
SELECT * FROM flyer_documents
WHERE organization = 'フーディアム 武蔵小杉'
ORDER BY created_at DESC;
```

### 特売商品を検索

```sql
SELECT
  p.*,
  f.organization,
  f.flyer_period
FROM flyer_products p
JOIN flyer_documents f ON p.flyer_document_id = f.id
WHERE p.is_special_offer = true
AND f.valid_until >= CURRENT_DATE
ORDER BY p.price;
```

### カテゴリ別の商品を検索

```sql
SELECT
  p.product_name,
  p.price,
  p.origin,
  f.organization
FROM flyer_products p
JOIN flyer_documents f ON p.flyer_document_id = f.id
WHERE p.category = '野菜'
ORDER BY p.price;
```

### 商品名で検索

```sql
SELECT * FROM flyer_products
WHERE product_name_normalized ILIKE '%トマト%';
```

## トラブルシューティング

### チラシが取得できない

- `stores_config.json` の URL が正しいか確認
- トクバイのウェブサイト構造が変更されていないか確認

### 商品情報が抽出できない

- Gemini API キーが設定されているか確認
- Step 1 の OCR 結果を確認（ログに出力される）
- プロンプトスキーマを調整

### 処理が遅い

- `--limit` で処理件数を減らす
- 特定の店舗のみ処理（`--store`）

## モデル情報

- **Stage B (Vision)**: Gemini 2.0 Flash Exp
- **Stage C (構造化)**: Claude Haiku 4.5
- **Stage A (要約)**: Gemini 2.5 Flash
- **Embedding**: OpenAI text-embedding-3-small (1536次元)

## 注意事項

1. **API コスト**: Gemini Vision は画像処理のためコストが高い
2. **処理時間**: 1チラシあたり30秒〜1分程度
3. **精度**: OCR精度はチラシの画質に依存
4. **重複**: 同じチラシを複数回処理しないよう `flyer_id` でチェック

## 今後の改善

- [ ] Step 2 のプロンプト最適化（商品抽出精度向上）
- [ ] エラーリトライ機能
- [ ] 処理進捗の可視化
- [ ] 商品画像の切り出しと保存
- [ ] 価格変動の追跡機能
