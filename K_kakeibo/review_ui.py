"""
家計簿レビューUI (Streamlit)

レシート単位でのレビュー：
- レシート画像プレビュー
- 商品一覧（表形式）
- 合計金額
- レシート単位での承認・編集
"""

import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image
import io

# 設定
from config import SUPABASE_URL, SUPABASE_KEY, GOOGLE_DRIVE_CREDENTIALS

# Supabase接続
db = create_client(SUPABASE_URL, SUPABASE_KEY)

# Google Drive接続
@st.cache_resource
def get_drive_service():
    """Google Drive APIサービスを取得"""
    import json
    from pathlib import Path

    # Streamlit Cloudの場合はSecretsから、ローカルの場合はファイルから
    if "gcp_service_account" in st.secrets:
        # Streamlit CloudのSecrets
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
    else:
        # ローカル環境
        cred_path = Path(GOOGLE_DRIVE_CREDENTIALS)
        if not cred_path.exists():
            st.error(f"サービスアカウントファイルが見つかりません: {GOOGLE_DRIVE_CREDENTIALS}")
            st.stop()
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_DRIVE_CREDENTIALS,
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
    return build("drive", "v3", credentials=credentials)


def get_receipt_image(drive_file_id: str):
    """Google Driveからレシート画像を取得"""
    try:
        service = get_drive_service()
        request = service.files().get_media(
            fileId=drive_file_id,
            supportsAllDrives=True
        )

        file_bytes = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(file_bytes, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        file_bytes.seek(0)
        return Image.open(file_bytes)
    except Exception as e:
        st.error(f"画像取得エラー: {e}")
        return None


def main():
    st.set_page_config(page_title="家計簿レビュー", layout="wide")
    st.title("📊 家計簿レビューシステム")

    # サイドバー：レシート一覧
    st.sidebar.header("レシート一覧")

    # 処理ログ取得（レシート単位）
    logs = db.table("99_lg_image_proc_log") \
        .select("*") \
        .order("processed_at", desc=True) \
        .limit(100) \
        .execute()

    if not logs.data:
        st.info("処理済みレシートがありません")
        return

    # フィルター
    status_filter = st.sidebar.selectbox(
        "ステータス",
        ["すべて", "未確認", "確認済み", "エラー"]
    )

    # レシート選択
    receipt_options = []
    for log in logs.data:
        status_icon = {
            "success": "✅",
            "failed": "❌"
        }.get(log["status"], "⚠️")

        label = f"{status_icon} {log['file_name']} ({log['processed_at'][:10]})"
        receipt_options.append((label, log))

    if not receipt_options:
        st.info("表示するレシートがありません")
        return

    selected_label = st.sidebar.radio(
        "レシートを選択",
        [opt[0] for opt in receipt_options],
        key="receipt_selector"
    )

    # 選択されたレシートを取得
    selected_log = next(opt[1] for opt in receipt_options if opt[0] == selected_label)

    # メイン画面：レシート詳細
    show_receipt_detail(selected_log)


def show_receipt_detail(log: dict):
    """レシート詳細表示"""

    st.header(f"📄 {log['file_name']}")

    # 2カラムレイアウト
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("レシート画像")

        if log.get("drive_file_id"):
            with st.spinner("画像を読み込み中..."):
                image = get_receipt_image(log["drive_file_id"])
                if image:
                    st.image(image, use_column_width=True)
                else:
                    st.warning("画像を取得できませんでした")
        else:
            st.info("画像IDがありません")

        # レシート情報
        st.subheader("処理情報")
        info_data = {
            "ファイル名": log["file_name"],
            "処理日時": log["processed_at"],
            "ステータス": log["status"],
            "OCRモデル": log.get("ocr_model", "不明"),
            "エラー": log.get("error_message", "なし")
        }

        for key, value in info_data.items():
            st.text(f"{key}: {value}")

    with col_right:
        st.subheader("取引明細")

        if log["status"] == "success" and log.get("receipt_id"):
            # レシート情報を取得
            receipt_result = db.table("60_rd_receipts") \
                .select("*") \
                .eq("id", log["receipt_id"]) \
                .execute()

            if not receipt_result.data:
                st.warning("レシート情報が見つかりません")
                return

            receipt = receipt_result.data[0]

            # トランザクション（3テーブルJOIN）を取得
            transactions = db.table("60_rd_transactions") \
                .select("""
                    *,
                    60_rd_standardized_items(
                        id,
                        std_amount,
                        tax_rate,
                        tax_amount,
                        official_name,
                        category_id,
                        situation_id,
                        major_category,
                        minor_category,
                        person,
                        purpose,
                        needs_review
                    )
                """) \
                .eq("receipt_id", log["receipt_id"]) \
                .order("line_number") \
                .execute()

            if transactions.data:
                # DataFrameに変換
                df_data = []
                for t in transactions.data:
                    std = t.get("60_rd_standardized_items", [{}])[0] if isinstance(t.get("60_rd_standardized_items"), list) else t.get("60_rd_standardized_items", {})
                    df_data.append({
                        "商品名": t["product_name"],
                        "数量": t["quantity"],
                        "単価": t['unit_price'],
                        "金額": std.get('std_amount', 0),
                        "税率": f"{std.get('tax_rate', 10)}%",
                        "内税額": std.get('tax_amount', 0),
                        "正式名": std.get("official_name") or "",
                        "物品名": t.get("item_name") or "",
                        "大分類": std.get("major_category") or "",
                        "小分類": std.get("minor_category") or "",
                        "人物": std.get("person") or "",
                        "名目": std.get("purpose") or "",
                        "要確認": "⚠️" if std.get("needs_review") else ""
                    })

                df = pd.DataFrame(df_data)

                # 金額関連のカラムをフォーマット
                df["単価"] = df["単価"].apply(lambda x: f"¥{x:,}")
                df["金額"] = df["金額"].apply(lambda x: f"¥{x:,}")
                df["内税額"] = df["内税額"].apply(lambda x: f"¥{x:,}")

                # データフレームを表示（横スクロール有効、高さ指定）
                st.dataframe(
                    df,
                    hide_index=True,
                    height=400  # 高さを指定して見やすく
                )

                # 合計金額・税額サマリー
                total = sum(
                    (t.get("60_rd_standardized_items", [{}])[0] if isinstance(t.get("60_rd_standardized_items"), list) else t.get("60_rd_standardized_items", {})).get("std_amount", 0)
                    for t in transactions.data
                )
                total_tax_8 = sum(
                    (t.get("60_rd_standardized_items", [{}])[0] if isinstance(t.get("60_rd_standardized_items"), list) else t.get("60_rd_standardized_items", {})).get("tax_amount", 0)
                    for t in transactions.data
                    if (t.get("60_rd_standardized_items", [{}])[0] if isinstance(t.get("60_rd_standardized_items"), list) else t.get("60_rd_standardized_items", {})).get("tax_rate") == 8
                )
                total_tax_10 = sum(
                    (t.get("60_rd_standardized_items", [{}])[0] if isinstance(t.get("60_rd_standardized_items"), list) else t.get("60_rd_standardized_items", {})).get("tax_amount", 0)
                    for t in transactions.data
                    if (t.get("60_rd_standardized_items", [{}])[0] if isinstance(t.get("60_rd_standardized_items"), list) else t.get("60_rd_standardized_items", {})).get("tax_rate") == 10
                )

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"### 合計: ¥{total:,}")
                with col2:
                    st.markdown(f"**8%税額: ¥{total_tax_8:,}**")
                with col3:
                    st.markdown(f"**10%税額: ¥{total_tax_10:,}**")

                # 税額サマリー取得（レシート記載値との比較）
                try:
                    tax_summary = db.table("money_receipt_tax_summary") \
                        .select("*") \
                        .eq("processing_log_id", log["id"]) \
                        .execute()
                except Exception as e:
                    # テーブルが存在しない場合はスキップ
                    tax_summary = None

                if tax_summary and tax_summary.data:
                    summary = tax_summary.data[0]
                    st.subheader("税額整合性チェック")

                    match_icon = "✅" if summary["calculated_matches_actual"] else "⚠️"
                    st.markdown(f"### {match_icon} 整合性: {'一致' if summary['calculated_matches_actual'] else '不一致'}")

                    comparison_data = {
                        "税率": ["8%", "10%"],
                        "レシート記載": [
                            f"¥{summary['tax_8_amount']:,}",
                            f"¥{summary['tax_10_amount']:,}"
                        ],
                        "計算値": [
                            f"¥{summary['calculated_tax_8_amount']:,}",
                            f"¥{summary['calculated_tax_10_amount']:,}"
                        ],
                        "差分": [
                            f"{summary['tax_8_diff']:+d}円",
                            f"{summary['tax_10_diff']:+d}円"
                        ]
                    }

                    st.table(pd.DataFrame(comparison_data))

                # 店名・日付（レシートから取得）
                st.text(f"店名: {receipt['shop_name']}")
                st.text(f"取引日: {receipt['transaction_date']}")
                st.text(f"レシート合計: ¥{receipt.get('total_amount_check', 0):,}")

                # 確認状態（レシート単位）
                if receipt["is_verified"]:
                    st.success("✅ このレシートは確認済みです")
                else:
                    st.warning(f"⏸️ このレシートは未確認です")

                # アクションボタン
                st.divider()

                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("✅ 全て承認", key="approve_all"):
                        # レシート単位で承認
                        db.table("60_rd_receipts") \
                            .update({"is_verified": True}) \
                            .eq("id", log["receipt_id"]) \
                            .execute()
                        st.success("承認しました")
                        st.rerun()

                with col2:
                    if st.button("📝 個別編集", key="edit_mode"):
                        st.session_state.edit_mode = True
                        st.rerun()

                with col3:
                    if st.button("🗑️ 全て削除", key="delete_all"):
                        # レシートを削除（CASCADE で子・孫も削除される）
                        db.table("60_rd_receipts") \
                            .delete() \
                            .eq("id", log["receipt_id"]) \
                            .execute()
                        st.warning("削除しました")
                        st.rerun()

                # 個別編集モード
                if st.session_state.get("edit_mode"):
                    st.divider()
                    st.subheader("個別編集")

                    for idx, t in enumerate(transactions.data):
                        with st.expander(f"{t['product_name']} (¥{t['total_amount']:,})"):
                            col_a, col_b, col_c = st.columns(3)

                            with col_a:
                                new_product = st.text_input(
                                    "商品名",
                                    value=t["product_name"],
                                    key=f"prod_{idx}"
                                )

                                new_amount = st.number_input(
                                    "金額",
                                    value=t["total_amount"],
                                    key=f"amt_{idx}"
                                )

                                new_tax_included = st.number_input(
                                    "内税額",
                                    value=t.get("tax_included_amount") or t["total_amount"],
                                    key=f"tax_{idx}"
                                )

                                new_official_name = st.text_input(
                                    "正式名",
                                    value=t.get("official_name") or "",
                                    key=f"official_{idx}"
                                )

                                new_item_name = st.text_input(
                                    "物品名",
                                    value=t.get("item_name") or "",
                                    key=f"item_{idx}"
                                )

                            with col_b:
                                new_major_category = st.text_input(
                                    "大分類",
                                    value=t.get("major_category") or "",
                                    key=f"major_{idx}"
                                )

                                new_minor_category = st.text_input(
                                    "小分類",
                                    value=t.get("minor_category") or "",
                                    key=f"minor_{idx}"
                                )

                            with col_c:
                                new_person = st.text_input(
                                    "人物",
                                    value=t.get("person") or "",
                                    key=f"person_{idx}"
                                )

                                new_purpose = st.text_input(
                                    "名目",
                                    value=t.get("purpose") or "",
                                    key=f"purpose_{idx}"
                                )

                            if st.button("💾 更新", key=f"update_{idx}"):
                                # 子テーブル（テキスト）の更新
                                db.table("60_rd_transactions").update({
                                    "product_name": new_product,
                                    "item_name": new_item_name
                                }).eq("id", t["id"]).execute()

                                # 孫テーブル（分類・金額）の更新
                                std = t.get("60_rd_standardized_items", [{}])[0] if isinstance(t.get("60_rd_standardized_items"), list) else t.get("60_rd_standardized_items", {})
                                if std and "id" in std:
                                    db.table("60_rd_standardized_items").update({
                                        "std_amount": new_amount,
                                        "tax_amount": new_tax_included,
                                        "official_name": new_official_name,
                                        "major_category": new_major_category,
                                        "minor_category": new_minor_category,
                                        "person": new_person,
                                        "purpose": new_purpose
                                    }).eq("id", std["id"]).execute()

                                # レシート全体を確認済みにマーク
                                db.table("60_rd_receipts").update({
                                    "is_verified": True
                                }).eq("id", log["receipt_id"]).execute()

                                st.success("更新しました")
                                st.rerun()

                    if st.button("編集モード終了", key="exit_edit"):
                        st.session_state.edit_mode = False
                        st.rerun()

            else:
                st.warning("トランザクションデータが見つかりません")

        elif log["status"] == "failed":
            st.error(f"❌ 処理エラー: {log.get('error_message', '不明')}")
            st.info("errorsフォルダを確認してください")

        else:
            st.info("トランザクションデータがありません")


if __name__ == "__main__":
    main()
