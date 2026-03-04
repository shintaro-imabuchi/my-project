import streamlit as st

from supabase_client import get_supabase

EVENTS: list[str] = ["ビギナー", "JP1.5", "JP2.5", "AG1", "AG2", "AG3"]


def fetch_summary() -> dict | None:
    """Supabaseから申し込み状況サマリーを取得する。

    Supabase RPC関数 get_registration_summary を呼び出し、
    ユーザー数・犬数・種目別犬数を含む辞書を返す。
    """
    try:
        response = get_supabase().rpc("get_registration_summary").execute()
        return response.data
    except Exception as e:
        st.error(f"データの取得に失敗しました: {e}")
        return None


def show_summary(summary: dict) -> None:
    """申し込み状況の集計を表示する。"""
    col1, col2 = st.columns(2)
    with col1:
        st.metric("参加登録者数", f"{summary['user_count']} 名")
    with col2:
        st.metric("登録済み犬数", f"{summary['dog_count']} 頭")

    st.subheader("種目別エントリー数")
    event_counts: dict = summary.get("event_counts") or {}
    rows = [
        {"種目": event, "頭数": event_counts.get(event, 0)}
        for event in EVENTS
    ]
    st.dataframe(rows, hide_index=True, use_container_width=True)


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

    st.subheader("【申し込み状況】")

    with st.spinner("集計中..."):
        summary = fetch_summary()

    if summary:
        show_summary(summary)

    st.divider()
    if st.button("ホームに戻る", use_container_width=True):
        st.switch_page("app_entry.py")


if __name__ == "__main__":
    main()
