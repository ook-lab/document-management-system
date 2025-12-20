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
document_management_system/
├── B_ingestion/
│   └── rakuten_seiyu/
│       ├── __init__.py
│       ├── README.md                              # 使用方法ドキュメント
│       ├── auth_manager.py                        # ログイン＆Cookie取得（Playwright）※旧版
│       ├── rakuten_seiyu_scraper_playwright.py    # スクレイパークラス（Playwright統合版）
│       ├── product_ingestion.py                   # データパイプライン
│       ├── categories_config.json                 # カテゴリー設定
│       └── schema.sql                             # データベーススキーマ
│
├── process_rakuten_seiyu.py                       # メイン実行スクリプト（ルート）
└── requirements.txt                                # 依存関係更新
```

---

## Phase 1: MVP実装（1カテゴリー・1ページ）

### アーキテクチャ概要: Playwright統合構成

楽天西友では**地域（配送エリア）ごとに在庫・価格が異なる**ため、正確なデータを取得するにはログインが必須です。

そのため**Playwright**を使用してブラウザセッションを維持したまま、ログインから商品データ取得まで一貫して処理します：

1. **Playwright統合**: `rakuten_seiyu_scraper_playwright.py`
   - ヘッドレスブラウザで楽天IDログイン
   - ログイン状態を保持したまま商品ページを取得
   - `window.__NUXT__` から商品JSONデータを抽出

2. **データパイプライン**: `product_ingestion.py`
   - スクレイパーを使用して商品データを取得
   - JANコードで重複チェック
   - Supabaseに保存（新規登録 or 更新）

**メリット:**
- ✅ 確実性: 正規の手順でログインし、ログイン状態を維持したままデータ取得
- ✅ シンプル: 認証からデータ取得まで一貫したPlaywrightフロー
- ✅ 安定性: ブラウザセッションを維持するため認証エラーが発生しにくい

---

### 1.1 auth_manager.py（新規作成）

**役割:** ログイン処理とCookie取得

**技術:** Playwright（ヘッドレスブラウザ）

**主要クラス:**
```python
class RakutenSeiyuAuthManager:
    def __init__(self, headless: bool = True)
    async def login(self, rakuten_id: str, password: str) -> bool
    async def set_delivery_area(self, zip_code: str) -> bool
    async def save_cookies(self, file_path: str = "rakuten_seiyu_cookies.json") -> bool
    async def close()
```

**実装フロー:**
1. Playwrightでブラウザ起動
2. 楽天西友トップページにアクセス
3. 「ログイン」ボタンをクリック
4. 楽天ID・パスワードを入力
5. 配送先設定画面で郵便番号を入力
6. セッションCookieを取得してJSON保存
7. ブラウザを閉じる

**参考ファイル:**
- `B_ingestion/waseda_academy/main_chrome.py`（Playwrightの使用例）

---

### 1.2 rakuten_seiyu_scraper.py

**技術選択:** requests + BeautifulSoup + JSON解析

**主要クラス:**
```python
class RakutenSeiyuScraper:
    def __init__(self, cookies_file: Optional[str] = None)
    def load_cookies_from_file(self, file_path: str) -> bool
    def fetch_products_page(self, category_id: str, page: int = 1) -> Optional[str]
    def extract_products_from_html(self, html_content: str) -> List[Dict[str, Any]]
    def _fix_image_url(self, url: str) -> str
```

**重要な実装ポイント:**
- `window.__NUXT__` からJSONデータを正規表現で抽出
- **Cookie読み込み**: `auth_manager`が保存したCookieをセット
- User-Agent設定とアクセス間隔制御（1～2秒のランダム）
- 画像URL修正（`//netsuper.r10s.jp/...` → `https://netsuper.r10s.jp/...`）

**修正内容:**
- ❌ 削除: `_set_area()` メソッド（エリア設定は`auth_manager`に任せる）
- ✅ 追加: `load_cookies_from_file()` メソッド

**参考ファイル:**
- `I:\マイドライブ\document-management-system\B_ingestion\tokubai\tokubai_scraper.py`

### 1.3 product_ingestion.py

**主要クラス:**
```python
class RakutenSeiyuProductIngestionPipeline:
    def __init__(self, cookies_file: Optional[str] = None)
    async def check_existing_products(self, jan_codes: List[str]) -> set
    async def process_category_page(self, category_id: str, page: int) -> List[Dict]
    def _prepare_product_data(self, product: Dict[str, Any]) -> Dict[str, Any]
```

**処理フロー:**
1. `auth_manager`で取得したCookieファイルを指定
2. `rakuten_seiyu_scraper`にCookieを渡して初期化
3. 1ページのHTMLを取得
4. 商品データをJSON解析
5. JANコードで重複チェック
6. Supabaseに保存（`rakuten_seiyu_products`テーブル）

**修正内容:**
- ✅ 追加: コンストラクタに`cookies_file`パラメータ
- ✅ 追加: スクレイパー初期化時にCookieを渡す処理

**参考ファイル:**
- `I:\マイドライブ\document-management-system\B_ingestion\tokubai\flyer_ingestion.py`

---

### 1.4 実装の流れ（Phase 1）

```python
# ステップ1: 認証してCookie取得（初回のみ、または有効期限切れ時）
from B_ingestion.rakuten_seiyu.auth_manager import RakutenSeiyuAuthManager

auth = RakutenSeiyuAuthManager()
await auth.login(rakuten_id="your_id", password="your_password")
await auth.set_delivery_area(zip_code="211-0063")
await auth.save_cookies("rakuten_seiyu_cookies.json")
await auth.close()

# ステップ2: Cookieを使って高速収集
from B_ingestion.rakuten_seiyu.product_ingestion import RakutenSeiyuProductIngestionPipeline

pipeline = RakutenSeiyuProductIngestionPipeline(cookies_file="rakuten_seiyu_cookies.json")
result = await pipeline.process_category_page(category_id="110001", page=1)
```

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

### 4.3 Cookie有効期限管理

**実装方法:**
```python
async def ensure_valid_session(
    self,
    cookies_file: str = "rakuten_seiyu_cookies.json",
    max_age_hours: int = 24
) -> bool:
    """
    Cookieの有効性をチェックし、必要なら再認証

    処理フロー:
    1. Cookieファイルの最終更新時刻を確認
    2. max_age_hours を超えていたら再認証
    3. テストリクエストを送信してCookieが有効か確認
    4. 無効なら auth_manager で再認証
    """
    if not os.path.exists(cookies_file):
        logger.warning("Cookie file not found, re-authenticating...")
        return await self._re_authenticate()

    # ファイルの最終更新時刻をチェック
    file_age = time.time() - os.path.getmtime(cookies_file)
    if file_age > max_age_hours * 3600:
        logger.info(f"Cookies expired ({file_age/3600:.1f}h old), re-authenticating...")
        return await self._re_authenticate()

    # テストリクエストで有効性を確認
    test_response = self.session.get(f"{self.base_url}/api/test")
    if test_response.status_code == 401:
        logger.warning("Cookies invalid, re-authenticating...")
        return await self._re_authenticate()

    logger.info("Cookies valid")
    return True

async def _re_authenticate(self) -> bool:
    """auth_manager を使って再認証"""
    from .auth_manager import RakutenSeiyuAuthManager

    auth = RakutenSeiyuAuthManager()
    success = await auth.login(
        rakuten_id=os.getenv("RAKUTEN_ID"),
        password=os.getenv("RAKUTEN_PASSWORD")
    )
    if success:
        await auth.set_delivery_area(os.getenv("DELIVERY_ZIP_CODE"))
        await auth.save_cookies("rakuten_seiyu_cookies.json")
    await auth.close()
    return success
```

**注意事項:**
- Cookie有効期限は通常24時間程度（サイトによる）
- 定期実行時は毎回有効性をチェック
- 認証情報は環境変数で管理（`.env`ファイル）

### 4.4 定期実行スクリプト

**process_rakuten_seiyu.py（プロジェクトルート）:**
```python
"""
楽天西友ネットスーパー 商品データ定期取得スクリプト

使用方法:
    # 初回: ログインしてCookie取得
    python process_rakuten_seiyu.py --auth

    # 商品データ取得
    python process_rakuten_seiyu.py --once              # 1回だけ実行
    python process_rakuten_seiyu.py --continuous        # 継続実行（24時間ごと）
    python process_rakuten_seiyu.py --categories 110001,110003  # 特定カテゴリーのみ
"""

import asyncio
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv
from B_ingestion.rakuten_seiyu.auth_manager import RakutenSeiyuAuthManager
from B_ingestion.rakuten_seiyu.product_ingestion import main as run_ingestion

load_dotenv()

async def authenticate():
    """ログインしてCookieを保存"""
    print("🔐 楽天西友にログイン中...")
    auth = RakutenSeiyuAuthManager()

    success = await auth.login(
        rakuten_id=os.getenv("RAKUTEN_ID"),
        password=os.getenv("RAKUTEN_PASSWORD")
    )

    if not success:
        print("❌ ログイン失敗")
        return False

    await auth.set_delivery_area(os.getenv("DELIVERY_ZIP_CODE", "211-0063"))
    await auth.save_cookies("rakuten_seiyu_cookies.json")
    await auth.close()

    print("✅ Cookie保存完了")
    return True

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--auth', action='store_true', help='ログインしてCookie取得')
    parser.add_argument('--once', action='store_true', help='1回だけ実行')
    parser.add_argument('--continuous', action='store_true', help='継続実行')
    parser.add_argument('--categories', type=str, help='カンマ区切りのカテゴリーID')
    args = parser.parse_args()

    if args.auth:
        await authenticate()
        return

    if args.once:
        await run_ingestion(categories=args.categories)
    elif args.continuous:
        while True:
            await run_ingestion(categories=args.categories)
            await asyncio.sleep(86400)  # 24時間待機
    else:
        parser.print_help()

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
2. **`auth_manager.py` 実装（ログイン・Cookie取得）**
3. `rakuten_seiyu_scraper.py` 実装（Cookie読み込み機能）
4. `product_ingestion.py` 実装（1ページ処理）
5. `.env` ファイルに認証情報を追加
6. テスト: `python process_rakuten_seiyu.py --auth` でCookie取得
7. テスト: カテゴリー `110001`（野菜）の1ページ目

**完了条件:**
- ログインが成功し、Cookieが保存される
- Cookieを使って1ページから10～50件の商品が取得できる
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

### ログインフローの調査
Playwrightで自動化する前に、手動でログインフローを確認：

1. **ログインボタンの特定**
   - セレクタ: `button:has-text("ログイン")` など
   - URLパターン: `/login` または `/auth`

2. **楽天ID認証画面の要素**
   - ユーザー名入力欄: `input[name="u"]` または `#loginInner_u`
   - パスワード入力欄: `input[name="p"]` または `#loginInner_p`
   - ログインボタン: `button[type="submit"]`

3. **配送先設定の要素**
   - 郵便番号入力欄のセレクタ
   - 「この住所に配送」ボタンのセレクタ

4. **Cookie名の確認**
   - DevToolsの Application > Cookies で認証後のCookieを確認
   - セッションIDやトークンの名前をメモ

**参考:** `B_ingestion/waseda_academy/main_chrome.py:89-120` でPlaywrightの要素待機・クリック処理を確認

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
