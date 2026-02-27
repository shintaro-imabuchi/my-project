import streamlit as st
import pandas as pd

# ── 初回だけDataFrameをsession_stateに保存 ──
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame({
        "犬名": ["フェリーチェ", "カーロ", "ディーノ"],
        "タイム": [0.0, 0.0, 0.0],
        "失敗": [0, 0, 0],
        "拒絶": [0, 0, 0],
        "減点": [0, 0, 0]
    })

# ── data_editorは1回だけ呼び出す ──
#    常にsession_stateの最新データを表示
edited_df = st.data_editor(
    st.session_state.df,
    num_rows="fixed",
    hide_index=True,
    column_config={
        "タイム": st.column_config.NumberColumn(
            "タイム",
            format="%.2f",
            step=0.01,
        ),
        # 必要に応じて他の列も設定
        "失敗": st.column_config.NumberColumn(step=1),
        "拒絶": st.column_config.NumberColumn(step=1),
        "減点": st.column_config.NumberColumn(disabled=True, format="%d"),
    },
    key="dog_editor"   # ユニークなkeyを付ける（重要）
)

if st.button("計算"):
    st.session_state.df.update(edited_df)  # ← ここが鍵！ 同じオブジェクトを更新
    st.session_state.df["減点"] = (
        st.session_state.df["失敗"] * 5 + 
        st.session_state.df["拒絶"] * 5
    )
    st.rerun()

# ── 保存ボタンも最新値を使う ──
if st.button("保存"):
    st.session_state.df.to_pickle("edited.pkl")
    st.success("保存しました！")

# デバッグ用（必要に応じて）
# st.write("現在のデータ（計算後）:", st.session_state.df)