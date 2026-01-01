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

    def process(
        self,
        file_path: Path,
        prompt: str,
        model: str,
        extracted_text: str = ""
    ) -> str:
        """
        画像/PDFから視覚情報を抽出（Stage E のテキストを検証・修正・補完）

        Args:
            file_path: ファイルパス
            prompt: プロンプトテキスト（config/prompts/stage_f/*.md から読み込み）
            model: モデル名（config/models.yaml から取得）
            extracted_text: Stage E で抽出した完全なテキスト

        Returns:
            vision_raw: 3つの情報（full_text, layout_info, visual_elements）のJSONテキスト
        """
        logger.info(f"[Stage F] Visual Analysis開始... (model={model})")
        logger.info(f"  Stage E テキスト: {len(extracted_text)} 文字")

        if not file_path.exists():
            logger.error(f"[Stage F エラー] ファイルが存在しません: {file_path}")
            return ""

        # Gemini Vision APIがサポートしていないファイルタイプをスキップ
        unsupported_extensions = {'.pptx', '.ppt', '.doc', '.docx', '.xls', '.xlsx'}
        if file_path.suffix.lower() in unsupported_extensions:
            logger.info(f"[Stage F] スキップ: {file_path.suffix} はVision APIでサポートされていません")
            return ""

        try:
            # Stage E のテキストをプロンプトに追加
            full_prompt = prompt

            if extracted_text:
                full_prompt += "\n\n---\n\n【Stage E で抽出したテキスト】\n"
                full_prompt += f"```\n{extracted_text}\n```\n\n"
                full_prompt += """【あなたの役割】
上記の Stage E のテキストを基準として、画像を詳細に見て以下を行ってください：

1. **検証**: Stage E のテキストが正しいか画像と照合する
2. **修正**: 間違いがあれば正しく修正する
3. **補完**: 欠けている部分があれば補完する（画像化されたタイトル、ロゴ、装飾文字など）

**重要**: Stage E のテキストはほぼ正確ですが、画像化された文字や装飾文字が欠けている可能性があります。画像を詳細に見て、欠けている文字を全て補完してください。
"""
            else:
                # Stage E のテキストがない場合は、ゼロから全て拾う
                full_prompt += "\n\n【注意】Stage E でテキストを抽出できませんでした。画像から全ての文字を拾い尽くしてください。\n"

            # Gemini Vision でOCR + レイアウト解析（max_tokensを明示的に指定）
            logger.info(f"[Stage F] Gemini Vision API呼び出し（max_tokens=65536）")
            vision_raw = self.llm_client.generate_with_vision(
                prompt=full_prompt,
                image_path=str(file_path),
                model=model,
                max_tokens=65536,  # Gemini 2.5の最大出力トークン数
                response_format="json"
            )

            logger.info(f"[Stage F] Gemini応答サイズ: {len(vision_raw)}文字")
            logger.debug(f"[Stage F] Gemini生応答（最初の500文字）: {vision_raw[:500]}")
            logger.debug(f"[Stage F] Gemini生応答（最後の500文字）: {vision_raw[-500:]}")

            # JSONをクリーニング（```json ... ``` を削除、余分なテキストを削除）
            vision_raw_cleaned = self._clean_json_response(vision_raw)

            # JSONをパースして各フィールドのサイズをログ出力
            try:
                import json
                vision_json = json.loads(vision_raw_cleaned)
                full_text = vision_json.get('full_text', '')
                layout_info = vision_json.get('layout_info', {})
                visual_elements = vision_json.get('visual_elements', {})

                logger.info(f"[Stage F完了] Vision結果:")
                logger.info(f"  ├─ full_text: {len(full_text)} 文字")
                logger.info(f"  ├─ layout_info: {len(str(layout_info))} 文字 (JSON)")
                logger.info(f"  │   ├─ sections: {len(layout_info.get('sections', []))} 個")
                logger.info(f"  │   └─ tables: {len(layout_info.get('tables', []))} 個")
                logger.info(f"  ├─ visual_elements: {len(str(visual_elements))} 文字 (JSON)")
                logger.info(f"  └─ 合計: {len(vision_raw_cleaned)} 文字 (JSON全体)")
            except Exception as e:
                logger.warning(f"[Stage F] JSON解析失敗: {e}")
                logger.debug(f"[Stage F] クリーニング前（最初の1000文字）: {vision_raw[:1000]}")
                logger.debug(f"[Stage F] クリーニング後（最初の1000文字）: {vision_raw_cleaned[:1000]}")
                logger.debug(f"[Stage F] クリーニング後（最後の500文字）: {vision_raw_cleaned[-500:]}")
                logger.info(f"[Stage F完了] Vision結果: {len(vision_raw_cleaned)} 文字")

            return vision_raw_cleaned

        except Exception as e:
            logger.error(f"[Stage F エラー] Vision処理失敗: {e}", exc_info=True)
            return ""

    def _clean_json_response(self, response: str) -> str:
        """
        Gemini の応答からJSONを抽出してクリーニング

        Args:
            response: Gemini の生の応答

        Returns:
            クリーニングされたJSON文字列
        """
        import re

        # パターン1: ```json ... ``` で囲まれている場合
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()

        # パターン2: ``` ... ``` で囲まれている場合
        code_match = re.search(r'```\s*\n(.*?)\n```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # パターン3: { ... } を探す（最初の{から最後の}まで）
        first_brace = response.find('{')
        last_brace = response.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return response[first_brace:last_brace + 1].strip()

        # パターン4: そのまま返す
        return response.strip()
