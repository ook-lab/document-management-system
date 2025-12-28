"""
Stage G: Text Formatting (書式整形)

Stage F で抽出した生テキストをAIが読める形式に整形
- 役割: 省略された文字の補完、レイアウト再構成、表整形
- モデル: gemini-2.0-flash-exp
- 重要性: 視覚情報を失わずに構造化（Stage H）に渡すための重要工程
"""
from typing import Dict, Any
from string import Template
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

    def process(
        self,
        vision_raw: str = "",
        extracted_text: str = "",
        prompt_template: str = "",
        model: str = "gemini-2.0-flash-exp",
        mode: str = "format"
    ) -> str:
        """
        Stage F の生テキストを整形 + テキスト統合（設定ベース版）

        Args:
            vision_raw: Stage F のOCR結果
            extracted_text: Stage E で抽出したテキスト（mode="integrate" の場合に使用）
            prompt_template: プロンプトテンプレート（{vision_raw} を含む）
            model: モデル名
            mode: "format" (整形のみ) または "integrate" (整形 + 統合)

        Returns:
            formatted_text: 整形されたテキスト（または統合されたテキスト）
        """
        if mode == "format":
            # 従来通り: Vision整形のみ
            return self._format_vision(vision_raw, prompt_template, model)

        elif mode == "integrate":
            # 新機能: Vision整形 + テキスト統合
            vision_formatted = self._format_vision(vision_raw, prompt_template, model)
            return self._integrate_texts(extracted_text, vision_formatted, model)

        else:
            logger.error(f"[Stage G エラー] 無効なモード: {mode}")
            return ""

    def _format_vision(self, vision_raw: str, prompt_template: str, model: str) -> str:
        """
        Vision結果を整形

        Args:
            vision_raw: Stage F のOCR結果
            prompt_template: プロンプトテンプレート
            model: モデル名

        Returns:
            formatted_text: 整形されたテキスト
        """
        if not vision_raw:
            return ""

        logger.info(f"[Stage G] Text Formatting開始... (model={model})")

        try:
            # string.Templateを使用してテンプレート変数を置換（JSONの{}と競合しない）
            template = Template(prompt_template)
            prompt = template.substitute(vision_raw=vision_raw)

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

    def _integrate_texts(self, extracted: str, vision: str, model: str) -> str:
        """
        2つのテキストをLLMで統合

        Args:
            extracted: Stage E で抽出したテキスト
            vision: Stage G で整形したVisionテキスト
            model: モデル名

        Returns:
            integrated_text: 統合されたテキスト
        """
        logger.info(f"[Stage G] Text Integration開始... (model={model})")

        # 両方が空の場合
        if not extracted and not vision:
            return ""

        # 片方だけの場合はそのまま返す
        if not vision:
            logger.info("[Stage G] Vision結果なし → 抽出テキストのみ")
            return extracted
        if not extracted:
            logger.info("[Stage G] 抽出テキストなし → Vision結果のみ")
            return vision

        # 両方ある場合はLLMで統合
        try:
            integration_prompt = f"""以下の2つのテキストを統合してください。

【ライブラリで抽出したテキスト】
{extracted}

【Vision OCRで抽出したテキスト】
{vision}

統合ルール:
1. 重複する内容は1つにまとめる
2. 補完的な情報はすべて含める（特にヘッダー、年号、日付などの重要情報）
3. Vision OCRで得られたヘッダー情報や年号は優先的に冒頭に配置
4. 表組みはVision OCRの結果を優先（より正確な構造を保持）
5. 自然な順序で配置（ヘッダー → 本文 → 表 → フッター）
6. OCRエラーやノイズは除去
7. セクション見出しや余計な注釈は不要

統合されたテキストのみを出力してください。
"""

            response = self.llm_client.call_model(
                tier="default",
                prompt=integration_prompt,
                model_name=model
            )

            if response.get('success'):
                integrated_text = response.get('content', response.get('response', ''))
                logger.info(f"[Stage G完了] 統合テキスト: {len(integrated_text)}文字")
                return integrated_text
            else:
                logger.error(f"[Stage G 統合エラー] LLM呼び出し失敗: {response.get('error')}")
                # 統合失敗時はフォールバック: シンプルな連結
                logger.warning("[Stage G] 統合失敗 → フォールバック（シンプル連結）")
                return f"{vision}\n\n{extracted}".strip()

        except Exception as e:
            logger.error(f"[Stage G 統合エラー] {e}", exc_info=True)
            # 統合失敗時はフォールバック: シンプルな連結
            return f"{vision}\n\n{extracted}".strip()
