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
