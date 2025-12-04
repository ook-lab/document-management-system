"""
PDF プロセッサ (総力戦アーキテクチャ: pdfplumber + Table + Vision)

設計書: COMPLETE_IMPLEMENTATION_GUIDE_v3.md の 1.4節に基づき、PDFファイルからテキストを抽出する。
v3.0: 「テキスト解析（pdfplumber）」で基礎を固め、「表構造解析」で論理を通し、
      最後に「Vision」で視覚情報を補完する総力戦アーキテクチャ。
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
import os
import tempfile
import hashlib
from loguru import logger

import pdfplumber

# pdf2image は poppler が必要（macOS: brew install poppler）
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logger.warning("pdf2image が利用できません。Gemini Vision補完機能は無効化されます。")


class PDFProcessor:
    """PDFファイルからテキストを抽出するプロセッサ（総力戦方式）"""

    # 構造化キーワード（これらが含まれるページはVision解析候補）
    STRUCTURED_KEYWORDS = [
        "表", "課題", "時間割", "宿題", "テスト", "予定", "スケジュール",
        "リスト", "一覧", "名簿", "メニュー", "議題", "会議", "学習"
    ]

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLMClient インスタンス（Vision補完用）
        """
        self.llm_client = llm_client
        logger.info("PDFプロセッサ初期化完了 (総力戦アーキテクチャ)")

    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        PDFファイルからテキストを抽出（総力戦方式）

        処理フロー:
        Layer 1: pdfplumber でテキスト + 表を抽出
        Layer 2: 構造化キーワードがあり、かつ表抽出が不十分な場合にVision補完
        Layer 3: 統合（pdfplumber + Vision）

        Args:
            file_path: PDFファイルのローカルパス

        Returns:
            抽出結果 (content, metadata, success)
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"ファイルが見つかりません: {file_path}")
            return {
                "content": "",
                "metadata": {"error": "File not found"},
                "success": False,
                "error_message": "File not found"
            }

        if file_path.suffix.lower() not in ['.pdf']:
            logger.warning(f"PDFファイルではありません: {file_path}")
            return {
                "content": "",
                "metadata": {"error": "Not a PDF file"},
                "success": False,
                "error_message": "Not a PDF file"
            }

        try:
            # ============================================
            # Layer 1: pdfplumber でテキスト + 表を抽出
            # ============================================
            pdfplumber_result = self._extract_with_pdfplumber(file_path)

            if not pdfplumber_result["success"]:
                logger.error(f"pdfplumber完全失敗: {file_path.name}")
                return pdfplumber_result

            page_texts = pdfplumber_result["page_texts"]
            page_tables = pdfplumber_result["page_tables"]
            metadata = pdfplumber_result["metadata"]

            logger.info(f"pdfplumber抽出完了: {len(page_texts)} ページ, {sum(len(t) for t in page_tables)} 表")

            # ============================================
            # Layer 2: Vision戦略の判定
            # ============================================
            vision_target_pages = self._detect_vision_target_pages(page_texts, page_tables)

            logger.info(f"Vision補完対象: {len(vision_target_pages)}/{len(page_texts)} ページ")

            # ============================================
            # Layer 2.5: Gemini Vision 補完（対象ページのみ）
            # ============================================
            vision_supplements = {}

            if vision_target_pages and self.llm_client and PDF2IMAGE_AVAILABLE:
                logger.info(f"Gemini Vision補完開始: {len(vision_target_pages)} ページ")
                vision_supplements = self._extract_with_gemini_vision(
                    file_path,
                    vision_target_pages
                )
            elif vision_target_pages and not PDF2IMAGE_AVAILABLE:
                logger.warning("pdf2image が利用できないため、Vision補完をスキップします")
            elif vision_target_pages and not self.llm_client:
                logger.warning("LLMClient が未指定のため、Vision補完をスキップします")

            # ============================================
            # Layer 3: 統合（pdfplumber + Vision）
            # ============================================
            full_text_parts = []

            for i, (text, tables) in enumerate(zip(page_texts, page_tables)):
                page_num = i + 1

                # ページヘッダー
                full_text_parts.append(f"\n\n--- Page {page_num} ---\n\n")

                # pdfplumberテキスト
                if text.strip():
                    full_text_parts.append(text)

                # pdfplumber表（Markdown形式）
                if tables:
                    full_text_parts.append("\n\n[Tables from pdfplumber]\n")
                    for table_idx, table_md in enumerate(tables, 1):
                        full_text_parts.append(f"\n**Table {table_idx}**\n{table_md}\n")

                # Vision補完（該当ページのみ）
                if i in vision_supplements:
                    full_text_parts.append("\n\n--- Vision Supplement ---\n")
                    full_text_parts.append(vision_supplements[i])

            final_content = "".join(full_text_parts)

            # メタデータ更新
            metadata['vision_supplemented'] = len(vision_supplements) > 0
            metadata['vision_pages'] = len(vision_supplements)
            metadata['pdfplumber_tables'] = sum(len(t) for t in page_tables)

            return {
                "content": final_content,
                "metadata": metadata,
                "success": True
            }

        except Exception as e:
            logger.error(f"PDFテキスト抽出エラー ({file_path}): {e}")
            import traceback
            traceback.print_exc()
            return {
                "content": "",
                "metadata": {"error": str(e)},
                "success": False,
                "error_message": str(e)
            }

    def _extract_with_pdfplumber(self, file_path: Path) -> Dict[str, Any]:
        """
        pdfplumber でテキスト + 表を抽出

        Returns:
            {
                "success": bool,
                "page_texts": List[str],
                "page_tables": List[List[str]],  # ページごとのMarkdown表リスト
                "metadata": dict
            }
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                num_pages = len(pdf.pages)
                page_texts = []
                page_tables = []

                for i, page in enumerate(pdf.pages):
                    # テキスト抽出
                    text = page.extract_text() or ""
                    page_texts.append(text)

                    # 表抽出（複数戦略で試行）
                    tables_md = []

                    # 戦略1: デフォルト（罫線ベース）
                    tables = page.extract_tables()
                    logger.debug(f"ページ {i+1}: extract_tables() 結果: {tables is None}, 長さ: {len(tables) if tables else 0}, 内容: {tables}")

                    if tables:
                        logger.info(f"ページ {i+1}: 罫線ベースで {len(tables)} 個の表を検出")
                        for table in tables:
                            table_md = self._table_to_markdown(table)
                            if table_md:
                                tables_md.append(table_md)

                    # 戦略2: テキストベース（罫線がない表用）
                    # tables が空リストまたはNoneの場合に実行
                    if not tables or len(tables) == 0:
                        logger.info(f"ページ {i+1}: 罫線なし - テキストベース戦略を試行")

                        # 戦略2-1: 基本的なテキストベース
                        text_tables = page.extract_tables({
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text"
                        })

                        if text_tables:
                            logger.info(f"ページ {i+1}: テキストベース（基本）で {len(text_tables)} 個の表を検出")
                            for table in text_tables:
                                table_md = self._table_to_markdown(table)
                                if table_md:
                                    tables_md.append(table_md)

                        # 戦略2-2: より細かい設定でテキストベース抽出を試行
                        if not text_tables or len(text_tables) == 0:
                            logger.info(f"ページ {i+1}: 拡張テキストベース戦略を試行")
                            extended_tables = page.extract_tables({
                                "vertical_strategy": "text",
                                "horizontal_strategy": "text",
                                "intersection_tolerance": 15,  # 交差判定の許容範囲を広げる
                                "text_tolerance": 5,  # テキスト位置の許容範囲
                            })

                            if extended_tables:
                                logger.info(f"ページ {i+1}: 拡張テキストベースで {len(extended_tables)} 個の表を検出")
                                for table in extended_tables:
                                    table_md = self._table_to_markdown(table)
                                    if table_md:
                                        tables_md.append(table_md)

                    page_tables.append(tables_md)

                metadata = {
                    'num_pages': num_pages,
                    'extractor': 'pdfplumber'
                }

                # 全ページが空テキストの場合
                if not any(page_texts) and not any(page_tables):
                    logger.warning(f"pdfplumber: テキストも表も抽出できませんでした ({file_path})")
                    return {
                        "success": False,
                        "page_texts": [],
                        "page_tables": [],
                        "metadata": metadata,
                        "error_message": "No text or tables extracted"
                    }

                return {
                    "success": True,
                    "page_texts": page_texts,
                    "page_tables": page_tables,
                    "metadata": metadata
                }

        except Exception as e:
            logger.error(f"pdfplumber抽出エラー: {e}")
            return {
                "success": False,
                "page_texts": [],
                "page_tables": [],
                "metadata": {"error": str(e)},
                "error_message": str(e)
            }

    def _table_to_markdown(self, table: List[List]) -> str:
        """
        pdfplumberの表データをMarkdown形式に変換

        Args:
            table: pdfplumberのextract_tables()が返す2次元リスト

        Returns:
            Markdown形式の表文字列
        """
        if not table or len(table) == 0:
            return ""

        # None を空文字列に変換
        cleaned_table = []
        for row in table:
            cleaned_row = [str(cell).strip() if cell is not None else "" for cell in row]
            cleaned_table.append(cleaned_row)

        if not cleaned_table:
            return ""

        # Markdownテーブル生成
        md_lines = []

        # ヘッダー行
        header = cleaned_table[0]
        md_lines.append("| " + " | ".join(header) + " |")

        # セパレーター
        md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")

        # データ行
        for row in cleaned_table[1:]:
            # ヘッダーと列数を合わせる
            if len(row) < len(header):
                row.extend([""] * (len(header) - len(row)))
            elif len(row) > len(header):
                row = row[:len(header)]

            md_lines.append("| " + " | ".join(row) + " |")

        return "\n".join(md_lines)

    def _detect_vision_target_pages(
        self,
        page_texts: List[str],
        page_tables: List[List[str]]
    ) -> List[int]:
        """
        Vision補完が必要なページを検出

        判定基準:
        1. 構造化キーワードを含む
        2. かつ、pdfplumberの表抽出が空または不十分（2個以下）
        3. または、「学習」と「予定」の両方を含む場合は常にVision対象

        Args:
            page_texts: 各ページのテキストリスト
            page_tables: 各ページの表リスト（Markdown形式）

        Returns:
            Vision補完対象のページ番号リスト（0-indexed）
        """
        target_pages = []

        for i, (text, tables) in enumerate(zip(page_texts, page_tables)):
            # キーワード検出
            has_keyword = any(keyword in text for keyword in self.STRUCTURED_KEYWORDS)

            # 表抽出が不十分か判定（2個以下の場合は不十分）
            table_insufficient = len(tables) <= 2

            # 特別な強制条件: 学習予定の重要性を考慮
            has_learning_schedule = ("学習" in text and "予定" in text) or ("授業" in text and "予定" in text)

            # 条件判定
            if has_learning_schedule:
                target_pages.append(i)
                logger.debug(f"ページ {i+1}: 学習予定検出 (tables={len(tables)}) → Vision対象（強制）")
            elif has_keyword and table_insufficient:
                target_pages.append(i)
                logger.debug(f"ページ {i+1}: キーワード検出 + 表抽出不十分 (tables={len(tables)}) → Vision対象")

        return target_pages

    def _extract_with_gemini_vision(
        self,
        pdf_path: Path,
        page_numbers: List[int]
    ) -> Dict[int, str]:
        """
        指定されたページをGemini Visionで解析

        Args:
            pdf_path: PDFファイルパス
            page_numbers: 解析対象のページ番号リスト（0-indexed）

        Returns:
            {ページ番号: Vision解析結果} の辞書
        """
        vision_results = {}

        # PDFを画像に変換
        try:
            logger.info(f"PDF→画像変換開始: {pdf_path}")
            images = convert_from_path(
                pdf_path,
                dpi=200,  # 表組み認識に十分な解像度
                fmt='png'
            )

            # 該当ページのみ処理
            for page_num in page_numbers:
                if page_num >= len(images):
                    logger.warning(f"ページ {page_num} は範囲外です")
                    continue

                image = images[page_num]

                # 一時ファイルに保存
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_path = Path(tmp_file.name)
                    image.save(tmp_path, 'PNG')

                try:
                    # Gemini Vision で解析
                    logger.info(f"Gemini Vision解析: ページ {page_num + 1}")
                    result = self.llm_client.transcribe_image(
                        image_path=tmp_path,
                        prompt="この画像内の表組み、リスト、構造化されたデータを、Markdown形式で正確に書き起こしてください。テキスト部分も含めて、見たままを忠実に再現してください。"
                    )

                    if result.get("success"):
                        content = result.get("content", "")
                        vision_results[page_num] = content
                        logger.info(f"Vision解析成功: ページ {page_num + 1}")
                    else:
                        logger.warning(f"Vision解析失敗: ページ {page_num + 1}, エラー: {result.get('error')}")

                finally:
                    # 一時ファイル削除
                    if tmp_path.exists():
                        os.unlink(tmp_path)

            return vision_results

        except Exception as e:
            logger.error(f"Gemini Vision補完エラー: {e}")
            import traceback
            traceback.print_exc()
            return {}


def calculate_content_hash(pdf_path: str) -> str:
    """
    PDFファイルの内容全体からSHA256ハッシュを計算する

    Args:
        pdf_path: PDFファイルのローカルパス

    Returns:
        SHA256ハッシュ値（16進数文字列）

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        IOError: ファイル読み込みエラー
    """
    file_path = Path(pdf_path)

    if not file_path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {pdf_path}")

    # SHA256ハッシュオブジェクトを作成
    sha256_hash = hashlib.sha256()

    # ファイルをバイナリモードで読み込み、チャンクごとにハッシュを更新
    # 大きなファイルでもメモリ効率的に処理
    with open(file_path, 'rb') as f:
        # 64KBずつ読み込む
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)

    # 16進数文字列として返す
    return sha256_hash.hexdigest()
