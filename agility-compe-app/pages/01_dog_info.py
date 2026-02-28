import streamlit as st

from supabase_client import supabase

CLASSES: list[str] = ["S", "M", "IM", "L"]
EVENTS: list[str] = ["ビギナー", "JP1.5", "JP2.5", "AG1", "AG2", "AG3"]
MAX_DOGS: int = 4


def get_dogs(user_id: str) -> list[dict]:
    """ユーザーの登録犬一覧をSupabaseから取得する。"""
    response = (
        supabase.table("dogs")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return response.data


def show_add_dog_form(user_id: str, current_count: int) -> None:
    """新規犬情報登録フォームを表示する。"""
    st.subheader("新規登録")

    if current_count >= MAX_DOGS:
        st.warning(f"登録できる犬は最大 {MAX_DOGS} 頭までです。")
        return

    with st.form("add_dog_form", clear_on_submit=True):
        dog_name = st.text_input("犬名")
        breed = st.text_input("犬種")
        dog_class = st.selectbox("クラス", CLASSES)
        events = st.multiselect("参加種目", EVENTS)
        submitted = st.form_submit_button("登録する", type="primary")

    if submitted:
        if not dog_name or not breed or not events:
            st.error("犬名・犬種・参加種目は必須です。")
            return
        supabase.table("dogs").insert(
            {
                "user_id": user_id,
                "dog_name": dog_name,
                "breed": breed,
                "dog_class": dog_class,
                "events": events,
            }
        ).execute()
        st.session_state["flash"] = f"「{dog_name}」を登録しました。"
        st.rerun()


def show_edit_dog_section(dogs: list[dict]) -> None:
    """登録済み犬の変更・削除セクションを表示する。"""
    st.subheader("登録済み犬の変更・削除")

    dog_names = [d["dog_name"] for d in dogs]
    selected_name = st.selectbox("変更・削除する犬を選択", dog_names, key="edit_select")
    selected_dog = next(d for d in dogs if d["dog_name"] == selected_name)

    current_class = selected_dog.get("dog_class", CLASSES[0])
    class_index = CLASSES.index(current_class) if current_class in CLASSES else 0
    current_events: list[str] = selected_dog.get("events") or []

    with st.form("edit_dog_form"):
        breed = st.text_input("犬種", value=selected_dog.get("breed", ""))
        dog_class = st.selectbox("クラス", CLASSES, index=class_index)
        events = st.multiselect("参加種目", EVENTS, default=current_events)
        confirm_delete = st.checkbox("この犬情報を削除する（チェックして削除実行）")

        col1, col2 = st.columns(2)
        with col1:
            update_btn = st.form_submit_button("変更を保存", type="primary")
        with col2:
            delete_btn = st.form_submit_button("削除実行")

    if update_btn:
        if not events:
            st.error("参加種目を1つ以上選択してください。")
            return
        supabase.table("dogs").update(
            {"breed": breed, "dog_class": dog_class, "events": events}
        ).eq("id", selected_dog["id"]).execute()
        st.session_state["flash"] = f"「{selected_name}」の情報を更新しました。"
        st.rerun()

    if delete_btn:
        if not confirm_delete:
            st.error("削除する場合はチェックボックスを確認してください。")
            return
        supabase.table("dogs").delete().eq("id", selected_dog["id"]).execute()
        st.session_state["flash"] = f"「{selected_name}」を削除しました。"
        st.rerun()


def main() -> None:
    """犬情報登録・変更ページのメインエントリーポイント。"""
    st.title("犬情報の登録・変更")

    # 未認証ならログインページへ
    if not st.session_state.get("user"):
        st.warning("ログインが必要です。トップページからログインしてください。")
        st.switch_page("app.py")
        return

    # フラッシュメッセージ表示
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

    user = st.session_state["user"]
    user_id: str = user.id
    name: str = user.user_metadata.get("name", "")

    st.caption(f"ログイン中: {name}")

    dogs = get_dogs(user_id)
    st.info(f"登録済み: {len(dogs)} 頭 / 最大 {MAX_DOGS} 頭")

    if dogs:
        show_edit_dog_section(dogs)
        st.divider()

    show_add_dog_form(user_id, len(dogs))

    st.divider()
    if st.button("ログアウト"):
        supabase.auth.sign_out()
        del st.session_state["user"]
        st.switch_page("app.py")


if __name__ == "__main__":
    main()
