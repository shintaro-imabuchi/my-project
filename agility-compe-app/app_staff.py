import io

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from supabase_client import get_supabase, get_competition_id, sign_in_as_owner
from app_admin import calc_fee
from utils.settings import get_event_fees, get_login_message

CLASS_ORDER: list[str] = ["S", "M", "IM", "L"]


def fetch_participants() -> list[dict] | None:
    """参加者と犬情報の一覧をSupabaseから取得する。"""
    try:
        response = get_supabase().rpc(
            "get_entries_with_dogs", {"p_competition_id": get_competition_id()}
        ).execute()
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
            sign_in_as_owner()
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
        response = get_supabase().rpc(
            "get_registration_summary", {"p_competition_id": get_competition_id()}
        ).execute()
        return response.data
    except Exception as e:
        st.error(f"データの取得に失敗しました: {e}")
        return None


def show_summary(summary: dict, participants: list[dict]) -> None:
    """申し込み状況の集計を表示する。"""
    st.markdown("#### 申し込み状況")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("参加登録数", f"{summary['entry_count']} 件")
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
    small = st.column_config.NumberColumn(width="small")
    st.dataframe(
        rows,
        hide_index=True,
        use_container_width=True,
        column_config={"頭数": small, "S": small, "M": small, "IM": small, "L": small},
    )


def fetch_race_configs() -> list[dict] | None:
    """race_configsテーブルからこの大会の全設定を取得する。種目・クラスの定義済み順でソートして返す。"""
    try:
        data = (
            get_supabase()
            .table("race_configs")
            .select("*")
            .eq("competition_id", get_competition_id())
            .execute()
            .data
        )
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
    event: str,
    dog_class: str,
    course_len: float | None,
    std_time: float | None,
    limit_time: float | None,
    bar_height: float | None,
) -> bool:
    """コース設定をSupabaseにupsertする。

    いずれの数値項目も任意（未入力ならNULL）。種目によってはコース全長や
    タイムの概念がない場合もあるため、必須にはしていない。
    bar_height（既定のバーの高さ）が未入力（None）の場合は「この種目には
    バーの高さの概念がない」とみなされ、参加登録アプリ（Next.js版）側で
    バーダウン希望のUIが表示されなくなる。
    """
    try:
        get_supabase().table("race_configs").upsert(
            {
                "competition_id": get_competition_id(),
                "event": event,
                "dog_class": dog_class,
                "course_len": course_len,
                "std_time": std_time,
                "limit_time": limit_time,
                "bar_height": bar_height,
            },
            on_conflict="competition_id,event,dog_class",
        ).execute()
        return True
    except Exception as e:
        st.error(f"コース設定の保存に失敗しました: {e}")
        return False


def delete_race_config(event: str, dog_class: str) -> bool:
    """指定種目・クラスのコース設定をSupabaseから削除する。"""
    try:
        get_supabase().table("race_configs").delete().eq(
            "competition_id", get_competition_id()
        ).eq("event", event).eq("dog_class", dog_class).execute()
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


def upsert_race_result(race_config_id: int, entry_id: int, run_time: float, fail: int, refuse: int) -> bool:
    """成績を1件upsertする。"""
    try:
        get_supabase().table("race_results").upsert(
            {"race_config_id": race_config_id, "entry_id": entry_id, "time": run_time, "fail": fail, "refuse": refuse},
            on_conflict="race_config_id,entry_id",
        ).execute()
        return True
    except Exception as e:
        st.error(f"成績の保存に失敗しました: {e}")
        return False


def _parse_optional_float(label: str, value_str: str) -> float | None:
    """空文字ならNone、そうでなければfloatに変換する。

    変換に失敗した場合は項目名（label）をメッセージに持つValueErrorを送出する
    （呼び出し側で f"{e}は数値で入力してください" のように使う）。
    """
    if not value_str.strip():
        return None
    try:
        return float(value_str)
    except ValueError:
        raise ValueError(label) from None


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
                    "バーの高さ (cm)": c.get("bar_height"),
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

    bar_height_str = st.text_input(
        "バーの高さ (cm)　※任意。参加登録アプリのバーダウン希望の基準値になります",
        value=_str_val("bar_height"),
        key=f"bar_height_{sfx}",
    )

    cols = st.columns(3) if existing else st.columns(2)

    if cols[0].button("保存", type="primary", use_container_width=True, key="config_save"):
        try:
            course_len = _parse_optional_float("コース全長", course_len_str)
            std_time = _parse_optional_float("標準タイム", std_time_str)
            limit_time = _parse_optional_float("リミットタイム", limit_time_str)
            bar_height = _parse_optional_float("バーの高さ", bar_height_str)
        except ValueError as e:
            st.error(f"{e}は数値で入力してください（未入力も可）。")
            return
        if upsert_race_config(event, dog_class, course_len, std_time, limit_time, bar_height):
            st.success(f"{event} - {dog_class}クラス のコース設定を保存しました。")
            st.rerun()

    if cols[1].button("入力を破棄", use_container_width=True, key="config_discard"):
        for k in [f"course_len_{sfx}", f"std_time_{sfx}", f"limit_time_{sfx}", f"bar_height_{sfx}"]:
            st.session_state.pop(k, None)
        st.rerun()

    if existing and cols[2].button("保存済みを削除", use_container_width=True, key="config_delete"):
        if delete_race_config(event, dog_class):
            for k in [f"course_len_{sfx}", f"std_time_{sfx}", f"limit_time_{sfx}", f"bar_height_{sfx}"]:
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
    results_dict = {str(r["entry_id"]): r for r in existing_results}

    # 種目・クラス切り替え時にsession_stateを初期化
    if st.session_state.get("_ri_config_id") != race_config_id:
        st.session_state["_ri_config_id"] = race_config_id
        for idx, p in enumerate(participants):
            k = f"{idx}_{p['entry_id']}"
            ex = results_dict.get(str(p["entry_id"]))
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
        k = f"{idx}_{p['entry_id']}"
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
            k = f"{idx}_{p['entry_id']}"
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
            if not upsert_race_result(race_config_id, p["entry_id"], rt, fail, refuse):
                errors.append(f"{p['user_name']}: 保存に失敗しました")

        if errors:
            for msg in errors:
                st.error(msg)
        else:
            st.success(f"{selected_label} の成績を保存しました。")


def _bar_height_map(race_configs: list[dict]) -> dict[tuple[str, str], float | None]:
    """(種目, クラス) をキーに、既定のバーの高さ(bar_height)を引けるdictを作る。"""
    return {(c["event"], c["dog_class"]): c.get("bar_height") for c in race_configs}


def _effective_bar_height(
    participant: dict, event: str, bar_height_map: dict[tuple[str, str], float | None]
) -> float:
    """出走順の並べ替えに使う「実効バーの高さ」を返す。

    バーダウン希望（entries.bar_down_requests）があればその高さ、無ければ
    その種目・クラスの既定のバーの高さ（race_configs.bar_height）を使う。
    どちらも無い（バーの高さの概念が無い種目等）場合は、常に末尾に来るよう
    無限大を返す（元の並び順＝氏名・登録日時順はソートの安定性により保持される）。
    """
    bar_down = (participant.get("bar_down_requests") or {}).get(event)
    if bar_down is not None:
        return float(bar_down)
    default_height = bar_height_map.get((event, participant["dog_class"]))
    if default_height is not None:
        return float(default_height)
    return float("inf")


def _bar_down_display(participant: dict, event: str) -> str:
    """バーダウン希望の表示用文字列を返す。希望が無ければ空文字（表示欄は空欄）。"""
    bar_down = (participant.get("bar_down_requests") or {}).get(event)
    return f"{bar_down}cm" if bar_down is not None else ""


def _rows_for_event_class(
    participants: list[dict], event: str, cls: str, bar_height_map: dict[tuple[str, str], float | None]
) -> list[dict]:
    """指定の種目・クラスに出陳する参加者を、バーの高さ昇順で返す。

    同じ高さの場合は元の並び順（参加者一覧の取得順＝氏名・登録日時順）を保持する
    （Pythonのsortedは安定ソートのため）。
    """
    rows = [
        p for p in participants
        if event in (p.get("events") or []) and p.get("dog_class") == cls
    ]
    return sorted(rows, key=lambda p: _effective_bar_height(p, event, bar_height_map))


def generate_race_schedule_pdf(
    participants: list[dict], event_fees: dict[str, int], race_configs: list[dict]
) -> bytes | None:
    """種目・クラス別出走表をPDF形式で生成してバイト列で返す。対象データなしの場合はNoneを返す。

    出走順は種目・クラスごとに、バーの高さの昇順（バーダウン希望があればその高さ、
    無ければ既定のバーの高さ）で決まる。
    """
    bar_height_map = _bar_height_map(race_configs)
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    FONT = "HeiseiKakuGo-W5"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )
    title_style = ParagraphStyle("title", fontName=FONT, fontSize=16, spaceAfter=6 * mm)
    col_names = ["No.", "氏名", "犬名", "犬種", "クラス", "バーダウン"]
    col_widths = [15 * mm, 40 * mm, 40 * mm, 50 * mm, 18 * mm, 22 * mm]
    header_bg = colors.HexColor("#D9E1F2")

    story: list = []
    created = False

    for event in event_fees:
        for cls in CLASS_ORDER:
            rows = _rows_for_event_class(participants, event, cls, bar_height_map)
            if not rows:
                continue

            if created:
                story.append(PageBreak())

            story.append(Paragraph(f"{event}　{cls}クラス　出走表", title_style))

            table_data = [col_names] + [
                [
                    str(i), p["user_name"], p["dog_name"], p["breed"], p["dog_class"],
                    _bar_down_display(p, event),
                ]
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
                ("ALIGN", (4, 0), (5, -1), "CENTER"),
            ]))
            story.append(table)
            created = True

    if not created:
        return None

    doc.build(story)
    return buf.getvalue()


def show_race_schedule(participants: list[dict]) -> None:
    """種目別・クラス別の出走表をWeb表示する。

    出走順は種目・クラスごとに、バーの高さの昇順（バーダウン希望があれば
    その高さ、無ければ既定のバーの高さ）で決まる。
    """
    st.markdown("#### 出走表")

    event_fees = get_event_fees()
    with st.spinner("読み込み中..."):
        race_configs = fetch_race_configs() or []
    bar_height_map = _bar_height_map(race_configs)

    pdf_bytes = generate_race_schedule_pdf(participants, event_fees, race_configs)
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
            rows = _rows_for_event_class(participants, event, cls, bar_height_map)
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
                    "バーダウン": _bar_down_display(p, event),
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


def generate_race_results_pdf(
    title: str,
    r0: dict,
    ranked: list[dict],
    clean_flags: list[bool],
) -> bytes:
    """成績表をA4横PDF形式で生成してバイト列で返す。クリーンランは青字で出力する。"""
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    FONT = "HeiseiKakuGo-W5"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )
    title_style = ParagraphStyle("title", fontName=FONT, fontSize=16, spaceAfter=4 * mm)
    info_style = ParagraphStyle("info", fontName=FONT, fontSize=10, spaceAfter=2 * mm)
    header_bg = colors.HexColor("#D9E1F2")

    def _fmt(v) -> str:
        if v is None:
            return "-"
        try:
            return f"{float(v):.2f}"
        except (TypeError, ValueError):
            return str(v)

    col_names = ["順位", "氏名", "犬名", "犬種", "クラス", "タイム", "失敗", "拒絶", "減点", "スピード"]
    col_widths = [15 * mm, 40 * mm, 35 * mm, 45 * mm, 17 * mm, 22 * mm, 15 * mm, 15 * mm, 20 * mm, 22 * mm]

    table_data = [col_names] + [
        [
            str(r["rank"]),
            r["user_name"],
            r["dog_name"],
            r["breed"],
            r["dog_class"],
            _fmt(r.get("run_time")),
            str(int(r.get("fail") or 0)),
            str(int(r.get("refuse") or 0)),
            _fmt(r.get("deduct")),
            _fmt(r.get("speed")),
        ]
        for r in ranked
    ]

    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (4, 0), (4, -1), "CENTER"),
        ("ALIGN", (5, 0), (5, -1), "RIGHT"),
        ("ALIGN", (6, 0), (6, -1), "CENTER"),
        ("ALIGN", (7, 0), (7, -1), "CENTER"),
        ("ALIGN", (8, 0), (8, -1), "RIGHT"),
        ("ALIGN", (9, 0), (9, -1), "RIGHT"),
    ]
    for i, is_clean in enumerate(clean_flags):
        if is_clean:
            style_cmds.append(("TEXTCOLOR", (0, i + 1), (-1, i + 1), colors.blue))

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle(style_cmds))

    info_text = (
        f"コース全長: {r0['course_len']} m　　"
        f"標準タイム: {r0['std_time']} sec　　"
        f"リミットタイム: {r0['limit_time']} sec　　"
        f"旋回スピード: {r0['turning_speed']} m/sec"
    )
    story = [
        Paragraph(title, title_style),
        Paragraph(info_text, info_style),
        Spacer(1, 4 * mm),
        table,
    ]
    doc.build(story)
    return buf.getvalue()


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

    pdf_bytes = generate_race_results_pdf(selected_label, r0, ranked, clean_flags)
    st.download_button(
        label="成績表をダウンロード（PDF）",
        data=pdf_bytes,
        file_name=f"{selected_label}_成績表.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

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
