import streamlit as st

from utils.settings import get_registration_open, set_registration_open


def check_admin_password() -> bool:
    """管理者パスワードを確認する。

    認証済みの場合はTrueを返す。未認証の場合はログインフォームを表示してFalseを返す。
    """
    if st.session_state.get("admin_authenticated"):
        return True

    st.subheader("管理者ログイン")
    password = st.text_input("パスワード", type="password", key="admin_password_input")

    if st.button("ログイン", type="primary", use_container_width=True):
        if password == st.secrets["admin"]["password"]:
            st.session_state["admin_authenticated"] = True
            st.rerun()
        else:
            st.error("パスワードが間違っています。")

    return False


def show_admin_home() -> None:
    """管理者ホーム画面を表示する。"""
    st.subheader("管理者メニュー")

    st.markdown("#### 新規登録受付設定")
    registration_open = get_registration_open()
    new_value = st.toggle("新規登録を受け付ける", value=registration_open)

    if new_value != registration_open:
        set_registration_open(new_value)
        status = "受付中" if new_value else "締め切り"
        st.success(f"新規登録を「{status}」に変更しました。")
        st.rerun()

    st.divider()
    if st.button("ログアウト", use_container_width=True):
        del st.session_state["admin_authenticated"]
        st.rerun()


def main() -> None:
    """管理者アプリのメインエントリーポイント。"""
    st.set_page_config(
        page_title="管理者 | アジリティー練習会",
        layout="wide",
    )

    if not check_admin_password():
        return

    show_admin_home()


if __name__ == "__main__":
    main()
