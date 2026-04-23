#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comicroom_tool_1.py
===================
COMIC ROOM X投稿ジェネレーター（統合版）
実行方法: streamlit run comicroom_tool_1.py
"""

import os
import re
import json
import base64
import anthropic
import streamlit as st
from PIL import Image
from io import BytesIO
from datetime import datetime, date
from pathlib import Path

# Google Sheets
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# ─────────────────────────────────────────────
#  設定
# ─────────────────────────────────────────────
SPREADSHEET_ID = "1_NK6cUMxr3piu7UcCx6LCdUq7DwEacJpsdzZHTAJmxs"
SHEET_NAME     = "自動配信カレンダー"

# ─────────────────────────────────────────────
#  ページ設定
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="COMIC ROOM X投稿ジェネレーター",
    page_icon="📚",
    layout="wide",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
  html, body, [class*="css"] { font-family: 'Noto Sans JP', sans-serif; }
  .main { background: #f7f6f2; }
  .block-container { padding-top: 2rem; max-width: 1100px; }
  .cr-header {
    background: #1a1a1a; color: white;
    padding: 20px 28px; border-radius: 8px;
    margin-bottom: 24px;
  }
  .cr-title { font-size: 22px; font-weight: 900; letter-spacing: 2px; }
  .cr-sub   { font-size: 12px; color: #888; margin-top: 4px; letter-spacing: 1px; }
  .cr-badge {
    display: inline-block; background: #e8003d;
    color: white; font-size: 10px; font-weight: 700;
    letter-spacing: 2px; padding: 4px 10px; border-radius: 3px; margin-top: 8px;
  }
  .post-card {
    background: white; border: 1px solid #e2e0d8;
    border-radius: 8px; padding: 16px 18px; margin-bottom: 12px;
  }
  .post-card-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #f0f0f0;
  }
  .pattern-num { color: #e8003d; font-weight: 900; font-size: 14px; }
  .pattern-tone { color: #999; font-size: 11px; letter-spacing: 1px; }
  .post-text { font-size: 14px; line-height: 1.9; white-space: pre-wrap; }
  .char-count { text-align: right; font-size: 11px; color: #bbb; margin-top: 8px; }
  .char-over  { color: #e8003d; font-weight: 700; }
  .schedule-card {
    background: white; border: 1px solid #e2e0d8; border-radius: 8px;
    padding: 14px 18px; margin-bottom: 8px; cursor: pointer;
  }
  .schedule-card:hover { border-color: #e8003d; background: #fff5f5; }
  .schedule-title { font-weight: 700; font-size: 15px; color: #1a1a1a; }
  .schedule-meta  { font-size: 12px; color: #888; margin-top: 4px; }
  .today-badge {
    display: inline-block; background: #e8003d; color: white;
    font-size: 10px; font-weight: 700; padding: 2px 8px;
    border-radius: 3px; margin-left: 8px;
  }
  div[data-testid="stButton"] button {
    background: #e8003d; color: white; border: none;
    font-weight: 700; letter-spacing: 1px; border-radius: 4px;
  }
  div[data-testid="stButton"] button:hover { background: #ff4d6d; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  ヘッダー
# ─────────────────────────────────────────────
st.markdown("""
<div class="cr-header">
  <div class="cr-title">📚 COMIC ROOM</div>
  <div class="cr-sub">X POST GENERATOR — マンガ公式投稿ツール</div>
  <div class="cr-badge">AI POWERED</div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  Google Sheets 読み取り
# ─────────────────────────────────────────────
def get_google_creds():
    """Streamlit SecretsまたはJSONファイルから認証情報を取得"""
    # Streamlit Cloud上の場合はSecretsから取得
    if "gcp_service_account" in st.secrets:
        return Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ]
        )
    # ローカルの場合はJSONファイルから取得
    json_files = list(Path(".").glob("*.json"))
    if json_files:
        return Credentials.from_service_account_file(
            str(json_files[0]),
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ]
        )
    return None


def parse_schedule_from_sheet(worksheet):
    all_values = worksheet.get_all_values()
    schedules = []
    try:
        month = int(all_values[1][3])
        year  = int(all_values[1][8])
    except (IndexError, ValueError):
        today = date.today()
        month, year = today.month, today.year
    date_cols = [1, 3, 5, 7, 9, 11, 13]
    date_row_idx = 3
    while date_row_idx < len(all_values):
        date_row = all_values[date_row_idx]
        has_date = any(col < len(date_row) and date_row[col].strip().isdigit() for col in date_cols)
        if not has_date:
            date_row_idx += 1
            continue
        dates_in_week = {}
        for col in date_cols:
            if col < len(date_row) and date_row[col].strip().isdigit():
                dates_in_week[col] = int(date_row[col].strip())
        for data_offset in range(1, 9):
            data_row_idx = date_row_idx + data_offset
            if data_row_idx >= len(all_values):
                break
            data_row = all_values[data_row_idx]
            col = 0
            while col < len(data_row) - 1:
                platform = data_row[col].strip() if col < len(data_row) else ""
                content  = data_row[col+1].strip() if col+1 < len(data_row) else ""
                if platform and content:
                    day = dates_in_week.get(col)
                    if day is None:
                        for dc in sorted(dates_in_week.keys()):
                            if dc >= col:
                                day = dates_in_week[dc]
                                break
                    if day:
                        try:
                            post_date = date(year, month, day)
                        except ValueError:
                            col += 2
                            continue
                        num = re.search("[0-9]+話", content)
                        if num:
                            episode = num.group(0)
                            title   = content[:num.start()].strip()
                        else:
                            episode = ""
                            title   = content
                        schedules.append({"date": post_date, "weekday": "", "platform": platform, "title": title, "episode": episode, "content": content})
                col += 2
        date_row_idx += 9
    return sorted(schedules, key=lambda x: x["date"])


@st.cache_data(ttl=300)
def load_schedule():
    """スプレッドシートからスケジュールを読み込む（5分キャッシュ）"""
    if not GSPREAD_AVAILABLE:
        return None, "gspread がインストールされていません"
    creds = get_google_creds()
    if not creds:
        return None, "認証情報（JSONファイル）が見つかりません"
    try:
        gc        = gspread.authorize(creds)
        sh        = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet(SHEET_NAME)
        schedules = parse_schedule_from_sheet(worksheet)
        return schedules, None
    except Exception as e:
        return None, str(e)


# ─────────────────────────────────────────────
#  テンプレート定義
# ─────────────────────────────────────────────
def tag(t): return re.sub(r'[\s　・『』【】「」()（）]', '', t)

TEMPLATE_PATTERNS = {
    "📖 最新話更新": [
        {
            "tone": "感情・没入系",
            "build": lambda t, g, ep, hook, cliff, platform: f"""📖{ep + ' ' if ep else ''}更新しました！
『{t}』{('｜' + platform) if platform else ''}

{hook}

{('▶ ' + cliff + chr(10) + chr(10)) if cliff else ''}続きはこちら👇
#コミックルーム #{tag(t)}"""
        },
        {
            "tone": "問いかけ・巻き込み系",
            "build": lambda t, g, ep, hook, cliff, platform: f"""『{t}』{ep if ep else '最新話'}、読みましたか？👀

{hook}

あなたはどう思う？
感想は #{tag(t)} で教えてください💬
#コミックルーム{(' #' + tag(platform)) if platform else ''}"""
        },
        {
            "tone": "煽り・次回引き系",
            "build": lambda t, g, ep, hook, cliff, platform: f"""⚡️見逃し厳禁⚡️
{('【' + ep + '】') if ep else ''}{hook}

{('▶ ' + cliff + chr(10)) if cliff else ''}{(platform + 'にて') if platform else ''}無料公開中📲
#コミックルーム #{tag(t)}"""
        },
    ],
    "📚 新刊告知": [
        {
            "tone": "キャッチー・感情的",
            "build": lambda t, g, vol, date_str, hook: f"""📚{(vol + ' ') if vol else ''}{(date_str + '発売！') if date_str else '発売！'}
『{t}』

{hook}

ぜひ手に取ってみてください✨
#コミックルーム #{tag(t)}"""
        },
        {
            "tone": "情報・ストレート",
            "build": lambda t, g, vol, date_str, hook: f"""【新刊情報】📚
『{t}』{(vol) if vol else ''}{('　' + date_str + '発売') if date_str else ''}

{hook}

書店・電子書籍ストアにて好評発売中！
#コミックルーム #{tag(t)}"""
        },
        {
            "tone": "共感・口コミ狙い",
            "build": lambda t, g, vol, date_str, hook: f"""待っていた方、お待たせしました🎉
『{t}』{(vol) if vol else ''}が{(date_str + 'に') if date_str else ''}発売！

{hook}

読んだ感想は #{tag(t)} で聞かせてください💬
#コミックルーム"""
        },
    ],
    "🔁 重版報告": [
        {
            "tone": "キャッチー・感謝系",
            "build": lambda t, g, info, hook: f"""🎉{(info + '！') if info else '重版決定！'}
『{t}』

{hook}

読んでくださったみなさん、本当にありがとうございます✨
#コミックルーム #{tag(t)}"""
        },
        {
            "tone": "情報・ストレート",
            "build": lambda t, g, info, hook: f"""【重版のお知らせ】
『{t}』の{(info + 'が決定しました') if info else '重版が決定しました'}📢

{hook}

引き続きよろしくお願いいたします。
#コミックルーム #{tag(t)}"""
        },
        {
            "tone": "共感・拡散狙い",
            "build": lambda t, g, info, hook: f"""みなさんのおかげです😭🙏
『{t}』{(info + '！') if info else '重版決定！'}

{hook}

シェア・感想をくれた方、すべての読者さんに感謝を💐
#{tag(t)} #コミックルーム"""
        },
    ],
    "🎬 TVアニメ化速報": [
        {
            "tone": "速報・興奮系",
            "build": lambda t, g, info, hook: f"""🚨速報🚨
『{t}』TVアニメ化決定！！🎬🎉

{(info + chr(10)) if info else ''}{hook}

続報をお楽しみに！！
#{tag(t)}アニメ化 #コミックルーム"""
        },
        {
            "tone": "情報・ストレート",
            "build": lambda t, g, info, hook: f"""【TVアニメ化決定】📺
{g}マンガ『{t}』のアニメ化が決定しました！

{('▷ ' + info + chr(10)) if info else ''}{hook}

続報は随時お知らせします。
#{tag(t)} #コミックルーム"""
        },
        {
            "tone": "読者への感謝",
            "build": lambda t, g, info, hook: f"""ずっと「アニメ化してほしい」という声をいただいてきました。
その夢が——叶いました🎬

『{t}』TVアニメ化決定！
{(info + chr(10)) if info else ''}
{hook}
#{tag(t)}アニメ化 #コミックルーム"""
        },
    ],
    "✍️ note作品紹介": [
        {
            "tone": "キャッチー・誘導系",
            "build": lambda t, g, note_title, hook: f"""📝noteを更新しました！
{('「' + note_title + '」' + chr(10)) if note_title else ''}
{hook}

{g}マンガ『{t}』が好きな方にぜひ読んでほしい記事です👇
#コミックルーム #{tag(t)} #note"""
        },
        {
            "tone": "情報・ストレート",
            "build": lambda t, g, note_title, hook: f"""【note更新】
{('「' + note_title + '」を公開しました。' + chr(10)) if note_title else '作品紹介記事を公開しました。' + chr(10)}
{hook}

『{t}』の詳細はnoteでご確認ください。
#コミックルーム #{tag(t)} #note"""
        },
        {
            "tone": "共感・口コミ狙い",
            "build": lambda t, g, note_title, hook: f"""『{t}』を知らない方にこそ読んでほしいnoteを書きました📖

{('「' + note_title + '」' + chr(10)) if note_title else ''}{hook}

{(g + 'が好きな方、') if g else ''}ぜひ覗いてみてください👀
#{tag(t)} #コミックルーム #note"""
        },
    ],
}

# ─────────────────────────────────────────────
#  サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 APIキー設定")
    api_key_input = st.text_input(
        "Anthropic APIキー",
        type="password",
        placeholder="sk-ant-api03-...",
    )
    api_key = api_key_input or os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        st.success("✅ APIキー設定済み")
    else:
        st.info("💡 AIモードで必要です")

    st.divider()
    st.markdown("### 📋 作品基本情報")
    title = st.text_input("作品名 *", placeholder="例：月光のソナタ")
    genre = st.text_input("ジャンル", placeholder="例：少女ファンタジー")

# ─────────────────────────────────────────────
#  タブ構成
# ─────────────────────────────────────────────
tab1, tab2 = st.tabs(["📅 スケジュールから投稿", "✏️ 手動で投稿作成"])

# ─────────────────────────────────────────────
#  TAB1: スプレッドシートから自動読み込み
# ─────────────────────────────────────────────
with tab1:
    st.markdown("### 📅 投稿スケジュール")
    st.caption("スプレッドシートから本日・直近の投稿予定を自動取得します")

    col_refresh, col_date = st.columns([1, 2])
    with col_refresh:
        if st.button("🔄 スケジュールを更新", use_container_width=True):
            st.cache_data.clear()

    schedules, error = load_schedule()

    if error:
        st.error(f"エラー：{error}")
    elif not schedules:
        st.warning("スケジュールが見つかりませんでした。")
        st.code(f"SHEET_NAME={SHEET_NAME}")
        st.code(f"SPREADSHEET_ID={SPREADSHEET_ID}")
    
    else:
        today = date.today()

        # 今日・今後7日分を表示
        upcoming = [s for s in schedules][:14]

        if not upcoming:
            st.info("今後の投稿予定はありません。")
        else:
            st.markdown(f"**{len(upcoming)}件** の投稿予定が見つかりました")

            selected = None
            for s in upcoming:
                is_today = s["date"] == today
                today_badge = '<span class="today-badge">TODAY</span>' if is_today else ""
                date_str = s["date"].strftime("%m/%d（" + s["weekday"] + "）")

                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"""
                    <div class="schedule-card">
                      <div class="schedule-title">
                        {s['title']}　{s['episode']}{today_badge}
                      </div>
                      <div class="schedule-meta">
                        📅 {date_str}　📱 {s['platform']}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                with col2:
                    if st.button("この作品で投稿文を作る", key=f"sel_{s['date']}_{s['platform']}_{s['title'][:10]}_{i}"):
                        selected = s

            if selected:
                st.divider()
                st.markdown(f"### ✍️ 「{selected['title']}」の投稿文を生成")

                c1, c2 = st.columns([1, 1])
                with c1:
                    ep_input   = st.text_input("話数", value=selected["episode"])
                    plt_input  = st.text_input("プラットフォーム", value=selected["platform"])
                    hook_input = st.text_area("この話の見どころ・引き *", height=80,
                        placeholder="例：ゼノがフラムをかばって傷を負う。初めて「守りたい」と口にする瞬間。")
                    cliff_input = st.text_area("引き・次回への期待（任意）", height=60,
                        placeholder="例：でも、その言葉の続きは——まだ、誰も知らない。")
                with c2:
                    st.markdown("**投稿画像**")
                    mode = st.radio("モード", ["🤖 AI画像分析", "📁 画像を1枚選ぶ"], label_visibility="collapsed")

                    if mode == "🤖 AI画像分析":
                        uploaded_files = st.file_uploader(
                            "マンガページ画像（複数）",
                            type=["jpg","jpeg","png","webp"],
                            accept_multiple_files=True
                        )
                        if uploaded_files:
                            st.success(f"✅ {len(uploaded_files)}枚読み込み済み")
                    else:
                        uploaded_img = st.file_uploader("投稿用画像（1枚）", type=["jpg","jpeg","png","webp"])
                        if uploaded_img:
                            st.image(uploaded_img, use_container_width=True)

                if st.button("✦ 投稿文を生成する", use_container_width=True):
                    title_val = selected["title"]
                    genre_val = genre or ""

                    if mode == "🤖 AI画像分析":
                        if not api_key:
                            st.error("AIモードにはAPIキーが必要です。")
                        elif not uploaded_files:
                            st.error("画像をアップロードしてください。")
                        else:
                            with st.spinner("🔍 Claudeが画像を分析中..."):
                                try:
                                    client = anthropic.Anthropic(api_key=api_key)
                                    content = []
                                    for f in sorted(uploaded_files, key=lambda x: x.name):
                                        b64 = base64.standard_b64encode(f.read()).decode()
                                        ext = f.name.split(".")[-1].lower()
                                        mt  = "image/jpeg" if ext in ["jpg","jpeg"] else f"image/{ext}"
                                        content.append({"type":"text","text":f"--- {f.name} ---"})
                                        content.append({"type":"image","source":{"type":"base64","media_type":mt,"data":b64}})

                                    content.append({"type":"text","text":f"""
あなたはマンガ編集者です。「{title_val}」{ep_input}の画像（{len(uploaded_files)}枚）を見て、
X投稿で「続きが読みたい！」と最も感じるヒキの強いシーンを1枚選び、
投稿文3パターンをJSONで返してください。前置き不要。
{{"index":<1始まり>,"reason":"<50字>","scene_summary":"<80字>","hook_phrase":"<30字>",
"posts":[
  {{"tone":"感情・没入系","text":"<140字以内 #コミックルーム #{tag(title_val)} 含む>"}},
  {{"tone":"問いかけ・巻き込み系","text":"<140字以内>"}},
  {{"tone":"煽り・次回引き系","text":"<140字以内>"}}
]}}"""})
                                    resp = client.messages.create(
                                        model="claude-opus-4-5", max_tokens=1500,
                                        messages=[{"role":"user","content":content}]
                                    )
                                    raw    = re.sub(r"```(?:json)?","",resp.content[0].text).strip().strip("`")
                                    result = json.loads(raw)
                                    idx    = max(0, min(int(result["index"])-1, len(uploaded_files)-1))

                                    st.divider()
                                    r1, r2 = st.columns([1,2])
                                    with r1:
                                        uploaded_files[idx].seek(0)
                                        pil = Image.open(uploaded_files[idx])
                                        w, h = pil.size
                                        new_h = int(w / (4/3))
                                        top   = int((h - new_h) * 0.3) if h > new_h else 0
                                        cropped = pil.crop((0, top, w, min(top+new_h, h)))
                                        st.image(cropped, caption="選ばれた画像（4:3）", use_container_width=True)
                                        buf = BytesIO()
                                        cropped.convert("RGB").save(buf,"JPEG",quality=85)
                                        st.download_button("💾 画像をダウンロード", buf.getvalue(),
                                            file_name=f"{tag(title_val)}_{ep_input}_x.jpg", mime="image/jpeg",
                                            use_container_width=True)
                                        st.info(f"📝 {result['scene_summary']}\n\n💥 {result['hook_phrase']}")
                                    with r2:
                                        for i, p in enumerate(result["posts"]):
                                            txt = p["text"].strip()
                                            st.markdown(f'<div class="post-card"><div class="post-card-header"><span class="pattern-num">PATTERN {i+1}</span><span class="pattern-tone">{p["tone"]}</span></div></div>', unsafe_allow_html=True)
                                            st.code(txt, language=None)
                                            st.caption(f"{len(txt)}字")
                                except Exception as e:
                                    st.error(f"エラー：{e}")
                    else:
                        if not hook_input:
                            st.error("この話の見どころを入力してください。")
                        else:
                            posts = []
                            for p in TEMPLATE_PATTERNS["📖 最新話更新"]:
                                txt = p["build"](title_val, genre_val, ep_input, hook_input, cliff_input, plt_input).strip()
                                posts.append({"tone": p["tone"], "text": txt})

                            st.divider()
                            c_img, c_txt = st.columns([1,2])
                            with c_img:
                                if uploaded_img:
                                    pil = Image.open(uploaded_img)
                                    w, h = pil.size
                                    new_h = int(w / (4/3))
                                    top = int((h - new_h) * 0.3) if h > new_h else 0
                                    cropped = pil.crop((0, top, w, min(top+new_h, h)))
                                    st.image(cropped, use_container_width=True)
                                    buf = BytesIO()
                                    cropped.convert("RGB").save(buf,"JPEG",quality=85)
                                    st.download_button("💾 画像をダウンロード", buf.getvalue(),
                                        file_name=f"{tag(title_val)}_{ep_input}_x.jpg", mime="image/jpeg",
                                        use_container_width=True)
                            with c_txt:
                                for i, p in enumerate(posts):
                                    st.markdown(f'<div class="post-card"><div class="post-card-header"><span class="pattern-num">PATTERN {i+1}</span><span class="pattern-tone">{p["tone"]}</span></div></div>', unsafe_allow_html=True)
                                    st.code(p["text"], language=None)
                                    st.caption(f"{len(p['text'])}字")

# ─────────────────────────────────────────────
#  TAB2: 手動入力
# ─────────────────────────────────────────────
with tab2:
    template = st.radio(
        "テンプレート",
        list(TEMPLATE_PATTERNS.keys()),
        horizontal=True,
        label_visibility="collapsed",
    )
    st.divider()

    if template == "📖 最新話更新":
        c1, c2 = st.columns([1,1])
        with c1:
            episode  = st.text_input("話数", placeholder="例：第12話")
            platform = st.text_input("掲載プラットフォーム", placeholder="例：マンガPark")
            hook     = st.text_area("この話で起きること・見どころ *", height=80, placeholder="例：ゼノがフラムをかばって傷を負う。")
            cliff    = st.text_area("引き・次回への期待（任意）", height=60, placeholder="例：でも、その言葉の続きは——")
        with c2:
            img = st.file_uploader("投稿用画像", type=["jpg","jpeg","png","webp"])
            if img: st.image(img, use_container_width=True)

        if st.button("✦ 投稿文を生成する", use_container_width=True, key="tab2_ep"):
            if not title or not hook:
                st.error("作品名とこの話の見どころを入力してください。")
            else:
                posts = [{"tone":p["tone"],"text":p["build"](title,genre,episode,hook,cliff,platform).strip()} for p in TEMPLATE_PATTERNS[template]]
                st.divider()
                c_i, c_t = st.columns([1,2])
                with c_i:
                    if img:
                        pil = Image.open(img)
                        w,h = pil.size; new_h=int(w/(4/3)); top=int((h-new_h)*0.3) if h>new_h else 0
                        cr = pil.crop((0,top,w,min(top+new_h,h))); st.image(cr, use_container_width=True)
                        buf=BytesIO(); cr.convert("RGB").save(buf,"JPEG",quality=85)
                        st.download_button("💾 画像をダウンロード",buf.getvalue(),file_name=f"{tag(title)}_x.jpg",mime="image/jpeg",use_container_width=True)
                with c_t:
                    for i,p in enumerate(posts):
                        st.markdown(f'<div class="post-card"><div class="post-card-header"><span class="pattern-num">PATTERN {i+1}</span><span class="pattern-tone">{p["tone"]}</span></div></div>',unsafe_allow_html=True)
                        st.code(p["text"],language=None); st.caption(f"{len(p['text'])}字")

    elif template == "📚 新刊告知":
        c1,c2=st.columns([1,1])
        with c1:
            vol=st.text_input("発売巻数",placeholder="例：第3巻"); date_s=st.text_input("発売日",placeholder="例：4月25日")
            hook=st.text_area("この巻の見どころ *",height=90,placeholder="例：ゼノとフラムがついに二人きりに。")
        with c2:
            img=st.file_uploader("投稿用画像",type=["jpg","jpeg","png","webp"]); 
            if img: st.image(img,use_container_width=True)
        if st.button("✦ 投稿文を生成する",use_container_width=True,key="tab2_sk"):
            if not title or not hook: st.error("作品名と見どころを入力してください。")
            else:
                posts=[{"tone":p["tone"],"text":p["build"](title,genre,vol,date_s,hook).strip()} for p in TEMPLATE_PATTERNS[template]]
                st.divider(); c_i,c_t=st.columns([1,2])
                with c_i:
                    if img:
                        pil=Image.open(img); w,h=pil.size; new_h=int(w/(4/3)); top=int((h-new_h)*0.3) if h>new_h else 0
                        cr=pil.crop((0,top,w,min(top+new_h,h))); st.image(cr,use_container_width=True)
                        buf=BytesIO(); cr.convert("RGB").save(buf,"JPEG",quality=85)
                        st.download_button("💾 画像をダウンロード",buf.getvalue(),file_name=f"{tag(title)}_x.jpg",mime="image/jpeg",use_container_width=True)
                with c_t:
                    for i,p in enumerate(posts):
                        st.markdown(f'<div class="post-card"><div class="post-card-header"><span class="pattern-num">PATTERN {i+1}</span><span class="pattern-tone">{p["tone"]}</span></div></div>',unsafe_allow_html=True)
                        st.code(p["text"],language=None); st.caption(f"{len(p['text'])}字")

    elif template == "🔁 重版報告":
        c1,c2=st.columns([1,1])
        with c1:
            info=st.text_input("重版情報",placeholder="例：第5刷決定 / 累計10万部突破")
            hook=st.text_area("読者へのメッセージ *",height=90,placeholder="例：応援ありがとうございます！")
        with c2:
            img=st.file_uploader("投稿用画像",type=["jpg","jpeg","png","webp"])
            if img: st.image(img,use_container_width=True)
        if st.button("✦ 投稿文を生成する",use_container_width=True,key="tab2_jh"):
            if not title or not hook: st.error("作品名とメッセージを入力してください。")
            else:
                posts=[{"tone":p["tone"],"text":p["build"](title,genre,info,hook).strip()} for p in TEMPLATE_PATTERNS[template]]
                st.divider(); c_i,c_t=st.columns([1,2])
                with c_i:
                    if img:
                        pil=Image.open(img); w,h=pil.size; new_h=int(w/(4/3)); top=int((h-new_h)*0.3) if h>new_h else 0
                        cr=pil.crop((0,top,w,min(top+new_h,h))); st.image(cr,use_container_width=True)
                        buf=BytesIO(); cr.convert("RGB").save(buf,"JPEG",quality=85)
                        st.download_button("💾 画像をダウンロード",buf.getvalue(),file_name=f"{tag(title)}_x.jpg",mime="image/jpeg",use_container_width=True)
                with c_t:
                    for i,p in enumerate(posts):
                        st.markdown(f'<div class="post-card"><div class="post-card-header"><span class="pattern-num">PATTERN {i+1}</span><span class="pattern-tone">{p["tone"]}</span></div></div>',unsafe_allow_html=True)
                        st.code(p["text"],language=None); st.caption(f"{len(p['text'])}字")

    elif template == "🎬 TVアニメ化速報":
        c1,c2=st.columns([1,1])
        with c1:
            info=st.text_input("放送時期・スタジオ",placeholder="例：2025年秋放送予定")
            hook=st.text_area("コメント *",height=90,placeholder="例：ずっと夢見ていました。")
        with c2:
            img=st.file_uploader("投稿用画像",type=["jpg","jpeg","png","webp"])
            if img: st.image(img,use_container_width=True)
        if st.button("✦ 投稿文を生成する",use_container_width=True,key="tab2_an"):
            if not title or not hook: st.error("作品名とコメントを入力してください。")
            else:
                posts=[{"tone":p["tone"],"text":p["build"](title,genre,info,hook).strip()} for p in TEMPLATE_PATTERNS[template]]
                st.divider(); c_i,c_t=st.columns([1,2])
                with c_i:
                    if img:
                        pil=Image.open(img); w,h=pil.size; new_h=int(w/(4/3)); top=int((h-new_h)*0.3) if h>new_h else 0
                        cr=pil.crop((0,top,w,min(top+new_h,h))); st.image(cr,use_container_width=True)
                        buf=BytesIO(); cr.convert("RGB").save(buf,"JPEG",quality=85)
                        st.download_button("💾 画像をダウンロード",buf.getvalue(),file_name=f"{tag(title)}_x.jpg",mime="image/jpeg",use_container_width=True)
                with c_t:
                    for i,p in enumerate(posts):
                        st.markdown(f'<div class="post-card"><div class="post-card-header"><span class="pattern-num">PATTERN {i+1}</span><span class="pattern-tone">{p["tone"]}</span></div></div>',unsafe_allow_html=True)
                        st.code(p["text"],language=None); st.caption(f"{len(p['text'])}字")

    elif template == "✍️ note作品紹介":
        c1,c2=st.columns([1,1])
        with c1:
            note_title=st.text_input("note記事タイトル",placeholder="例：なぜ私がこの作品を作ったか")
            hook=st.text_area("記事の内容・ポイント *",height=90,placeholder="例：制作秘話、キャラへの思いを書きました。")
        with c2:
            img=st.file_uploader("投稿用画像",type=["jpg","jpeg","png","webp"])
            if img: st.image(img,use_container_width=True)
        if st.button("✦ 投稿文を生成する",use_container_width=True,key="tab2_nt"):
            if not title or not hook: st.error("作品名と記事内容を入力してください。")
            else:
                posts=[{"tone":p["tone"],"text":p["build"](title,genre,note_title,hook).strip()} for p in TEMPLATE_PATTERNS[template]]
                st.divider(); c_i,c_t=st.columns([1,2])
                with c_i:
                    if img:
                        pil=Image.open(img); w,h=pil.size; new_h=int(w/(4/3)); top=int((h-new_h)*0.3) if h>new_h else 0
                        cr=pil.crop((0,top,w,min(top+new_h,h))); st.image(cr,use_container_width=True)
                        buf=BytesIO(); cr.convert("RGB").save(buf,"JPEG",quality=85)
                        st.download_button("💾 画像をダウンロード",buf.getvalue(),file_name=f"{tag(title)}_x.jpg",mime="image/jpeg",use_container_width=True)
                with c_t:
                    for i,p in enumerate(posts):
                        st.markdown(f'<div class="post-card"><div class="post-card-header"><span class="pattern-num">PATTERN {i+1}</span><span class="pattern-tone">{p["tone"]}</span></div></div>',unsafe_allow_html=True)
                        st.code(p["text"],language=None); st.caption(f"{len(p['text'])}字")

# フッター
st.divider()
st.markdown('<div style="text-align:center;color:#bbb;font-size:11px;letter-spacing:2px">COMIC ROOM X POST GENERATOR　©2025 株式会社コミックルーム</div>', unsafe_allow_html=True)
