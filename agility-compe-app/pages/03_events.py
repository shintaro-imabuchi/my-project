from datetime import date

import streamlit as st

from utils.events import EVENT_TYPES, get_events, is_registration_open


def _fetch_events(event_types: list[str]) -> list[dict] | None:
    """絞り込み条件に合うイベント一覧を取得する。失敗時はエラーを表示しNoneを返す。"""
    try:
        return get_events(event_types)
    except Exception as e:
        st.error(f"データの取得に失敗しました: {e}")
        return None


_BADGE_COLORS: dict[str, str] = {
    "公式競技会": "red",
    "練習会": "blue",
    "壮行会": "orange",
    "セミナー": "green",
}


def _format_date(iso_str: str) -> str:
    """ISO形式の日付文字列を表示用文字列にする。"""
    d = date.fromisoformat(iso_str)
    return f"{d.year}/{d.month}/{d.day}"


def _format_date_range(event: dict) -> str:
    """開催日〜終了日を表示用文字列にする。"""
    text = _format_date(event["event_date"])
    end_raw = event.get("event_end_date")
    if end_raw and end_raw != event["event_date"]:
        text += f" 〜 {_format_date(end_raw)}"
    return text


def _format_registration_period(event: dict) -> str | None:
    """申込開始日〜締切日を表示用文字列にする。どちらも未設定ならNoneを返す。"""
    opens_on = event.get("registration_opens_on")
    deadline = event.get("registration_deadline")
    if opens_on and deadline:
        return f"{_format_date(opens_on)} 〜 {_format_date(deadline)}"
    if opens_on:
        return f"{_format_date(opens_on)} 〜"
    if deadline:
        return f"〜 {_format_date(deadline)}"
    return None


def _registration_status_label(event: dict) -> tuple[str, str]:
    """受付状況の表示種別（success/info/caption）とラベルを返す。

    受付中でない場合、申込開始日・締切日から「受付開始前」「受付終了」を
    判別できるならそれを返し、日付から判断できない場合のみ
    「受付終了/未定」とする。
    """
    if is_registration_open(event):
        return "success", "受付中"

    today = date.today()
    opens_on = event.get("registration_opens_on")
    deadline = event.get("registration_deadline")

    if opens_on and date.fromisoformat(opens_on) > today:
        return "info", "受付開始前"
    if deadline and date.fromisoformat(deadline) < today:
        return "caption", "受付終了"
    return "caption", "受付終了/未定"


def _sort_by_proximity(events: list[dict]) -> list[dict]:
    """開催日が近い順（当日以降を優先）に並び替える。"""
    today = date.today()
    upcoming = [e for e in events if date.fromisoformat(e["event_date"]) >= today]
    past = [e for e in events if date.fromisoformat(e["event_date"]) < today]
    past.reverse()
    return upcoming + past


def show_event_card(event: dict) -> None:
    """1件の開催情報をカード形式で表示する。"""
    color = _BADGE_COLORS.get(event["event_type"], "gray")
    with st.container(border=True):
        st.markdown(f"**{event['name']}** :{color}-badge[{event['event_type']}]")
        st.caption(f"開催日: {_format_date_range(event)}")
        if event.get("organizer_name"):
            st.caption(f"主催: {event['organizer_name']}")
        if event.get("venue"):
            st.caption(f"会場: {event['venue']}")
        registration_period = _format_registration_period(event)
        if registration_period:
            st.caption(f"申込期間: {registration_period}")

        status_kind, status_label = _registration_status_label(event)
        if status_kind == "success":
            st.success(status_label, icon="✅")
        elif status_kind == "info":
            st.info(status_label, icon="⏳")
        else:
            st.caption(status_label)

        with st.expander("詳細を見る"):
            url = event.get("registration_url")
            if url:
                st.link_button("参加登録はこちら", url=url, use_container_width=True)
                st.caption("※別サイトに移動します。")
            else:
                st.caption("詳細・申込方法は主催クラブにお問い合わせください。")

            if event.get("registration_note"):
                st.markdown(event["registration_note"])
            if event.get("notes"):
                st.markdown(event["notes"])


def main() -> None:
    """開催情報一覧ページのメインエントリーポイント。ログイン不要で閲覧できる。"""
    st.set_page_config(
        page_title="開催情報一覧 | アジリティー練習会",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    st.subheader("開催情報一覧")

    if st.button("戻る", use_container_width=True):
        st.switch_page("app_entry.py")

    selected_types = st.multiselect(
        "イベント種別で絞り込み", options=EVENT_TYPES, default=EVENT_TYPES
    )

    fetched = _fetch_events(selected_types) if selected_types else []
    events = _sort_by_proximity(fetched) if fetched else []

    if fetched is not None and not events:
        st.info("該当するイベントがありません。")
    else:
        for event in events:
            show_event_card(event)


if __name__ == "__main__":
    main()
