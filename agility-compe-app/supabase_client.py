from supabase import create_client, Client
import streamlit as st


def get_supabase() -> Client:
    """ユーザーセッションごとのSupabaseクライアントを返す。

    st.session_state に格納することで、ユーザー間でクライアントが
    共有されるのを防ぐ。
    """
    if "supabase_client" not in st.session_state:
        url: str = st.secrets["supabase"]["url"]
        key: str = st.secrets["supabase"]["key"]
        st.session_state["supabase_client"] = create_client(url, key)
    return st.session_state["supabase_client"]


def get_competition_id() -> int:
    """このデプロイが扱うcompetitions.idを返す。"""
    return st.secrets["competition"]["id"]


def sign_in_as_owner() -> None:
    """クラブ専用のSupabase Authオーナーアカウントでサインインする。

    管理者・スタッフの共有パスワード確認が通った直後に呼ぶ。
    competitions・entries等のRLSはowner_user_id = auth.uid()を軸にしているため、
    anonのままでは書き込みが弾かれる。二重サインインを避けるため、
    st.session_stateにサインイン済みフラグを持たせる。
    """
    if st.session_state.get("owner_signed_in"):
        return
    get_supabase().auth.sign_in_with_password(
        {
            "email": st.secrets["admin"]["owner_email"],
            "password": st.secrets["admin"]["owner_password"],
        }
    )
    st.session_state["owner_signed_in"] = True
