import streamlit as st

from supabase_client import get_supabase, get_competition_id
from utils.settings import get_event_fees

CLASSES: list[str] = ["S", "M", "IM", "L"]
MAX_DOGS: int = 4


def get_dogs(user_id: str) -> list[dict]:
    """ユーザーの登録犬一覧をSupabaseから取得する。"""
    response = (
        get_supabase()
        .table("dogs")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return response.data


def get_entries_map(competition_id: int, dog_ids: list[str]) -> dict[str, list[str]]:
    """犬IDをキーに、この大会でのエントリー種目一覧を返す。"""
    if not dog_ids:
        return {}
    response = (
        get_supabase()
        .table("entries")
        .select("dog_id, events")
        .eq("competition_id", competition_id)
        .in_("dog_id", dog_ids)
        .execute()
    )
    return {row["dog_id"]: row["events"] for row in response.data}


def upsert_entry(competition_id: int, dog_id: str, events: list[str]) -> None:
    """犬の参加種目をentriesテーブルにupsertする。"""
    get_supabase().table("entries").upsert(
        {"competition_id": competition_id, "dog_id": dog_id, "events": events},
        on_conflict="competition_id,dog_id",
    ).execute()


def delete_entry(competition_id: int, dog_id: str) -> None:
    """犬のこの大会への参加登録をentriesテーブルから削除する。"""
    get_supabase().table("entries").delete().eq(
        "competition_id", competition_id
    ).eq("dog_id", dog_id).execute()


def show_dog_list(dogs: list[dict], entries_map: dict[str, list[str]]) -> None:
    """登録犬一覧をカード形式で表示する。選択ボタンで編集対象を切り替える。"""
    if not dogs:
        st.info("まだ犬が登録されていません。")
        return
    selected_id = (st.session_state.get("selected_dog") or {}).get("id")
    for dog in dogs:
        is_selected = dog["id"] == selected_id
        with st.container(border=True):
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                prefix = "✏️ " if is_selected else ""
                st.markdown(f"{prefix}**{dog['dog_name']}**　{dog['breed']}")
                events_str = "、".join(entries_map.get(dog["id"]) or [])
                st.caption(f"クラス: {dog['dog_class']}　／　参加種目: {events_str or '未選択'}")
            with col_btn:
                if not is_selected and st.button("選択", key=f"sel_{dog['id']}"):
                    st.session_state["selected_dog"] = dog
                    st.session_state.pop("edit_form_v", None)
                    st.rerun()


def show_edit_form(dog: dict) -> None:
    """選択された犬のプロフィール編集・削除フォームを表示する。"""
    st.subheader(f"「{dog['dog_name']}」を編集")
    form_v: int = st.session_state.get("edit_form_v", 0)
    with st.form(f"edit_dog_form_{form_v}"):
        dog_name = st.text_input("犬名 *", value=dog["dog_name"])
        breed = st.text_input("犬種 *", value=dog["breed"])
        class_idx = CLASSES.index(dog["dog_class"]) if dog["dog_class"] in CLASSES else 0
        dog_class = st.radio("クラス *", CLASSES, index=class_idx, horizontal=True)
        col_upd, col_del = st.columns(2)
        with col_upd:
            update_btn = st.form_submit_button(
                "変更する", type="primary", use_container_width=True
            )
        with col_del:
            delete_btn = st.form_submit_button("削除する", use_container_width=True)

    if update_btn:
        if not dog_name or not breed:
            st.error("犬名・犬種は必須です。")
            return
        get_supabase().table("dogs").update(
            {
                "dog_name": dog_name,
                "breed": breed,
                "dog_class": dog_class,
            }
        ).eq("id", dog["id"]).execute()
        st.session_state["flash"] = f"「{dog_name}」の情報を更新しました。"
        st.session_state.pop("selected_dog", None)
        st.session_state["edit_form_v"] = form_v + 1
        st.rerun()

    if delete_btn:
        get_supabase().table("dogs").delete().eq("id", dog["id"]).execute()
        st.session_state["flash"] = f"「{dog['dog_name']}」を削除しました。"
        st.session_state.pop("selected_dog", None)
        st.session_state["edit_form_v"] = form_v + 1
        st.rerun()

    if st.button("キャンセル", use_container_width=True):
        st.session_state.pop("selected_dog", None)
        st.rerun()


def show_add_form(user_id: str, current_count: int) -> None:
    """犬プロフィール登録フォームを表示する。参加種目は別セクションで選択する。"""
    st.subheader("犬を追加登録する")
    if current_count >= MAX_DOGS:
        st.warning(f"登録できる犬は最大 {MAX_DOGS} 頭までです。")
        return

    form_v: int = st.session_state.get("dog_form_v", 0)
    with st.form(f"add_dog_form_{form_v}"):
        dog_name = st.text_input("犬名 *")
        breed = st.text_input("犬種 *")
        dog_class = st.radio("クラス *", CLASSES, horizontal=True)
        submitted = st.form_submit_button(
            "登録する", type="primary", use_container_width=True
        )

    if submitted:
        if not dog_name or not breed:
            st.error("犬名・犬種は必須です。")
            return
        get_supabase().table("dogs").insert(
            {
                "user_id": user_id,
                "dog_name": dog_name,
                "breed": breed,
                "dog_class": dog_class,
            }
        ).execute()
        st.session_state["dog_form_v"] = form_v + 1
        st.session_state["flash"] = (
            f"「{dog_name}」を登録しました。続けて参加種目を選択してください。"
        )
        st.rerun()


def show_event_entry_form(competition_id: int, dog: dict, current_events: list[str]) -> None:
    """1頭分の参加種目選択フォームを表示する。"""
    form_v: int = st.session_state.get("entry_form_v", 0)
    with st.form(f"entry_form_{dog['id']}_{form_v}"):
        st.markdown(f"**{dog['dog_name']}**　（クラス: {dog['dog_class']}）")
        checked: dict[str, bool] = {}
        for event in get_event_fees():
            checked[event] = st.checkbox(
                event,
                value=event in current_events,
                key=f"entry_{dog['id']}_{event}_{form_v}",
            )
        submitted = st.form_submit_button("この犬の参加種目を保存", use_container_width=True)

    if submitted:
        selected_events = [e for e, v in checked.items() if v]
        if not selected_events:
            delete_entry(competition_id, dog["id"])
            st.session_state["flash"] = f"「{dog['dog_name']}」の参加登録を取り消しました。"
        else:
            upsert_entry(competition_id, dog["id"], selected_events)
            st.session_state["flash"] = f"「{dog['dog_name']}」の参加種目を保存しました。"
        st.session_state["entry_form_v"] = form_v + 1
        st.rerun()


def show_event_entry_section(
    competition_id: int, dog: dict, current_events: list[str]
) -> None:
    """選択中の犬1頭ぶんの参加種目選択セクションを表示する。"""
    st.subheader("参加種目の選択")
    with st.container(border=True):
        show_event_entry_form(competition_id, dog, current_events)


def main() -> None:
    """犬情報ページのメインエントリーポイント。"""
    st.set_page_config(
        page_title="犬情報 | アジリティー練習会",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    if not st.session_state.get("user"):
        st.warning("ログインが必要です。")
        st.switch_page("app_entry.py")
        return

    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

    user = st.session_state["user"]
    user_id: str = user.id
    competition_id = get_competition_id()

    st.subheader("犬情報")
    st.caption("参加種目の登録・変更、削除は選択ボタンで")

    dogs = get_dogs(user_id)
    st.caption(f"登録済み: {len(dogs)} 頭 / 最大 {MAX_DOGS} 頭")

    entries_map = get_entries_map(competition_id, [d["id"] for d in dogs])

    show_dog_list(dogs, entries_map)

    selected_dog = st.session_state.get("selected_dog")
    if selected_dog:
        st.divider()
        show_edit_form(selected_dog)
        st.divider()
        show_event_entry_section(
            competition_id, selected_dog, entries_map.get(selected_dog["id"]) or []
        )

    if not selected_dog:
        st.divider()
        show_add_form(user_id, len(dogs))

    st.divider()
    if st.button("ホームに戻る", use_container_width=True):
        st.session_state.pop("selected_dog", None)
        st.switch_page("app_entry.py")


if __name__ == "__main__":
    main()
