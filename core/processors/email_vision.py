"""
Email Vision Processor

HTMLメールをスクリーンショット化してGemini 2.0 Flash-LiteでVision解析
"""
import base64
from typing import Dict, Any, Optional
from loguru import logger

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

    async def extract_email_content(
        self,
        html_content: str,
        email_metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        HTMLメールの内容をVision APIで抽出

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

            # JSONレスポンスをパース
            import json
            import re

            # JSONブロックを抽出
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # JSONブロックがない場合、全体をJSONとして解析
                json_str = response

            try:
                result = json.loads(json_str)
            except json.JSONDecodeError:
                # JSONパースに失敗した場合、テキストとして扱う
                logger.warning("JSON解析失敗、テキストとして扱います")
                result = {
                    'extracted_text': response,
                    'summary': response[:200] + '...' if len(response) > 200 else response,
                    'key_information': [],
                    'has_images': False,
                    'image_descriptions': [],
                    'tables': [],
                    'links': []
                }

            # メタデータを追加
            result['metadata'] = email_metadata or {}

            return result

        except Exception as e:
            logger.error(f"メールVision処理エラー: {e}", exc_info=True)
            raise
