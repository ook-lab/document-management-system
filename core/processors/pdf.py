#【実行場所】: ターミナルまたはVS Code
#【対象ファイル】: 新規作成
#【ファイルパス】: core/processors/pdf.py
#【実行方法】: 以下のコードをファイルにコピー＆ペーストして保存してください。

"""
PDF プロセッサ (テキスト抽出)

設計書: COMPLETE_IMPLEMENTATION_GUIDE_v3.md の 1.4節に基づき、PDFファイルからテキストを抽出する。
"""
from typing import Dict, Any
from pathlib import Path
import os
import io
import logging

# pypdf は requirements.txt で定義されているが、pdfplumber がより表構造抽出に優れるため、
# ここでは一旦 pypdf でシンプルなテキスト抽出を実装する。
from pypdf import PdfReader
# logger は loguru を想定

class PDFProcessor:
    """PDFファイルからテキストを抽出するプロセッサ"""
    
    def __init__(self):
        # logger.info("PDFプロセッサ初期化完了")
        pass

    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        PDFファイルから全文を抽出する
        
        Args:
            file_path: PDFファイルのローカルパス
            
        Returns:
            抽出結果 (content, metadata, success)
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            # logger.error(f"ファイルが見つかりません: {file_path}")
            return {"content": "", "metadata": {"error": "File not found"}, "success": False}

        if file_path.suffix.lower() not in ['.pdf']:
            # logger.warning(f"PDFファイルではありません: {file_path}")
            return {"content": "", "metadata": {"error": "Not a PDF file"}, "success": False}

        full_text = []
        metadata = {}
        
        try:
            # Stage 1 (Gemini) でOCR不要だが、テキスト抽出自体は必要 (FINAL_UNIFIED_COMPLETE_v4.md の 4.3節)
            # Stage 2 (Claude) が利用できるテキストを準備する
            
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                num_pages = len(reader.pages)
                
                for i in range(num_pages):
                    page = reader.pages[i]
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
                
                metadata['num_pages'] = num_pages
                
            content = "\n\n---PAGE BREAK---\n\n".join(full_text)
            
            if not content.strip():
                # テキストが抽出できなかった場合（スキャンPDFなど）
                # OCR フォールバック機能が必要だが、Phase 1Aでは Gemni が代替するため、一旦失敗とする
                return {"content": "", "metadata": metadata, "success": False, "error_message": "No text extracted (Scanned PDF or OCR required)"}
            
            return {"content": content, "metadata": metadata, "success": True}
            
        except Exception as e:
            # logger.error(f"PDFテキスト抽出エラー ({file_path}): {e}")
            return {"content": "", "metadata": {"error": str(e)}, "success": False, "error_message": str(e)}