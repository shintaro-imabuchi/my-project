import streamlit as st

from supabase_client import get_supabase
from utils.settings import get_event_fees

CLASS_ORDER: list[str] = ["S", "M", "IM", "L"]


def fetch_summary() -> dict | None:
    """Supabaseから申し込み状況サマリーを取得する。"""
    try:
        response = get_supabase().rpc("get_registration_summary").execute()
        return response.data
    except Exception as e:
        st.error(f"データの取得に失敗しました: {e}")
        return None


def fetch_participants() -> list[dict] | None:
    """参加者と犬情報の一覧をSupabaseから取得する。"""
    try:
        response = get_supabase().rpc("get_participants_with_dogs").execute()
        return response.data
    except Exception as e:
        st.error(f"データの取得に失敗しました: {e}")
        return None


def show_summary(summary: dict, participants: list[dict]) -> None:
    """申し込み状況の集計を表示する。"""
    col1, col2 = st.columns(2)
    with col1:
        st.metric("参加登録者数", f"{summary['user_count']} 名")
    with col2:
        st.metric("登録済み犬数", f"{summary['dog_count']} 頭")

    st.subheader("種目別エントリー数")
    event_counts: dict = summary.get("event_counts") or {}
    rows = []
    for event in get_event_fees():
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


def main() -> None:
    """申し込み状況ページのメインエントリーポイント。"""
    st.set_page_config(
        page_title="申し込み状況 | アジリティー練習会",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    if not st.session_state.get("user"):
        st.warning("ログインが必要です。")
        st.switch_page("app_entry.py")
        return

    st.subheader("申し込み状況")

    with st.spinner("集計中..."):
        summary = fetch_summary()
        participants = fetch_participants()

    if summary and participants is not None:
        show_summary(summary, participants)

    st.divider()
    if st.button("ホームに戻る", use_container_width=True):
        st.switch_page("app_entry.py")


if __name__ == "__main__":
    main()
