#!/usr/bin/env python3
"""
JSON Schemaバリデーションテスト
null値が許可されることを確認
"""

import json
from pathlib import Path
from core.ai.json_validator import validate_metadata

def test_schema_with_null_values():
    """null値を含むメタデータがスキーマ検証を通過することを確認"""

    # テストケース1: basic_infoのgradeがnull
    metadata_with_null_grade = {
        "basic_info": {
            "school_name": None,
            "grade": None,  # これがnullでもエラーにならないことを確認
            "issue_date": None,
            "period": None,
            "document_title": None,
            "document_number": None
        },
        "text_blocks": None,
        "weekly_schedule": None,
        "structured_tables": None,
        "important_notes": None,
        "special_events": None
    }

    print("=" * 60)
    print("テスト1: basic_info.grade が null の場合")
    print("=" * 60)
    is_valid, error_message = validate_metadata(
        metadata=metadata_with_null_grade,
        doc_type='ikuya_school'
    )

    if is_valid:
        print("✅ 検証成功: null値が許可されています")
    else:
        print(f"❌ 検証失敗: {error_message}")

    print()

    # テストケース2: 全フィールドが空（最小限のメタデータ）
    metadata_minimal = {
        "basic_info": {}
    }

    print("=" * 60)
    print("テスト2: 最小限のメタデータ（basic_info が空）")
    print("=" * 60)
    is_valid, error_message = validate_metadata(
        metadata=metadata_minimal,
        doc_type='ikuya_school'
    )

    if is_valid:
        print("✅ 検証成功: 最小限のメタデータが許可されています")
    else:
        print(f"❌ 検証失敗: {error_message}")

    print()

    # テストケース3: 正常なデータ
    metadata_normal = {
        "basic_info": {
            "school_name": "サンプル小学校",
            "grade": "5年生",
            "issue_date": "2024-11-18",
            "period": "2024年11月18日-21日",
            "document_title": "学年通信",
            "document_number": "第12号"
        },
        "text_blocks": [
            {
                "title": "今週の予定",
                "content": "今週は遠足があります。"
            }
        ],
        "weekly_schedule": [],
        "important_notes": ["持ち物: 水筒、帽子"]
    }

    print("=" * 60)
    print("テスト3: 正常なデータ")
    print("=" * 60)
    is_valid, error_message = validate_metadata(
        metadata=metadata_normal,
        doc_type='ikuya_school'
    )

    if is_valid:
        print("✅ 検証成功: 正常なデータが許可されています")
    else:
        print(f"❌ 検証失敗: {error_message}")

    print()
    print("=" * 60)
    print("全テスト完了")
    print("=" * 60)

if __name__ == "__main__":
    test_schema_with_null_values()
