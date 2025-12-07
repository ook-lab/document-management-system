"""
Email Vision Processor

HTMLメールをスクリーンショット化してGemini 2.0 Flash-LiteでVision解析
+ HTMLからのテキスト抽出とインテリジェントマージ
"""
import base64
from typing import Dict, Any, Optional, List
from loguru import logger
from bs4 import BeautifulSoup
import re

from core.utils.html_screenshot import HTMLScreenshotGenerator
from core.ai.llm_client import LLMClient
from config.model_tiers import ModelTier


class EmailVisionProcessor:
    """HTMLメールをVision APIで解析するプロセッサ"""

    def __init__(self):
        """初期化"""
        self.screenshot_generator = HTMLScreenshotGenerator(
            viewport_width=1200,
            viewport_height=800
        )
        self.llm_client = LLMClient()
        self.model_config = ModelTier.EMAIL_VISION

        logger.info(f"EmailVisionProcessor初期化: {self.model_config['model']}")

    def _extract_html_text(self, html_content: str) -> Dict[str, Any]:
        """
        HTMLからテキストとリンクを抽出

        Args:
            html_content: HTML文字列

        Returns:
            {
                'text': str,  # 抽出されたテキスト
                'links': List[str],  # URLリスト
                'has_tables': bool,  # テーブルがあるか
                'has_lists': bool  # リストがあるか
            }
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # スクリプトとスタイルを除去
            for script in soup(['script', 'style']):
                script.decompose()

            # テキストを抽出
            text = soup.get_text(separator='\n', strip=True)

            # 空行を削減（連続する改行を2つまでに）
            text = re.sub(r'\n{3,}', '\n\n', text)

            # リンクを抽出
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('http://') or href.startswith('https://'):
                    links.append(href)

            # テーブルとリストの存在チェック
            has_tables = len(soup.find_all('table')) > 0
            has_lists = len(soup.find_all(['ul', 'ol'])) > 0

            logger.info(f"HTML解析: テキスト={len(text)}文字, リンク={len(links)}個, テーブル={has_tables}, リスト={has_lists}")

            return {
                'text': text,
                'links': links,
                'has_tables': has_tables,
                'has_lists': has_lists
            }

        except Exception as e:
            logger.error(f"HTMLテキスト抽出エラー: {e}")
            return {
                'text': '',
                'links': [],
                'has_tables': False,
                'has_lists': False
            }

    def _merge_vision_and_html(
        self,
        vision_result: Dict[str, Any],
        html_extract: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Vision解析結果とHTML抽出結果をインテリジェントにマージ

        Args:
            vision_result: Vision APIの解析結果
            html_extract: HTMLから抽出したテキスト・リンク

        Returns:
            マージされた結果
        """
        try:
            # Visionのテキストを基本とする（画像説明などを含む）
            vision_text = vision_result.get('extracted_text', '')
            html_text = html_extract.get('text', '')

            # HTMLテキストの方が明らかに長い場合は、両方を組み合わせる
            if len(html_text) > len(vision_text) * 1.5:
                logger.info("HTMLテキストの方が長いため、両方を組み合わせます")

                # Visionの画像説明や特殊情報を抽出
                vision_special_info = []
                if vision_result.get('has_images') and vision_result.get('image_descriptions'):
                    vision_special_info.append("【画像内容】")
                    vision_special_info.extend(vision_result.get('image_descriptions', []))

                # 組み合わせ
                combined_text = f"{html_text}\n\n"
                if vision_special_info:
                    combined_text += "\n".join(vision_special_info)

                final_text = combined_text
            else:
                # Visionのテキストを優先
                final_text = vision_text

            # リンクをマージ（重複排除）
            vision_links = vision_result.get('links', [])
            html_links = html_extract.get('links', [])
            all_links = list(set(vision_links + html_links))

            # 結果をマージ
            merged_result = {
                'extracted_text': final_text,
                'summary': vision_result.get('summary', ''),
                'key_information': vision_result.get('key_information', []),
                'has_images': vision_result.get('has_images', False),
                'image_descriptions': vision_result.get('image_descriptions', []),
                'tables': vision_result.get('tables', []),
                'links': all_links,
                'has_tables': html_extract.get('has_tables', False) or len(vision_result.get('tables', [])) > 0,
                'has_lists': html_extract.get('has_lists', False)
            }

            logger.info(f"マージ完了: 最終テキスト={len(final_text)}文字, リンク={len(all_links)}個")

            return merged_result

        except Exception as e:
            logger.error(f"マージエラー: {e}")
            # エラー時はVisionの結果をそのまま返す
            return vision_result

    async def extract_email_content(
        self,
        html_content: str,
        email_metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        HTMLメールの内容をVision API + HTML解析で抽出

        処理フロー:
        1. Vision解析（画像・レイアウト・表を優先的に取得）
        2. HTMLテキスト抽出（純粋なテキスト部分を取得）
        3. インテリジェントマージ（両方の結果を統合）

        Args:
            html_content: メールのHTML内容
            email_metadata: メールのメタデータ（送信者、件名、日時など）

        Returns:
            抽出された内容
            {
                'extracted_text': str,  # 抽出されたテキスト内容
                'summary': str,  # 要約
                'key_information': list,  # 重要な情報のリスト
                'metadata': dict  # メタデータ
            }
        """
        try:
            logger.info("=" * 60)
            logger.info("メール解析開始: Vision + HTML解析")
            logger.info("=" * 60)
            logger.info("メールスクリーンショット生成中...")

            # HTMLをスクリーンショット化
            screenshot_bytes = await self.screenshot_generator.html_to_screenshot(
                html_content=html_content,
                full_page=True
            )

            # Base64エンコード
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

            logger.info(f"スクリーンショット生成完了: {len(screenshot_bytes):,} bytes")

            # メタデータからプロンプトを構築
            metadata_info = ""
            if email_metadata:
                metadata_info = f"""
メールメタデータ:
- 送信者: {email_metadata.get('from', 'Unknown')}
- 受信者: {email_metadata.get('to', 'Unknown')}
- 件名: {email_metadata.get('subject', 'No Subject')}
- 日時: {email_metadata.get('date', 'Unknown')}
"""

            # Gemini Vision APIで解析
            prompt = f"""このメールのスクリーンショットを解析して、以下の情報を抽出してください。

{metadata_info}

抽出する情報:
1. メール本文の全文（可能な限り正確に）
2. メールの要約（2-3文）
3. 重要な情報（日付、金額、リンク、アクションアイテムなど）
4. 画像がある場合、その説明
5. テーブルやリストがある場合、その内容

以下のJSON形式で出力してください:
{{
  "extracted_text": "メール本文の全文",
  "summary": "メールの要約",
  "key_information": [
    "重要な情報1",
    "重要な情報2"
  ],
  "has_images": true/false,
  "image_descriptions": ["画像の説明"],
  "tables": ["テーブルの内容"],
  "links": ["リンクURL"]
}}"""

            logger.info("Gemini 2.0 Flash-Lite でVision解析中...")

            # Gemini APIを呼び出し
            response = self.llm_client.generate_with_images(
                prompt=prompt,
                image_data=screenshot_base64,
                model=self.model_config['model'],
                temperature=self.model_config['temperature'],
                max_tokens=self.model_config['max_tokens']
            )

            logger.info("Vision解析完了")

            # デバッグ: レスポンスの最初の500文字をログ出力
            logger.debug(f"Vision APIレスポンス（最初の500文字）: {response[:500]}")

            # JSONレスポンスをパース
            import json
            import re

            # JSONブロックを抽出（非貪欲マッチから貪欲マッチに変更）
            json_match = re.search(r'```json\s*(\{.*\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                logger.debug(f"JSONブロック抽出成功。長さ: {len(json_str)} 文字")
            else:
                # JSONブロックがない場合、{ } で囲まれた部分を抽出
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    logger.debug(f"JSON抽出（ブロックなし）。長さ: {len(json_str)} 文字")
                else:
                    json_str = response
                    logger.debug("JSON構造が見つかりません。全体を使用")

            try:
                vision_result = json.loads(json_str)
                logger.info("JSON解析成功")
            except json.JSONDecodeError as e:
                # エスケープシーケンスエラーの場合、修正を試みる
                if 'escape' in str(e).lower():
                    logger.warning(f"エスケープエラー検出。修正を試みます: {str(e)[:100]}")
                    try:
                        # すべてのバックスラッシュを二重エスケープ
                        fixed_str = json_str
                        # 既に正しくエスケープされている部分を保護するため、段階的に処理

                        # Step 1: すべての \ を一時的にプレースホルダーに置き換え
                        fixed_str = fixed_str.replace('\\', '\x00BACKSLASH\x00')

                        # Step 2: プレースホルダーを \\ に置き換え
                        fixed_str = fixed_str.replace('\x00BACKSLASH\x00', '\\\\')

                        # Step 3: 正しいエスケープシーケンスを復元
                        # \\n -> \n, \\t -> \t, \\" -> \", \\\\ -> \\
                        fixed_str = fixed_str.replace('\\\\n', '\\n')
                        fixed_str = fixed_str.replace('\\\\t', '\\t')
                        fixed_str = fixed_str.replace('\\\\r', '\\r')
                        fixed_str = fixed_str.replace('\\\\"', '\\"')
                        fixed_str = fixed_str.replace('\\\\/', '\\/')
                        # Unicode エスケープ: \\uXXXX -> \uXXXX
                        import re
                        fixed_str = re.sub(r'\\\\u([0-9a-fA-F]{4})', r'\\u\1', fixed_str)
                        # 二重バックスラッシュ: \\\\\\\\ -> \\\\
                        fixed_str = fixed_str.replace('\\\\\\\\', '\\\\')

                        vision_result = json.loads(fixed_str)
                        logger.info("エスケープ修正後、JSON解析成功！")
                    except json.JSONDecodeError as e2:
                        logger.warning(f"修正後もJSON解析失敗: {str(e2)[:100]}")
                        # それでも失敗した場合、テキストとして扱う
                        vision_result = {
                            'extracted_text': response,
                            'summary': response[:200] + '...' if len(response) > 200 else response,
                            'key_information': [],
                            'has_images': False,
                            'image_descriptions': [],
                            'tables': [],
                            'links': []
                        }
                else:
                    # エスケープエラー以外の場合、テキストとして扱う
                    logger.warning(f"JSON解析失敗: {str(e)[:100]}")
                    logger.debug(f"失敗したJSON文字列（最初の500文字）: {json_str[:500]}")
                    vision_result = {
                        'extracted_text': response,
                        'summary': response[:200] + '...' if len(response) > 200 else response,
                        'key_information': [],
                        'has_images': False,
                        'image_descriptions': [],
                        'tables': [],
                        'links': []
                    }

            logger.info(f"Vision解析結果: テキスト={len(vision_result.get('extracted_text', ''))}文字")

            # ステップ2: HTMLからテキストとリンクを抽出
            logger.info("HTMLからテキスト抽出中...")
            html_extract = self._extract_html_text(html_content)

            # ステップ3: Vision結果とHTML抽出結果をマージ
            logger.info("Vision結果とHTML抽出結果をマージ中...")
            merged_result = self._merge_vision_and_html(vision_result, html_extract)

            # メタデータを追加
            merged_result['metadata'] = email_metadata or {}

            logger.info("=" * 60)
            logger.info("メール解析完了")
            logger.info(f"  最終テキスト: {len(merged_result.get('extracted_text', ''))}文字")
            logger.info(f"  リンク: {len(merged_result.get('links', []))}個")
            logger.info(f"  画像: {merged_result.get('has_images', False)}")
            logger.info("=" * 60)

            return merged_result

        except Exception as e:
            logger.error(f"メールVision処理エラー: {e}", exc_info=True)
            raise
