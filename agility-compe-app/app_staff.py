import io

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from supabase_client import get_supabase
from app_admin import calc_fee
from utils.settings import get_event_fees, get_login_message

CLASS_ORDER: list[str] = ["S", "M", "IM", "L"]


def fetch_participants() -> list[dict] | None:
    """参加者と犬情報の一覧をSupabaseから取得する。"""
    try:
        response = get_supabase().rpc("get_participants_with_dogs").execute()
        return response.data
    except Exception as e:
        st.error(f"データの取得に失敗しました: {e}")
        return None


def check_staff_password() -> bool:
    """スタッフパスワードを確認する。

    認証済みの場合はTrueを返す。未認証の場合はログインフォームを表示してFalseを返す。
    """
    if st.session_state.get("staff_authenticated"):
        return True

    st.subheader("スタッフログイン")
    password = st.text_input("パスワード", type="password", key="staff_password_input")

    if st.button("ログイン", type="primary", use_container_width=True):
        if password == st.secrets["staff"]["password"]:
            st.session_state["staff_authenticated"] = True
            st.rerun()
        else:
            st.error("パスワードが間違っています。")

    return False


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

    event_fees = get_event_fees()
    total_fee = sum(event_fees.get(e, 0) for row in rows for e in (row.get("events") or []))
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


def fetch_summary() -> dict | None:
    """Supabaseから申し込み状況サマリーを取得する。"""
    try:
        response = get_supabase().rpc("get_registration_summary").execute()
        return response.data
    except Exception as e:
        st.error(f"データの取得に失敗しました: {e}")
        return None


def show_summary(summary: dict, participants: list[dict]) -> None:
    """申し込み状況の集計を表示する。"""
    st.markdown("#### 申し込み状況")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("参加登録者数", f"{summary['user_count']} 名")
    with col2:
        st.metric("登録済み犬数", f"{summary['dog_count']} 頭")

    st.markdown("##### 種目別エントリー数")
    event_counts: dict = summary.get("event_counts") or {}
    event_fees = get_event_fees()
    rows = []
    for event in event_fees:
        total = event_counts.get(event, 0)
        class_counts = {
            cls: sum(
                1 for p in participants
                if event in (p.get("events") or []) and p.get("dog_class") == cls
            )
            for cls in CLASS_ORDER
        }
        rows.append({"種目": event, "頭数": total, **class_counts})
    totals = {"種目": "合計", "頭数": sum(r["頭数"] for r in rows)}
    totals.update({cls: sum(r[cls] for r in rows) for cls in CLASS_ORDER})
    rows.append(totals)
    st.dataframe(rows, hide_index=True, use_container_width=True)


def fetch_race_configs() -> list[dict] | None:
    """race_configsテーブルから全設定を取得する。種目・クラスの定義済み順でソートして返す。"""
    try:
        data = get_supabase().table("race_configs").select("*").execute().data
        if not data:
            return data
        event_order = list(get_event_fees().keys())
        return sorted(
            data,
            key=lambda c: (
                event_order.index(c["event"]) if c["event"] in event_order else 999,
                CLASS_ORDER.index(c["dog_class"]) if c["dog_class"] in CLASS_ORDER else 999,
            ),
        )
    except Exception as e:
        st.error(f"コース設定の取得に失敗しました: {e}")
        return None


def upsert_race_config(
    event: str, dog_class: str, course_len: float, std_time: float, limit_time: float
) -> bool:
    """コース設定をSupabaseにupsertする。"""
    try:
        get_supabase().table("race_configs").upsert(
            {
                "event": event,
                "dog_class": dog_class,
                "course_len": course_len,
                "std_time": std_time,
                "limit_time": limit_time,
            },
            on_conflict="event,dog_class",
        ).execute()
        return True
    except Exception as e:
        st.error(f"コース設定の保存に失敗しました: {e}")
        return False


def delete_race_config(event: str, dog_class: str) -> bool:
    """指定種目・クラスのコース設定をSupabaseから削除する。"""
    try:
        get_supabase().table("race_configs").delete().eq("event", event).eq("dog_class", dog_class).execute()
        return True
    except Exception as e:
        st.error(f"コース設定の削除に失敗しました: {e}")
        return False


def fetch_results_for_config(race_config_id: int) -> list[dict] | None:
    """指定race_config_idの成績一覧をRPC経由で取得する。"""
    try:
        return get_supabase().rpc("get_race_results", {"p_race_config_id": race_config_id}).execute().data
    except Exception as e:
        st.error(f"成績データの取得に失敗しました: {e}")
        return None


def upsert_race_result(race_config_id: int, dog_id: str, run_time: float, fail: int, refuse: int) -> bool:
    """成績を1件upsertする。"""
    try:
        get_supabase().table("race_results").upsert(
            {"race_config_id": race_config_id, "dog_id": dog_id, "time": run_time, "fail": fail, "refuse": refuse},
            on_conflict="race_config_id,dog_id",
        ).execute()
        return True
    except Exception as e:
        st.error(f"成績の保存に失敗しました: {e}")
        return False


def show_race_config_input() -> None:
    """コース設定入力画面を表示する。"""
    st.markdown("#### コース設定入力")

    with st.spinner("読み込み中..."):
        configs = fetch_race_configs()

    if configs:
        st.markdown("##### 現在の設定一覧")
        st.dataframe(
            [
                {
                    "種目": c["event"],
                    "クラス": c["dog_class"],
                    "コース全長 (m)": c["course_len"],
                    "標準タイム (sec)": c["std_time"],
                    "リミットタイム (sec)": c["limit_time"],
                }
                for c in configs
            ],
            hide_index=True,
            use_container_width=True,
        )
        st.divider()

    st.markdown("##### 設定を入力・更新")
    col1, col2 = st.columns(2)
    with col1:
        event = st.selectbox("種目", options=list(get_event_fees().keys()), key="config_event")
    with col2:
        dog_class = st.selectbox("クラス", options=CLASS_ORDER, key="config_class")

    existing = next(
        (c for c in (configs or []) if c["event"] == event and c["dog_class"] == dog_class),
        None,
    )
    # 種目・クラスが変わるとキーが変わりデフォルト値でリセットされる
    sfx = f"{event}_{dog_class}"

    def _str_val(key: str) -> str:
        v = existing.get(key) if existing else None
        return str(v) if v is not None else ""

    col3, col4, col5 = st.columns(3)
    with col3:
        course_len_str = st.text_input("コース全長 (m)", value=_str_val("course_len"), key=f"course_len_{sfx}")
    with col4:
        std_time_str = st.text_input("標準タイム (sec)", value=_str_val("std_time"), key=f"std_time_{sfx}")
    with col5:
        limit_time_str = st.text_input("リミットタイム (sec)", value=_str_val("limit_time"), key=f"limit_time_{sfx}")

    cols = st.columns(3) if existing else st.columns(2)

    if cols[0].button("保存", type="primary", use_container_width=True, key="config_save"):
        try:
            course_len = float(course_len_str)
            std_time = float(std_time_str)
            limit_time = float(limit_time_str)
        except ValueError:
            st.error("コース全長・標準タイム・リミットタイムは数値で入力してください。")
            return
        if upsert_race_config(event, dog_class, course_len, std_time, limit_time):
            st.success(f"{event} - {dog_class}クラス のコース設定を保存しました。")
            st.rerun()

    if cols[1].button("入力を破棄", use_container_width=True, key="config_discard"):
        for k in [f"course_len_{sfx}", f"std_time_{sfx}", f"limit_time_{sfx}"]:
            st.session_state.pop(k, None)
        st.rerun()

    if existing and cols[2].button("保存済みを削除", use_container_width=True, key="config_delete"):
        if delete_race_config(event, dog_class):
            for k in [f"course_len_{sfx}", f"std_time_{sfx}", f"limit_time_{sfx}"]:
                st.session_state.pop(k, None)
            st.success(f"{event} - {dog_class}クラス のコース設定を削除しました。")
            st.rerun()


def show_race_results_input() -> None:
    """成績入力画面を表示する。"""
    st.markdown("#### 成績入力")

    with st.spinner("読み込み中..."):
        configs = fetch_race_configs()
        participants_all = fetch_participants()

    if not configs:
        st.info("コース設定が登録されていません。先にコース設定を入力してください。")
        return

    config_labels = [f"{c['event']} - {c['dog_class']}クラス" for c in configs]
    selected_label = st.selectbox("種目・クラスを選択", options=config_labels, key="ri_config_label")
    selected_config = next(c for c in configs if f"{c['event']} - {c['dog_class']}クラス" == selected_label)
    race_config_id: int = selected_config["id"]
    event, dog_class = selected_config["event"], selected_config["dog_class"]

    participants = [
        p for p in (participants_all or [])
        if event in (p.get("events") or []) and p.get("dog_class") == dog_class
    ]
    if not participants:
        st.info("この種目・クラスに参加者がいません。")
        return

    existing_results = fetch_results_for_config(race_config_id) or []
    results_dict = {str(r["dog_id"]): r for r in existing_results}

    # 種目・クラス切り替え時にsession_stateを初期化
    if st.session_state.get("_ri_config_id") != race_config_id:
        st.session_state["_ri_config_id"] = race_config_id
        for idx, p in enumerate(participants):
            k = f"{idx}_{p['dog_id']}"
            ex = results_dict.get(str(p["dog_id"]))
            if ex:
                rt = float(ex.get("run_time") or 0)
                st.session_state[f"ri_disq_{k}"] = (rt == 0)
                st.session_state[f"ri_time_{k}"] = f"{rt:.2f}" if rt > 0 else "0.00"
                st.session_state[f"ri_fail_{k}"] = int(ex.get("fail") or 0)
                st.session_state[f"ri_refuse_{k}"] = int(ex.get("refuse") or 0)
            else:
                st.session_state[f"ri_disq_{k}"] = False
                st.session_state[f"ri_time_{k}"] = "0.00"
                st.session_state[f"ri_fail_{k}"] = 0
                st.session_state[f"ri_refuse_{k}"] = 0

    st.caption(f"参加者: {len(participants)}名")

    # ヘッダー行
    h1, h2, h3, h4, h5 = st.columns([3, 1.5, 2, 1.5, 1.5])
    h1.markdown("**氏名 / 犬名**")
    h2.markdown("**失格**")
    h3.markdown("**タイム (sec)**")
    h4.markdown("**失敗**")
    h5.markdown("**拒絶**")
    st.divider()

    for idx, p in enumerate(participants):
        k = f"{idx}_{p['dog_id']}"
        c1, c2, c3, c4, c5 = st.columns([3, 1.5, 2, 1.5, 1.5])
        with c1:
            st.write(f"{p['user_name']} / {p['dog_name']}")
        with c2:
            disq = st.checkbox("失格", key=f"ri_disq_{k}", label_visibility="collapsed")
        with c3:
            st.text_input("タイム", disabled=disq, key=f"ri_time_{k}", label_visibility="collapsed")
        with c4:
            st.number_input("失敗", min_value=0, step=1, disabled=disq, key=f"ri_fail_{k}", label_visibility="collapsed")
        with c5:
            st.number_input("拒絶", min_value=0, step=1, disabled=disq, key=f"ri_refuse_{k}", label_visibility="collapsed")
        st.divider()

    if st.button("一括保存", type="primary", use_container_width=True, key="ri_save"):
        errors: list[str] = []
        for idx, p in enumerate(participants):
            k = f"{idx}_{p['dog_id']}"
            if st.session_state.get(f"ri_disq_{k}", False):
                rt, fail, refuse = 0.0, 0, 0
            else:
                try:
                    rt = round(float(st.session_state.get(f"ri_time_{k}") or "0"), 2)
                except ValueError:
                    errors.append(f"{p['user_name']}: タイムの形式が正しくありません")
                    continue
                fail = int(st.session_state.get(f"ri_fail_{k}") or 0)
                refuse = int(st.session_state.get(f"ri_refuse_{k}") or 0)
            if not upsert_race_result(race_config_id, p["dog_id"], rt, fail, refuse):
                errors.append(f"{p['user_name']}: 保存に失敗しました")

        if errors:
            for msg in errors:
                st.error(msg)
        else:
            st.success(f"{selected_label} の成績を保存しました。")


def generate_race_schedule_pdf(participants: list[dict], event_fees: dict[str, int]) -> bytes | None:
    """種目・クラス別出走表をPDF形式で生成してバイト列で返す。対象データなしの場合はNoneを返す。"""
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    FONT = "HeiseiKakuGo-W5"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )
    title_style = ParagraphStyle("title", fontName=FONT, fontSize=16, spaceAfter=6 * mm)
    col_names = ["No.", "氏名", "犬名", "犬種", "クラス"]
    col_widths = [15 * mm, 45 * mm, 45 * mm, 55 * mm, 20 * mm]
    header_bg = colors.HexColor("#D9E1F2")

    story: list = []
    created = False

    for event in event_fees:
        for cls in CLASS_ORDER:
            rows = [
                p for p in participants
                if event in (p.get("events") or []) and p.get("dog_class") == cls
            ]
            if not rows:
                continue

            if created:
                story.append(PageBreak())

            story.append(Paragraph(f"{event}　{cls}クラス　出走表", title_style))

            table_data = [col_names] + [
                [str(i), p["user_name"], p["dog_name"], p["breed"], p["dog_class"]]
                for i, p in enumerate(rows, start=1)
            ]
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("BACKGROUND", (0, 0), (-1, 0), header_bg),
                ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (4, 0), (4, -1), "CENTER"),
            ]))
            story.append(table)
            created = True

    if not created:
        return None

    doc.build(story)
    return buf.getvalue()


def show_race_schedule(participants: list[dict]) -> None:
    """種目別・クラス別の出走表をWeb表示する。"""
    st.markdown("#### 出走表")

    event_fees = get_event_fees()
    pdf_bytes = generate_race_schedule_pdf(participants, event_fees)
    if pdf_bytes:
        st.download_button(
            label="出走表をダウンロード（PDF）",
            data=pdf_bytes,
            file_name="出走表.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    any_shown = False
    for event in event_fees:
        for cls in CLASS_ORDER:
            rows = [
                p for p in participants
                if event in (p.get("events") or []) and p.get("dog_class") == cls
            ]
            if not rows:
                continue

            any_shown = True
            st.markdown(f"##### {event} - {cls}クラス")
            data = [
                {
                    "No.": i,
                    "氏名": p["user_name"],
                    "犬名": p["dog_name"],
                    "犬種": p["breed"],
                    "クラス": p["dog_class"],
                }
                for i, p in enumerate(rows, start=1)
            ]
            st.dataframe(data, hide_index=True, use_container_width=True)

    if not any_shown:
        st.info("出走表を表示できるデータがありません。")


def calc_rankings(results: list[dict]) -> list[dict]:
    """成績リストに順位を付けて返す。"""
    group1 = sorted(
        [r for r in results if not r.get("fail") and not r.get("refuse") and (r.get("run_time") or 0) > 0],
        key=lambda r: r["run_time"],
    )
    group2 = sorted(
        [r for r in results if ((r.get("fail") or 0) + (r.get("refuse") or 0) > 0) and (r.get("run_time") or 0) > 0],
        key=lambda r: (r.get("deduct") or 0, r["run_time"]),
    )
    group3 = [r for r in results if not (r.get("run_time") or 0)]

    rank = 1
    for r in group1:
        r["rank"] = rank
        rank += 1
    for r in group2:
        r["rank"] = rank
        rank += 1
    for r in group3:
        r["rank"] = "失格"

    return group1 + group2 + group3


def show_race_results_view() -> None:
    """成績表表示画面を表示する。"""
    st.markdown("#### 成績表")

    with st.spinner("読み込み中..."):
        configs = fetch_race_configs()

    if not configs:
        st.info("コース設定が登録されていません。")
        return

    config_labels = [f"{c['event']} - {c['dog_class']}クラス" for c in configs]
    selected_label = st.selectbox("種目・クラスを選択", options=config_labels, key="rv_config_label")
    selected_config = next(c for c in configs if f"{c['event']} - {c['dog_class']}クラス" == selected_label)

    with st.spinner("成績を読み込み中..."):
        results = fetch_results_for_config(selected_config["id"])

    if not results:
        st.info("成績データがありません。先に成績を入力してください。")
        return

    r0 = results[0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("コース全長", f"{r0['course_len']} m")
    col2.metric("標準タイム", f"{r0['std_time']} sec")
    col3.metric("リミットタイム", f"{r0['limit_time']} sec")
    col4.metric("旋回スピード", f"{r0['turning_speed']} m/sec")

    st.divider()

    ranked = calc_rankings(results)
    clean_flags = [r["rank"] != "失格" and (r.get("deduct") or 0) == 0 for r in ranked]

    df = pd.DataFrame([
        {
            "順位": r["rank"],
            "氏名": r["user_name"],
            "犬名": r["dog_name"],
            "犬種": r["breed"],
            "クラス": r["dog_class"],
            "タイム": r["run_time"],
            "失敗": int(r.get("fail") or 0),
            "拒絶": int(r.get("refuse") or 0),
            "減点": r.get("deduct"),
            "スピード": r.get("speed"),
        }
        for r in ranked
    ])

    def _highlight_clean(row: pd.Series) -> list[str]:
        color = "color: #0000FF" if clean_flags[row.name] else ""
        return [color] * len(row)

    st.dataframe(
        df.style.apply(_highlight_clean, axis=1).format(
            {"タイム": "{:.2f}", "減点": "{:.2f}", "スピード": "{:.2f}"},
            na_rep="-",
        ),
        hide_index=True,
        use_container_width=True,
    )


def show_nav_buttons() -> None:
    """ナビゲーションボタンを表示し、選択状態をsession_stateに保存する。"""
    if st.button("参加者・犬情報一覧を見る", use_container_width=True):
        st.session_state["staff_view"] = "participants"
    if st.button("申し込み状況をみる", use_container_width=True):
        st.session_state["staff_view"] = "summary"
    if st.button("出走表を見る", use_container_width=True):
        st.session_state["staff_view"] = "schedule"
    if st.button("コース設定を入力する", use_container_width=True):
        st.session_state["staff_view"] = "race_config"
    if st.button("成績を入力する", use_container_width=True):
        st.session_state["staff_view"] = "race_results"
    if st.button("成績表を見る", use_container_width=True):
        st.session_state["staff_view"] = "race_results_view"


def main() -> None:
    """スタッフアプリのメインエントリーポイント。"""
    st.set_page_config(
        page_title="スタッフ | アジリティー練習会",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    if not st.session_state.get("staff_authenticated"):
        msg = get_login_message()
        if msg:
            st.markdown(f"### **{msg}**")

    st.subheader("スタッフ画面")

    if not check_staff_password():
        return

    show_nav_buttons()

    view = st.session_state.get("staff_view")

    if view == "participants":
        st.divider()
        with st.spinner("読み込み中..."):
            participants = fetch_participants()
        if participants is not None:
            show_participants_table(participants)

    elif view == "summary":
        st.divider()
        with st.spinner("読み込み中..."):
            participants = fetch_participants()
            summary = fetch_summary()
        if participants is not None and summary:
            show_summary(summary, participants)

    elif view == "schedule":
        st.divider()
        with st.spinner("読み込み中..."):
            participants = fetch_participants()
        if participants is not None:
            show_race_schedule(participants)

    elif view == "race_config":
        st.divider()
        show_race_config_input()

    elif view == "race_results":
        st.divider()
        show_race_results_input()

    elif view == "race_results_view":
        st.divider()
        show_race_results_view()

    st.divider()
    if st.button("ログアウト", use_container_width=True):
        del st.session_state["staff_authenticated"]
        st.session_state.pop("staff_view", None)
        st.rerun()


if __name__ == "__main__":
    main()
