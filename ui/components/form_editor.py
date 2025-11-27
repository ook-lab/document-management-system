"""
Form Editor Component
スキーマベースのフォーム編集UI
"""
import streamlit as st
from typing import Dict, Any, List
from datetime import datetime, date


def render_form_editor(metadata: Dict[str, Any], fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    スキーマ定義に基づいてフォーム形式のエディタを表示

    Args:
        metadata: 現在のメタデータ
        fields: スキーマから取得したフィールド定義リスト

    Returns:
        編集後のメタデータ
    """
    edited_metadata = {}

    st.markdown("### 📝 フォーム編集")
    st.markdown("各フィールドを個別に編集できます")
    st.markdown("---")

    for field in fields:
        field_name = field["name"]
        field_type = field["type"]
        field_title = field["title"]
        field_description = field["description"]
        required = field["required"]
        current_value = metadata.get(field_name)

        # フィールドラベル
        label = f"{'🔴 ' if required else ''}{field_title}"
        help_text = field_description if field_description else None

        # 型に応じた入力ウィジェット
        if field_type == "string":
            if field.get("format") == "date":
                # 日付入力
                edited_metadata[field_name] = _render_date_input(
                    field_name, label, current_value, help_text
                )
            elif field.get("enum"):
                # 選択肢入力
                edited_metadata[field_name] = _render_select_input(
                    field_name, label, current_value, field["enum"], help_text
                )
            else:
                # テキスト入力
                edited_metadata[field_name] = st.text_input(
                    label,
                    value=current_value if current_value else "",
                    help=help_text,
                    key=f"form_{field_name}"
                )

        elif field_type == "integer":
            # 整数入力
            edited_metadata[field_name] = st.number_input(
                label,
                value=int(current_value) if current_value is not None else 0,
                step=1,
                help=help_text,
                key=f"form_{field_name}"
            )

        elif field_type == "number":
            # 数値入力
            edited_metadata[field_name] = st.number_input(
                label,
                value=float(current_value) if current_value is not None else 0.0,
                help=help_text,
                key=f"form_{field_name}"
            )

        elif field_type == "boolean":
            # チェックボックス
            edited_metadata[field_name] = st.checkbox(
                label,
                value=bool(current_value) if current_value is not None else False,
                help=help_text,
                key=f"form_{field_name}"
            )

        elif field_type == "array":
            # 配列入力
            edited_metadata[field_name] = _render_array_input(
                field_name, label, current_value, field.get("items"), help_text
            )

        elif field_type == "object":
            # オブジェクト入力（展開表示）
            with st.expander(label, expanded=False):
                if field_description:
                    st.caption(field_description)
                edited_metadata[field_name] = _render_object_input(
                    field_name, current_value
                )

        else:
            # その他の型はテキストエリアで表示
            edited_metadata[field_name] = st.text_area(
                label,
                value=str(current_value) if current_value else "",
                help=help_text,
                key=f"form_{field_name}"
            )

    return edited_metadata


def _render_date_input(field_name: str, label: str, current_value: Any, help_text: str) -> str:
    """日付入力フィールド"""
    if current_value:
        try:
            if isinstance(current_value, str):
                current_date = datetime.strptime(current_value, "%Y-%m-%d").date()
            else:
                current_date = current_value
        except:
            current_date = date.today()
    else:
        current_date = date.today()

    selected_date = st.date_input(
        label,
        value=current_date,
        help=help_text,
        key=f"form_{field_name}"
    )

    return selected_date.strftime("%Y-%m-%d")


def _render_select_input(field_name: str, label: str, current_value: Any, options: List[str], help_text: str) -> str:
    """選択肢入力フィールド"""
    if current_value and current_value in options:
        index = options.index(current_value)
    else:
        index = 0

    return st.selectbox(
        label,
        options=options,
        index=index,
        help=help_text,
        key=f"form_{field_name}"
    )


def _render_array_input(field_name: str, label: str, current_value: Any, items_def: Dict, help_text: str) -> List:
    """配列入力フィールド"""
    st.markdown(f"**{label}**")
    if help_text:
        st.caption(help_text)

    if not current_value:
        current_value = []

    # 配列の型に応じた処理
    if items_def and items_def.get("type") == "string":
        # 文字列配列: テキストエリアで改行区切り入力
        text_value = "\n".join(current_value) if isinstance(current_value, list) else ""
        edited_text = st.text_area(
            f"{label}（1行1項目）",
            value=text_value,
            height=150,
            label_visibility="collapsed",
            key=f"form_{field_name}"
        )
        return [line.strip() for line in edited_text.split("\n") if line.strip()]

    elif items_def and items_def.get("type") == "object":
        # オブジェクト配列: 展開可能なリストとして表示
        edited_array = []
        for idx, item in enumerate(current_value):
            with st.expander(f"項目 {idx + 1}", expanded=False):
                edited_item = _render_object_input(f"{field_name}_{idx}", item)
                edited_array.append(edited_item)

        # 新規追加ボタン
        if st.button(f"➕ {label}に項目を追加", key=f"add_{field_name}"):
            st.info("保存後、新しい項目が追加されます")

        return edited_array

    else:
        # デフォルト: JSON文字列として表示
        import json
        json_str = json.dumps(current_value, ensure_ascii=False, indent=2)
        edited_json = st.text_area(
            f"{label}（JSON形式）",
            value=json_str,
            height=200,
            label_visibility="collapsed",
            key=f"form_{field_name}"
        )
        try:
            return json.loads(edited_json)
        except:
            st.error("JSON形式が不正です")
            return current_value


def _render_object_input(field_name: str, current_value: Any) -> Dict:
    """オブジェクト入力フィールド"""
    import json

    if not current_value:
        current_value = {}

    json_str = json.dumps(current_value, ensure_ascii=False, indent=2)
    edited_json = st.text_area(
        "JSON形式で編集",
        value=json_str,
        height=200,
        key=f"form_obj_{field_name}"
    )

    try:
        return json.loads(edited_json)
    except json.JSONDecodeError:
        st.error("JSON形式が不正です")
        return current_value
