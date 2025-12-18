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
    """Stage E: 前処理（ライブラリベースのテキスト抽出）"""

    def __init__(self, llm_client: LLMClient):
        """
        Args:
            llm_client: LLMクライアント
        """
        self.pdf_processor = PDFProcessor(llm_client=llm_client)
        self.office_processor = OfficeProcessor()

    def extract_text(self, file_path: Path, mime_type: str) -> Dict[str, Any]:
        """
        ファイルからテキストを抽出

        Args:
            file_path: ファイルパス
            mime_type: MIMEタイプ

        Returns:
            {
                'success': bool,
                'text': str,
                'char_count': int,
                'method': str  # 'pdf', 'docx', 'xlsx', 'pptx', 'none'
            }
        """
        logger.info("[Stage E] Pre-processing開始...")

        extracted_text = ""
        method = "none"

        try:
            # PDF処理
            if mime_type == 'application/pdf':
                result = self.pdf_processor.extract_text_from_pdf(str(file_path))
                if result.get('success'):
                    extracted_text = result.get('content', '')
                    method = 'pdf'

            # Office文書処理
            elif mime_type in [
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',      # .xlsx
                'application/vnd.openxmlformats-officedocument.presentationml.presentation'  # .pptx
            ]:
                result = self.office_processor.extract_text(str(file_path))
                if result.get('success'):
                    extracted_text = result.get('content', '')
                    if 'word' in mime_type:
                        method = 'docx'
                    elif 'sheet' in mime_type:
                        method = 'xlsx'
                    elif 'presentation' in mime_type:
                        method = 'pptx'

            char_count = len(extracted_text)
            logger.info(f"[Stage E完了] 抽出テキスト長: {char_count}文字 (method: {method})")

            return {
                'success': True,
                'text': extracted_text,
                'char_count': char_count,
                'method': method
            }

        except Exception as e:
            logger.error(f"[Stage E エラー] テキスト抽出失敗: {e}", exc_info=True)
            return {
                'success': False,
                'text': '',
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
