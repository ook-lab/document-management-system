"""
Stage E: Pre-processing (前処理)

ライブラリベースのテキスト抽出
- PDF: pdfplumber
- Office: python-docx, openpyxl
- コスト: ほぼゼロ
"""
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from A_common.processors.pdf import PDFProcessor
from A_common.processors.office import OfficeProcessor
from C_ai_common.llm_client.llm_client import LLMClient


class StageEPreprocessor:
    """Stage E: 前処理（ライブラリベースのテキスト抽出 + 画像Vision補完）"""

    def __init__(self, llm_client: LLMClient):
        """
        Args:
            llm_client: LLMクライアント
        """
        # Stage E: pdfplumber + 選択的Vision補完（gemini-2.5-flash-lite）
        # 画像化された文字情報をGemini Visionで補完
        self.llm_client = llm_client
        self.pdf_processor = PDFProcessor(llm_client=llm_client)
        self.office_processor = OfficeProcessor()

    def extract_text(self, file_path: Path, mime_type: str) -> Dict[str, Any]:
        """
        ファイルからテキストを抽出（補完型）

        Args:
            file_path: ファイルパス
            mime_type: MIMEタイプ

        Returns:
            {
                'success': bool,
                'content': str,  # 完全なテキスト（単一）
                'char_count': int,
                'method': str  # 'pdf', 'docx', 'xlsx', 'pptx', 'image', 'none'
            }
        """
        logger.info("[Stage E] Pre-processing開始...")

        content = ""
        method = "none"

        try:
            # PDF処理（pdfplumber + gemini-2.5-flash 補完）
            if mime_type == 'application/pdf':
                result = self.pdf_processor.extract_text(str(file_path))
                if result.get('success'):
                    content = result.get('content', '')
                    method = 'pdf'

            # Office文書処理
            elif mime_type in [
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',      # .xlsx
                'application/vnd.openxmlformats-officedocument.presentationml.presentation'  # .pptx
            ]:
                result = self.office_processor.extract_text(str(file_path))
                if result.get('success'):
                    content = result.get('content', '')
                    if 'word' in mime_type:
                        method = 'docx'
                    elif 'sheet' in mime_type:
                        method = 'xlsx'
                    elif 'presentation' in mime_type:
                        method = 'pptx'

            # 画像ファイル処理（gemini-2.5-flash で全文字拾い）
            elif mime_type.startswith('image/'):
                if self.llm_client:
                    logger.info(f"[Stage E] 画像処理開始 (model: gemini-2.5-flash)")
                    vision_result = self.llm_client.transcribe_image(
                        image_path=file_path,
                        model="gemini-2.5-flash",
                        prompt="""この画像から、全ての文字を徹底的に拾い尽くしてください。

【あなたの役割】
画像から全ての文字を漏らさず拾ってください。

【文字拾いの徹底指示】
- **小さな文字**: 注釈、脚注、コピーライト表記なども全て拾う
- **ロゴ化された文字**: 画像として埋め込まれたタイトル、会社名、ブランド名なども全て読み取る
- **装飾された文字**: 太字、斜体、色付きなど、装飾に関わらず全て拾う
- **背景に埋もれた文字**: 薄い色、透かし文字なども可能な限り読み取る
- **手書き文字**: 判読可能な範囲で全て拾う

【出力形式】
画像内の全てのテキストを、上から下、左から右の順に書き起こしてください。
構造化は不要です。見つけた文字を全て列挙してください。

**重要**: 1文字も見逃さないでください。"""
                    )
                    if vision_result.get('success'):
                        content = vision_result.get('content', '')
                        method = 'image'
                        logger.info(f"[Stage E] 画像処理完了: {len(content)}文字")
                    else:
                        logger.warning(f"[Stage E] 画像処理失敗: {vision_result.get('error', 'Unknown error')}")
                else:
                    logger.warning("[Stage E] LLMクライアントが未指定のため、画像処理をスキップ")

            logger.info(f"[Stage E完了] (method: {method})")
            logger.info(f"  └─ 完全なテキスト: {len(content)} 文字")

            return {
                'success': True,
                'content': content,
                'char_count': len(content),
                'method': method
            }

        except Exception as e:
            logger.error(f"[Stage E エラー] テキスト抽出失敗: {e}", exc_info=True)
            return {
                'success': False,
                'content': '',
                'char_count': 0,
                'method': 'error',
                'error': str(e)
            }

    def process(self, file_path: Path, mime_type: str) -> str:
        """
        ファイルからテキストを抽出（process() エイリアス）

        Args:
            file_path: ファイルパス
            mime_type: MIMEタイプ

        Returns:
            extracted_text: 抽出されたテキスト
        """
        result = self.extract_text(file_path, mime_type)
        return result.get('content', '') if result.get('success') else ''
