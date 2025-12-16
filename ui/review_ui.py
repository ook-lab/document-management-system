"""
Streamlit App Wrapper
このファイルは後方互換性のために存在します。
実際のアプリケーションはH_streamlit/review_ui.pyにあります。
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 実際のアプリケーションをインポートして実行
from H_streamlit import review_ui

# review_ui.pyの内容を実行
if __name__ == "__main__":
    # H_streamlit/review_ui.pyを直接実行
    import runpy
    runpy.run_path(str(project_root / "H_streamlit" / "review_ui.py"), run_name="__main__")
