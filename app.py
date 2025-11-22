import streamlit as st
from openai import OpenAI

# ==========================================
# 1. 設定部分
# ==========================================

# ページの設定（タイトルやアイコン）
st.set_page_config(page_title="サンタさんとおしゃべり", page_icon="🎅")

# タイトルの表示
st.title("🎅 サンタさんとおはなししよう！")
st.caption("いいこにしてたかな？サンタさんにおしえてね。")

# secrets.toml にキーがあればそれを使い、なければサイドバーを表示
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    api_key = st.sidebar.text_input("OpenAI API Key", type="password")

# サンタさんの性格設定（システムプロンプト）
# ここを変えると「鬼」にもなります！
SYSTEM_PROMPT = """
あなたは子供が大好きな優しいサンタクロースです。
以下のルールを守って会話してください。
1. 相手は2〜5歳の小さい子供です。優しく、分かりやすい言葉で話してください。
2. 「〜じゃよ」「〜だよ」のような、親しみやすいサンタ口調を使ってください。
3. 漢字は使わず、ひらがなで話してください。
4. 子供が良い行いをしたら褒め、悪い行いをしたら優しく諭してください。
"""

# ==========================================
# 2. チャットのロジック部分
# ==========================================

if not api_key:
    st.warning("設定ファイル(.streamlit/secrets.toml)が見つからないか、サイドバーにキーが入っていません。")
    st.stop()

client = OpenAI(api_key=api_key)

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

for msg in st.session_state.messages:
    if msg["role"] != "system":
        icon = "🎅" if msg["role"] == "assistant" else "🧒"
        with st.chat_message(msg["role"], avatar=icon):
            st.markdown(msg["content"])

# ==========================================
# 3. ユーザーの入力と応答
# ==========================================

# ユーザーが何か入力したら実行される
if user_input := st.chat_input("ここになにかかいてね..."):
    
    with st.chat_message("user", avatar="🧒"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.messages
        )
        santa_reply = response.choices[0].message.content

        with st.chat_message("assistant", avatar="🎅"):
            st.markdown(santa_reply)
        st.session_state.messages.append({"role": "assistant", "content": santa_reply})
        
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")