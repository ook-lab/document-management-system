"""
Form Editor Component
スキーマベースのフォーム編集UI
"""
import streamlit as st
from typing import Dict, Any, List
from datetime import datetime, date


def _calculate_text_height(text: str, min_height: int = 100, max_height: int = 600) -> int:
    """
    テキストの内容に基づいて適切な高さを計算

    Args:
        text: テキストの内容
        min_height: 最小の高さ（ピクセル）
        max_height: 最大の高さ（ピクセル）

    Returns:
        計算された高さ（ピクセル）
    """
    if not text:
        return min_height

    # 行数をカウント
    line_count = text.count('\n') + 1

    # 各行の長さをチェックして折り返しを考慮
    # 1行あたり約80文字で折り返すと仮定
    estimated_lines = 0
    for line in text.split('\n'):
        estimated_lines += max(1, len(line) // 80 + (1 if len(line) % 80 else 0))

    # より正確な行数を使用
    total_lines = max(line_count, estimated_lines)

    # 1行あたり約25ピクセルとして計算
    calculated_height = total_lines * 25

    # min_heightとmax_heightの範囲内に収める
    return max(min_height, min(calculated_height, max_height))


def _is_empty_value(value: Any) -> bool:
    """
    値が空かどうかをチェック

    Args:
        value: チェックする値

    Returns:
        空の場合True、値がある場合False
    """
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


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

        # text_blocksの特別処理: 最初に処理して他の処理をスキップ
        if field_name == "text_blocks":
            current_value = metadata.get(field_name)
            if not _is_empty_value(current_value):
                edited_metadata[field_name] = _render_text_blocks_input(
                    field_name, "", current_value, field.get("items")
                )
            continue  # 他の処理をスキップ

        field_type = field["type"]
        field_title = field["title"]
        field_description = field["description"]
        required = field["required"]
        current_value = metadata.get(field_name)

        # 空のフィールドをスキップ（必須フィールドは除く）
        if not required and _is_empty_value(current_value):
            continue

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
            text_value = str(current_value) if current_value else ""
            edited_metadata[field_name] = st.text_area(
                label,
                value=text_value,
                height=_calculate_text_height(text_value),
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
    if not current_value:
        current_value = []

    # 配列の型に応じた処理
    if items_def and items_def.get("type") == "string":
        # 文字列配列: テキストエリアで改行区切り入力
        st.markdown(f"**{label}**")
        if help_text:
            st.caption(help_text)

        text_value = "\n".join(current_value) if isinstance(current_value, list) else ""
        edited_text = st.text_area(
            f"{label}（1行1項目）",
            value=text_value,
            height=_calculate_text_height(text_value, min_height=100, max_height=400),
            label_visibility="collapsed",
            key=f"form_{field_name}"
        )
        return [line.strip() for line in edited_text.split("\n") if line.strip()]

    elif items_def and items_def.get("type") == "object":
        # オブジェクト配列: ラベルを表示してから処理
        st.markdown(f"**{label}**")
        if help_text:
            st.caption(help_text)
        return _render_object_array_input(field_name, label, current_value, items_def)

    else:
        # デフォルト: JSON文字列として表示
        import json
        json_str = json.dumps(current_value, ensure_ascii=False, indent=2)
        edited_json = st.text_area(
            f"{label}（JSON形式）",
            value=json_str,
            height=_calculate_text_height(json_str, min_height=150, max_height=500),
            label_visibility="collapsed",
            key=f"form_{field_name}"
        )
        try:
            return json.loads(edited_json)
        except:
            st.error("JSON形式が不正です")
            return current_value


def _render_text_blocks_input(field_name: str, label: str, current_value: List[Dict], items_def: Dict) -> List[Dict]:
    """
    text_blocks専用の入力フィールド
    各ブロックをtitleをヘッダーとするボックスで表示

    Args:
        field_name: フィールド名
        label: ラベル
        current_value: 現在の値（text_blocksの配列）
        items_def: スキーマのitems定義

    Returns:
        編集後のtext_blocks配列
    """
    if not current_value:
        current_value = []

    edited_array = []

    for idx, block in enumerate(current_value):
        block_title = block.get("title", f"セクション {idx + 1}")
        block_content = block.get("content", "")

        # 各ブロックをexpanderで表示
        with st.expander(f"📝 {block_title}", expanded=True):
            # タイトルの編集
            edited_title = st.text_input(
                "見出し",
                value=block_title,
                key=f"form_{field_name}_{idx}_title"
            )

            # コンテンツの編集（動的サイズ）
            edited_content = st.text_area(
                "本文",
                value=block_content,
                height=_calculate_text_height(block_content, min_height=150, max_height=600),
                key=f"form_{field_name}_{idx}_content"
            )

            edited_array.append({
                "title": edited_title,
                "content": edited_content
            })

    # 追加・削除コントロール
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button(f"➕ 新しいセクションを追加", key=f"add_{field_name}"):
            st.info("💡 保存後、新しいセクションが追加されます")

    with col2:
        if len(edited_array) > 0:
            if st.button(f"🗑️ 最後のセクションを削除", key=f"remove_{field_name}"):
                edited_array = edited_array[:-1]
                st.success("最後のセクションを削除しました")

    return edited_array


def _render_object_array_input(field_name: str, label: str, current_value: List[Dict], items_def: Dict) -> List[Dict]:
    """
    オブジェクト配列入力フィールド（スキーマ定義に基づく）

    Args:
        field_name: フィールド名
        label: ラベル
        current_value: 現在の値（オブジェクトの配列）
        items_def: スキーマのitems定義

    Returns:
        編集後のオブジェクト配列
    """
    if not current_value:
        current_value = []

    # スキーマからプロパティ定義を取得
    properties = items_def.get("properties", {})
    required_fields = items_def.get("required", [])

    # プロパティ定義がない場合は、フォールバックとしてJSON編集
    if not properties:
        st.info("📝 このフィールドはJSON形式で編集してください")
        edited_array = []
        for idx, item in enumerate(current_value):
            with st.expander(f"項目 {idx + 1}", expanded=False):
                edited_item = _render_object_input(f"{field_name}_{idx}", item)
                edited_array.append(edited_item)
        return edited_array

    # 各アイテムをアコーディオンで表示
    edited_array = []
    for idx, item in enumerate(current_value):
        # アイテムのタイトルを生成（titleフィールドがあれば使用）
        item_title = item.get("title", f"項目 {idx + 1}")

        with st.expander(f"📄 {item_title}", expanded=False):
            edited_item = {}

            # 各プロパティを個別の入力フィールドとして表示
            for prop_name, prop_def in properties.items():
                prop_type = prop_def.get("type", "string")
                prop_title = prop_def.get("title", prop_name)
                prop_description = prop_def.get("description", "")
                is_required = prop_name in required_fields

                prop_value = item.get(prop_name, "")

                # 空のフィールドをスキップ（必須フィールドとtitle/contentは除く）
                # title/contentは文書セクションで重要なので常に表示
                if not is_required and prop_name not in ["title", "content"] and _is_empty_value(prop_value):
                    continue

                # フィールドラベル
                prop_label = f"{'🔴 ' if is_required else ''}{prop_title}"

                # 型に応じた入力ウィジェット
                if prop_type == "string":
                    # contentフィールドは大きなテキストエリアで表示
                    if prop_name == "content" or len(str(prop_value)) > 100:
                        text_value = str(prop_value) if prop_value else ""
                        edited_item[prop_name] = st.text_area(
                            prop_label,
                            value=text_value,
                            height=_calculate_text_height(text_value, min_height=150, max_height=600),
                            help=prop_description,
                            key=f"form_{field_name}_{idx}_{prop_name}"
                        )
                    else:
                        edited_item[prop_name] = st.text_input(
                            prop_label,
                            value=str(prop_value) if prop_value else "",
                            help=prop_description,
                            key=f"form_{field_name}_{idx}_{prop_name}"
                        )

                elif prop_type == "integer":
                    edited_item[prop_name] = st.number_input(
                        prop_label,
                        value=int(prop_value) if prop_value is not None else 0,
                        step=1,
                        help=prop_description,
                        key=f"form_{field_name}_{idx}_{prop_name}"
                    )

                elif prop_type == "number":
                    edited_item[prop_name] = st.number_input(
                        prop_label,
                        value=float(prop_value) if prop_value is not None else 0.0,
                        help=prop_description,
                        key=f"form_{field_name}_{idx}_{prop_name}"
                    )

                elif prop_type == "boolean":
                    edited_item[prop_name] = st.checkbox(
                        prop_label,
                        value=bool(prop_value) if prop_value is not None else False,
                        help=prop_description,
                        key=f"form_{field_name}_{idx}_{prop_name}"
                    )

                else:
                    # その他の型はテキスト入力
                    edited_item[prop_name] = st.text_input(
                        prop_label,
                        value=str(prop_value) if prop_value else "",
                        help=prop_description,
                        key=f"form_{field_name}_{idx}_{prop_name}"
                    )

            edited_array.append(edited_item)

    # 削除と追加のコントロール
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button(f"➕ 新しい項目を追加", key=f"add_{field_name}"):
            st.info("💡 保存後、新しい項目が追加されます")

    with col2:
        if len(edited_array) > 0:
            if st.button(f"🗑️ 最後の項目を削除", key=f"remove_{field_name}"):
                edited_array = edited_array[:-1]
                st.success("最後の項目を削除しました")

    return edited_array


def _render_object_input(field_name: str, current_value: Any) -> Dict:
    """オブジェクト入力フィールド"""
    import json

    if not current_value:
        current_value = {}

    json_str = json.dumps(current_value, ensure_ascii=False, indent=2)
    edited_json = st.text_area(
        "JSON形式で編集",
        value=json_str,
        height=_calculate_text_height(json_str, min_height=150, max_height=500),
        key=f"form_obj_{field_name}"
    )

    try:
        return json.loads(edited_json)
    except json.JSONDecodeError:
        st.error("JSON形式が不正です")
        return current_value
