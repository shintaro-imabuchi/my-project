from datetime import date

import streamlit as st

from utils.ai_event_parser import parse_event_with_ai
from utils.events import EVENT_TYPES, delete_event, get_events, insert_event, update_event


def _parse_date_input(value: str | None) -> date | None:
    """文字列をdateに変換する。パースできない場合はNoneを返す。"""
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def show_events_list() -> None:
    """登録済みイベントを一覧表示し、編集・削除ボタンを提供する。"""
    try:
        events = get_events()
    except Exception as e:
        st.error(f"データの取得に失敗しました: {e}")
        return
    if not events:
        st.info("登録されているイベントがありません。")
        return

    selected_id = (st.session_state.get("selected_event") or {}).get("id")
    for event in events:
        with st.container(border=True):
            col_info, col_edit, col_del = st.columns([4, 1, 1])
            with col_info:
                prefix = "✏️ " if event["id"] == selected_id else ""
                st.markdown(f"{prefix}**{event['name']}**　（{event['event_type']}）")
                date_range = event["event_date"]
                end_date = event.get("event_end_date")
                if end_date and end_date != event["event_date"]:
                    date_range += f" 〜 {end_date}"
                st.caption(
                    f"開催日: {date_range}　／　主催: {event.get('organizer_name') or '-'}"
                )
            with col_edit:
                if st.button("編集", key=f"event_row_edit_{event['id']}", use_container_width=True):
                    st.session_state["selected_event"] = event
                    st.session_state["event_form_v"] = st.session_state.get("event_form_v", 0) + 1
                    st.rerun()
            with col_del:
                if st.button("削除", key=f"event_row_del_{event['id']}", use_container_width=True):
                    delete_event(event["id"])
                    st.session_state.pop("selected_event", None)
                    st.session_state["flash_admin_event"] = f"「{event['name']}」を削除しました。"
                    st.rerun()


def show_event_form(defaults: dict, event_id: int | None) -> None:
    """イベント登録・編集フォームを表示する。event_idがNoneなら新規登録。"""
    form_v: int = st.session_state.get("event_form_v", 0)
    with st.form(f"event_form_{event_id or 'new'}_{form_v}"):
        name = st.text_input("イベント名 *", value=defaults.get("name") or "")
        type_idx = (
            EVENT_TYPES.index(defaults["event_type"])
            if defaults.get("event_type") in EVENT_TYPES
            else 1
        )
        event_type = st.radio("種別 *", EVENT_TYPES, index=type_idx, horizontal=True)
        organizer_name = st.text_input("主催クラブ名", value=defaults.get("organizer_name") or "")
        venue = st.text_input("会場", value=defaults.get("venue") or "")

        col1, col2 = st.columns(2)
        with col1:
            event_date_val = st.date_input(
                "開催日 *", value=_parse_date_input(defaults.get("event_date")) or date.today()
            )
        with col2:
            event_end_date_val = st.date_input(
                "終了日", value=_parse_date_input(defaults.get("event_end_date"))
            )

        col3, col4 = st.columns(2)
        with col3:
            opens_on_val = st.date_input(
                "申込開始日", value=_parse_date_input(defaults.get("registration_opens_on"))
            )
        with col4:
            deadline_val = st.date_input(
                "申込締切日", value=_parse_date_input(defaults.get("registration_deadline"))
            )

        registration_open = st.checkbox(
            "受付中フラグ", value=defaults.get("registration_open", True)
        )
        registration_url = st.text_input(
            "登録サイトURL", value=defaults.get("registration_url") or ""
        )
        registration_note = st.text_area(
            "申込補足", value=defaults.get("registration_note") or ""
        )
        notes = st.text_area("備考", value=defaults.get("notes") or "")

        label = "変更する" if event_id else "登録する"
        submitted = st.form_submit_button(label, type="primary", use_container_width=True)

    if submitted:
        if not name or not event_type or not event_date_val:
            st.error("イベント名・種別・開催日は必須です。")
            return
        data = {
            "name": name,
            "event_type": event_type,
            "organizer_name": organizer_name or None,
            "venue": venue or None,
            "event_date": event_date_val.isoformat(),
            "event_end_date": event_end_date_val.isoformat() if event_end_date_val else None,
            "registration_opens_on": opens_on_val.isoformat() if opens_on_val else None,
            "registration_deadline": deadline_val.isoformat() if deadline_val else None,
            "registration_open": registration_open,
            "registration_url": registration_url or None,
            "registration_note": registration_note or None,
            "notes": notes or None,
        }
        if event_id:
            update_event(event_id, data)
            st.session_state["flash_admin_event"] = f"「{name}」を更新しました。"
            st.session_state.pop("selected_event", None)
        else:
            insert_event(data)
            st.session_state["flash_admin_event"] = f"「{name}」を登録しました。"
            st.session_state.pop("event_ai_result", None)
            st.session_state["ai_reader_v"] = st.session_state.get("ai_reader_v", 0) + 1
        st.session_state["event_form_v"] = form_v + 1
        st.rerun()

    if event_id and st.button("キャンセル", key=f"event_cancel_{event_id}"):
        st.session_state.pop("selected_event", None)
        st.rerun()


def show_ai_reader() -> None:
    """AIによるイベント読み取りUIを表示する。

    結果はセッションに保持し、下の新規登録フォームへ事前入力する
    （AIの読み取り結果はここでは保存しない）。
    """
    st.markdown("##### AIによる読み取り登録")
    st.caption(
        "告知テキストやスクリーンショットをAIに読み取らせ、下の新規登録フォームに"
        "事前入力します。内容を確認・修正してから保存してください。"
    )
    ai_v: int = st.session_state.get("ai_reader_v", 0)
    text = st.text_area("テキストを貼り付ける", key=f"ai_event_text_{ai_v}", height=100)
    image = st.file_uploader(
        "スクリーンショットをアップロードする",
        type=["png", "jpg", "jpeg"],
        key=f"ai_event_image_{ai_v}",
    )

    if st.button("AIで読み取る", key="ai_event_parse_btn"):
        image_bytes = image.getvalue() if image else None
        mime_type = image.type if image else None
        if not text and not image_bytes:
            st.warning("テキストまたは画像を入力してください。")
        else:
            try:
                with st.spinner("AIが読み取り中..."):
                    result = parse_event_with_ai(text or None, image_bytes, mime_type)
                if result:
                    st.session_state["event_ai_result"] = result
                    st.session_state["event_form_v"] = st.session_state.get("event_form_v", 0) + 1
                    st.success("読み取り結果を下のフォームに反映しました。内容を確認してください。")
                    st.rerun()
                else:
                    st.warning("読み取れる内容がありませんでした。")
            except Exception as e:
                st.error(f"AIでの読み取りに失敗しました: {e}")


def show_events_management() -> None:
    """開催情報一覧の管理UI（一覧・編集・削除・新規登録・AI読み取り）を表示する。"""
    st.markdown("#### 開催情報管理")

    if "flash_admin_event" in st.session_state:
        st.success(st.session_state.pop("flash_admin_event"))

    show_events_list()

    selected_event = st.session_state.get("selected_event")
    if selected_event:
        st.markdown(f"##### 「{selected_event['name']}」を編集")
        show_event_form(selected_event, selected_event["id"])
    else:
        st.divider()
        show_ai_reader()
        st.markdown("##### 新規登録")
        show_event_form(st.session_state.get("event_ai_result") or {}, None)
