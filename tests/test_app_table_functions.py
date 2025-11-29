"""
app.py の表データ変換機能（Phase 2.2.3 構造的クエリ対応）のテスト
"""

import pytest
import sys
import os

# app.py をインポートできるようにパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import _format_table_to_markdown, _format_metadata, _build_context


class TestFormatTableToMarkdown:
    """_format_table_to_markdown 関数のテストクラス"""

    def test_simple_table_with_headers_and_rows(self):
        """
        テストケース 1: シンプルなヘッダーと行を持つ表
        """
        table_data = {
            "table_type": "simple_table",
            "headers": ["名前", "年齢", "職業"],
            "rows": [
                {"cells": [{"value": "太郎"}, {"value": "25"}, {"value": "エンジニア"}]},
                {"cells": [{"value": "花子"}, {"value": "30"}, {"value": "デザイナー"}]}
            ]
        }

        result = _format_table_to_markdown(table_data)

        # ヘッダー行が含まれることを確認
        assert "| 名前 | 年齢 | 職業 |" in result
        # セパレーター行が含まれることを確認
        assert "|---|---|---|" in result
        # データ行が含まれることを確認
        assert "| 太郎 | 25 | エンジニア |" in result
        assert "| 花子 | 30 | デザイナー |" in result
        # テーブルタイプが含まれることを確認
        assert "simple_table" in result

    def test_class_timetable_with_complex_headers(self):
        """
        テストケース 2: 複雑なヘッダー構造を持つクラス別時間割
        """
        table_data = {
            "table_type": "class_timetable",
            "headers": {
                "classes": ["1組", "2組", "3組"]
            },
            "rows": []
        }

        result = _format_table_to_markdown(table_data)

        # クラス別時間割のヘッダーが含まれることを確認
        assert "クラス別時間割" in result
        assert "| 日 | 1組 | 2組 | 3組 |" in result

    def test_daily_schedule_structure(self):
        """
        テストケース 3: daily_schedule 構造（日別スケジュール）
        """
        table_data = {
            "table_type": "timetable",
            "headers": {"classes": ["1組", "2組"]},
            "rows": [],
            "daily_schedule": [
                {
                    "day": "月",
                    "class_schedules": [
                        {
                            "class": "1組",
                            "subjects": ["数学", "国語", "英語"]
                        },
                        {
                            "class": "2組",
                            "subjects": ["英語", "数学", "体育"]
                        }
                    ]
                },
                {
                    "day": "火",
                    "class_schedules": [
                        {
                            "class": "1組",
                            "subjects": ["理科", "社会", "音楽"]
                        }
                    ]
                }
            ]
        }

        result = _format_table_to_markdown(table_data)

        # 日別スケジュールが含まれることを確認
        assert "日別スケジュール" in result
        assert "月曜日" in result
        assert "火曜日" in result
        assert "1組: 数学, 国語, 英語" in result
        assert "2組: 英語, 数学, 体育" in result
        assert "1組: 理科, 社会, 音楽" in result

    def test_agenda_groups_structure(self):
        """
        テストケース 4: agenda_groups 構造（議事録の議題グループ）
        """
        table_data = {
            "table_type": "meeting_minutes",
            "headers": ["議題", "決定事項", "担当者", "期限"],
            "rows": [],
            "agenda_groups": [
                {
                    "topic": "プロジェクト計画",
                    "items": [
                        {
                            "decision": "要件定義を完了する",
                            "assignee": "山田",
                            "deadline": "2025-12-01"
                        },
                        {
                            "decision": "設計書を作成する",
                            "assignee": "佐藤",
                            "deadline": "2025-12-15"
                        }
                    ]
                },
                {
                    "topic": "予算確認",
                    "items": [
                        {
                            "decision": "予算案を承認する",
                            "assignee": "鈴木",
                            "deadline": "2025-11-30"
                        }
                    ]
                }
            ]
        }

        result = _format_table_to_markdown(table_data)

        # 議題グループが含まれることを確認
        assert "議題グループ" in result
        assert "プロジェクト計画" in result
        assert "予算確認" in result
        assert "要件定義を完了する" in result
        assert "担当: 山田" in result
        assert "期限: 2025-12-01" in result
        assert "設計書を作成する" in result
        assert "担当: 佐藤" in result

    def test_empty_table_data(self):
        """
        テストケース 5: 空の表データ
        """
        table_data = {
            "table_type": "empty_table",
            "headers": [],
            "rows": []
        }

        result = _format_table_to_markdown(table_data)

        # エラーなく処理され、テーブルタイプが含まれることを確認
        assert "empty_table" in result

    def test_error_handling_invalid_structure(self):
        """
        テストケース 6: エラーハンドリング（無効な構造）
        """
        table_data = None

        result = _format_table_to_markdown(table_data)

        # エラーメッセージが含まれることを確認
        assert "表データの変換エラー" in result


class TestFormatMetadata:
    """_format_metadata 関数のテストクラス"""

    def test_metadata_with_tables_field(self):
        """
        テストケース 1: tables フィールドを含むメタデータ
        """
        metadata = {
            "title": "テスト文書",
            "author": "テスト太郎",
            "tables": [
                {
                    "table_type": "simple_table",
                    "headers": ["列1", "列2"],
                    "rows": [
                        {"cells": [{"value": "値1"}, {"value": "値2"}]}
                    ]
                }
            ]
        }

        result = _format_metadata(metadata)

        # 通常のメタデータが含まれることを確認
        assert "title: テスト文書" in result
        assert "author: テスト太郎" in result
        # 表データセクションが含まれることを確認
        assert "【表データ】" in result
        # Markdown形式の表が含まれることを確認
        assert "| 列1 | 列2 |" in result

    def test_metadata_with_empty_tables(self):
        """
        テストケース 2: 空の tables フィールド
        """
        metadata = {
            "title": "テスト文書",
            "tables": []
        }

        result = _format_metadata(metadata)

        # 通常のメタデータは含まれるが、表データセクションは含まれない
        assert "title: テスト文書" in result
        assert "【表データ】" not in result

    def test_metadata_without_tables(self):
        """
        テストケース 3: tables フィールドがないメタデータ
        """
        metadata = {
            "title": "テスト文書",
            "author": "テスト太郎",
            "tags": ["タグ1", "タグ2"]
        }

        result = _format_metadata(metadata)

        # 通常のメタデータが正しく整形されることを確認
        assert "title: テスト文書" in result
        assert "author: テスト太郎" in result
        assert "tags:" in result
        assert "タグ1" in result
        assert "タグ2" in result

    def test_metadata_with_nested_dict(self):
        """
        テストケース 4: ネストされた辞書を含むメタデータ
        """
        metadata = {
            "document_info": {
                "title": "テスト文書",
                "version": "1.0"
            },
            "author": "テスト太郎"
        }

        result = _format_metadata(metadata)

        # ネストされた辞書が正しく整形されることを確認
        assert "document_info:" in result
        assert "title: テスト文書" in result
        assert "version: 1.0" in result
        assert "author: テスト太郎" in result

    def test_empty_metadata(self):
        """
        テストケース 5: 空のメタデータ
        """
        metadata = {}

        result = _format_metadata(metadata)

        # 空文字列が返されることを確認
        assert result == ""


class TestBuildContext:
    """_build_context 関数のテストクラス"""

    def test_empty_documents_list(self):
        """
        テストケース 1: 空のドキュメントリスト
        """
        documents = []

        result = _build_context(documents)

        # 適切なメッセージが返されることを確認
        assert "関連する文書が見つかりませんでした" in result

    def test_single_document_without_tables(self):
        """
        テストケース 2: 1つのドキュメント（表データなし）
        """
        documents = [
            {
                "file_name": "テスト文書.pdf",
                "doc_type": "PDF",
                "summary": "これはテスト文書です。",
                "similarity": 0.95,
                "metadata": {
                    "title": "テスト文書",
                    "author": "テスト太郎"
                }
            }
        ]

        result = _build_context(documents)

        # 基本情報が含まれることを確認
        assert "【文書1】" in result
        assert "ファイル名: テスト文書.pdf" in result
        assert "文書タイプ: PDF" in result
        assert "類似度: 0.95" in result
        assert "要約: これはテスト文書です。" in result
        assert "title: テスト文書" in result
        assert "author: テスト太郎" in result

    def test_multiple_documents_with_tables(self):
        """
        テストケース 3: 複数のドキュメント（表データを含む）
        """
        documents = [
            {
                "file_name": "時間割.pdf",
                "doc_type": "PDF",
                "summary": "クラス別の時間割表",
                "similarity": 0.98,
                "metadata": {
                    "title": "2年生時間割",
                    "tables": [
                        {
                            "table_type": "timetable",
                            "headers": {"classes": ["1組", "2組"]},
                            "rows": [],
                            "daily_schedule": [
                                {
                                    "day": "月",
                                    "class_schedules": [
                                        {
                                            "class": "1組",
                                            "subjects": ["数学", "国語"]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            },
            {
                "file_name": "議事録.pdf",
                "doc_type": "PDF",
                "summary": "プロジェクト会議の議事録",
                "similarity": 0.87,
                "metadata": {
                    "title": "プロジェクト会議",
                    "tables": [
                        {
                            "table_type": "meeting_minutes",
                            "headers": ["議題", "決定事項"],
                            "rows": [],
                            "agenda_groups": [
                                {
                                    "topic": "進捗確認",
                                    "items": [
                                        {
                                            "decision": "スケジュール見直し",
                                            "assignee": "山田",
                                            "deadline": "2025-12-01"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            }
        ]

        result = _build_context(documents)

        # 2つのドキュメントが含まれることを確認
        assert "【文書1】" in result
        assert "【文書2】" in result

        # 時間割の情報が含まれることを確認
        assert "時間割.pdf" in result
        assert "2年生時間割" in result
        assert "【表データ】" in result
        assert "日別スケジュール" in result
        assert "月曜日" in result
        assert "1組: 数学, 国語" in result

        # 議事録の情報が含まれることを確認
        assert "議事録.pdf" in result
        assert "プロジェクト会議" in result
        assert "議題グループ" in result
        assert "進捗確認" in result
        assert "担当: 山田" in result

    def test_document_without_metadata(self):
        """
        テストケース 4: メタデータなしのドキュメント
        """
        documents = [
            {
                "file_name": "簡易文書.txt",
                "doc_type": "TXT",
                "summary": "簡単な文書",
                "similarity": 0.75,
                "metadata": {}
            }
        ]

        result = _build_context(documents)

        # 基本情報のみが含まれることを確認
        assert "【文書1】" in result
        assert "ファイル名: 簡易文書.txt" in result
        assert "文書タイプ: TXT" in result
        assert "類似度: 0.75" in result
        assert "要約: 簡単な文書" in result

    def test_document_with_missing_fields(self):
        """
        テストケース 5: フィールドが欠けているドキュメント
        """
        documents = [
            {
                "file_name": "不完全文書.pdf",
                # doc_type, summary, similarity, metadata が欠けている
            }
        ]

        result = _build_context(documents)

        # エラーなく処理され、デフォルト値が使用されることを確認
        assert "【文書1】" in result
        assert "ファイル名: 不完全文書.pdf" in result
        assert "文書タイプ: 不明" in result
        assert "類似度: 0.00" in result


# pytest実行時のエントリーポイント
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
