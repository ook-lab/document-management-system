"""
YAML Loader
CLASSIFICATION_MAPPING_v2.0.yaml を読み込んで文字列として返す
"""
from pathlib import Path
import yaml


def get_classification_yaml_string() -> str:
    """
    CLASSIFICATION_MAPPING_v2.0.yaml を読み込んで文字列として返す
    
    Returns:
        YAMLファイルの内容（文字列）
    """
    yaml_path = Path(__file__).parent / "CLASSIFICATION_MAPPING_v2.0.yaml"
    
    if not yaml_path.exists():
        raise FileNotFoundError(f"分類マッピングファイルが見つかりません: {yaml_path}")
    
    with open(yaml_path, "r", encoding="utf-8") as f:
        return f.read()


def load_classification_mapping() -> dict:
    """
    CLASSIFICATION_MAPPING_v2.0.yaml を辞書として読み込む

    Returns:
        YAMLファイルの内容（辞書）
    """
    yaml_path = Path(__file__).parent / "CLASSIFICATION_MAPPING_v2.0.yaml"

    if not yaml_path.exists():
        raise FileNotFoundError(f"分類マッピングファイルが見つかりません: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_user_context() -> dict:
    """
    user_context.yaml を辞書として読み込む

    Returns:
        YAMLファイルの内容（辞書）
        ファイルが存在しない場合は空の辞書を返す
    """
    yaml_path = Path(__file__).parent / "user_context.yaml"

    if not yaml_path.exists():
        # ファイルが存在しない場合は空の辞書を返す（エラーにしない）
        return {"children": [], "settings": {}}

    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_user_context_string() -> str:
    """
    user_context.yaml を読み込んで文字列として返す

    Returns:
        YAMLファイルの内容（文字列）
        ファイルが存在しない場合は空文字列を返す
    """
    yaml_path = Path(__file__).parent / "user_context.yaml"

    if not yaml_path.exists():
        return ""

    with open(yaml_path, "r", encoding="utf-8") as f:
        return f.read()