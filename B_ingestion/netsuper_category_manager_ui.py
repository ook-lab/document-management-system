"""
ネットスーパーカテゴリー管理UI

Streamlitを使用して、カテゴリーごとの実行スケジュールを管理します。
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys

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
        now = datetime.now()
        runnable_count = sum(
            1 for cat in categories
            if cat.get("enabled", True) and manager.should_run_category(store_name, cat["name"], now)
        )
        st.metric("実行可能", runnable_count)

    st.divider()

    # カテゴリー一覧を表形式で表示・編集
    st.subheader("カテゴリー一覧")

    # データフレームに変換
    df_data = []
    for cat in categories:
        df_data.append({
            "名前": cat["name"],
            "有効": cat.get("enabled", True),
            "次回実行日時": cat.get("next_run_datetime", ""),
            "インターバル（日）": cat.get("interval_days", 7),
            "前回実行日時": cat.get("last_run_datetime", "未実行"),
            "備考": cat.get("notes", "")
        })

    df = pd.DataFrame(df_data)

    # データエディタで編集
    edited_df = st.data_editor(
        df,
        column_config={
            "名前": st.column_config.TextColumn("カテゴリー名", disabled=True, width="medium"),
            "有効": st.column_config.CheckboxColumn("有効", width="small"),
            "次回実行日時": st.column_config.TextColumn(
                "次回実行日時",
                help="YYYY-MM-DD HH:MM形式で入力（例: 2025-12-24 14:30）",
                width="medium"
            ),
            "インターバル（日）": st.column_config.NumberColumn(
                "インターバル（日）",
                min_value=1,
                max_value=365,
                step=1,
                width="small"
            ),
            "前回実行日時": st.column_config.TextColumn("前回実行日時", disabled=True, width="medium"),
            "備考": st.column_config.TextColumn("備考", width="large")
        },
        hide_index=True,
        width=None,
        key=f"editor_{store_name}"
    )

    # ボタン行
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        if st.button("💾 変更を保存", type="primary", key=f"save_{store_name}"):
            # 変更内容を反映
            for idx, row in edited_df.iterrows():
                category_name = row["名前"]
                manager.update_category(
                    store_name,
                    category_name,
                    {
                        "enabled": row["有効"],
                        "next_run_datetime": row["次回実行日時"],
                        "interval_days": int(row["インターバル（日）"]),
                        "notes": row["備考"]
                    }
                )
            st.success("✅ 変更を保存しました")
            st.rerun()

    with col2:
        # 2分後に実行ボタン
        # 選択可能なカテゴリーのリストを作成
        enabled_category_names = [cat["name"] for cat in categories if cat.get("enabled", True)]

        if enabled_category_names:
            # セッション状態で選択を保持
            if f"selected_for_2min_{store_name}" not in st.session_state:
                st.session_state[f"selected_for_2min_{store_name}"] = []

            selected_for_2min = st.multiselect(
                "2分後実行するカテゴリー",
                options=enabled_category_names,
                default=st.session_state[f"selected_for_2min_{store_name}"],
                key=f"multiselect_2min_{store_name}"
            )
            st.session_state[f"selected_for_2min_{store_name}"] = selected_for_2min

            if st.button("⏱️ 2分後に実行", disabled=len(selected_for_2min) == 0, key=f"set_2min_{store_name}"):
                # 2分後の日時を計算
                two_min_later = datetime.now() + timedelta(minutes=2)
                next_run_str = two_min_later.strftime("%Y-%m-%d %H:%M")

                # 選択されたカテゴリーの次回実行日時を更新
                for cat_name in selected_for_2min:
                    manager.update_category(
                        store_name,
                        cat_name,
                        {"next_run_datetime": next_run_str}
                    )

                st.success(f"✅ {len(selected_for_2min)}件のカテゴリーを2分後（{next_run_str}）に実行するよう設定しました")
                st.info("💡 GitHub Actionsが毎日午前2時に実行され、設定時刻を過ぎているカテゴリーが処理されます")
                st.rerun()

    with col3:
        if st.button("🔄 最終実行日をリセット", key=f"reset_{store_name}"):
            for cat in categories:
                manager.update_category(store_name, cat["name"], {"last_run_datetime": None})
            st.success("✅ すべてのカテゴリーの最終実行日をリセットしました")
            st.rerun()

    with col4:
        if st.button("✅ すべて有効化", key=f"enable_all_{store_name}"):
            for cat in categories:
                manager.update_category(store_name, cat["name"], {"enabled": True})
            st.success("✅ すべてのカテゴリーを有効化しました")
            st.rerun()

    st.divider()

    # 実行日・インターバルの説明
    with st.expander("ℹ️ 次回実行日時・インターバルの仕組み"):
        st.markdown("""
        ### 実行の仕組み

        1. **次回実行日時**
           - 手動で自由に設定可能（YYYY-MM-DD HH:MM形式）
           - GitHub Actionsが毎日午前2時に実行
           - 「現在時刻 >= 次回実行日時」のカテゴリーが処理される

        2. **実行後の自動更新**
           - 実行後、次回実行日時が自動更新される
           - 計算式: `(実行日 + インターバル日数 + 1日) の 午前1時`
           - 例: 12/24実行、インターバル7日 → 次回は 1/1 01:00

        3. **2分後に実行ボタン**
           - カテゴリーを選択して押すと、次回実行日時が「現在+2分」に設定される
           - 次回のGitHub Actions実行時（毎日午前2時）に処理される
           - つまり、翌日午前2時に実行される

        ### 例

        - **通常運用**: 次回実行日時 = 2025-12-28 01:00、インターバル = 7日
          - 12/28 午前2時のGitHub Actions実行時に処理
          - 次回実行日時が自動的に 1/5 01:00 に更新

        - **即時実行したい場合**:
          - 次回実行日時を過去の日時（例: 2025-12-23 00:00）に設定
          - または「2分後に実行」ボタンを押す
          - 翌日午前2時のGitHub Actions実行時に処理される
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
        # 日時入力（日付と時間）
        default_date = st.date_input(
            "デフォルト次回実行日",
            value=datetime.now() + timedelta(days=1),
            key="default_date"
        )
        default_time = st.time_input(
            "デフォルト次回実行時刻",
            value=datetime.strptime("01:00", "%H:%M").time(),
            key="default_time"
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
        # 日付と時刻を結合
        default_datetime = datetime.combine(default_date, default_time)
        next_run_str = default_datetime.strftime("%Y-%m-%d %H:%M")

        categories = manager.get_all_categories(target_store)
        for cat in categories:
            manager.update_category(
                target_store,
                cat["name"],
                {
                    "next_run_datetime": next_run_str,
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
