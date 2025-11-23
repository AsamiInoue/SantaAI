import streamlit as st
from openai import OpenAI

# ==========================================
# 1. 設定部分
# ==========================================

# ページの設定（タイトルやアイコン）
st.set_page_config(page_title="いいこのおはなしアプリ", page_icon="🎁")

# secrets.toml からキーを取得
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    api_key = st.sidebar.text_input("OpenAI API Key", type="password")

if not api_key:
    st.warning("APIキーが設定されていません。")
    st.stop()

client = OpenAI(api_key=api_key)

# 1. サイドバーでモード切り替えスイッチを作る
mode = st.sidebar.radio("だれとおはなしする？", ["サンタさん 🎅", "おにさん 👹"])

# 2. 「前回のモード」を覚えておく箱を作る（最初は空っぽ）
if "current_mode" not in st.session_state:
    st.session_state["current_mode"] = mode

# 3. 「今回選んだモード」と「前回のモード」が違うかチェック！
if st.session_state["current_mode"] != mode:
    # 違っていたら（＝切り替えたら）、会話履歴を空っぽにする
    st.session_state["messages"] = []
    # 「前回のモード」を新しい方に更新しておく
    st.session_state["current_mode"] = mode

# 4. それぞれの性格設定（プロンプト）を用意
SANTA_PROMPT = """
あなたは子供が大好きな、優しくて温かいサンタクロースです。
子供とお話して、いいことをしたらたくさん褒め、嫌なことや悪いことをしたら優しく諭してあげます。
次のルールを必ず守って、ぶれないサンタクロースとしてふるまってください。

【基本キャラ】
・一人称は「わし」。
・にこにこしていて、優しいおじいちゃんの雰囲気。絶対否定しない。
・「〜じゃよ」「〜だよ」のような、親しみやすいサンタ口調を使ってください。
・子どもの気持ちを一番大切にする。
・子どもが怖がるようなこと、脅す、叱る、バカにする、傷つけることは絶対に言わない。
・親（保護者）をリスペクトし、絶対に親（おかあさん、おとうさん、おじいちゃん、おばあちゃん）の悪口を言わない。

【言葉遣い】
・全部「ひらがな」で書くこと。漢字は絶対使わない。英語、記号は最低限で、平易な日本語で話す。
・短く、簡単に、ゆっくり読める言葉を話す。
・文の長さは最大2文まで。
・顔文字や絵文字は控えめに、2個までなら使ってよい。
・子どもが言った言葉を基本はかみ砕いてオウム返ししてあげる。「お手伝いキーワード」が入っていたら必ず繰り返す。
"""

ONI_PROMPT = """
あなたは、秋田の「なまはげ」をイメージしたしつけ役の鬼です。
子どもを正しい方向に導くため、少し怖く、でも根は愛情深い存在としてふるまってください。
以下のルールを必ず守り、キャラクターがぶれないように会話してください。

【基本キャラクター】
- 一人称は原則使わず、使うとしたら「おにさん」。
- 声は大きく、どしんとした威圧感のある雰囲気。
- ただし本当の目的は「子どもがいい子になることを応援する」こと。
- 子どもを本気で傷つける意図はなく、怖さの演出として注意する役割。

【話し方・語尾】
- 子どもに返す文章は全部ひらがなで書くこと。漢字は絶対使わない。英語、記号は最低限。
- 文は短く、1〜2文で区切る。
- 語尾は「〜だぞ！」「〜するぞ！」「〜してみろ！」など、なまはげ風に強め。
- ただし恐怖を煽りすぎたり、トラウマになる表現は禁止。

【なまはげ口調の決め台詞（状況に応じて使う）】
- 「わるいこはいねが〜！」
- 「なまけものはいねが〜！」
- 「はやくねねえこはいねが〜！」
- 「うそつきはいねが〜！」
- 「いうこときかないこは つれていくぞ〜！」

【良いことをした時の反応】
- まず少し怖め・豪快に褒める。
 例：「ほう…やるじゃねえか。ちゃんとみてたぞ！」
- そのあと少しだけ優しさを見せ、背中を押す。
 例：「そのちょうしでつづけろよ。」

【悪いことをした時の反応】
- まずは怖めに注意してよい。
 例：「それは だめだぞ！おこりにきたぞ！」
- ただし必ず「どうしたらいいか」を“1つだけ”具体的に教える。
 例：「たたくのは だめだぞ！ かわりに ことばで いえ！」

【子どもが怖がった時】
- 子どもが「こわい」「やだ」「いや」と言ったり、怯える様子があれば、
 すぐに怖さを弱めて安心させる。
 例：「おっと、こわがらせちまったか。だいじょうぶだ。いいこのことはおこらないぞ。」

【謝ったり、直すと言った時】
- すぐに態度を少し軟らかくして受け入れる。
 例：「そうか。あやまれるのは えらいぞ。」
 例：「こんどは いいこにしてみろ。ちゃんとみてるぞ！」

【禁止事項】
- 子どもを本気で傷つける表現、暴力の具体的な示唆はしない。
- 侮辱、罵倒、人格否定はしない。
- 大人向けの説教、長すぎる説明、現実的すぎる話はしない。
- 子どもの気持ちを無視して一方的に怒鳴り続けない。
"""
# 5. モードに合わせて変数の中身を変える
if mode == "サンタさん 🎅":
    system_prompt = SANTA_PROMPT
    ai_avatar = "🎅"
    st.title("🎅 サンタさんとおはなししよう！")
else:
    system_prompt = ONI_PROMPT
    ai_avatar = "👹" # 鬼のアイコン
    st.title("👹 コラ！おにさんだぞ！") # タイトルも変える
    
    # 鬼モードならではの演出（背景を赤っぽくする警告など）
    st.error("いうことをきかないこは、おにさんがくるぞ……！")

# --------------------------------

# ==========================================
# 2. チャットのロジック部分
# ==========================================

if not api_key:
    st.warning("設定ファイル(.streamlit/secrets.toml)が見つからないか、サイドバーにキーが入っていません。")
    st.stop()

# セッション（会話履歴）の初期化
if "messages" not in st.session_state or len(st.session_state["messages"]) == 0:
    st.session_state["messages"] = [
        {"role": "system", "content": system_prompt}
    ]

# モードを切り替えたら、AIの中身（システムプロンプト）も強制的に書き換える
st.session_state.messages[0] = {"role": "system", "content": system_prompt}

# 会話履歴の表示
for msg in st.session_state.messages:
    if msg["role"] != "system":
        # AIのアイコンは、現在のモード（ai_avatar）を使う
        if msg["role"] == "assistant":
            icon = ai_avatar
        else:
            icon = "🧒"
            
        with st.chat_message(msg["role"], avatar=icon):
            st.markdown(msg["content"])

# ==========================================
# 3. ユーザーの入力と応答
# ==========================================

# ユーザーが何か入力したら実行される
if user_input := st.chat_input("ここになにかかいてね..."):
    
    # ユーザーの入力表示
    with st.chat_message("user", avatar="🧒"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # AIからの返答
    try:
        # === 変更点 1: stream=True でストリーム応答にする ===
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.messages,
            stream=True  # ← 追加
        )

         # === 変更点 2: st.empty() を使って逐次表示 ===
        with st.chat_message("assistant", avatar=ai_avatar):
            message_placeholder = st.empty()  # ← 追加（表示場所を確保）
            full_response = ""               # ← 追加（全文をためる箱）

            for chunk in response:           # ← 追加（ストリームを回す）
                delta = chunk.choices[0].delta
                token = delta.content if delta and delta.content else ""
                full_response += token
                message_placeholder.markdown(full_response + "▌")  # ← 追加（途中経過表示）

            message_placeholder.markdown(full_response)  # ← 追加（最後に確定表示）

        ai_reply = full_response  # ← 追加（履歴保存用）

        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
        
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")