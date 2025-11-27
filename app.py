import streamlit as st
from openai import OpenAI
from supabase import create_client  # Supabase接続

# ==========================================
# 1. 設定部分
# ==========================================

# ページの設定（タイトルやアイコン）
st.set_page_config(page_title="いいこのおはなしアプリ", page_icon="🎁", layout="wide")  # wideで横長UI

# ---- CSSでざっくりフレーム寄せ（見た目調整）----
# === UI変更点: 左ポイント枠/右チャット枠の雰囲気を近づける ===
st.markdown("""
<style>
/* ページ全体の左右余白を減らす */
.main .block-container {
    padding-top: 1.2rem;
    padding-bottom: 1.5rem;
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100%;
}

/* 上部のデフォルト空白を少し詰める */
header[data-testid="stHeader"] {
    height: 0rem;
}

/* タイトル行を折り返さない（切れを防ぐ） */
.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
}

.app-title {
    font-size: 32px;
    font-weight: 800;
    white-space: nowrap;
}

</style>
""", unsafe_allow_html=True)

# secrets.toml からキーを取得
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    api_key = st.sidebar.text_input("OpenAI API Key", type="password")

if not api_key:
    st.warning("APIキーが設定されていません。")
    st.stop()

client = OpenAI(api_key=api_key)

# Supabaseからお手伝いキーワードやポイントを持ってくる

if "SUPABASE_URL" not in st.secrets or "SUPABASE_ANON_KEY" not in st.secrets:
    st.error("Supabaseの設定（SUPABASE_URL / SUPABASE_ANON_KEY）がsecrets.tomlにありません。")
    st.stop()

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

# ---------------------------
# サイドバー：モード & 名前 & ポイント
# ---------------------------

# モード切り替え
mode = st.sidebar.radio("だれとおはなしする？", ["サンタさん 🎅", "おにさん 👹"])

# 子どもの名前（ログイン不要なので入力だけ）
if "child_name" not in st.session_state:
    st.session_state["child_name"] = ""

child_name_input = st.sidebar.text_input("おなまえ（ひらがな）", value=st.session_state["child_name"])
st.session_state["child_name"] = child_name_input.strip()

if not st.session_state["child_name"]:
    st.sidebar.info("おなまえをいれてね")

# DBから累計ポイント取得

def load_child_total(child_name: str) -> int:
    res = supabase.table("For_Children") \
        .select("total_points") \
        .eq("child_name", child_name) \
        .execute()

    if res.data and len(res.data) > 0:
        return res.data[0]["total_points"]
    else:
        # 登録がない子は0で新規作成しておく
        supabase.table("For_Children").insert({
            "child_name": child_name,
            "total_points": 0
        }).execute()
        return 0    

# total_points を必ず先に用意（KeyError防止）
if "total_points" not in st.session_state:
    st.session_state["total_points"] = 0

# 名前が変わったタイミングでDBからポイント復元
if "prev_child_name" not in st.session_state:
    st.session_state["prev_child_name"] = ""

if st.session_state["child_name"] and st.session_state["child_name"] != st.session_state["prev_child_name"]:
    st.session_state["total_points"] = load_child_total(st.session_state["child_name"])
    st.session_state["prev_child_name"] = st.session_state["child_name"]

# よいこポイント
with st.sidebar:
    st.markdown("### よいこポイント")
    st.metric("いまのポイント", st.session_state["total_points"])
    st.caption("もくひょうポイント： （あとで決めよう）")  # TODO: 目標ポイントはあとで決定

# ---------------------------
# モード切替時に会話履歴をリセット
# ---------------------------

if "current_mode" not in st.session_state:
    st.session_state["current_mode"] = mode

# 「今回選んだモード」と「前回のモード」が違うかチェック！
if st.session_state["current_mode"] != mode:
    # 違っていたら（＝切り替えたら）、会話履歴を空っぽにする
    st.session_state["messages"] = []
    # 「前回のモード」を新しい方に更新しておく
    st.session_state["current_mode"] = mode

# ---------------------------
# キャラプロンプト
# ---------------------------
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
・全部「ひらがな」で書くこと。漢字と記号と顔文字は絶対使わない。英語は最低限で、平易な日本語で話す。絵文字はかわいいから使ってもいいよ。
・短く、簡単に、ゆっくり読める言葉を話す。
・文の長さは最大2文まで。
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
    header_title = "🎅 サンタさんとおはなししよう！" 
    system_prompt = SANTA_PROMPT
    ai_avatar = "🎅"
else:
    header_title = "👹 コラ！おにさんだぞ！" 
    system_prompt = ONI_PROMPT
    ai_avatar = "👹"

# Supabaseから有効なキーワード取得
def fetch_active_keywords():
    res = supabase.table("Otetsudai_Keywords") \
        .select("id, keyword, points, category") \
        .eq("is_active", True) \
        .execute()
    return res.data or []

# 入力文 → マッチ判定して加点計算
def calc_points(text, keywords):
    matched_rows = []
    for row in keywords:
        if row["keyword"] in text:
            matched_rows.append(row)
    total = sum(r["points"] for r in matched_rows)
    return total, matched_rows

# Points_logに保存
def insert_points_log(child_name, matched_rows, user_text):
    for r in matched_rows:
        supabase.table("Points_log").insert({
            "child_name": child_name,
            "keyword_id": r["id"],
            "matched_text": user_text,
            "points": r["points"],
        }).execute()

# For_Children
def upsert_child_total(child_name, new_total):
    supabase.table("For_Children").upsert({
        "child_name": child_name,
        "total_points": new_total
    }).execute()

# --------------------------------
# 画面レイアウト（左/右）
# --------------------------------
left_col, right_col = st.columns([1, 4], gap="large")

# 右側メインUI
with right_col:
    # ヘッダー行（タイトル＋終了ボタン）
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.markdown(f'<div class="app-title">{header_title}</div>', unsafe_allow_html=True)
    with col_btn:
        if st.button("チャットを終わる"):
            st.session_state["show_end_dialog"] = True  # ←ダイアログ表示フラグON

    if mode == "おにさん 👹":
        st.error("いうことをきかないこは、おにさんがくるぞ……！")

    # イラスト枠（仮URL）
    st.markdown("#### イラスト")
    st.image(
        "https://eiyoushi-hutaba.com/wp-content/uploads/2022/11/%E3%82%B5%E3%83%B3%E3%82%BF%E3%81%95%E3%82%93-940x940.png",
        width=200,  # ←サイズはここで調整
        caption="サンタさん"
    )

    st.write("")

# ==========================================
# 2. チャットのロジック部分
# ==========================================

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

 # キーワード判定 → ポイント加算
    if st.session_state["child_name"]:
        keywords = fetch_active_keywords()
        add_points, matched_rows = calc_points(user_input, keywords)

        if add_points > 0:
            st.session_state["total_points"] += add_points

            # Points_log に保存
            insert_points_log(st.session_state["child_name"], matched_rows, user_input)

            # For Children に合計保存
            upsert_child_total(st.session_state["child_name"], st.session_state["total_points"])

            matched_words = [r["keyword"] for r in matched_rows]
            st.success(f"すごい！「{'、'.join(matched_words)}」で {add_points} てん たまったよ！")

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

# ==========================================
# 4. チャット終了ダイアログ
# ==========================================
if "show_end_dialog" not in st.session_state:
    st.session_state["show_end_dialog"] = False

if st.session_state["show_end_dialog"]:
    # Streamlitのダイアログ（モーダル風）
    @st.dialog("チャットを終わりますか？")
    def end_chat_dialog():
        st.write("ほごしゃのぱすわーどをいれてね。")

        # ★ここでパスワード入力
        pw = st.text_input("パスワード", type="password")

        # TODO: ここに「正しいパスワード」をあとで設定する
        # ex) CORRECT_PASSWORD = "xxxx"
        CORRECT_PASSWORD = "password"  # ←あとで決めた値に差し替える

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("キャンセル"):
                st.session_state["show_end_dialog"] = False
                st.rerun()

        with col_b:
            if st.button("チャットを終わる"):
                # ★パスワード一致チェック
                if pw == CORRECT_PASSWORD:
                    st.session_state["show_end_dialog"] = False

                    # TODO: ここで「親の管理画面」に遷移する想定
                    # いまは管理画面未実装なので、会話履歴リセットだけしておく
                    st.session_state["messages"] = []
                    st.success("チャットをおわったよ。")
                    st.rerun()
                else:
                    st.error("ぱすわーどがちがうよ。")

    end_chat_dialog()