import io
import unicodedata

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import streamlit as st

from supabase_client import get_supabase
from utils.settings import get_registration_open, set_registration_open

EVENT_FEES: dict[str, int] = {
    "ビギナー": 2000,
    "JP1.5": 3000,
    "JP2.5": 3000,
    "AG1": 3000,
    "AG2": 3000,
    "AG3": 3000,
}


def calc_fee(events: list[str]) -> int:
    """参加種目リストから参加料金の合計を計算する。"""
    return sum(EVENT_FEES.get(e, 0) for e in events)


def check_admin_password() -> bool:
    """管理者パスワードを確認する。

    認証済みの場合はTrueを返す。未認証の場合はログインフォームを表示してFalseを返す。
    """
    if st.session_state.get("admin_authenticated"):
        return True

    st.subheader("管理者ログイン")
    password = st.text_input("パスワード", type="password", key="admin_password_input")

    if st.button("ログイン", type="primary", use_container_width=True):
        if password == st.secrets["admin"]["password"]:
            st.session_state["admin_authenticated"] = True
            st.rerun()
        else:
            st.error("パスワードが間違っています。")

    return False


def fetch_participants() -> list[dict] | None:
    """参加者と犬情報の一覧をSupabaseから取得する。"""
    try:
        response = get_supabase().rpc("get_participants_with_dogs").execute()
        return response.data
    except Exception as e:
        st.error(f"データの取得に失敗しました: {e}")
        return None


def _str_width(s: str) -> int:
    """文字列の表示幅を返す（全角=2、半角=1）。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def generate_excel(data: list[dict]) -> bytes:
    """参加者一覧をExcel(.xlsx)形式で生成してバイト列で返す。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "参加者一覧"

    headers = list(data[0].keys())
    header_fill = PatternFill(fill_type="solid", fgColor="D9E1F2")
    total_fill = PatternFill(fill_type="solid", fgColor="F2F2F2")

    # ヘッダー行
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    fee_col = headers.index("参加料金") + 1

    # データ行
    for row_idx, row in enumerate(data, start=2):
        is_total = row.get("参加者名") == "合計"
        for col_idx, key in enumerate(headers, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=row[key])
            if col_idx == fee_col:
                cell.alignment = Alignment(horizontal="right")
            if is_total:
                cell.font = Font(bold=True)
                cell.fill = total_fill

    # 列幅を最大文字列幅に合わせる
    for col_idx, key in enumerate(headers, start=1):
        max_width = _str_width(key)
        for row in data:
            max_width = max(max_width, _str_width(row[key]))
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = max_width + 2

    # A4縦・1ページ幅に収める印刷設定
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def show_participants_table(rows: list[dict]) -> None:
    """参加者・犬情報の一覧表を表示する。"""
    st.markdown("#### 参加者・犬情報一覧")

    if not rows:
        st.info("登録データがありません。")
        return

    data = []
    for i, row in enumerate(rows, start=1):
        events = row.get("events") or []
        data.append({
            "No.": i,
            "参加者名": row["user_name"],
            "犬名": row["dog_name"],
            "犬種": row["breed"],
            "クラス": row["dog_class"],
            "参加種目": "、".join(events),
            "参加料金": f"{calc_fee(events):,}円",
        })

    total_fee = sum(EVENT_FEES.get(e, 0) for row in rows for e in (row.get("events") or []))
    data.append({
        "No.": "",
        "参加者名": "合計",
        "犬名": "",
        "犬種": "",
        "クラス": "",
        "参加種目": "",
        "参加料金": f"{total_fee:,}円",
    })

    st.dataframe(
        data,
        hide_index=True,
        use_container_width=True,
        column_config={"参加料金": st.column_config.TextColumn(width="small")},
    )

    st.download_button(
        label="Excelダウンロード",
        data=generate_excel(data),
        file_name="参加者一覧.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def show_admin_home() -> None:
    """管理者ホーム画面を表示する。"""
    st.subheader("管理者メニュー")

    st.markdown("#### 新規登録受付設定")
    registration_open = get_registration_open()
    new_value = st.toggle("新規登録を受け付ける", value=registration_open)

    if new_value != registration_open:
        set_registration_open(new_value)
        status = "受付中" if new_value else "締め切り"
        st.success(f"新規登録を「{status}」に変更しました。")
        st.rerun()

    st.divider()

    with st.spinner("読み込み中..."):
        participants = fetch_participants()

    if participants is not None:
        show_participants_table(participants)

    st.divider()
    if st.button("ログアウト", use_container_width=True):
        del st.session_state["admin_authenticated"]
        st.rerun()


def main() -> None:
    """管理者アプリのメインエントリーポイント。"""
    st.set_page_config(
        page_title="管理者 | アジリティー練習会",
        layout="wide",
    )

    if not check_admin_password():
        return

    show_admin_home()


if __name__ == "__main__":
    main()
