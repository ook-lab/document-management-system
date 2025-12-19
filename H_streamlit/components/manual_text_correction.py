"""
手動テキスト補正コンポーネント (Human-in-the-loop)

Gemini Visionが取りこぼしたテキストを人間が補完し、
Stage H（Claude 4.5 Haiku）で再構造化する機能を提供します。

使用例:
- スキャンPDFで500文字のテキストがある
- Gemini Visionが一部しか拾えなかった（200文字）
- 人間が残りの300文字を手入力
- 完全なテキスト（500文字）+ Gemini Visionのレイアウト情報でStage H再実行
- → 高品質な構造化データが生成される
"""
import streamlit as st
from typing import Dict, Any, Optional
from loguru import logger
import difflib


def _highlight_diff(original: str, corrected: str) -> str:
    """
    2つのテキストの差分をハイライト表示用のマークダウンに変換

    Args:
        original: 元のテキスト
        corrected: 補正後のテキスト

    Returns:
        差分をハイライトしたマークダウン文字列
    """
    diff = list(difflib.unified_diff(
        original.split('\n'),
        corrected.split('\n'),
        lineterm='',
        n=0  # コンテキスト行数を0に
    ))

    if not diff:
        return "（変更なし）"

    result_lines = []
    for line in diff[2:]:  # 最初の2行はヘッダーなのでスキップ
        if line.startswith('+'):
            result_lines.append(f"**+ {line[1:]}**")  # 追加行を太字
        elif line.startswith('-'):
            result_lines.append(f"~~- {line[1:]}~~")  # 削除行を取り消し線
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)


def render_manual_text_correction(
    doc_id: str,
    file_name: str,
    extracted_text: str,
    metadata: Dict[str, Any],
    doc_type: str
) -> Optional[str]:
    """
    手動テキスト補正UIをレンダリング

    このコンポーネントは以下の機能を提供します：
    1. Gemini Visionが抽出したテキストの表示
    2. 人間による手動補正・完全入力
    3. 補正前後の差分表示
    4. Stage H再実行ボタン

    Args:
        doc_id: ドキュメントID
        file_name: ファイル名
        extracted_text: Gemini Visionが抽出したテキスト
        metadata: 既存のメタデータ（Stage Aの結果を含む）
        doc_type: ドキュメントタイプ

    Returns:
        補正されたテキスト（再実行が要求された場合）、またはNone
    """
    st.markdown("---")
    st.markdown("### 🛠️ テキスト抽出の手動補正（Human-in-the-loop）")

    # 説明エリア
    with st.expander("💡 この機能について", expanded=False):
        st.markdown("""
        **Gemini Visionが取りこぼしたテキストを補完できます！**

        **使用例:**
        - スキャンされたPDFで、OCRが一部の文字を読めなかった場合
        - 手書き文字が含まれている場合
        - 複雑なレイアウトで抽出が不完全な場合

        **処理フロー:**
        1. 👇 下のエリアに正しいテキストを入力してください
        2. 🔄 「再構造化」ボタンを押すと...
        3. **完全なテキスト（人間）+ レイアウト情報（Vision）** でStage Hが再実行されます
        4. ✨ 構造化データの品質がレベルアップ！

        **ポイント:**
        - Gemini Visionのレイアウト情報（見出し、箇条書きなどの構造）は保持されます
        - Claude 4.5 Haikuが、完全なテキストとレイアウト情報を統合して構造化します
        """)

    # 現在の抽出状況
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("元の文字数", len(extracted_text))
    with col_info2:
        stagea_confidence = metadata.get('stagea_confidence', 0)
        st.metric("Stage A 信頼度", f"{stagea_confidence:.2%}")
    with col_info3:
        st.metric("ファイル名", file_name[:20] + "..." if len(file_name) > 20 else file_name)

    # Stage Aの情報を表示
    with st.expander("🔍 Gemini Visionの解析情報（保持されるレイアウト情報）"):
        st.json({
            "doc_type": doc_type,
            "summary": metadata.get('summary', '')[:200] + "...",
            "relevant_date": metadata.get('relevant_date'),
            "confidence": metadata.get('stagea_confidence', 0)
        })

    st.markdown("---")

    # タブで編集方法を選択
    tab1, tab2, tab3 = st.tabs(["📝 全文編集", "✏️ 行単位編集", "📊 差分プレビュー"])

    # セッション状態でテキストを管理
    if f'corrected_text_{doc_id}' not in st.session_state:
        st.session_state[f'corrected_text_{doc_id}'] = extracted_text

    corrected_text = None

    with tab1:
        st.markdown("#### 全文を編集")
        st.info("💡 取りこぼされた文字を追加するか、テキスト全体を書き直してください")

        user_input = st.text_area(
            "テキストの手動入力・補正",
            value=st.session_state[f'corrected_text_{doc_id}'],
            height=400,
            key=f"manual_text_full_{doc_id}",
            help="Gemini Visionが取りこぼした文字を追加してください"
        )

        # リアルタイム文字数表示
        char_diff = len(user_input) - len(extracted_text)
        if char_diff > 0:
            st.success(f"✅ {char_diff} 文字追加されました（合計: {len(user_input)} 文字）")
        elif char_diff < 0:
            st.warning(f"⚠️ {abs(char_diff)} 文字削除されました（合計: {len(user_input)} 文字）")
        else:
            st.info("変更なし")

        st.session_state[f'corrected_text_{doc_id}'] = user_input

    with tab2:
        st.markdown("#### 行単位で編集")
        st.info("💡 各行を個別に編集できます。間違っている行だけを修正してください")

        lines = extracted_text.split('\n')
        edited_lines = []

        for i, line in enumerate(lines):
            col1, col2 = st.columns([1, 20])
            with col1:
                st.markdown(f"`{i+1:02d}`")
            with col2:
                edited_line = st.text_input(
                    f"行 {i+1}",
                    value=line,
                    key=f"line_{doc_id}_{i}",
                    label_visibility="collapsed"
                )
                edited_lines.append(edited_line)

        # 行編集の結果を反映
        line_edited_text = "\n".join(edited_lines)
        st.session_state[f'corrected_text_{doc_id}'] = line_edited_text

        # 変更行数をカウント
        changed_lines = sum(1 for orig, edit in zip(lines, edited_lines) if orig != edit)
        if changed_lines > 0:
            st.success(f"✅ {changed_lines} 行が変更されました")

    with tab3:
        st.markdown("#### 変更内容のプレビュー")
        st.info("💡 元のテキストと補正後のテキストの差分を確認できます")

        current_text = st.session_state[f'corrected_text_{doc_id}']

        if current_text != extracted_text:
            st.markdown("**差分:**")
            diff_markdown = _highlight_diff(extracted_text, current_text)
            st.markdown(diff_markdown)

            # 統計情報
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                st.metric("元の文字数", len(extracted_text))
            with col_stat2:
                st.metric("補正後の文字数", len(current_text))
        else:
            st.info("変更がありません")

    st.markdown("---")

    # 再実行ボタン
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 6])

    with col_btn1:
        if st.button(
            "🔄 Stage H 再実行",
            type="primary",
            use_container_width=True,
            key=f"reprocess_{doc_id}",
            help="補正されたテキストでClaude 4.5 Haikuによる構造化を再実行します"
        ):
            current_text = st.session_state[f'corrected_text_{doc_id}']
            if current_text != extracted_text:
                corrected_text = current_text
                logger.info(f"[手動補正] テキスト補正完了: {len(extracted_text)} → {len(corrected_text)} 文字")
            else:
                st.warning("⚠️ テキストが変更されていません")

    with col_btn2:
        if st.button(
            "↩️ リセット",
            use_container_width=True,
            key=f"reset_{doc_id}",
            help="元のテキストに戻します"
        ):
            st.session_state[f'corrected_text_{doc_id}'] = extracted_text
            st.rerun()

    return corrected_text


def execute_stageh_reprocessing(
    corrected_text: str,
    file_name: str,
    metadata: Dict[str, Any],
    workspace: str
) -> Dict[str, Any]:
    """
    補正されたテキストでStage Hを再実行

    このラッパー関数は後方互換性のために残されています。
    新しいコードでは ui.utils.stageh_reprocessor を使用してください。

    Args:
        corrected_text: 人間が補正したテキスト
        file_name: ファイル名
        metadata: Stage Aの結果を含むメタデータ
        workspace: ワークスペース

    Returns:
        新しい構造化データ
    """
    logger.warning("[Deprecated] execute_stageh_reprocessing() は非推奨です。H_streamlit.utils.stageC_reprocessor.reprocess_with_stageC() を使用してください。")

    # この関数は後方互換性のために残されていますが、実装は削除されました
    # 新しいコードでは H_streamlit.utils.stageC_reprocessor.reprocess_with_stageC() を直接使用してください
    raise NotImplementedError(
        "execute_stageh_reprocessing() は非推奨です。"
        "H_streamlit.utils.stageC_reprocessor.reprocess_with_stageC() を使用してください。"
    )
