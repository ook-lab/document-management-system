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

                    # 表抽出（より厳密な設定）
                    table_settings = {
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "snap_tolerance": 3,
                        "join_tolerance": 3,
                        "edge_min_length": 3,
                        "min_words_vertical": 3,
                        "min_words_horizontal": 1,
                        "intersection_tolerance": 3
                    }
                    tables = page.extract_tables(table_settings=table_settings)
                    tables_md = []

                    if tables:
                        for table in tables:
                            # 表の品質チェック
                            if self._is_valid_table(table):
                                # 表をMarkdown形式に変換
                                table_md = self._table_to_markdown(table)
                                if table_md:
                                    tables_md.append(table_md)
                            else:
                                logger.debug(f"ページ {i+1}: 品質チェック不合格の表をスキップ")

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

    def _is_valid_table(self, table: List[List]) -> bool:
        """
        表の品質をチェック（緩和版）

        判定基準:
        1. 最低行数・列数チェック（2行2列以上）
        2. 空セル率チェック（85%以下） - 緩和
        3. 不要な行の除外（最後の数行のみチェック）

        Args:
            table: pdfplumberのextract_tables()が返す2次元リスト

        Returns:
            True: 有効な表, False: 無効な表
        """
        if not table or len(table) < 2:
            return False

        # 列数チェック（最初の行を基準）
        num_cols = len(table[0]) if table[0] else 0
        if num_cols < 2:
            return False

        # 空セル率チェック（緩和: 85%に変更）
        total_cells = 0
        empty_cells = 0
        for row in table:
            for cell in row:
                total_cells += 1
                if cell is None or str(cell).strip() == "":
                    empty_cells += 1

        empty_ratio = empty_cells / total_cells if total_cells > 0 else 1.0
        if empty_ratio > 0.85:  # 85%以上が空セル
            logger.debug(f"表の品質チェック: 空セル率が高すぎます ({empty_ratio:.1%})")
            return False

        # 表の後処理：最後の行に不要な情報が含まれる場合は削除
        # (営業時間、E-MAILなどは表の最後に記載されることが多い)
        self._remove_irrelevant_rows(table)

        return True

    def _remove_irrelevant_rows(self, table: List[List]) -> None:
        """
        表の最後の行から不要な行を削除（in-place）

        Args:
            table: 2次元リスト（変更される）
        """
        if not table or len(table) < 3:
            return

        irrelevant_keywords = [
            "営業時間", "E-MAIL", "Ｅ-ＭＡＩＬ", "TEL", "FAX",
            "住所", "アクセス", "URL", "http", "www."
        ]

        # 最後の5行をチェック
        rows_to_remove = []
        check_range = min(5, len(table))

        for i in range(len(table) - check_range, len(table)):
            row = table[i]
            row_text = " ".join(str(cell) for cell in row if cell)

            # 不要なキーワードが含まれているかチェック
            if any(keyword in row_text for keyword in irrelevant_keywords):
                rows_to_remove.append(i)
                logger.debug(f"不要な行を検出: {row_text[:50]}...")

        # 後ろから削除（インデックスがずれないように）
        for i in sorted(rows_to_remove, reverse=True):
            del table[i]

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
