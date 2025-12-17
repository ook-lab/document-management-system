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
from K_kakeibo.config import SUPABASE_URL, SUPABASE_KEY, GOOGLE_DRIVE_CREDENTIALS

# Supabase接続
db = create_client(SUPABASE_URL, SUPABASE_KEY)

# Google Drive接続
@st.cache_resource
def get_drive_service():
    """Google Drive APIサービスを取得"""
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
    logs = db.table("money_image_processing_log") \
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
                    st.image(image, use_container_width=True)
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

        if log["status"] == "success" and log.get("transaction_ids"):
            # トランザクションを取得
            transactions = db.table("money_transactions") \
                .select("*, money_categories(name), money_situations(name)") \
                .in_("id", log["transaction_ids"]) \
                .execute()

            if transactions.data:
                # DataFrameに変換
                df_data = []
                for t in transactions.data:
                    df_data.append({
                        "商品名": t["product_name"],
                        "数量": t["quantity"],
                        "単価": t['unit_price'],
                        "金額": t['total_amount'],
                        "内税額": t.get('tax_included_amount') or t['total_amount'],
                        "正式名": t.get("official_name") or "",
                        "物品名": t.get("item_name") or "",
                        "大分類": t.get("major_category") or "",
                        "小分類": t.get("minor_category") or "",
                        "人物": t.get("person") or "",
                        "名目": t.get("purpose") or "",
                        "確認": "✅" if t["is_verified"] else "⏸️"
                    })

                df = pd.DataFrame(df_data)

                # 金額関連のカラムをフォーマット
                df["単価"] = df["単価"].apply(lambda x: f"¥{x:,}")
                df["金額"] = df["金額"].apply(lambda x: f"¥{x:,}")
                df["内税額"] = df["内税額"].apply(lambda x: f"¥{x:,}")

                # データフレームを表示（横スクロール有効、高さ指定）
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    height=400  # 高さを指定して見やすく
                )

                # 合計金額
                total = sum(t["total_amount"] for t in transactions.data)
                st.markdown(f"### 合計: ¥{total:,}")

                # 店名・日付
                if transactions.data:
                    first = transactions.data[0]
                    st.text(f"店名: {first['shop_name']}")
                    st.text(f"取引日: {first['transaction_date']}")

                # 確認状態
                all_verified = all(t["is_verified"] for t in transactions.data)

                if all_verified:
                    st.success("✅ このレシートは確認済みです")
                else:
                    st.warning(f"⏸️ 未確認の商品があります")

                # アクションボタン
                st.divider()

                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("✅ 全て承認", key="approve_all", use_container_width=True):
                        for t in transactions.data:
                            db.table("money_transactions") \
                                .update({"is_verified": True}) \
                                .eq("id", t["id"]) \
                                .execute()
                        st.success("承認しました")
                        st.rerun()

                with col2:
                    if st.button("📝 個別編集", key="edit_mode", use_container_width=True):
                        st.session_state.edit_mode = True
                        st.rerun()

                with col3:
                    if st.button("🗑️ 全て削除", key="delete_all", use_container_width=True):
                        for t in transactions.data:
                            db.table("money_transactions") \
                                .delete() \
                                .eq("id", t["id"]) \
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
                                db.table("money_transactions").update({
                                    "product_name": new_product,
                                    "total_amount": new_amount,
                                    "tax_included_amount": new_tax_included,
                                    "official_name": new_official_name,
                                    "item_name": new_item_name,
                                    "major_category": new_major_category,
                                    "minor_category": new_minor_category,
                                    "person": new_person,
                                    "purpose": new_purpose,
                                    "is_verified": True
                                }).eq("id", t["id"]).execute()

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
