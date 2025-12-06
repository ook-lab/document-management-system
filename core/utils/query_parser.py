"""
検索クエリ解析ユーティリティ

ユーザーの質問からフィルタ条件を自動抽出します。
"""
from typing import Dict, Any, Optional
import re
from datetime import datetime
from loguru import logger


class QueryParser:
    """検索クエリからフィルタ条件を抽出"""

    # 文書タイプのキーワードマッピング
    DOC_TYPE_KEYWORDS = {
        "ikuya_school": ["学年通信", "学級通信", "時間割", "予定表", "学校", "宿題", "テスト"],
        "notice": ["お知らせ", "通知", "案内"],
        "invoice": ["請求書", "領収書", "見積書"],
        "contract": ["契約書", "同意書"],
        "report": ["レポート", "報告書"],
        "cram_school_text": ["塾", "ゼミ", "教材"],
    }

    @staticmethod
    def parse_query(query: str) -> Dict[str, Any]:
        """
        クエリからフィルタ条件を抽出

        Args:
            query: ユーザーの検索クエリ

        Returns:
            フィルタ条件の辞書:
            {
                "year": int,
                "month": int,
                "doc_type": str,
                "grade_level": str,
                "date_range": {"start": str, "end": str}
            }
        """
        filters = {
            "year": None,
            "month": None,
            "doc_type": None,
            "grade_level": None,
            "date_range": None
        }

        # 年の抽出
        year = QueryParser._extract_year(query)
        if year:
            filters["year"] = year
            logger.info(f"[QueryParser] 年を抽出: {year}")

        # 月の抽出
        month = QueryParser._extract_month(query)
        if month:
            filters["month"] = month
            logger.info(f"[QueryParser] 月を抽出: {month}")

        # 文書タイプの抽出
        doc_type = QueryParser._extract_doc_type(query)
        if doc_type:
            filters["doc_type"] = doc_type
            logger.info(f"[QueryParser] 文書タイプを抽出: {doc_type}")

        # 学年の抽出
        grade_level = QueryParser._extract_grade_level(query)
        if grade_level:
            filters["grade_level"] = grade_level
            logger.info(f"[QueryParser] 学年を抽出: {grade_level}")

        return filters

    @staticmethod
    def _extract_year(query: str) -> Optional[int]:
        """
        クエリから年を抽出

        Args:
            query: 検索クエリ

        Returns:
            年（整数）
        """
        # パターン1: "2023年" のような形式
        match = re.search(r'(\d{4})年', query)
        if match:
            return int(match.group(1))

        # パターン2: "2023/12" や "2023-12" のような形式
        match = re.search(r'(\d{4})[-/]', query)
        if match:
            return int(match.group(1))

        # パターン3: 単独の4桁数字（2000-2099年の範囲）
        match = re.search(r'\b(20\d{2})\b', query)
        if match:
            return int(match.group(1))

        # パターン4: 相対年（「去年」「今年」「来年」）
        current_year = datetime.now().year

        if "去年" in query or "昨年" in query:
            return current_year - 1
        elif "今年" in query or "本年" in query:
            return current_year
        elif "来年" in query or "翌年" in query:
            return current_year + 1

        return None

    @staticmethod
    def _extract_month(query: str) -> Optional[int]:
        """
        クエリから月を抽出

        Args:
            query: 検索クエリ

        Returns:
            月（1-12の整数）
        """
        # パターン1: "12月" のような形式
        match = re.search(r'(\d{1,2})月', query)
        if match:
            month = int(match.group(1))
            if 1 <= month <= 12:
                return month

        # パターン2: "2023/12" や "2023-12" のような形式
        match = re.search(r'\d{4}[-/](\d{1,2})', query)
        if match:
            month = int(match.group(1))
            if 1 <= month <= 12:
                return month

        # パターン3: 相対月（「先月」「今月」「来月」）
        current_month = datetime.now().month

        if "先月" in query:
            month = current_month - 1
            if month == 0:
                month = 12
            return month
        elif "今月" in query or "本月" in query:
            return current_month
        elif "来月" in query or "翌月" in query:
            month = current_month + 1
            if month == 13:
                month = 1
            return month

        return None

    @staticmethod
    def _extract_doc_type(query: str) -> Optional[str]:
        """
        クエリから文書タイプを抽出

        Args:
            query: 検索クエリ

        Returns:
            文書タイプ（doc_type）
        """
        # キーワードマッチング
        for doc_type, keywords in QueryParser.DOC_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query:
                    return doc_type

        return None

    @staticmethod
    def _extract_grade_level(query: str) -> Optional[str]:
        """
        クエリから学年を抽出

        Args:
            query: 検索クエリ

        Returns:
            学年（例：「5年生」）
        """
        # パターン1: "5年生" のような形式
        match = re.search(r'([1-6])年生', query)
        if match:
            return f"{match.group(1)}年生"

        # パターン2: "小学5年" のような形式
        match = re.search(r'小学([1-6])年', query)
        if match:
            return f"{match.group(1)}年生"

        return None

    @staticmethod
    def build_filter_summary(filters: Dict[str, Any]) -> str:
        """
        フィルタ条件の要約文を生成

        Args:
            filters: フィルタ条件の辞書

        Returns:
            フィルタ条件の要約文
        """
        conditions = []

        if filters.get("year"):
            conditions.append(f"{filters['year']}年")

        if filters.get("month"):
            conditions.append(f"{filters['month']}月")

        if filters.get("doc_type"):
            conditions.append(f"文書タイプ: {filters['doc_type']}")

        if filters.get("grade_level"):
            conditions.append(f"学年: {filters['grade_level']}")

        if conditions:
            return "フィルタ条件: " + "、".join(conditions)
        else:
            return "フィルタ条件なし"
