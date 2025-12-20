"""
楽天西友ネットスーパー スクレイピングモジュール (Playwright版 / 強化版)

Playwrightを使用してログイン状態を保持したまま商品データを取得します。
データ取得は以下の順で試行し、確実性を高めています：
1. JavaScript (Piniaストア) からの動的データ抽出（最優先）
2. HTML内のRATタグ（分析用隠しパラメータ）からの抽出（バックアップ）
3. DOM（表示要素）からの抽出（最終手段）
"""

import json
import re
import time
import random
import logging
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

# ロガー設定
logger = logging.getLogger(__name__)

class RakutenSeiyuScraperPlaywright:
    """楽天西友ネットスーパーのスクレイピングクラス (Playwright版)"""

    def __init__(self):
        self.base_url = "https://netsuper.rakuten.co.jp/seiyu"
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        """async with構文でのコンテキスト開始"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """async with構文でのコンテキスト終了"""
        await self.close()

    async def start(self, headless: bool = True):
        """
        ブラウザを起動
        Args:
            headless: ヘッドレスモードで起動するか
        """
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=headless)
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            self.page = await self.context.new_page()
            logger.info("✅ Playwrightブラウザ起動完了")

        except Exception as e:
            logger.error(f"ブラウザ起動エラー: {e}", exc_info=True)
            raise

    async def close(self):
        """ブラウザを閉じる"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("✅ ブラウザ終了")
        except Exception as e:
            logger.error(f"ブラウザ終了エラー: {e}", exc_info=True)

    async def _is_logged_in(self) -> bool:
        """ログイン状態をチェック"""
        try:
            page_content = await self.page.content()
            # ログイン時のみ表示される要素を確認
            return "ログアウト" in page_content or "マイページ" in page_content or "購入履歴" in page_content
        except:
            return False

    async def login(self, rakuten_id: str, password: str) -> bool:
        """
        楽天西友にログイン (堅牢版)
        """
        try:
            logger.info("🔐 楽天西友にログイン中...")

            # トップページにアクセス
            await self.page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(2000)

            # 既にログイン済みかチェック
            if await self._is_logged_in():
                logger.info("✅ 既にログイン済みです")
                return True

            # ログインボタンを探してクリック
            login_selectors = [
                'a:has-text("ログイン")',
                'button:has-text("ログイン")',
                '[data-test="login-button"]',
                '.login-button',
                '#login-link'
            ]

            login_clicked = False
            for selector in login_selectors:
                try:
                    login_button = await self.page.wait_for_selector(
                        selector, timeout=5000, state="visible"
                    )
                    if login_button:
                        await login_button.click()
                        login_clicked = True
                        logger.info(f"ログインボタンをクリック: {selector}")
                        break
                except Exception:
                    continue

            if not login_clicked:
                # 念のためもう一度ログイン確認
                if await self._is_logged_in():
                    logger.info("✅ 既にログイン済みです")
                    return True
                logger.error("ログイン画面に遷移できませんでした")
                return False

            await self.page.wait_for_load_state("domcontentloaded")

            # --- ステップ1: 楽天ID入力 ---
            logger.info("ステップ1: 楽天IDを入力中...")
            username_selectors = [
                'input[name="username"]',
                '#user_id',
                'input[autocomplete="username"]',
                'input[name="u"]',
                '#loginInner_u',
                'input[type="email"]'
            ]

            username_filled = False
            for selector in username_selectors:
                try:
                    username_input = await self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if username_input:
                        await username_input.click()
                        await username_input.fill(rakuten_id)
                        logger.info(f"✅ 楽天ID入力完了: {selector}")
                        username_filled = True
                        break
                except Exception:
                    continue

            if not username_filled:
                logger.error("楽天ID入力欄が見つかりませんでした")
                return False

            # 「次へ」ボタンをクリック
            next_button_selectors = [
                '#cta001',
                'div[role="button"]:has-text("次へ")',
                'button:has-text("次へ")',
                '[id*="cta"]',
                'button[type="submit"]',
                '.submit-button'
            ]

            next_clicked = False
            for selector in next_button_selectors:
                try:
                    next_button = await self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if next_button:
                        await next_button.click()
                        logger.info(f"「次へ」ボタンをクリック: {selector}")
                        next_clicked = True
                        await asyncio.sleep(0.5) # 短縮
                        await self.page.wait_for_load_state("domcontentloaded")
                        break
                except Exception:
                    continue

            # --- ステップ2: パスワード入力 ---
            logger.info("ステップ2: パスワードを入力中...")
            password_selectors = [
                '#password_current',
                'input[name="password"]',
                'input[autocomplete="current-password"]',
                'input[type="password"]'
            ]

            password_filled = False
            for selector in password_selectors:
                try:
                    password_input = await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                    if password_input:
                        await password_input.click()
                        await password_input.fill(password)
                        logger.info(f"✅ パスワード入力完了: {selector}")
                        password_filled = True
                        break
                except Exception:
                    continue

            if not password_filled:
                logger.error("パスワード入力欄が見つかりませんでした")
                return False

            # ログインボタンをクリック
            await asyncio.sleep(0.5) # 短縮
            login_button_selectors = [
                '#cta011',
                '#cta001',
                'div[role="button"]:has-text("ログイン")', # 文言が変わる場合あり
                '[id*="cta"]'
            ]

            login_clicked = False
            for selector in login_button_selectors:
                try:
                    login_button = await self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if login_button:
                        await login_button.click()
                        logger.info(f"ログインボタンをクリック: {selector}")
                        login_clicked = True
                        break
                except Exception:
                    continue

            if not login_clicked:
                logger.error("ログインボタンが見つかりませんでした")
                return False

            # ログイン完了を待機
            await asyncio.sleep(2) # 短縮
            await self.page.wait_for_load_state("domcontentloaded")

            # ログイン成功確認
            if await self._is_logged_in():
                logger.info("✅ ログイン成功")
                return True
            else:
                logger.error("❌ ログイン失敗")
                return False

        except Exception as e:
            logger.error(f"ログイン処理エラー: {e}", exc_info=True)
            return False

    async def fetch_products_page(
        self,
        category_url: str,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        カテゴリーページにアクセスし、商品データを取得する
        Returns:
            商品データのリスト
        """
        try:
            # URL構築
            if '?' in category_url:
                url = f"{category_url}&page={page}"
            else:
                url = f"{category_url}?page={page}"
            
            logger.info(f"商品ページ取得中: {url}")

            # ページ遷移
            await self.page.goto(url, wait_until="networkidle", timeout=60000)
            await self.page.wait_for_timeout(3000) # データロード待機

            # 商品データ抽出（3段構え）
            products = await self._extract_products_robust()
            
            # アクセス間隔制御
            await self.page.wait_for_timeout(random.randint(1000, 2000))

            return products

        except Exception as e:
            logger.error(f"商品ページ取得エラー: {e}", exc_info=True)
            return []

    async def _extract_products_robust(self) -> List[Dict[str, Any]]:
        """
        堅牢な商品データ抽出ロジック
        1. Piniaストア探索
        2. RATタグ解析
        3. DOM解析
        """
        products = []

        # --- 戦略1: Piniaストアからの抽出 (最優先) ---
        try:
            pinia_products = await self.page.evaluate("""
                () => {
                    const nuxt = window.__NUXT__;
                    if (!nuxt || !nuxt.pinia) return null;
                    
                    const pinia = nuxt.pinia;
                    const keys = Object.keys(pinia);
                    
                    // すべてのStoreを走査して商品配列っぽいものを探す
                    for (const key of keys) {
                        const store = pinia[key];
                        // オブジェクトでない場合はスキップ
                        if (!store || typeof store !== 'object') continue;

                        // Store内のプロパティを探索
                        for (const prop in store) {
                            const val = store[prop];
                            if (Array.isArray(val) && val.length > 0) {
                                // 配列の最初の要素をチェック
                                const first = val[0];
                                // 商品データの特徴を持つか？ (ID, 名前, 価格など)
                                if (first && (first.itemId || first.janCode) && (first.name || first.productName)) {
                                    return val;
                                }
                            }
                        }
                    }
                    return null;
                }
            """)

            if pinia_products and len(pinia_products) > 0:
                logger.info(f"✅ Piniaストアから {len(pinia_products)} 件の商品を抽出")
                for item in pinia_products:
                    p = self._parse_product_item(item)
                    if p: products.append(p)
                return products

        except Exception as e:
            logger.warning(f"Pinia抽出失敗: {e}")

        # --- 戦略2: RATタグからの抽出 (バックアップ) ---
        try:
            logger.info("⚠️ Pinia取得失敗、RATタグからの抽出を試みます")
            
            # 隠しinputタグから値を取得
            rat_ids_str = await self.page.get_attribute('#ratItemId', 'value')
            rat_prices_str = await self.page.get_attribute('#ratPrice', 'value')
            rat_genre = await self.page.get_attribute('#ratItemGenre', 'value')

            if rat_ids_str and rat_prices_str:
                ids = rat_ids_str.split(',')
                prices = rat_prices_str.split(',')
                
                logger.info(f"✅ RATタグから {len(ids)} 件のIDを発見")
                
                # 商品ごとの詳細情報をDOMから補完して構築
                # 注: RATにはIDと価格しかないため、名前などはDOMから取らないといけないが、
                # ここでは最低限のデータとして保存する
                for i, pid in enumerate(ids):
                    price = prices[i] if i < len(prices) else None
                    # IDの接頭辞 "seiyu_" を除去
                    clean_id = pid.replace("seiyu_", "")
                    
                    product = {
                        "product_name": f"商品ID_{clean_id}", # 仮の名前
                        "jan_code": clean_id,
                        "price": int(price) if price and price.isdigit() else None,
                        "category": rat_genre.split(',')[0] if rat_genre else None,
                        "in_stock": True, # リストにあるなら在庫ありとみなす
                        "source": "rat_tag"
                    }
                    products.append(product)
                
                return products

        except Exception as e:
            logger.warning(f"RATタグ抽出失敗: {e}")

        logger.error("❌ 全ての抽出方法が失敗しました")
        return []

    def _parse_product_item(self, item: dict) -> Optional[Dict[str, Any]]:
        """商品アイテムをパースして統一フォーマットに変換"""
        try:
            # 商品名
            product_name = item.get("name") or item.get("productName") or item.get("title")
            if not product_name: return None

            # 価格
            price = None
            price_data = item.get("price") or item.get("priceInfo") or {}
            if isinstance(price_data, dict):
                price = price_data.get("value") or price_data.get("price")
            elif isinstance(price_data, (int, float, str)):
                price = price_data

            # JANコード / ID
            jan_code = item.get("janCode") or item.get("itemId") or item.get("id")
            # "seiyu_" などのプレフィックスがあれば除去
            if jan_code and isinstance(jan_code, str):
                jan_code = jan_code.replace("seiyu_", "")

            # 画像URL
            image_url = item.get("imageUrl") or item.get("image") or item.get("thumbnailUrl")
            if image_url:
                image_url = self._fix_image_url(image_url)

            return {
                "product_name": product_name,
                "price": price,
                "jan_code": jan_code,
                "image_url": image_url,
                "manufacturer": item.get("manufacturer") or item.get("brand"),
                "category": item.get("category"),
                "in_stock": item.get("inStock", True),
                "raw_data": item
            }

        except Exception as e:
            logger.error(f"商品パースエラー: {e}")
            return None

    def _fix_image_url(self, url: str) -> str:
        if url.startswith("//"):
            return f"https:{url}"
        elif not url.startswith("http"):
            return f"{self.base_url}{url}"
        return url