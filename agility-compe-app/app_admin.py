import io
import unicodedata
import zipfile

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

CLASS_ORDER: list[str] = ["S", "M", "IM", "L"]

# 成績表の行・列定数
_ROW_COURSE_LEN = 3
_ROW_STD_TIME = 4
_ROW_LIMIT_TIME = 5
_ROW_TURNING_SPEED = 6
_ROW_HEADER = 8
_ROW_DATA_START = 9
_RESULT_COLS = ["順位", "氏名", "犬名", "犬種", "クラス", "タイム", "失敗", "拒絶", "減点", "スピード", "合計タイム"]


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


def generate_race_excel(participants: list[dict]) -> bytes | None:
    """種目・クラス別出走表をExcel形式で生成してバイト列で返す。シートが1枚も作成できない場合はNoneを返す。"""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # デフォルトシートを削除

    header_fill = PatternFill(fill_type="solid", fgColor="D9E1F2")
    col_names = ["No.", "氏名", "犬名", "犬種", "クラス"]

    for event in EVENT_FEES:
        for cls in CLASS_ORDER:
            rows = [
                p for p in participants
                if event in (p.get("events") or []) and p.get("dog_class") == cls
            ]
            if not rows:
                continue

            sheet_name = f"{event}-{cls}"
            ws = wb.create_sheet(title=sheet_name)

            # 1行目: シート名をタイトルとして表示
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(col_names))
            title_cell = ws.cell(row=1, column=1, value=sheet_name)
            title_cell.font = Font(bold=True, size=14)
            title_cell.alignment = Alignment(horizontal="center")

            # 2行目: カラムヘッダー
            for col_idx, col_name in enumerate(col_names, start=1):
                cell = ws.cell(row=2, column=col_idx, value=col_name)
                cell.font = Font(bold=True)
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")

            # 3行目以降: データ（下線付き）
            underline_side = openpyxl.styles.Side(style="thin")
            bottom_border = openpyxl.styles.Border(bottom=underline_side)
            for i, p in enumerate(rows, start=1):
                values = [i, p["user_name"], p["dog_name"], p["breed"], p["dog_class"]]
                for col_idx, val in enumerate(values, start=1):
                    cell = ws.cell(row=i + 2, column=col_idx, value=val)
                    cell.border = bottom_border

            # 列幅を最大文字列幅に合わせる
            col_values: list[list[str]] = [
                [str(i) for i in range(1, len(rows) + 1)],
                [p["user_name"] for p in rows],
                [p["dog_name"] for p in rows],
                [p["breed"] for p in rows],
                [p["dog_class"] for p in rows],
            ]
            for col_idx, (col_name, values) in enumerate(zip(col_names, col_values), start=1):
                max_width = _str_width(col_name)
                for v in values:
                    max_width = max(max_width, _str_width(v))
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = max_width + 2

            # 印刷設定
            ws.page_setup.paperSize = ws.PAPERSIZE_A4
            ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
            ws.page_setup.fitToPage = True
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0

    if not wb.sheetnames:
        return None

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_results_workbook(
    title: str,
    course_len,
    std_time,
    limit_time,
    turning_speed,
    data: list[dict],
) -> openpyxl.Workbook:
    """成績表Workbookを生成して返す。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title[:31]

    header_fill = PatternFill(fill_type="solid", fgColor="D9E1F2")
    underline_side = openpyxl.styles.Side(style="thin")
    bottom_border = openpyxl.styles.Border(bottom=underline_side)
    num_cols = len(_RESULT_COLS)

    # タイトル行
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols)
    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.font = Font(bold=True, size=14)
    title_cell.alignment = Alignment(horizontal="center")

    # 初期入力値セクション
    for row_num, label, value, unit in [
        (_ROW_COURSE_LEN, "コース全長", course_len, "m"),
        (_ROW_STD_TIME, "標準タイム", std_time, "sec"),
        (_ROW_LIMIT_TIME, "リミットタイム", limit_time, "sec"),
        (_ROW_TURNING_SPEED, "旋回スピード", turning_speed, "m/sec"),
    ]:
        ws.cell(row=row_num, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row_num, column=3, value=value)
        ws.cell(row=row_num, column=4, value=unit)

    # カラムヘッダー行
    for col_idx, col_name in enumerate(_RESULT_COLS, start=1):
        cell = ws.cell(row=_ROW_HEADER, column=col_idx, value=col_name)
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # データ行（下線付き）
    _TIME_COLS = {6, 10, 11}  # タイム列・スピード列・合計タイム列（1-indexed）
    for i, p in enumerate(data):
        row_num = _ROW_DATA_START + i
        row_vals = [
            p["rank"], p["user_name"], p["dog_name"], p["breed"], p["dog_class"],
            p["time"], p["fail"], p["refuse"], p["deduct"], p["speed"], p["total_time"],
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=row_num, column=col_idx, value=val)
            cell.border = bottom_border
            if col_idx in _TIME_COLS:
                cell.number_format = "0.00"

    # 列幅調整
    col_values_list = [
        [str(p["rank"]) for p in data],
        [p["user_name"] for p in data],
        [p["dog_name"] for p in data],
        [p["breed"] for p in data],
        [p["dog_class"] for p in data],
        [str(p["time"]) for p in data],
        [str(p["fail"]) for p in data],
        [str(p["refuse"]) for p in data],
        [str(p["deduct"]) for p in data],
        [str(p["speed"]) for p in data],
        [str(p["total_time"]) for p in data],
    ]
    for col_idx, (col_name, values) in enumerate(zip(_RESULT_COLS, col_values_list), start=1):
        max_width = _str_width(col_name)
        for v in values:
            max_width = max(max_width, _str_width(str(v)))
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = max_width + 2

    # 印刷設定
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    return wb


def generate_results_skeleton_zip(participants: list[dict]) -> bytes | None:
    """種目・クラス別成績表骨格をZIP形式で生成してバイト列で返す。対象データなしの場合はNoneを返す。"""
    zip_buf = io.BytesIO()
    created = 0

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for event in EVENT_FEES:
            for cls in CLASS_ORDER:
                rows = [
                    p for p in participants
                    if event in (p.get("events") or []) and p.get("dog_class") == cls
                ]
                if not rows:
                    continue

                sheet_name = f"{event}-{cls}"
                pdata = [
                    {
                        "rank": "", "user_name": p["user_name"], "dog_name": p["dog_name"],
                        "breed": p["breed"], "dog_class": p["dog_class"],
                        "time": 0, "fail": 0, "refuse": 0, "deduct": 0, "speed": 0.00, "total_time": 0,
                    }
                    for p in rows
                ]
                wb = _build_results_workbook(sheet_name, None, None, None, None, pdata)
                excel_buf = io.BytesIO()
                wb.save(excel_buf)
                zf.writestr(f"成績表_{sheet_name}.xlsx", excel_buf.getvalue())
                created += 1

    if created == 0:
        return None

    return zip_buf.getvalue()


def process_results_excel(file_bytes: bytes) -> bytes:
    """成績入力済みExcelを読み込み、順位計算を行った完成版Excelのバイト列を返す。"""
    ws = openpyxl.load_workbook(io.BytesIO(file_bytes)).active

    title = str(ws.cell(row=1, column=1).value or "")
    course_len = ws.cell(row=_ROW_COURSE_LEN, column=3).value or 0
    std_time = ws.cell(row=_ROW_STD_TIME, column=3).value or 0
    limit_time = ws.cell(row=_ROW_LIMIT_TIME, column=3).value or 0
    turning_speed = round(course_len / std_time, 2) if std_time else 0

    # データ読み込み
    raw: list[dict] = []
    row_num = _ROW_DATA_START
    while True:
        user_name = ws.cell(row=row_num, column=2).value
        if user_name is None:
            break
        time_val = float(ws.cell(row=row_num, column=6).value or 0)
        fail_val = int(ws.cell(row=row_num, column=7).value or 0)
        refuse_val = int(ws.cell(row=row_num, column=8).value or 0)
        deduct = (fail_val + refuse_val) * 5 + max(0, int(time_val - std_time))
        speed = round(course_len / time_val, 2) if time_val > 0 else 0.00
        total_time = round(time_val + deduct, 2)
        raw.append({
            "rank": "",
            "user_name": str(user_name),
            "dog_name": str(ws.cell(row=row_num, column=3).value or ""),
            "breed": str(ws.cell(row=row_num, column=4).value or ""),
            "dog_class": str(ws.cell(row=row_num, column=5).value or ""),
            "time": round(time_val, 2),
            "fail": fail_val,
            "refuse": refuse_val,
            "deduct": deduct,
            "speed": speed,
            "total_time": total_time,
        })
        row_num += 1

    # グループ分けと並び替え
    group1 = sorted(
        [p for p in raw if p["time"] > 0 and p["deduct"] == 0],
        key=lambda p: p["total_time"],
    )
    group2 = sorted(
        [p for p in raw if p["time"] > 0 and p["deduct"] > 0],
        key=lambda p: p["total_time"],
    )
    group3 = [p for p in raw if p["time"] == 0]

    # 順位付け
    rank = 1
    for p in group1:
        p["rank"] = rank
        rank += 1
    for p in group2:
        p["rank"] = rank
        rank += 1
    for p in group3:
        p["rank"] = "失格"

    wb_out = _build_results_workbook(
        title, course_len, std_time, limit_time, turning_speed, group1 + group2 + group3
    )
    buf = io.BytesIO()
    wb_out.save(buf)
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
        st.markdown("#### 種目別出走表")
        race_excel = generate_race_excel(participants)
        if race_excel:
            st.download_button(
                label="出走表をダウンロード（Excel）",
                data=race_excel,
                file_name="出走表.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("出走表を作成できるデータがありません。")

        st.divider()
        st.markdown("#### 種目別成績表")
        skeleton_zip = generate_results_skeleton_zip(participants)
        if skeleton_zip:
            st.download_button(
                label="成績表骨格をダウンロード（ZIP）",
                data=skeleton_zip,
                file_name="成績表骨格.zip",
                mime="application/zip",
            )
        else:
            st.info("成績表を作成できるデータがありません。")

        st.markdown("##### 成績計算")
        uploaded = st.file_uploader(
            "成績入力済みファイルをアップロード", type=["xlsx"], key="results_upload"
        )
        if uploaded:
            result_bytes = process_results_excel(uploaded.read())
            st.download_button(
                label="成績表をダウンロード（Excel）",
                data=result_bytes,
                file_name=f"成績表_{uploaded.name}",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="results_download",
            )

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
