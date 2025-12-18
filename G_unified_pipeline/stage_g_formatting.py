"""
Stage G: Text Formatting (書式整形)

Stage F で抽出した生テキストをAIが読める形式に整形
- 役割: 省略された文字の補完、レイアウト再構成、表整形
- モデル: gemini-2.0-flash-exp
- 重要性: 視覚情報を失わずに構造化（Stage H）に渡すための重要工程
"""
from typing import Dict, Any
from loguru import logger

from C_ai_common.llm_client.llm_client import LLMClient
from .prompts import STAGE_G_FORMATTING_PROMPT


class StageGTextFormatter:
    """Stage G: テキスト整形（Gemini）"""

    def __init__(self, llm_client: LLMClient):
        """
        Args:
            llm_client: LLMクライアント
        """
        self.llm_client = llm_client

    def format_text(self, vision_raw: str) -> Dict[str, Any]:
        """
        Stage F の生テキストを整形

        Args:
            vision_raw: Stage F のOCR結果（JSON文字列）

        Returns:
            {
                'success': bool,
                'formatted_text': str,
                'char_count': int
            }
        """
        if not vision_raw:
            logger.info("[Stage G] Stage F の結果なし → スキップ")
            return {
                'success': True,
                'formatted_text': '',
                'char_count': 0
            }

        logger.info("[Stage G] Text Formatting開始...")

        try:
            # プロンプト生成
            prompt = STAGE_G_FORMATTING_PROMPT.format(vision_raw=vision_raw)

            # Gemini でテキスト整形
            response = self.llm_client.call_model(
                tier="default",
                prompt=prompt,
                model_name="gemini-2.0-flash-exp"
            )

            if not response.get('success'):
                logger.error(f"[Stage G エラー] LLM呼び出し失敗: {response.get('error')}")
                return {
                    'success': False,
                    'formatted_text': '',
                    'char_count': 0,
                    'error': response.get('error')
                }

            formatted_text = response.get('content', response.get('response', ''))
            logger.info(f"[Stage G完了] 整形テキスト: {len(formatted_text)}文字")

            return {
                'success': True,
                'formatted_text': formatted_text,
                'char_count': len(formatted_text)
            }

        except Exception as e:
            logger.error(f"[Stage G エラー] テキスト整形失敗: {e}", exc_info=True)
            return {
                'success': False,
                'formatted_text': '',
                'char_count': 0,
                'error': str(e)
            }

    def process(self, vision_raw: str, prompt_template: str, model: str) -> str:
        """
        Stage F の生テキストを整形（設定ベース版）

        Args:
            vision_raw: Stage F のOCR結果
            prompt_template: プロンプトテンプレート（{vision_raw} を含む）
            model: モデル名

        Returns:
            formatted_text: 整形されたテキスト
        """
        if not vision_raw:
            return ""

        logger.info(f"[Stage G] Text Formatting開始... (model={model})")

        try:
            # プロンプトテンプレートに vision_raw を挿入
            prompt = prompt_template.format(vision_raw=vision_raw)

            response = self.llm_client.call_model(
                tier="default",
                prompt=prompt,
                model_name=model
            )

            if response.get('success'):
                formatted_text = response.get('content', response.get('response', ''))
                logger.info(f"[Stage G完了] 整形テキスト: {len(formatted_text)}文字")
                return formatted_text
            else:
                logger.error(f"[Stage G エラー] LLM呼び出し失敗: {response.get('error')}")
                return ""

        except Exception as e:
            logger.error(f"[Stage G エラー] テキスト整形失敗: {e}", exc_info=True)
            return ""
