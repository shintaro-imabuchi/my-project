from datetime import date

import streamlit as st

from utils.events import EVENT_TYPES, STATUS_DEFAULT_SELECTED, STATUS_LABELS, get_event_status, get_events

# このアプリは特定のクラブ・大会に紐づかない、開催情報の公開閲覧専用サイト。
# ログイン不要・読み取り専用（Supabaseのanonキーのみ使用）。
# app_entry.py（各クラブの参加登録アプリ）のpages/03_events.pyと内容は同じだが、
# 独立したStreamlit Community Cloudデプロイとして運用するために分離した。


def _fetch_events(event_types: list[str]) -> list[dict] | None:
    """絞り込み条件に合う、掲載ONのイベント一覧を取得する。失敗時はエラーを表示しNoneを返す。"""
    try:
        return get_events(event_types, published_only=True)
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

        info_lines = [f"開催日: {_format_date_range(event)}"]
        if event.get("organizer_name"):
            info_lines.append(f"主催: {event['organizer_name']}")
        if event.get("venue"):
            info_lines.append(f"会場: {event['venue']}")
        registration_period = _format_registration_period(event)
        if registration_period:
            info_lines.append(f"申込期間: {registration_period}")
        st.caption("  \n".join(info_lines))

        status_kind, status_label = get_event_status(event)
        if status_kind == "success":
            st.success(status_label, icon="✅")
        elif status_kind == "info":
            st.info(status_label, icon="⏳")
        else:
            st.caption(status_label)

        with st.expander("詳細を見る"):
            guideline_url = event.get("guideline_url")
            if guideline_url:
                st.link_button("開催要項を見る", url=guideline_url, use_container_width=True)

            url = event.get("registration_url")
            if url:
                st.link_button("参加登録はこちら", url=url, use_container_width=True)
                st.caption("※別サイトに移動します。")
            elif not guideline_url:
                st.caption("詳細・申込方法は主催クラブにお問い合わせください。")

            if event.get("registration_note"):
                st.markdown(event["registration_note"])
            if event.get("notes"):
                st.markdown(event["notes"])


def main() -> None:
    """開催情報一覧サイトのメインエントリーポイント。ログイン不要で閲覧できる。"""
    col_title, col_date = st.columns([3, 1])
    with col_title:
        st.subheader("犬のアジリティー 開催情報一覧")
    with col_date:
        st.markdown(
            f"<div style='text-align:right; padding-top:0.8em; color:gray;'>"
            f"本日: {_format_date(date.today().isoformat())}</div>",
            unsafe_allow_html=True,
        )
    st.caption("公式競技会・練習会・壮行会・セミナーの開催情報をまとめています。")

    selected_types = st.pills(
        "イベント種別で絞り込み",
        options=EVENT_TYPES,
        selection_mode="multi",
        default=EVENT_TYPES,
    ) or []

    selected_statuses = st.pills(
        "受付状況で絞り込み",
        options=STATUS_LABELS,
        selection_mode="multi",
        default=STATUS_DEFAULT_SELECTED,
    ) or []

    fetched = _fetch_events(selected_types) if selected_types else []
    if fetched and selected_statuses:
        fetched = [e for e in fetched if get_event_status(e)[1] in selected_statuses]
    elif fetched:
        fetched = []
    events = _sort_by_proximity(fetched) if fetched else []

    if fetched is not None and not events:
        st.info("該当するイベントがありません。")
    else:
        for event in events:
            show_event_card(event)


if __name__ == "__main__":
    # st.navigationで「このアプリのページはこれだけ」と明示することで、
    # 同じフォルダにあるpages/（dog info・registration status等、
    # app_entry.py側のページ）が自動的にサイドバーへ紛れ込むのを防ぐ。
    st.set_page_config(
        page_title="開催情報一覧 | 犬のアジリティー",
        layout="centered",
    )
    page = st.navigation([st.Page(main, title="開催情報一覧")])
    page.run()
