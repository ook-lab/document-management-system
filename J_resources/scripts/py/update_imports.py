#!/usr/bin/env python3
"""
Import文を新しいフォルダ構造に合わせて一括更新するスクリプト
"""
import os
import re
from pathlib import Path

# 置換マッピング（古いimport -> 新しいimport）
REPLACEMENTS = [
    # core.ai 関連
    (r'from core\.ai\.llm_client import', 'from C_ai_common.llm_client.llm_client import'),
    (r'from core\.ai\.embeddings import', 'from C_ai_common.embeddings.embeddings import'),
    (r'from core\.ai\.stageA_classifier import', 'from D_stage_a_classifier.classifier import'),
    (r'from core\.ai\.stageB_vision import', 'from E_stage_b_vision.vision import'),
    (r'from core\.ai\.stageC_extractor import', 'from F_stage_c_extractor.extractor import'),
    (r'import core\.ai\.llm_client', 'import C_ai_common.llm_client.llm_client'),
    (r'import core\.ai\.embeddings', 'import C_ai_common.embeddings.embeddings'),

    # core.database
    (r'from core\.database\.client import', 'from A_common.database.client import'),
    (r'from core\.database import', 'from A_common.database import'),
    (r'import core\.database', 'import A_common.database'),

    # core.utils
    (r'from core\.utils\.', 'from A_common.utils.'),
    (r'import core\.utils', 'import A_common.utils'),

    # core.processors
    (r'from core\.processors\.', 'from A_common.processors.'),
    (r'import core\.processors', 'import A_common.processors'),

    # core.connectors
    (r'from core\.connectors\.', 'from A_common.connectors.'),
    (r'import core\.connectors', 'import A_common.connectors'),

    # core.processing
    (r'from core\.processing\.', 'from A_common.processing.'),
    (r'import core\.processing', 'import A_common.processing'),

    # config
    (r'from config\.', 'from A_common.config.'),
    (r'import config\.', 'import A_common.config.'),
    (r'^import config$', 'import A_common.config'),

    # ui
    (r'from ui\.components\.', 'from H_streamlit.components.'),
    (r'from ui\.utils\.', 'from H_streamlit.utils.'),
    (r'from ui\.', 'from H_streamlit.'),
    (r'import ui\.', 'import H_streamlit.'),

    # pipelines
    (r'from pipelines\.', 'from B_ingestion.'),
    (r'import pipelines\.', 'import B_ingestion.'),
]

def update_file(file_path: Path) -> tuple[int, list]:
    """ファイル内のimport文を更新"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        changes = []

        for pattern, replacement in REPLACEMENTS:
            matches = re.findall(pattern, content, re.MULTILINE)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
                changes.append(f"{pattern} -> {replacement}")

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return len(changes), changes

        return 0, []

    except Exception as e:
        print(f"[ERROR] {file_path}: {e}")
        return 0, []

def main():
    """メイン処理"""
    base_dir = Path(__file__).parent

    # 対象フォルダ
    target_dirs = [
        'A_common',
        'B_ingestion',
        'C_ai_common',
        'D_stage_a_classifier',
        'E_stage_b_vision',
        'F_stage_c_extractor',
        'G_cloud_run',
        'H_streamlit',
        'tests',
    ]

    total_files = 0
    total_changes = 0

    print("=" * 60)
    print("Import文の一括更新を開始します")
    print("=" * 60)

    for dir_name in target_dirs:
        dir_path = base_dir / dir_name
        if not dir_path.exists():
            print(f"[SKIP] {dir_name} が見つかりません")
            continue

        print(f"\n[処理中] {dir_name}/")

        # .pyファイルを再帰的に検索
        py_files = list(dir_path.rglob('*.py'))

        for py_file in py_files:
            if '__pycache__' in str(py_file):
                continue

            num_changes, changes = update_file(py_file)

            if num_changes > 0:
                total_files += 1
                total_changes += num_changes
                rel_path = py_file.relative_to(base_dir)
                print(f"  [OK] {rel_path} ({num_changes}件の変更)")
                for change in changes:
                    print(f"    -> {change}")

    print("\n" + "=" * 60)
    print(f"完了: {total_files}ファイル、{total_changes}箇所を更新しました")
    print("=" * 60)

if __name__ == '__main__':
    main()
