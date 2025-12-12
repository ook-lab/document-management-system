"""
統合Stage C再実行ユーティリティ

全ての編集箇所（全文編集、行単位編集、フォーム編集、表形式編集）から
Stage C（構造化）を再実行できる共通機能を提供します。
旧名: Stage 2 Reprocessor
"""
import streamlit as st
from typing import Dict, Any, Optional
from loguru import logger


def reprocess_with_stageC(
    doc_id: str,
    full_text: str,
    file_name: str,
    metadata: Dict[str, Any],
    workspace: str,
    db_client,
    trigger_source: str = "manual_edit"
) -> bool:
    """
    Stage C（構造化）を再実行し、データベースに保存

    Args:
        doc_id: ドキュメントID
        full_text: 補正後の全文テキスト
        file_name: ファイル名
        metadata: 既存のメタデータ
        workspace: ワークスペース
        db_client: データベースクライアント
        trigger_source: 再実行のトリガー元（ログ用）

    Returns:
        成功した場合True、失敗した場合False
    """
    from core.ai.stageC_extractor import StageCExtractor
    from core.ai.llm_client import LLMClient

    logger.info(f"[Stage C 再実行] 開始 - トリガー: {trigger_source}")
    logger.info(f"  ドキュメントID: {doc_id}")
    logger.info(f"  テキスト長: {len(full_text)} 文字")
    logger.info(f"  Workspace: {workspace}")

    try:
        # Stage 1の結果を復元
        stage1_result = {
            "doc_type": metadata.get('doc_type', 'other'),
            "summary": metadata.get('summary', ''),
            "relevant_date": metadata.get('relevant_date'),
            "confidence": metadata.get('stage1_confidence', 0.0)
        }

        # Stage 2 Extractorを初期化
        llm_client = LLMClient()
        extractor = StageCExtractor(llm_client=llm_client)

        # Stage 2再実行
        with st.spinner(f"🔄 Stage 2（構造化）を再実行中... ({trigger_source})"):
            stage2_result = extractor.extract_metadata(
                full_text=full_text,
                file_name=file_name,
                stage1_result=stage1_result,
                workspace=workspace
            )

        logger.info(f"[Stage 2 再実行] 完了: 信頼度={stage2_result.get('extraction_confidence', 0):.2f}")

        # メタデータを更新
        new_metadata = {
            **metadata,
            **stage2_result.get('metadata', {}),
            'manually_corrected': True,
            'correction_trigger': trigger_source,
            'correction_timestamp': __import__('datetime').datetime.now().isoformat(),
            'corrected_text_length': len(full_text)
        }

        # データベースに保存
        success = db_client.record_correction(
            doc_id=doc_id,
            new_metadata=new_metadata,
            new_doc_type=stage2_result.get('doc_type', metadata.get('doc_type')),
            corrector_email=None,
            notes=f"{trigger_source}からのStage 2再実行"
        )

        if success:
            st.success(f"✅ Stage 2再実行が完了しました！（トリガー: {trigger_source}）")
            logger.info(f"[Stage 2 再実行] データベース保存成功")

            # 補正前後の比較を表示
            with st.expander("📊 再実行結果の比較", expanded=True):
                col_before, col_after = st.columns(2)

                with col_before:
                    st.markdown("**補正前**")
                    st.metric("信頼度", f"{metadata.get('extraction_confidence', 0):.2%}")
                    st.metric("メタデータフィールド数", len(metadata.get('metadata', {})))

                with col_after:
                    st.markdown("**補正後**")
                    st.metric("信頼度", f"{stage2_result.get('extraction_confidence', 0):.2%}")
                    st.metric("メタデータフィールド数", len(new_metadata.get('metadata', {})))

            return True
        else:
            st.error("❌ データベースへの保存に失敗しました")
            logger.error(f"[Stage 2 再実行] データベース保存失敗")
            return False

    except Exception as e:
        logger.error(f"[Stage 2 再実行] エラー: {e}", exc_info=True)
        st.error(f"❌ Stage 2再実行エラー: {e}")
        return False


def show_reprocess_button(
    doc_id: str,
    full_text: str,
    original_text: str,
    file_name: str,
    metadata: Dict[str, Any],
    workspace: str,
    db_client,
    trigger_source: str = "manual_edit",
    button_label: str = "🔄 変更を反映してStage 2再実行"
) -> bool:
    """
    Stage 2再実行ボタンを表示

    Args:
        doc_id: ドキュメントID
        full_text: 補正後の全文テキスト
        original_text: 元のテキスト
        file_name: ファイル名
        metadata: 既存のメタデータ
        workspace: ワークスペース
        db_client: データベースクライアント
        trigger_source: 再実行のトリガー元（ログ用）
        button_label: ボタンのラベル

    Returns:
        再実行が成功した場合True
    """
    # 変更検知
    text_changed = full_text != original_text

    if not text_changed:
        st.info("💡 変更がありません。編集後に再実行ボタンが表示されます。")
        return False

    # 変更があることを表示
    char_diff = len(full_text) - len(original_text)
    if char_diff > 0:
        st.success(f"✅ {char_diff} 文字追加されました（合計: {len(full_text)} 文字）")
    elif char_diff < 0:
        st.warning(f"⚠️ {abs(char_diff)} 文字削除されました（合計: {len(full_text)} 文字）")

    # 再実行ボタン
    col_btn1, col_btn2 = st.columns([3, 1])

    with col_btn1:
        if st.button(
            button_label,
            type="primary",
            use_container_width=True,
            key=f"reprocess_{trigger_source}_{doc_id}"
        ):
            success = reprocess_with_stageC(
                doc_id=doc_id,
                full_text=full_text,
                file_name=file_name,
                metadata=metadata,
                workspace=workspace,
                db_client=db_client,
                trigger_source=trigger_source
            )

            if success:
                st.balloons()
                import time
                time.sleep(2)
                st.rerun()

            return success

    with col_btn2:
        if st.button(
            "↩️ リセット",
            use_container_width=True,
            key=f"reset_{trigger_source}_{doc_id}"
        ):
            st.rerun()

    return False
