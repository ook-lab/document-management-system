"""
ネットスーパーカテゴリー管理UI

Streamlitを使用して、カテゴリーごとの実行スケジュールを管理します。
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from pathlib import Path
import sys
import subprocess
import os
import threading

# プロジェクトルートをパスに追加
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from B_ingestion.common.category_manager import CategoryManager

# ページ設定
st.set_page_config(
    page_title="ネットスーパーカテゴリー管理",
    page_icon="🛒",
    layout="wide"
)

st.title("🛒 ネットスーパーカテゴリー管理")

# CategoryManagerの初期化
if 'manager' not in st.session_state:
    st.session_state['manager'] = CategoryManager()

manager = st.session_state['manager']

# 店舗ごとのスクリプト設定
STORE_SCRIPTS = {
    "rakuten_seiyu": {
        "module": "B_ingestion.rakuten_seiyu.process_with_schedule",
        "display_name": "楽天西友ネットスーパー"
    },
    "tokyu_store": {
        "module": "B_ingestion.tokyu_store.process_with_schedule",
        "display_name": "東急ストア"
    },
    "daiei": {
        "module": "B_ingestion.daiei.process_with_schedule",
        "display_name": "ダイエーネットスーパー"
    }
}

def run_manual_fetch(store_name: str, categories: list):
    """選択されたカテゴリーの商品を今すぐ取り込む

    Args:
        store_name: 店舗名 (rakuten_seiyu, tokyu_store, daiei)
        categories: 取り込むカテゴリー名のリスト
    """
    try:
        # プロジェクトルートに移動してスクリプトを実行
        script_module = STORE_SCRIPTS[store_name]["module"]

        # Pythonスクリプトをサブプロセスで実行
        # カテゴリーを環境変数として渡す
        env = os.environ.copy()
        env["MANUAL_CATEGORIES"] = ",".join(categories)

        cmd = [sys.executable, "-m", script_module, "--manual"]

        result = subprocess.run(
            cmd,
            cwd=root_dir,
            capture_output=True,
            text=True,
            env=env,
            timeout=3600  # 1時間タイムアウト
        )

        return result.returncode == 0, result.stdout, result.stderr

    except Exception as e:
        return False, "", str(e)

# タブで店舗を切り替え
tabs = st.tabs(["楽天西友", "東急ストア", "ダイエー", "設定"])

# 各店舗の共通処理
def show_store_categories(store_name: str, store_display_name: str):
    """店舗のカテゴリー管理画面を表示"""
    st.header(f"{store_display_name} カテゴリー管理")

    categories = manager.get_all_categories(store_name)

    if not categories:
        st.info(f"{store_display_name} のカテゴリーが登録されていません。")
        st.markdown("初期化するには、スクレイピングスクリプトを一度実行してください。")
        return

    # 統計情報
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("総カテゴリー数", len(categories))
    with col2:
        enabled_count = sum(1 for cat in categories if cat.get("enabled", True))
        st.metric("有効", enabled_count)
    with col3:
        disabled_count = len(categories) - enabled_count
        st.metric("無効", disabled_count)
    with col4:
        today = datetime.now()
        runnable_count = sum(
            1 for cat in categories
            if cat.get("enabled", True) and manager.should_run_category(store_name, cat["name"], today)
        )
        st.metric("本日実行可能", runnable_count)

    st.divider()

    # 今すぐ取り込みセクション
    st.subheader("🚀 商品データ取り込み")

    col1, col2 = st.columns([3, 1])
    with col1:
        # カテゴリー選択（有効なカテゴリーのみ）
        enabled_categories = [cat for cat in categories if cat.get("enabled", True)]
        if enabled_categories:
            selected_category_names = st.multiselect(
                "取り込むカテゴリーを選択",
                options=[cat["name"] for cat in enabled_categories],
                default=None,
                key=f"selected_categories_{store_name}"
            )
        else:
            selected_category_names = []
            st.info("有効なカテゴリーがありません")

    with col2:
        fetch_button_disabled = len(selected_category_names) == 0
        if st.button(
            "📥 今すぐ取り込み",
            type="primary",
            disabled=fetch_button_disabled,
            key=f"fetch_{store_name}"
        ):
            if selected_category_names:
                with st.spinner(f"{store_display_name} から商品データを取り込み中..."):
                    success, stdout, stderr = run_manual_fetch(store_name, selected_category_names)

                    if success:
                        st.success(f"✅ {len(selected_category_names)}件のカテゴリーから商品データを取り込みました")
                        # 実行済みとしてマーク
                        for cat_name in selected_category_names:
                            manager.mark_as_run(store_name, cat_name, datetime.now())
                        st.rerun()
                    else:
                        st.error("❌ 取り込み中にエラーが発生しました")
                        if stderr:
                            with st.expander("エラー詳細"):
                                st.code(stderr)
                        if stdout:
                            with st.expander("実行ログ"):
                                st.code(stdout)

    if selected_category_names:
        st.caption(f"選択中: {len(selected_category_names)}件のカテゴリー")

    st.divider()

    # カテゴリー一覧を表形式で表示・編集
    st.subheader("カテゴリー一覧")

    # データフレームに変換
    df_data = []
    for cat in categories:
        next_run = manager.get_next_run_date(store_name, cat["name"])

        # 文字列の日付をdatetimeオブジェクトに変換
        start_date = datetime.strptime(cat["start_date"], "%Y-%m-%d").date()

        df_data.append({
            "名前": cat["name"],
            "有効": cat.get("enabled", True),
            "開始日": start_date,
            "インターバル（日）": cat["interval_days"],
            "前回実行": cat.get("last_run", "未実行"),
            "次回実行予定": next_run or "—",
            "備考": cat.get("notes", "")
        })

    df = pd.DataFrame(df_data)

    # データエディタで編集
    edited_df = st.data_editor(
        df,
        column_config={
            "名前": st.column_config.TextColumn("カテゴリー名", disabled=True, width="medium"),
            "有効": st.column_config.CheckboxColumn("有効", width="small"),
            "開始日": st.column_config.DateColumn("開始日", format="YYYY-MM-DD", width="small"),
            "インターバル（日）": st.column_config.NumberColumn(
                "インターバル（日）",
                min_value=1,
                max_value=365,
                step=1,
                width="small"
            ),
            "前回実行": st.column_config.TextColumn("前回実行", disabled=True, width="small"),
            "次回実行予定": st.column_config.TextColumn("次回実行予定", disabled=True, width="small"),
            "備考": st.column_config.TextColumn("備考", width="large")
        },
        hide_index=True,
        use_container_width=True,
        key=f"editor_{store_name}"
    )

    # 保存ボタン
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("💾 変更を保存", type="primary", key=f"save_{store_name}"):
            # 変更内容を反映
            for idx, row in edited_df.iterrows():
                category_name = row["名前"]
                # 日付オブジェクトを文字列に変換
                start_date_value = row["開始日"]
                if isinstance(start_date_value, (datetime, date)):
                    start_date_str = start_date_value.strftime("%Y-%m-%d")
                else:
                    start_date_str = start_date_value

                manager.update_category(
                    store_name,
                    category_name,
                    {
                        "enabled": row["有効"],
                        "start_date": start_date_str,
                        "interval_days": int(row["インターバル（日）"]),
                        "notes": row["備考"]
                    }
                )
            st.success("✅ 変更を保存しました")
            st.rerun()

    with col2:
        if st.button("🔄 最終実行日をリセット", key=f"reset_{store_name}"):
            for cat in categories:
                manager.update_category(store_name, cat["name"], {"last_run": None})
            st.success("✅ すべてのカテゴリーの最終実行日をリセットしました")
            st.rerun()

    with col3:
        if st.button("✅ すべて有効化", key=f"enable_all_{store_name}"):
            for cat in categories:
                manager.update_category(store_name, cat["name"], {"enabled": True})
            st.success("✅ すべてのカテゴリーを有効化しました")
            st.rerun()

    st.divider()

    # 実行日・インターバルの説明
    with st.expander("ℹ️ 実行日・インターバルの仕組み"):
        st.markdown("""
        ### 実行日の計算ルール

        1. **開始日が未来の場合**
           - 開始日が1回目の実行日
           - 2回目以降は、前回実行日 + インターバル日数

        2. **開始日が今日または過去の場合**
           - まだ一度も実行していない場合: 開始日 + インターバル日数が1回目の実行日
           - すでに実行済みの場合: 前回実行日 + インターバル日数が次回実行日

        ### 例

        - 開始日: 2025-12-25、インターバル: 7日
          - 2025-12-25 に実行される（開始日が未来のため）
          - 次回: 2026-01-01（前回 + 7日）

        - 開始日: 2025-12-20（過去）、インターバル: 3日、前回実行: なし
          - 次回: 2025-12-23（開始日 + 3日）

        - 開始日: 2025-12-20（過去）、インターバル: 3日、前回実行: 2025-12-22
          - 次回: 2025-12-25（前回実行 + 3日）
        """)

# 各タブに店舗を表示
with tabs[0]:
    show_store_categories("rakuten_seiyu", "楽天西友ネットスーパー")

with tabs[1]:
    show_store_categories("tokyu_store", "東急ストア")

with tabs[2]:
    show_store_categories("daiei", "ダイエーネットスーパー")

# 設定タブ
with tabs[3]:
    st.header("⚙️ 全般設定")

    st.subheader("設定ファイル")
    st.text(f"パス: {manager.config_path}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 設定を再読み込み"):
            manager.load_config()
            st.success("✅ 設定を再読み込みしました")
            st.rerun()

    with col2:
        if st.button("🗑️ 設定ファイルを削除（初期化）"):
            if manager.config_path.exists():
                manager.config_path.unlink()
                st.success("✅ 設定ファイルを削除しました。スクリプトを再実行して初期化してください。")
                st.session_state['manager'] = CategoryManager()
                st.rerun()

    st.divider()

    st.subheader("一括設定")

    col1, col2, col3 = st.columns(3)

    with col1:
        default_interval = st.number_input(
            "デフォルトインターバル（日）",
            min_value=1,
            max_value=365,
            value=7,
            key="default_interval"
        )

    with col2:
        default_start = st.date_input(
            "デフォルト開始日",
            value=datetime.now(),
            key="default_start"
        )

    with col3:
        target_store = st.selectbox(
            "対象店舗",
            ["rakuten_seiyu", "tokyu_store", "daiei"],
            format_func=lambda x: {
                "rakuten_seiyu": "楽天西友",
                "tokyu_store": "東急ストア",
                "daiei": "ダイエー"
            }[x],
            key="target_store"
        )

    if st.button("🔄 選択した店舗のすべてのカテゴリーに一括適用"):
        categories = manager.get_all_categories(target_store)
        for cat in categories:
            manager.update_category(
                target_store,
                cat["name"],
                {
                    "start_date": default_start.strftime("%Y-%m-%d"),
                    "interval_days": default_interval
                }
            )
        st.success(f"✅ {target_store} のすべてのカテゴリーに設定を適用しました")
        st.rerun()

    st.divider()

    st.subheader("設定ファイルの内容")
    if manager.config:
        st.json(manager.config)
    else:
        st.info("設定ファイルが空です")
