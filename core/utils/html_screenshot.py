"""
HTML to Screenshot Utility

PlaywrightでHTMLをスクリーンショット画像に変換（Async版）
"""
import base64
from pathlib import Path
from typing import Optional, Union
from playwright.async_api import async_playwright
from loguru import logger


class HTMLScreenshotGenerator:
    """HTMLをスクリーンショット画像に変換するクラス（Async対応）"""

    def __init__(self, viewport_width: int = 1200, viewport_height: int = 800):
        """
        初期化

        Args:
            viewport_width: ビューポート幅
            viewport_height: ビューポート高さ
        """
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height

    async def html_to_screenshot(
        self,
        html_content: str,
        output_path: Optional[Union[str, Path]] = None,
        full_page: bool = True
    ) -> bytes:
        """
        HTMLコンテンツをスクリーンショット画像に変換

        Args:
            html_content: HTML文字列
            output_path: 保存先パス（Noneの場合は保存しない）
            full_page: フルページスクリーンショット（Trueの場合）

        Returns:
            スクリーンショット画像のバイナリデータ（PNG形式）
        """
        try:
            async with async_playwright() as p:
                # ブラウザを起動（ヘッドレスモード）
                browser = await p.chromium.launch(headless=True)

                # ページを作成
                page = await browser.new_page(
                    viewport={'width': self.viewport_width, 'height': self.viewport_height}
                )

                # HTMLコンテンツを設定
                await page.set_content(html_content, wait_until='networkidle')

                # スクリーンショット撮影
                screenshot_bytes = await page.screenshot(
                    full_page=full_page,
                    type='png'
                )

                # ファイルに保存（オプション）
                if output_path:
                    output_path = Path(output_path)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(screenshot_bytes)
                    logger.info(f"スクリーンショット保存: {output_path}")

                await browser.close()
                return screenshot_bytes

        except Exception as e:
            logger.error(f"スクリーンショット生成エラー: {e}")
            raise

    async def html_to_base64(self, html_content: str, full_page: bool = True) -> str:
        """
        HTMLをBase64エンコードされた画像に変換

        Args:
            html_content: HTML文字列
            full_page: フルページスクリーンショット

        Returns:
            Base64エンコードされた画像文字列
        """
        screenshot_bytes = await self.html_to_screenshot(
            html_content=html_content,
            full_page=full_page
        )
        return base64.b64encode(screenshot_bytes).decode('utf-8')

    async def html_file_to_screenshot(
        self,
        html_file_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        full_page: bool = True
    ) -> bytes:
        """
        HTMLファイルをスクリーンショット画像に変換

        Args:
            html_file_path: HTMLファイルのパス
            output_path: 保存先パス（Noneの場合は保存しない）
            full_page: フルページスクリーンショット

        Returns:
            スクリーンショット画像のバイナリデータ（PNG形式）
        """
        html_file_path = Path(html_file_path)
        if not html_file_path.exists():
            raise FileNotFoundError(f"HTMLファイルが見つかりません: {html_file_path}")

        html_content = html_file_path.read_text(encoding='utf-8')
        return await self.html_to_screenshot(
            html_content=html_content,
            output_path=output_path,
            full_page=full_page
        )
