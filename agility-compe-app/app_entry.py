import streamlit as st
from supabase_auth.errors import AuthApiError

from supabase_client import get_supabase
from utils.settings import get_registration_open


def show_top() -> None:
    """トップ画面（ログイン/新規登録ボタン）を表示する。"""
    st.subheader("アジリティー練習会")
    st.subheader("参加登録システム")

    if st.button("ログイン", type="primary", use_container_width=True):
        st.session_state["mode"] = "login"
        st.rerun()

    if get_registration_open():
        if st.button("新規登録", use_container_width=True):
            st.session_state["mode"] = "register"
            st.rerun()
    else:
        st.warning("新規登録を締め切りました")
        st.button("新規登録", use_container_width=True, disabled=True)

    st.link_button(
        "練習会要綱を見る",
        url="https://drive.google.com/file/d/1dVK-AFDItP7RHFZ7QnN3nkHVNIkK-6iD/view?usp=drive_link",
        use_container_width=True,
    )


def show_login_form() -> None:
    """ログインフォームを表示する。"""
    st.subheader("ログイン")

    email = st.text_input("メールアドレス", key="login_email")
    password = st.text_input("パスワード", type="password", key="login_password")

    if st.button("ログイン", type="primary", use_container_width=True):
        if not email or not password:
            st.error("メールアドレスとパスワードを入力してください。")
            return
        try:
            response = get_supabase().auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            st.session_state["user"] = response.user
            st.session_state["mode"] = None
            st.rerun()
        except AuthApiError as e:
            st.error(f"ログインに失敗しました。メールアドレスまたはパスワードが間違っています。: {e.message}")

    st.divider()
    if st.button("戻る", use_container_width=True):
        st.session_state["mode"] = None
        st.rerun()


def show_register_form() -> None:
    """新規登録フォームを表示する。"""
    st.subheader("新規登録")

    name = st.text_input("氏名", key="register_name")
    email = st.text_input("メールアドレス", key="register_email")
    password = st.text_input(
        "パスワード（6文字以上）", type="password", key="register_password"
    )

    if st.button("登録する", type="primary", use_container_width=True):
        if not name or not email or not password:
            st.error("すべての項目を入力してください。")
            return
        if len(password) < 6:
            st.error("パスワードは6文字以上で入力してください。")
            return
        try:
            response = get_supabase().auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {"data": {"name": name}},
                }
            )
            if response.session:
                st.session_state["user"] = response.user
                st.session_state["mode"] = None
                st.rerun()
            else:
                st.success(
                    "確認メールを送信しました。"
                    "メール内のリンクをクリックしてからログインしてください。"
                )
        except AuthApiError as e:
            msg = e.message.lower()
            if "already registered" in msg or "already been registered" in msg:
                st.error(
                    "このメールアドレスはすでに登録されています。"
                    "別のメールアドレスで登録してください。"
                )
            else:
                st.error(f"登録に失敗しました: {e.message}")

    st.divider()
    if st.button("戻る", use_container_width=True):
        st.session_state["mode"] = None
        st.rerun()


def show_home() -> None:
    """認証済みユーザーのホーム画面を表示する。"""
    user = st.session_state["user"]
    name: str = user.user_metadata.get("name", "")

    st.subheader("アジリティー練習会")
    st.subheader("参加登録システム")
    st.success(f"ようこそ、{name} さん！")

    if st.button("犬情報の登録・変更・削除", type="primary", use_container_width=True):
        st.switch_page("pages/01_dog_info.py")

    if st.button("申し込み状況を見る", use_container_width=True):
        st.switch_page("pages/02_registration_status.py")

    st.link_button(
        "練習会実施のご案内を見る",
        url="https://drive.google.com/file/d/1dVK-AFDItP7RHFZ7QnN3nkHVNIkK-6iD/view?usp=drive_link",
        use_container_width=True,
    )

    st.info(
        "参加をキャンセルされる場合は、次のメールアドレスまでキャンセルの連絡をお願いします。\n\n"
        "compe@puffin.tokyo.jp"
    )

    st.divider()
    if st.button("ログアウト", use_container_width=True):
        get_supabase().auth.sign_out()
        del st.session_state["user"]
        st.rerun()


def main() -> None:
    """参加登録アプリのメインエントリーポイント。"""
    st.set_page_config(
        page_title="参加登録 | アジリティー練習会",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    if st.session_state.get("user"):
        show_home()
    elif st.session_state.get("mode") == "login":
        show_login_form()
    elif st.session_state.get("mode") == "register":
        if get_registration_open():
            show_register_form()
        else:
            st.session_state["mode"] = None
            st.rerun()
    else:
        show_top()


if __name__ == "__main__":
    main()
