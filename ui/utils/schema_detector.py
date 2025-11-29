"""
Schema Detector
メタデータの構造から適切なスキーマを判定
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional, List


class SchemaDetector:
    """スキーマ検出クラス"""

    def __init__(self):
        """スキーマファイルをロード"""
        self.schemas = {}
        self.schema_dir = Path(__file__).parent.parent / "schemas"
        self._load_schemas()

    def _load_schemas(self):
        """schemas/ディレクトリから全てのスキーマをロード"""
        if not self.schema_dir.exists():
            return

        for schema_file in self.schema_dir.glob("*.json"):
            try:
                with open(schema_file, 'r', encoding='utf-8') as f:
                    schema_name = schema_file.stem
                    self.schemas[schema_name] = json.load(f)
            except Exception as e:
                print(f"スキーマ読み込みエラー ({schema_file.name}): {e}")

    def detect_schema(self, doc_type: str, metadata: Dict[str, Any]) -> Optional[str]:
        """
        doc_typeとmetadataからスキーマを判定

        Args:
            doc_type: ドキュメントタイプ
            metadata: メタデータ辞書

        Returns:
            スキーマ名（例: "timetable"）、判定できない場合はNone
        """
        # メタデータがNoneの場合、安全のために空の辞書に変換
        if metadata is None:
            metadata = {}

        # doc_typeベースの直接マッピング
        doc_type_to_schema = {
            "timetable": "timetable",
            "school_notice": "school_notice",
            "notice": "school_notice",
            "classroom_letter": "school_notice",
            "event_schedule": "school_notice"
        }

        if doc_type in doc_type_to_schema:
            schema_name = doc_type_to_schema[doc_type]
            if schema_name in self.schemas:
                return schema_name

        # メタデータの構造から推測
        if self._is_timetable_structure(metadata):
            return "timetable"

        if self._is_school_notice_structure(metadata):
            return "school_notice"

        return None

    def _is_timetable_structure(self, metadata: Dict[str, Any]) -> bool:
        """時間割の構造かどうか判定"""
        # daily_scheduleフィールドの存在をチェック
        if "daily_schedule" in metadata:
            daily_schedule = metadata["daily_schedule"]
            if isinstance(daily_schedule, list) and len(daily_schedule) > 0:
                # 最初の要素がdate, day_of_week, periodsを持つかチェック
                first_day = daily_schedule[0]
                return all(key in first_day for key in ["date", "day_of_week", "periods"])
        return False

    def _is_school_notice_structure(self, metadata: Dict[str, Any]) -> bool:
        """学校通知の構造かどうか判定"""
        # notice_typeまたはweekly_scheduleフィールドの存在をチェック
        if "notice_type" in metadata:
            return True
        if "weekly_schedule" in metadata:
            return True
        # school_nameとgradeの両方が存在する場合も学校通知として扱う
        if "school_name" in metadata and "grade" in metadata:
            return True
        return False

    def get_schema(self, schema_name: str) -> Optional[Dict[str, Any]]:
        """
        スキーマ名からスキーマ定義を取得

        Args:
            schema_name: スキーマ名

        Returns:
            スキーマ定義辞書、存在しない場合はNone
        """
        return self.schemas.get(schema_name)

    def get_editable_fields(self, schema_name: str) -> List[Dict[str, Any]]:
        """
        スキーマから編集可能なフィールドリストを取得

        Args:
            schema_name: スキーマ名

        Returns:
            フィールド定義のリスト
        """
        schema = self.get_schema(schema_name)
        if not schema or "properties" not in schema:
            return []

        fields = []
        for field_name, field_def in schema["properties"].items():
            fields.append({
                "name": field_name,
                "type": field_def.get("type", "string"),
                "title": field_def.get("title", field_name),
                "description": field_def.get("description", ""),
                "required": field_name in schema.get("required", []),
                "enum": field_def.get("enum"),
                "format": field_def.get("format"),
                "items": field_def.get("items")
            })

        return fields

    def validate_metadata(self, schema_name: str, metadata: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        メタデータがスキーマに適合しているか検証

        Args:
            schema_name: スキーマ名
            metadata: 検証するメタデータ

        Returns:
            (検証結果, エラーメッセージリスト)
        """
        # メタデータがNoneの場合、安全のために空の辞書に変換
        if metadata is None:
            metadata = {}

        schema = self.get_schema(schema_name)
        if not schema:
            return False, [f"スキーマ '{schema_name}' が見つかりません"]

        errors = []

        # 必須フィールドのチェック
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in metadata:
                errors.append(f"必須フィールド '{field}' が欠けています")

        # 型のチェック（簡易版）
        properties = schema.get("properties", {})
        for field_name, value in metadata.items():
            if field_name in properties:
                expected_type = properties[field_name].get("type")
                if expected_type and not self._check_type(value, expected_type):
                    errors.append(f"フィールド '{field_name}' の型が不正です（期待: {expected_type}）")

        return len(errors) == 0, errors

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """値の型をチェック"""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }

        expected_python_type = type_map.get(expected_type)
        if expected_python_type is None:
            return True  # 不明な型は検証をスキップ

        return isinstance(value, expected_python_type)
