import streamlit as st

from supabase_client import get_supabase

CLASSES: list[str] = ["S", "M", "IM", "L"]
EVENTS: list[str] = ["ビギナー", "JP1.5", "JP2.5", "AG1", "AG2", "AG3"]
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


def show_dog_list(dogs: list[dict]) -> None:
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
                events_str = "、".join(dog.get("events") or [])
                st.caption(f"クラス: {dog['dog_class']}　／　種目: {events_str}")
            with col_btn:
                if not is_selected and st.button("選択", key=f"sel_{dog['id']}"):
                    st.session_state["selected_dog"] = dog
                    st.session_state.pop("edit_form_v", None)
                    st.rerun()


def show_edit_form(dog: dict) -> None:
    """選択された犬の編集・削除フォームを表示する。"""
    st.subheader(f"「{dog['dog_name']}」を編集")
    form_v: int = st.session_state.get("edit_form_v", 0)
    with st.form(f"edit_dog_form_{form_v}"):
        dog_name = st.text_input("犬名 *", value=dog["dog_name"])
        breed = st.text_input("犬種 *", value=dog["breed"])
        class_idx = CLASSES.index(dog["dog_class"]) if dog["dog_class"] in CLASSES else 0
        dog_class = st.radio("クラス *", CLASSES, index=class_idx, horizontal=True)
        st.markdown("**参加種目 *** （1つ以上選択）")
        col1, col2 = st.columns(2)
        checked: dict[str, bool] = {}
        current_events = dog.get("events") or []
        for i, event in enumerate(EVENTS):
            with col1 if i % 2 == 0 else col2:
                checked[event] = st.checkbox(event, value=event in current_events)
        col_upd, col_del = st.columns(2)
        with col_upd:
            update_btn = st.form_submit_button(
                "変更する", type="primary", use_container_width=True
            )
        with col_del:
            delete_btn = st.form_submit_button("削除する", use_container_width=True)

    if update_btn:
        selected_events = [e for e, v in checked.items() if v]
        if not dog_name or not breed or not selected_events:
            st.error("犬名・犬種・参加種目は必須です。")
            return
        get_supabase().table("dogs").update(
            {
                "dog_name": dog_name,
                "breed": breed,
                "dog_class": dog_class,
                "events": selected_events,
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
    """犬情報登録フォームを表示する。"""
    st.subheader("犬を追加登録する")
    if current_count >= MAX_DOGS:
        st.warning(f"登録できる犬は最大 {MAX_DOGS} 頭までです。")
        return

    form_v: int = st.session_state.get("dog_form_v", 0)
    with st.form(f"add_dog_form_{form_v}"):
        dog_name = st.text_input("犬名 *")
        breed = st.text_input("犬種 *")
        dog_class = st.radio("クラス *", CLASSES, horizontal=True)
        st.markdown("**参加種目 *** （1つ以上選択）")
        col1, col2 = st.columns(2)
        checked: dict[str, bool] = {}
        for i, event in enumerate(EVENTS):
            with col1 if i % 2 == 0 else col2:
                checked[event] = st.checkbox(event)
        submitted = st.form_submit_button(
            "登録する", type="primary", use_container_width=True
        )

    if submitted:
        selected_events = [e for e, v in checked.items() if v]
        if not dog_name or not breed or not selected_events:
            st.error("犬名・犬種・参加種目は必須です。")
            return
        get_supabase().table("dogs").insert(
            {
                "user_id": user_id,
                "dog_name": dog_name,
                "breed": breed,
                "dog_class": dog_class,
                "events": selected_events,
            }
        ).execute()
        st.session_state["dog_form_v"] = form_v + 1
        st.session_state["flash"] = f"「{dog_name}」を登録しました。"
        st.rerun()


def main() -> None:
    """犬情報ページのメインエントリーポイント。"""
    st.set_page_config(
        page_title="犬情報 | アジリティー競技会",
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

    st.title("犬情報の登録・確認")

    dogs = get_dogs(user_id)
    st.caption(f"登録済み: {len(dogs)} 頭 / 最大 {MAX_DOGS} 頭")

    show_dog_list(dogs)

    selected_dog = st.session_state.get("selected_dog")
    if selected_dog:
        st.divider()
        show_edit_form(selected_dog)

    st.divider()
    show_add_form(user_id, len(dogs))

    st.divider()
    if st.button("ホームに戻る", use_container_width=True):
        st.switch_page("app_entry.py")


if __name__ == "__main__":
    main()
