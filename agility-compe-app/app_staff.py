import streamlit as st

from supabase_client import get_supabase
from app_admin import EVENT_FEES, CLASS_ORDER, calc_fee


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


EVENTS: list[str] = ["ビギナー", "JP1.5", "JP2.5", "AG1", "AG2", "AG3"]


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
    rows = []
    for event in EVENTS:
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


def show_race_schedule(participants: list[dict]) -> None:
    """種目別・クラス別の出走表をWeb表示する。"""
    st.markdown("#### 出走表")

    any_shown = False
    for event in EVENT_FEES:
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


def show_nav_buttons() -> None:
    """ナビゲーションボタンを表示し、選択状態をsession_stateに保存する。"""
    if st.button("参加者・犬情報一覧を見る", use_container_width=True):
        st.session_state["staff_view"] = "participants"
    if st.button("申し込み状況をみる", use_container_width=True):
        st.session_state["staff_view"] = "summary"
    if st.button("出走表を見る", use_container_width=True):
        st.session_state["staff_view"] = "schedule"


def main() -> None:
    """スタッフアプリのメインエントリーポイント。"""
    st.set_page_config(
        page_title="スタッフ | アジリティー練習会",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.title("アジリティー練習会 スタッフ画面")

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

    st.divider()
    if st.button("ログアウト", use_container_width=True):
        del st.session_state["staff_authenticated"]
        st.session_state.pop("staff_view", None)
        st.rerun()


if __name__ == "__main__":
    main()
