# 楽天西友ネットスーパー スクレイピングツール 実装計画

## 実装概要

楽天西友ネットスーパーから商品データを自動取得し、Supabaseに保存する独立したスクレイピングツールを実装します。既存のトクバイパターンに従い、Phase 1からPhase 4まで完全実装します。

**主要機能:**
- 全カテゴリー・全ページの商品データ取得
- エリア設定（郵便番号）対応
- 価格履歴管理（日々の価格変動追跡）
- 定期実行による自動更新
- 既存のドキュメント管理システムとの統合

## 実装スコープ

✅ Phase 1: MVP（1カテゴリー・1ページ）
✅ Phase 2: 全ページ対応
✅ Phase 3: 全カテゴリー対応
✅ Phase 4: 統合・定期実行・価格履歴管理

## ディレクトリ構成

```
I:\マイドライブ\document-management-system\
├── B_ingestion/
│   └── rakuten_seiyu/                    # 新規作成
│       ├── __init__.py
│       ├── README.md                      # 使用方法ドキュメント
│       ├── rakuten_seiyu_scraper.py       # スクレイパークラス
│       ├── product_ingestion.py           # データパイプライン
│       ├── categories_config.json         # カテゴリー設定
│       └── schema.sql                     # データベーススキーマ
│
├── process_rakuten_seiyu.py               # メイン実行スクリプト（ルート）
└── requirements.txt                        # 依存関係更新
```

---

## Phase 1: MVP実装（1カテゴリー・1ページ）

### 1.1 rakuten_seiyu_scraper.py

**技術選択:** requests + BeautifulSoup + JSON解析

**主要クラス:**
```python
class RakutenSeiyuScraper:
    def __init__(self, area_zip_code: Optional[str] = None)
    def _set_area(self, zip_code: str) -> bool  # エリア設定
    def fetch_products_page(self, category_id: str, page: int = 1) -> Optional[str]
    def extract_products_from_html(self, html_content: str) -> List[Dict[str, Any]]
    def _fix_image_url(self, url: str) -> str
```

**重要な実装ポイント:**
- `window.__NUXT__` からJSONデータを正規表現で抽出
- エリア設定: 初回アクセス時にクッキーを設定（郵便番号POSTリクエスト）
- User-Agent設定とアクセス間隔制御（1～2秒のランダム）
- 画像URL修正（`//netsuper.r10s.jp/...` → `https://netsuper.r10s.jp/...`）

**参考ファイル:**
- `I:\マイドライブ\document-management-system\B_ingestion\tokubai\tokubai_scraper.py`

### 1.2 product_ingestion.py

**主要クラス:**
```python
class RakutenSeiyuProductIngestionPipeline:
    def __init__(self, zip_code: Optional[str] = None)
    async def check_existing_products(self, jan_codes: List[str]) -> set
    async def process_category_page(self, category_id: str, page: int) -> List[Dict]
    def _prepare_product_data(self, product: Dict[str, Any]) -> Dict[str, Any]
```

**処理フロー:**
1. 1ページのHTMLを取得
2. 商品データをJSON解析
3. JANコードで重複チェック
4. Supabaseに保存（`rakuten_seiyu_products`テーブル）

**参考ファイル:**
- `I:\マイドライブ\document-management-system\B_ingestion\tokubai\flyer_ingestion.py`

---

## Phase 2: 全ページ対応

### 2.1 ページネーション実装

**追加メソッド:**
```python
def scrape_category_all_pages(
    self,
    category_id: str,
    category_name: str,
    max_pages: int = 100
) -> List[Dict[str, Any]]
```

**実装内容:**
- ページ番号を増やしながらループ（`?page=1`, `?page=2`, ...）
- 商品がなくなるまで継続（空配列を検知したら終了）
- ページ間に1～2秒のランダム待機（`time.sleep(random.uniform(1.0, 2.0))`）
- 最大ページ数100の安全装置

### 2.2 アクセス制御強化

- User-Agent設定
- Refererヘッダー追加
- レート制限検知（HTTPステータス429）時の60秒待機
- タイムアウト処理（30秒）

---

## Phase 3: 全カテゴリー対応

### 3.1 カテゴリー管理

**categories_config.json:**
```json
{
  "categories": [
    {"id": "110001", "name": "野菜", "enabled": true},
    {"id": "110003", "name": "肉", "enabled": true},
    {"id": "120004", "name": "日用品", "enabled": true}
  ],
  "scraping_config": {
    "area_zip_code": "211-0063",
    "access_interval_min": 1.0,
    "access_interval_max": 2.0,
    "max_pages_per_category": 100
  }
}
```

### 3.2 メインループ

```python
async def main():
    config = load_categories_config()
    pipeline = RakutenSeiyuProductIngestionPipeline(zip_code=config['area_zip_code'])

    for category in enabled_categories:
        result = await pipeline.process_category(category['id'], category['name'])
        # カテゴリー間で3～5秒待機
        time.sleep(random.uniform(3.0, 5.0))
```

### 3.3 重複チェック強化

- JANコードでの重複排除
- 既存商品の価格更新検知
- ハッシュ値による完全一致チェック

---

## Phase 4: 統合・定期実行・価格履歴管理

### 4.1 データベーススキーマ

#### テーブル1: rakuten_seiyu_products（商品マスタ）

```sql
CREATE TABLE IF NOT EXISTS rakuten_seiyu_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 基本情報
    source_type VARCHAR(50) DEFAULT 'online_shop',
    workspace VARCHAR(50) DEFAULT 'shopping',
    doc_type VARCHAR(50) DEFAULT 'online shop',
    organization VARCHAR(255) DEFAULT '楽天西友ネットスーパー',

    -- 商品基本情報
    product_name VARCHAR(500) NOT NULL,
    product_name_normalized VARCHAR(500),
    jan_code VARCHAR(20),

    -- 現在の価格（最新価格）
    current_price DECIMAL(10, 2),
    current_price_tax_included DECIMAL(10, 2),
    price_text VARCHAR(255),

    -- 分類
    category VARCHAR(100),
    category_id VARCHAR(50),
    tags TEXT[],

    -- 商品詳細
    manufacturer VARCHAR(255),
    image_url TEXT,

    -- 在庫・販売状況
    in_stock BOOLEAN DEFAULT true,
    is_available BOOLEAN DEFAULT true,

    -- メタデータ
    metadata JSONB,

    -- 日付
    document_date DATE,
    last_scraped_at TIMESTAMPTZ DEFAULT NOW(),

    -- 表示用
    display_subject VARCHAR(500),
    display_sender VARCHAR(255),

    -- 検索用
    search_vector tsvector,

    -- ユニーク制約
    CONSTRAINT unique_rakuten_seiyu_jan_code UNIQUE(jan_code)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_category ON rakuten_seiyu_products(category);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_jan_code ON rakuten_seiyu_products(jan_code);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_price ON rakuten_seiyu_products(current_price);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_name ON rakuten_seiyu_products(product_name);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_scraped ON rakuten_seiyu_products(last_scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_rakuten_seiyu_products_search ON rakuten_seiyu_products USING GIN(search_vector);

-- 検索ベクトル自動更新トリガー
CREATE OR REPLACE FUNCTION update_rakuten_seiyu_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('japanese', COALESCE(NEW.product_name, '')), 'A') ||
        setweight(to_tsvector('japanese', COALESCE(NEW.manufacturer, '')), 'B') ||
        setweight(to_tsvector('japanese', COALESCE(NEW.category, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER rakuten_seiyu_search_vector_update
    BEFORE INSERT OR UPDATE ON rakuten_seiyu_products
    FOR EACH ROW
    EXECUTE FUNCTION update_rakuten_seiyu_search_vector();
```

#### テーブル2: rakuten_seiyu_price_history（価格履歴）

```sql
CREATE TABLE IF NOT EXISTS rakuten_seiyu_price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- 商品参照
    product_id UUID REFERENCES rakuten_seiyu_products(id) ON DELETE CASCADE,
    jan_code VARCHAR(20) NOT NULL,
    product_name VARCHAR(500),

    -- 価格情報
    price DECIMAL(10, 2) NOT NULL,
    price_tax_included DECIMAL(10, 2) NOT NULL,
    price_text VARCHAR(255),

    -- 在庫状況
    in_stock BOOLEAN DEFAULT true,

    -- 日付
    scraped_date DATE NOT NULL,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),

    -- メタデータ
    metadata JSONB,

    -- 複合ユニーク制約（1日1レコード）
    CONSTRAINT unique_price_record UNIQUE(jan_code, scraped_date)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_price_history_product_id ON rakuten_seiyu_price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_jan_code ON rakuten_seiyu_price_history(jan_code);
CREATE INDEX IF NOT EXISTS idx_price_history_date ON rakuten_seiyu_price_history(scraped_date DESC);
```

### 4.2 価格履歴管理

**実装内容:**
```python
async def update_product_and_record_history(
    self,
    product_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    商品マスタを更新し、価格履歴を記録

    処理フロー:
    1. JANコードで既存商品を検索
    2. 既存商品がある場合:
       - 価格が変わっていれば履歴テーブルに記録
       - current_price を更新
       - updated_at を更新
    3. 新規商品の場合:
       - rakuten_seiyu_products に挿入
       - 初回価格を履歴テーブルに記録
    """
```

**価格変動検知:**
- 前回の価格と比較
- 変更があれば `rakuten_seiyu_price_history` に記録
- 変更率の計算とログ出力

### 4.3 エリア設定実装

**実装方法:**
```python
def _set_area(self, zip_code: str) -> bool:
    """
    エリア設定（郵便番号）

    実装手順:
    1. トップページにアクセスしてセッションを確立
    2. エリア設定APIを探索（DevToolsでネットワークタブを確認）
    3. 郵便番号をPOSTリクエストで送信
    4. クッキーを保存して以降のリクエストで使用
    """
    # エリア設定エンドポイント（要調査）
    area_url = f"{self.base_url}/api/area/set"

    response = self.session.post(
        area_url,
        json={'zip_code': zip_code},
        headers=self.headers
    )

    if response.status_code == 200:
        logger.info(f"エリア設定成功: {zip_code}")
        return True
    else:
        logger.warning(f"エリア設定失敗: {response.status_code}")
        return False
```

**注意事項:**
- 実際のエリア設定APIは楽天西友のサイトを調査して特定
- クッキー名とパラメータはブラウザのDevToolsで確認
- エリア設定に失敗した場合は全国共通商品のみ取得

### 4.4 定期実行スクリプト

**process_rakuten_seiyu.py（プロジェクトルート）:**
```python
"""
楽天西友ネットスーパー 商品データ定期取得スクリプト

使用方法:
    python process_rakuten_seiyu.py --once              # 1回だけ実行
    python process_rakuten_seiyu.py --continuous        # 継続実行（24時間ごと）
    python process_rakuten_seiyu.py --categories 110001,110003  # 特定カテゴリーのみ
"""

import asyncio
import argparse
from pathlib import Path
from B_ingestion.rakuten_seiyu.product_ingestion import main as run_ingestion

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='1回だけ実行')
    parser.add_argument('--continuous', action='store_true', help='継続実行')
    parser.add_argument('--categories', type=str, help='カンマ区切りのカテゴリーID')
    args = parser.parse_args()

    if args.once:
        await run_ingestion(categories=args.categories)
    elif args.continuous:
        while True:
            await run_ingestion(categories=args.categories)
            await asyncio.sleep(86400)  # 24時間待機

if __name__ == "__main__":
    asyncio.run(main())
```

**Cron設定（Linux/Mac）:**
```bash
# 毎日午前3時に実行
0 3 * * * cd /path/to/project && /path/to/venv/bin/python process_rakuten_seiyu.py --once
```

**タスクスケジューラ（Windows）:**
- トリガー: 毎日午前3時
- 操作: `python.exe process_rakuten_seiyu.py --once`
- 開始: `I:\マイドライブ\document-management-system`

### 4.5 既存システムとの統合

**検索統合:**
- `rakuten_seiyu_products` の `search_vector` を活用
- 既存の統一検索APIに楽天西友商品を含める

**家計簿連携（K_kakeibo）:**
- レシートOCRで認識した商品名を `product_name_normalized` で検索
- JANコードが一致すればネットスーパー価格と比較
- 価格差をレビューUIに表示

**価格アラート（オプション）:**
- 特定商品の価格が閾値を下回ったらLINE通知
- `rakuten_seiyu_price_history` から価格トレンドを分析

---

## 実装の進め方

### ステップ1: Phase 1（MVP）実装
1. `B_ingestion/rakuten_seiyu/` ディレクトリ作成
2. `rakuten_seiyu_scraper.py` 実装（基本機能）
3. `product_ingestion.py` 実装（1ページ処理）
4. テスト: カテゴリー `110001`（野菜）の1ページ目

**完了条件:**
- 1ページから10～50件の商品が取得できる
- Supabaseに正しく保存される

### ステップ2: Phase 2（全ページ対応）
1. `scrape_category_all_pages()` 実装
2. ページネーション対応
3. アクセス制御強化
4. テスト: 1カテゴリーの全ページ（1,000件以上）

**完了条件:**
- 1カテゴリーの全商品が取得できる
- レート制限にかからない

### ステップ3: Phase 3（全カテゴリー対応）
1. `categories_config.json` 作成
2. メインループ実装
3. 重複チェック強化
4. テスト: 全カテゴリー処理

**完了条件:**
- 全カテゴリーの商品が取得できる
- 重複が排除される

### ステップ4: Phase 4（完全版）
1. 価格履歴テーブル作成（schema.sql）
2. 価格履歴管理機能実装
3. エリア設定機能実装
4. 定期実行スクリプト作成
5. 既存システムとの統合

**完了条件:**
- 定期実行が安定稼働
- 価格履歴が正しく記録される
- エリア設定が機能する

---

## 重要な参考ファイル

### スクレイパー実装の参考
- `I:\マイドライブ\document-management-system\B_ingestion\tokubai\tokubai_scraper.py`
  - requests + BeautifulSoup のパターン
  - HTMLからのデータ抽出
  - 画像ダウンロードとサイズチェック

### パイプライン実装の参考
- `I:\マイドライブ\document-management-system\B_ingestion\tokubai\flyer_ingestion.py`
  - 非同期処理パターン
  - Supabase登録
  - 重複チェック
  - 設定ファイル読み込み

### データベース操作の参考
- `I:\マイドライブ\document-management-system\A_common\database\client.py`
  - DatabaseClient の使用方法
  - insert_document, upsert_document
  - ベクトル形式への変換

### 設定ファイルの参考
- `I:\マイドライブ\document-management-system\B_ingestion\tokubai\stores_config.json`
  - JSON形式の設定ファイル
  - 店舗・カテゴリーの管理

---

## エラーハンドリング

### レート制限検知
```python
if response.status_code == 429:
    logger.warning("レート制限検知、60秒待機します")
    time.sleep(60)
    return self.fetch_products_page(category_id, page)  # リトライ
```

### JSON解析失敗
```python
try:
    nuxt_data = json.loads(match.group(1))
except json.JSONDecodeError as e:
    logger.error(f"JSON解析エラー: {e}")
    return []
```

### データベースエラー
```python
try:
    result = await self.db.insert_document('rakuten_seiyu_products', product_data)
except Exception as e:
    logger.error(f"Supabase保存エラー: {e}", exc_info=True)
    # 失敗した商品をファイルに記録
    with open('failed_products.json', 'a') as f:
        json.dump(product_data, f)
```

---

## テスト計画

### 単体テスト
```python
# tests/test_rakuten_seiyu_scraper.py

def test_extract_products_from_html():
    """HTMLからの商品抽出テスト"""
    scraper = RakutenSeiyuScraper()
    with open('test_data/sample_page.html', 'r') as f:
        html = f.read()
    products = scraper.extract_products_from_html(html)

    assert len(products) > 0
    assert 'product_name' in products[0]
    assert 'price' in products[0]
```

### 統合テスト
```python
async def test_full_pipeline():
    """全体パイプラインのテスト"""
    pipeline = RakutenSeiyuProductIngestionPipeline()
    result = await pipeline.process_category('110001', '野菜')

    assert result['total_products'] > 0
    assert result['new_products'] >= 0
```

---

## 運用モニタリング

### ログ出力
- 取得した商品数
- 新規商品数
- 価格変更商品数
- エラー発生数

### アラート条件
- 取得商品数が前回の50%以下
- エラー率が10%以上
- 3回連続で失敗

---

## 備考

### window.__NUXT__ の構造調査
実装前に楽天西友のHTMLソースから `window.__NUXT__` の実際の構造を確認する必要があります。ブラウザのDevToolsで以下を実行して調査：

```javascript
console.log(JSON.stringify(window.__NUXT__, null, 2));
```

商品データの配列がどこにあるか（例: `data[0].itemList`）を特定し、スクレイパーの実装に反映します。

### エリア設定APIの調査
ブラウザのDevToolsで郵便番号入力時のネットワークリクエストを監視し、以下を特定：
- エンドポイントURL
- リクエストメソッド（POST/GET）
- パラメータ（zip_code, postal_code など）
- クッキー名

---

## 実装完了後の確認事項

✅ 全カテゴリーの商品が取得できる
✅ 価格履歴が正しく記録される
✅ エリア設定が機能する
✅ 定期実行が安定稼働する
✅ レート制限にかからない
✅ エラーハンドリングが適切に動作する
✅ ログが十分に出力される
✅ 既存システムから検索できる

---

以上、楽天西友ネットスーパー スクレイピングツールの実装計画でした。
