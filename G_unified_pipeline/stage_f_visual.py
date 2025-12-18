"""
Stage F: Visual Analysis (視覚解析)

Gemini Vision を使った視覚情報抽出
- 役割: 人間が見たままの視覚情報をそのまま捉える（OCR、レイアウト認識）
- モデル: 設定ファイルで指定（config/models.yaml）
- プロンプト: 設定ファイルで指定（config/prompts/stage_f/*.md）
- 出力: 生のOCR結果、レイアウト情報（整形されていない状態）
"""
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger
import json

from C_ai_common.llm_client.llm_client import LLMClient


class StageFVisualAnalyzer:
    """Stage F: 視覚解析（Gemini Vision）"""

    def __init__(self, llm_client: LLMClient):
        """
        Args:
            llm_client: LLMクライアント
        """
        self.llm_client = llm_client

    def should_run(self, mime_type: str, extracted_text_length: int) -> bool:
        """
        Stage F を実行すべきか判定

        発動条件:
        1. 画像ファイル
        2. Pre-processing でテキストがほとんど抽出できなかった（100文字未満）

        Args:
            mime_type: MIMEタイプ
            extracted_text_length: Stage E で抽出したテキストの長さ

        Returns:
            True: Stage F を実行すべき
        """
        # 条件1: 画像ファイル
        if mime_type and mime_type.startswith('image/'):
            logger.info("[Stage F] 画像ファイルを検出 → Vision処理実行")
            return True

        # 条件2: テキストがほとんど抽出できなかった
        if extracted_text_length < 100:
            logger.info(f"[Stage F] テキスト量が少ない({extracted_text_length}文字) → Vision処理実行")
            return True

        return False

    def analyze(self, file_path: Path) -> Dict[str, Any]:
        """
        画像/PDFから視覚情報を抽出

        Args:
            file_path: ファイルパス

        Returns:
            {
                'success': bool,
                'vision_raw': str,        # JSONテキスト
                'vision_json': dict,      # パース済みJSON
                'char_count': int
            }
        """
        logger.info("[Stage F] Visual Analysis開始...")

        if not file_path.exists():
            logger.error(f"[Stage F エラー] ファイルが存在しません: {file_path}")
            return {
                'success': False,
                'vision_raw': '',
                'vision_json': None,
                'char_count': 0,
                'error': 'File not found'
            }

        try:
            # NOTE: この analyze() メソッドは廃止予定
            # 代わりに process() メソッドを使用してください
            # Gemini Vision でOCR + レイアウト解析
            vision_raw = self.llm_client.generate_with_vision(
                prompt="<deprecated>",  # 廃止予定
                image_path=str(file_path),
                model="gemini-2.5-flash",
                response_format="json"
            )

            logger.info(f"[Stage F完了] Vision結果: {len(vision_raw)}文字")

            # JSONパース（Stage G で使用）
            vision_json = None
            try:
                vision_json = json.loads(vision_raw)
            except json.JSONDecodeError as e:
                logger.warning(f"[Stage F] JSON解析失敗: {e}")
                # JSONパース失敗しても、生テキストは返す

            return {
                'success': True,
                'vision_raw': vision_raw,
                'vision_json': vision_json,
                'char_count': len(vision_raw)
            }

        except Exception as e:
            logger.error(f"[Stage F エラー] Vision処理失敗: {e}", exc_info=True)
            return {
                'success': False,
                'vision_raw': '',
                'vision_json': None,
                'char_count': 0,
                'error': str(e)
            }

    def process(self, file_path: Path, prompt: str, model: str) -> str:
        """
        画像/PDFから視覚情報を抽出（設定ベース版）

        Args:
            file_path: ファイルパス
            prompt: プロンプトテキスト（config/prompts/stage_f/*.md から読み込み）
            model: モデル名（config/models.yaml から取得）

        Returns:
            vision_raw: 生のOCR結果（JSONテキスト）
        """
        logger.info(f"[Stage F] Visual Analysis開始... (model={model})")

        if not file_path.exists():
            logger.error(f"[Stage F エラー] ファイルが存在しません: {file_path}")
            return ""

        try:
            # Gemini Vision でOCR + レイアウト解析
            vision_raw = self.llm_client.generate_with_vision(
                prompt=prompt,
                image_path=str(file_path),
                model=model,
                response_format="json"
            )

            logger.info(f"[Stage F完了] Vision結果: {len(vision_raw)}文字")
            return vision_raw

        except Exception as e:
            logger.error(f"[Stage F エラー] Vision処理失敗: {e}", exc_info=True)
            return ""
