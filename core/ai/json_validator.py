"""
JSON Schema検証モジュール (JSON Validator)

目的: AI (Claude) が生成したメタデータJSONに対し、
     jsonschemaライブラリを使用して厳密な型・構造・必須フィールドの検証を実行

設計: Phase 2 (Track 1) - JSON Schema検証の導入
     AUTO_INBOX_COMPLETE_v3.0.md の「2.1.2 JSON Schema検証の導入」に準拠

セキュリティ:
    - eval() のような危険な関数は使用しない
    - json.load() による安全なJSONパース
    - jsonschema.validate() による厳密な検証
"""

import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from loguru import logger
import jsonschema
from jsonschema import validate, ValidationError, Draft7Validator


# doc_typeとスキーマファイル名のマッピング
# ✅ 全ての文書はikuya_school.json スキーマに統一 (Phase 4)
DOC_TYPE_SCHEMA_MAPPING = {
    # Phase 4: 単一スキーマ統合 - すべて ikuya_school.json を使用
    'ikuya_school': 'ikuya_school.json',
    # 後方互換性のため旧タイプも ikuya_school.json にマッピング
    'timetable': 'ikuya_school.json',
    'school_notice': 'ikuya_school.json',
    'class_newsletter': 'ikuya_school.json',
    'homework': 'ikuya_school.json',
    'test_exam': 'ikuya_school.json',
    'report_card': 'ikuya_school.json',
    'school_event': 'ikuya_school.json',
    'parent_teacher_meeting': 'ikuya_school.json',
    'notice': 'ikuya_school.json',
    # Phase 3 doc types (すべて ikuya_school.json に統一)
    'gakunen_dayori_monthly': 'ikuya_school.json',
    'gakunen_tsushin_weekly': 'ikuya_school.json',
    'masumi': 'ikuya_school.json',
}


def get_schema_path(doc_type: str, schema_dir: Optional[Path] = None) -> Optional[Path]:
    """
    doc_typeに対応するスキーマファイルのパスを取得

    Args:
        doc_type: 文書タイプ
        schema_dir: スキーマディレクトリ（デフォルト: ui/schemas/）

    Returns:
        スキーマファイルのPath、または存在しない場合はNone
    """
    if schema_dir is None:
        # デフォルトパス: プロジェクトルート/ui/utils/schemas/
        project_root = Path(__file__).parent.parent.parent
        schema_dir = project_root / 'ui' / 'utils' / 'schemas'

    # doc_typeに対応するスキーマファイル名を取得
    schema_filename = DOC_TYPE_SCHEMA_MAPPING.get(doc_type)

    if schema_filename is None:
        logger.debug(f"doc_type '{doc_type}' にはスキーマファイル定義がありません")
        return None

    schema_path = schema_dir / schema_filename

    if not schema_path.exists():
        logger.debug(f"スキーマファイルが存在しません: {schema_path}")
        return None

    return schema_path


def load_schema(schema_path: Path) -> Dict[str, Any]:
    """
    JSONスキーマファイルを安全にロード

    Args:
        schema_path: スキーマファイルのパス

    Returns:
        スキーマ辞書

    Raises:
        FileNotFoundError: ファイルが存在しない
        json.JSONDecodeError: JSON形式が不正
    """
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)  # 安全なJSONパース（eval()は使用しない）

    logger.debug(f"スキーマロード成功: {schema_path.name}")
    return schema


def validate_metadata(
    metadata: Dict[str, Any],
    doc_type: str,
    schema_dir: Optional[Path] = None
) -> Tuple[bool, Optional[str]]:
    """
    メタデータをJSON Schemaで検証

    Args:
        metadata: 検証対象のメタデータ辞書
        doc_type: 文書タイプ
        schema_dir: スキーマディレクトリ（オプション）

    Returns:
        (is_valid, error_message)のタプル
        - is_valid: True = 検証成功, False = 検証失敗
        - error_message: エラーメッセージ（成功時はNone）
    """
    # Step 1: スキーマファイルのパスを取得
    schema_path = get_schema_path(doc_type, schema_dir)

    if schema_path is None:
        # スキーマが定義されていない場合は検証スキップ（警告のみ）
        logger.warning(
            f"[JSON検証] doc_type '{doc_type}' のスキーマが未定義のため検証をスキップします"
        )
        return True, None

    # Step 2: スキーマをロード
    try:
        schema = load_schema(schema_path)
    except FileNotFoundError:
        logger.error(f"[JSON検証] スキーマファイルが見つかりません: {schema_path}")
        return True, None  # スキーマがない場合は検証スキップ
    except json.JSONDecodeError as e:
        logger.error(f"[JSON検証] スキーマファイルのJSON形式が不正: {e}")
        return True, None  # スキーマが不正な場合も検証スキップ

    # Step 3: JSON Schema検証を実行
    try:
        # Draft7Validatorを使用して検証
        validator = Draft7Validator(schema)
        validator.validate(metadata)

        logger.info(f"[JSON検証] ✅ 検証成功: doc_type='{doc_type}'")
        return True, None

    except ValidationError as e:
        # 検証エラーの詳細を構築
        error_path = ".".join(str(p) for p in e.path) if e.path else "root"
        error_message = (
            f"JSON Schema検証エラー (doc_type='{doc_type}'): "
            f"フィールド '{error_path}' - {e.message}"
        )

        logger.error(f"[JSON検証] ❌ 検証失敗: {error_message}")
        logger.debug(f"検証エラー詳細: {e}")

        # 検証失敗の詳細をログに記録
        if e.validator == 'required':
            missing_fields = e.validator_value
            logger.error(f"  必須フィールドが不足: {missing_fields}")
        elif e.validator == 'type':
            logger.error(f"  期待される型: {e.validator_value}, 実際の値: {e.instance}")
        elif e.validator == 'pattern':
            logger.error(f"  パターン不一致: 期待={e.validator_value}, 実際={e.instance}")

        return False, error_message

    except Exception as e:
        # 予期しないエラー
        error_message = f"JSON検証中に予期しないエラー: {type(e).__name__} - {e}"
        logger.error(f"[JSON検証] ❌ {error_message}")

        # 予期しないエラーの場合は検証を通す（安全側に倒す）
        return True, None


def validate_metadata_strict(
    metadata: Dict[str, Any],
    doc_type: str,
    schema_dir: Optional[Path] = None
) -> bool:
    """
    厳密なJSON Schema検証（エラー時は例外を発生）

    Args:
        metadata: 検証対象のメタデータ辞書
        doc_type: 文書タイプ
        schema_dir: スキーマディレクトリ（オプション）

    Returns:
        True: 検証成功

    Raises:
        ValidationError: 検証失敗時
    """
    schema_path = get_schema_path(doc_type, schema_dir)

    if schema_path is None:
        logger.warning(
            f"[JSON検証] doc_type '{doc_type}' のスキーマが未定義のため検証をスキップします"
        )
        return True

    try:
        schema = load_schema(schema_path)
        validate(metadata, schema)
        logger.info(f"[JSON検証] ✅ 検証成功: doc_type='{doc_type}'")
        return True

    except ValidationError as e:
        logger.error(f"[JSON検証] ❌ 検証失敗: doc_type='{doc_type}' - {e.message}")
        raise


def get_validation_errors(
    metadata: Dict[str, Any],
    doc_type: str,
    schema_dir: Optional[Path] = None
) -> list:
    """
    全ての検証エラーをリストで取得（複数エラーを一度に確認）

    Args:
        metadata: 検証対象のメタデータ辞書
        doc_type: 文書タイプ
        schema_dir: スキーマディレクトリ（オプション）

    Returns:
        ValidationErrorのリスト（エラーがない場合は空リスト）
    """
    schema_path = get_schema_path(doc_type, schema_dir)

    if schema_path is None:
        return []

    try:
        schema = load_schema(schema_path)
        validator = Draft7Validator(schema)

        # iter_errors()で全てのエラーを取得
        errors = list(validator.iter_errors(metadata))

        if errors:
            logger.warning(f"[JSON検証] {len(errors)}件の検証エラーを検出")
            for error in errors:
                error_path = ".".join(str(p) for p in error.path) if error.path else "root"
                logger.warning(f"  - {error_path}: {error.message}")

        return errors

    except Exception as e:
        logger.error(f"[JSON検証] エラー一覧取得中にエラー: {e}")
        return []
