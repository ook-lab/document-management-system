"""
Gemini OCR 処理モジュール

- レシート画像をGemini APIに送信
- JSON形式で構造化データを取得
- エラー検出（複数レシート、不正な画像など）
"""

import json
import base64
from pathlib import Path
from typing import Dict, Optional
import google.generativeai as genai

from loguru import logger
from .config import GEMINI_API_KEY, GEMINI_PROMPT, MAX_RETRY


class GeminiOCR:
    """Gemini API を使ったOCR処理"""

    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)

    def process_receipt(self, image_path: Path, model_name: str = "gemini-2.5-flash") -> Dict:
        """
        レシート画像を処理してJSON形式で返す

        Args:
            image_path: レシート画像のパス
            model_name: 使用するGeminiモデル名（デフォルト: gemini-2.5-flash）

        Returns:
            Dict: 処理結果
                - 成功時: {"shop_name": "...", "items": [...], ...}
                - エラー時: {"error": "...", "message": "..."}
        """
        try:
            # 画像を読み込み
            with open(image_path, "rb") as f:
                image_data = f.read()

            # Gemini APIに送信（モデル指定）
            response = self._call_gemini_api(image_data, model_name=model_name)

            # JSON パース
            result = self._parse_response(response)

            # バリデーション
            if "error" in result:
                logger.warning(f"Gemini returned error: {result}")
                return result

            logger.info(f"Successfully processed: {image_path.name}")
            return result

        except Exception as e:
            logger.error(f"Failed to process {image_path.name}: {e}")
            return {
                "error": "processing_failed",
                "message": str(e)
            }

    def _call_gemini_api(self, image_data: bytes, model_name: str, retry_count: int = 0) -> str:
        """
        Gemini APIを呼び出し

        Args:
            image_data: 画像のバイナリデータ
            model_name: 使用するモデル名
            retry_count: リトライ回数

        Returns:
            str: APIのレスポンステキスト
        """
        try:
            # モデルを初期化（呼び出しごとに異なるモデルを使用可能）
            model = genai.GenerativeModel(model_name)

            # 画像をbase64エンコード
            image_b64 = base64.b64encode(image_data).decode()

            # プロンプトと画像を送信
            response = model.generate_content([
                GEMINI_PROMPT,
                {
                    "mime_type": "image/jpeg",
                    "data": image_b64
                }
            ])

            return response.text

        except Exception as e:
            if retry_count < MAX_RETRY:
                logger.warning(f"API call failed (retry {retry_count + 1}/{MAX_RETRY}): {e}")
                return self._call_gemini_api(image_data, model_name, retry_count + 1)
            else:
                raise

    def _parse_response(self, response_text: str) -> Dict:
        """
        Geminiのレスポンスをパース

        Args:
            response_text: Gemini APIのレスポンス

        Returns:
            Dict: パース結果
        """
        try:
            # JSONブロックを抽出（マークダウン形式の場合）
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()

            # JSONパース
            data = json.loads(json_str)

            # バリデーション
            if "error" in data:
                return data

            # 必須フィールドチェック
            required = ["shop_name", "transaction_date", "items"]
            missing = [f for f in required if f not in data]

            if missing:
                return {
                    "error": "invalid_format",
                    "message": f"Missing fields: {', '.join(missing)}"
                }

            return data

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nResponse: {response_text}")
            return {
                "error": "json_parse_failed",
                "message": str(e),
                "raw_response": response_text
            }


# ========================================
# テスト実行
# ========================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python gemini_ocr.py <image_path>")
        sys.exit(1)

    image_path = Path(sys.argv[1])

    if not image_path.exists():
        print(f"Error: File not found: {image_path}")
        sys.exit(1)

    ocr = GeminiOCR()
    result = ocr.process_receipt(image_path)

    print(json.dumps(result, ensure_ascii=False, indent=2))
