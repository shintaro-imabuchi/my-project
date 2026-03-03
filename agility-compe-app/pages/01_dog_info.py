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
    """登録犬一覧を表示する。"""
    if not dogs:
        st.info("まだ犬が登録されていません。")
        return
    for dog in dogs:
        with st.container(border=True):
            st.markdown(f"**{dog['dog_name']}**　{dog['breed']}")
            events_str = "、".join(dog.get("events") or [])
            st.caption(f"クラス: {dog['dog_class']}　／　種目: {events_str}")


def show_add_form(user_id: str, current_count: int) -> None:
    """犬情報登録フォームを表示する。"""
    st.subheader("犬を追加登録する")
    if current_count >= MAX_DOGS:
        st.warning(f"登録できる犬は最大 {MAX_DOGS} 頭までです。")
        return

    with st.form("add_dog_form"):
        dog_name = st.text_input("犬名 *")
        breed = st.text_input("犬種 *")
        dog_class = st.selectbox("クラス *", CLASSES)
        events = st.multiselect("参加種目 *", EVENTS)
        submitted = st.form_submit_button(
            "登録する", type="primary", use_container_width=True
        )

    if submitted:
        if not dog_name or not breed or not events:
            st.error("犬名・犬種・参加種目は必須です。")
            return
        get_supabase().table("dogs").insert(
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

    st.divider()
    show_add_form(user_id, len(dogs))

    st.divider()
    if st.button("ホームに戻る", use_container_width=True):
        st.switch_page("app_entry.py")


if __name__ == "__main__":
    main()
