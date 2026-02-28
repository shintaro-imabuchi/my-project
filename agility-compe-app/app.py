import streamlit as st
from gotrue.errors import AuthApiError

from supabase_client import supabase


def show_login_form() -> None:
    """ログインフォームを表示する。"""
    st.subheader("ログイン")
    email = st.text_input("メールアドレス", key="login_email")
    password = st.text_input("パスワード", type="password", key="login_password")

    if st.button("ログイン", type="primary"):
        if not email or not password:
            st.error("メールアドレスとパスワードを入力してください。")
            return
        try:
            response = supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            st.session_state["user"] = response.user
            st.rerun()
        except AuthApiError as e:
            st.error(f"ログインに失敗しました: {e.message}")


def show_register_form() -> None:
    """新規登録フォームを表示する。"""
    st.subheader("新規登録")
    name = st.text_input("氏名", key="register_name")
    email = st.text_input("メールアドレス", key="register_email")
    password = st.text_input(
        "パスワード（6文字以上）", type="password", key="register_password"
    )

    if st.button("新規登録", type="primary"):
        if not name or not email or not password:
            st.error("すべての項目を入力してください。")
            return
        if len(password) < 6:
            st.error("パスワードは6文字以上で入力してください。")
            return
        try:
            response = supabase.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {"data": {"name": name}},
                }
            )
            st.session_state["user"] = response.user
            st.rerun()
        except AuthApiError as e:
            msg = e.message.lower()
            if "already registered" in msg or "already been registered" in msg:
                st.error(
                    "このメールアドレスはすでに登録されています。"
                    "別のメールアドレスで登録してください。"
                )
            else:
                st.error(f"登録に失敗しました: {e.message}")


def main() -> None:
    """アプリのメインエントリーポイント。"""
    st.title("アジリティー競技会 参加登録システム")

    # 認証済みの場合は犬情報登録ページへ
    if st.session_state.get("user"):
        user = st.session_state["user"]
        name = user.user_metadata.get("name", "")
        st.success(f"ようこそ、{name} さん！")
        st.switch_page("pages/01_dog_info.py")
        return

    tab_login, tab_register = st.tabs(["ログイン", "新規登録"])

    with tab_login:
        show_login_form()

    with tab_register:
        show_register_form()


if __name__ == "__main__":
    main()
