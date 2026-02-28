from supabase import create_client, Client
import streamlit as st

url: str = st.secrets["supabase"]["url"]
key: str = st.secrets["supabase"]["key"]

supabase: Client = create_client(url, key)
