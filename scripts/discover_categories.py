"""
楽天西友ネットスーパーの実際のカテゴリー情報を取得

実行方法:
    python discover_categories.py
"""

import asyncio
import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

from B_ingestion.rakuten_seiyu.rakuten_seiyu_scraper_playwright import RakutenSeiyuScraperPlaywright

# 環境変数を読み込み
load_dotenv()

# ロガー設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def discover_categories():
    """実際のカテゴリー情報を取得"""

    rakuten_id = os.getenv("RAKUTEN_ID")
    password = os.getenv("RAKUTEN_PASSWORD")

    if not rakuten_id or not password:
        logger.error("❌ 環境変数 RAKUTEN_ID と RAKUTEN_PASSWORD を設定してください")
        return

    # スクレイパーを使用してログイン
    async with RakutenSeiyuScraperPlaywright() as scraper:
        await scraper.start(headless=False)

        # ログイン
        logger.info("🔐 ログイン中...")
        success = await scraper.login(rakuten_id, password)
        if not success:
            logger.error("❌ ログインに失敗しました")
            return

        page = scraper.page

        # トップページに戻る
        logger.info("🌐 トップページにアクセス中...")
        await page.goto("https://netsuper.rakuten.co.jp/seiyu", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # ページのHTMLを保存（デバッグ用）
        html_content = await page.content()
        with open("homepage_debug.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info("📄 ホームページHTMLを保存: homepage_debug.html")

        # カテゴリーリンクを探す
        logger.info("🔍 カテゴリーリンクを探索中...")

        # 複数のセレクターパターンを試す
        category_selectors = [
            'a[href*="/category/"]',
            'nav a[href*="/seiyu/"]',
            '.category-link',
            '[class*="category"] a',
        ]

        all_categories = []

        for selector in category_selectors:
            try:
                links = await page.query_selector_all(selector)
                logger.info(f"セレクター '{selector}': {len(links)}件のリンク発見")

                for link in links:
                    try:
                        href = await link.get_attribute('href')
                        text = await link.inner_text()

                        # 空のリンクやJavaScriptリンクをスキップ
                        if not href or href.startswith('javascript:') or not text:
                            continue

                        # カテゴリーIDを抽出（複数パターン対応）
                        category_id = None
                        if '/search/' in href:
                            parts = href.split('/search/')
                            if len(parts) > 1:
                                category_id = parts[1].split('?')[0].split('/')[0]
                        elif '/category/' in href:
                            parts = href.split('/category/')
                            if len(parts) > 1:
                                category_id = parts[1].split('?')[0].split('/')[0]
                        elif '/c/' in href:
                            parts = href.split('/c/')
                            if len(parts) > 1:
                                category_id = parts[1].split('?')[0].split('/')[0]

                        # 完全なURLを構築
                        full_url = href if href.startswith('http') else f"https://netsuper.rakuten.co.jp{href}"

                        category_info = {
                            'name': text.strip(),
                            'url': full_url,
                            'category_id': category_id,
                            'selector': selector
                        }

                        # 重複チェック（URLで判定）
                        if not any(cat['url'] == full_url for cat in all_categories):
                            all_categories.append(category_info)

                    except Exception as e:
                        continue

            except Exception as e:
                logger.debug(f"セレクター '{selector}' でエラー: {e}")
                continue

        # 結果を表示
        logger.info("\n" + "=" * 60)
        logger.info(f"✅ 発見したカテゴリー数: {len(all_categories)}件")
        logger.info("=" * 60)

        for i, cat in enumerate(all_categories, 1):
            logger.info(f"{i}. {cat['name']}")
            logger.info(f"   URL: {cat['url']}")
            logger.info(f"   ID: {cat['category_id']}")
            logger.info("")

        # JSONファイルに保存
        output_file = "_runtime/data/categories/discovered_categories.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "discovered_at": "2025-12-19",
                "total_categories": len(all_categories),
                "categories": all_categories
            }, f, indent=2, ensure_ascii=False)

        logger.info(f"💾 カテゴリー情報を保存: {output_file}")

        # 10秒待機してから終了（ユーザーが画面を確認できるように）
        logger.info("\n10秒後にブラウザを閉じます...")
        await page.wait_for_timeout(10000)


if __name__ == "__main__":
    asyncio.run(discover_categories())
