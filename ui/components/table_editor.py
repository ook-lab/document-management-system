"""
Table Editor Component
データフレーム形式での表編集UI
"""
import streamlit as st
import pandas as pd
from typing import Dict, Any, List


def render_table_editor(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    メタデータを表形式で編集

    Args:
        metadata: 現在のメタデータ

    Returns:
        編集後のメタデータ
    """
    st.markdown("### 📊 表エディタ")
    st.markdown("配列データを表形式で編集できます")
    st.markdown("---")

    edited_metadata = metadata.copy()

    # 配列型のフィールドを検出して表示
    array_fields = _find_array_fields(metadata)

    if not array_fields:
        st.info("表形式で編集可能な配列データが見つかりません")
        return edited_metadata

    # タブで配列ごとに表示
    if len(array_fields) > 1:
        tabs = st.tabs([field["label"] for field in array_fields])
        for tab, field in zip(tabs, array_fields):
            with tab:
                edited_value = _render_array_table(
                    field["name"],
                    field["value"],
                    field["label"]
                )
                edited_metadata[field["name"]] = edited_value
    else:
        # 配列が1つの場合はタブなしで表示
        field = array_fields[0]
        edited_value = _render_array_table(
            field["name"],
            field["value"],
            field["label"]
        )
        edited_metadata[field["name"]] = edited_value

    return edited_metadata


def _find_array_fields(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    メタデータから配列フィールドを抽出

    Returns:
        [{"name": フィールド名, "value": 配列値, "label": 表示名}, ...]
    """
    array_fields = []

    for key, value in metadata.items():
        if isinstance(value, list) and len(value) > 0:
            # 配列の要素が辞書の場合のみ表エディタで扱う
            if isinstance(value[0], dict):
                array_fields.append({
                    "name": key,
                    "value": value,
                    "label": _format_field_name(key)
                })

    return array_fields


def _format_field_name(field_name: str) -> str:
    """フィールド名を表示用に整形"""
    name_map = {
        "daily_schedule": "日別時間割",
        "weekly_schedule": "週間予定",
        "periods": "時限別科目",
        "class_schedules": "クラス別時間割",
        "requirements": "持ち物・準備",
        "important_points": "重要事項",
        "special_events": "特別イベント"
    }
    return name_map.get(field_name, field_name)


def _render_array_table(field_name: str, array_value: List[Dict], label: str) -> List[Dict]:
    """
    配列データを表形式で編集

    Args:
        field_name: フィールド名
        array_value: 配列データ
        label: 表示ラベル

    Returns:
        編集後の配列データ
    """
    if not array_value:
        st.info(f"{label}のデータがありません")
        return []

    # データフレームに変換
    try:
        df = pd.DataFrame(array_value)

        # PyArrow エラー対策: 型強制とデータクリーニング
        # すべての列を文字列型に変換して混合型を解消
        df = df.astype(str)

        # NaN, None を空文字列に置き換え
        df = df.fillna("")

        # 文字列化された "None", "nan", "NaN" も空文字列に置き換え
        df = df.replace(["None", "nan", "NaN", "null"], "")

    except Exception as e:
        st.error(f"データフレーム変換エラー: {e}")
        st.json(array_value)
        return array_value

    # st.data_editorで編集可能な表を表示
    st.markdown(f"#### {label}")
    st.caption(f"全 {len(df)} 行")

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",  # 行の追加・削除を許可
        key=f"table_{field_name}",
        height=400
    )

    # データフレームを辞書のリストに戻す
    try:
        edited_array = edited_df.to_dict('records')

        # データクリーニング: 空文字列を削除（オプショナルなフィールド用）
        cleaned_array = []
        for record in edited_array:
            cleaned_record = {k: v for k, v in record.items() if v != ""}
            # 空のレコードは除外
            if cleaned_record:
                cleaned_array.append(cleaned_record)

        return cleaned_array

    except Exception as e:
        st.error(f"データ変換エラー: {e}")
        return array_value


def render_nested_table_editor(metadata: Dict[str, Any], path: List[str] = None) -> Dict[str, Any]:
    """
    ネストした配列データを再帰的に表示・編集

    Args:
        metadata: メタデータ
        path: 現在のパス（再帰用）

    Returns:
        編集後のメタデータ
    """
    if path is None:
        path = []

    edited_metadata = {}

    for key, value in metadata.items():
        current_path = path + [key]

        if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
            # 配列データ: 展開して表示
            with st.expander(f"📋 {_format_field_name(key)} ({len(value)}件)", expanded=True):
                edited_metadata[key] = _render_array_table(
                    "_".join(current_path),
                    value,
                    _format_field_name(key)
                )

        elif isinstance(value, dict):
            # ネストしたオブジェクト: 再帰的に処理
            with st.expander(f"📂 {_format_field_name(key)}", expanded=False):
                edited_metadata[key] = render_nested_table_editor(value, current_path)

        else:
            # その他のフィールドは表示のみ
            edited_metadata[key] = value

    return edited_metadata
