#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comicroom_tool.py
=================
COMIC ROOM X投稿ジェネレーター（統合版）
実行方法: streamlit run comicroom_tool.py
"""

import os
import re
import json
import base64
import anthropic
import streamlit as st
from PIL import Image
from io import BytesIO
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
#  ページ設定
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="COMIC ROOM X投稿ジェネレーター",
    page_icon="📚",
    layout="wide",
)

# ─────────────────────────────────────────────
#  スタイル
# ─────────────────────────────────────────────
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
    display: flex; align-items: center; gap: 16px;
  }
  .cr-title { font-size: 22px; font-weight: 900; letter-spacing: 2px; }
  .cr-sub   { font-size: 12px; color: #888; margin-top: 4px; letter-spacing: 1px; }
  .cr-badge {
    margin-left: auto; background: #e8003d;
    color: white; font-size: 10px; font-weight: 700;
    letter-spacing: 2px; padding: 4px 10px; border-radius: 3px;
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

  .section-head {
    font-size: 11px; font-weight: 700; letter-spacing: 3px;
    color: #999; text-transform: uppercase; margin-bottom: 8px;
  }
  .result-img {
    border-radius: 6px; width: 100%;
    border: 1px solid #e2e0d8;
  }
  .info-box {
    background: #eef6ff; border-left: 3px solid #0984e3;
    border-radius: 4px; padding: 10px 14px;
    font-size: 13px; color: #444; margin: 8px 0;
  }
  .warn-box {
    background: #fff5f0; border-left: 3px solid #e17055;
    border-radius: 4px; padding: 10px 14px;
    font-size: 13px; color: #444; margin: 8px 0;
  }
  div[data-testid="stButton"] button {
    background: #e8003d; color: white; border: none;
    font-weight: 700; letter-spacing: 1px; border-radius: 4px;
    padding: 10px 24px; width: 100%;
  }
  div[data-testid="stButton"] button:hover { background: #ff4d6d; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  ヘッダー
# ─────────────────────────────────────────────
st.markdown("""
<div class="cr-header">
  <div>
    <div class="cr-title">📚 COMIC ROOM</div>
    <div class="cr-sub">X POST GENERATOR — マンガ公式投稿ツール</div>
  </div>
  <div class="cr-badge">AI POWERED</div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  テンプレート定義（テンプレートベース）
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
            "build": lambda t, g, vol, date, hook: f"""📚{(vol + ' ') if vol else ''}{(date + '発売！') if date else '発売！'}
『{t}』

{hook}

ぜひ手に取ってみてください✨
#コミックルーム #{tag(t)}"""
        },
        {
            "tone": "情報・ストレート",
            "build": lambda t, g, vol, date, hook: f"""【新刊情報】📚
『{t}』{(vol) if vol else ''}{('　' + date + '発売') if date else ''}

{hook}

書店・電子書籍ストアにて好評発売中！
#コミックルーム #{tag(t)}"""
        },
        {
            "tone": "共感・口コミ狙い",
            "build": lambda t, g, vol, date, hook: f"""待っていた方、お待たせしました🎉
『{t}』{(vol) if vol else ''}が{(date + 'に') if date else ''}発売！

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
#  画像分析関数（AIモード）
# ─────────────────────────────────────────────
def analyze_images_with_ai(client, images_data, title, episode, genre):
    """全画像をClaudeに送り、最もヒキになるシーンを特定する"""
    content = []
    for i, (name, b64, media_type) in enumerate(images_data):
        content.append({"type": "text", "text": f"--- 画像{i+1}枚目: {name} ---"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}})

    content.append({"type": "text", "text": f"""
あなたはマンガ編集者です。
上記は「{title}」{episode}の画像（計{len(images_data)}枚）です。
ジャンル：{genre or 'マンガ'}

X（旧Twitter）に投稿したときに「続きが読みたい！」と読者が最も感じる"ヒキ"の強いシーンを1枚選んでください。

選んだ理由・シーン要約・煽り文句・投稿文3パターンを以下のJSONのみで返してください。前置き不要。
{{
  "index": <選んだ画像の番号（1始まり）>,
  "reason": "<選んだ理由（50字以内）>",
  "scene_summary": "<そのシーンで何が起きているかの要約（80字以内）>",
  "hook_phrase": "<煽り文句（30字以内）>",
  "posts": [
    {{"tone": "感情・没入系",       "text": "<140字以内の投稿文。#コミックルーム と #{title.replace('　','').replace(' ','')} を含める>"}},
    {{"tone": "問いかけ・巻き込み系", "text": "<140字以内の投稿文>"}},
    {{"tone": "煽り・次回引き系",   "text": "<140字以内の投稿文>"}}
  ]
}}
"""})

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": content}]
    )
    raw = re.sub(r"```(?:json)?", "", response.content[0].text).strip().strip("`")
    return json.loads(raw)


def crop_image(pil_img):
    """4:3にセンタークロップ（上部30%基点）"""
    w, h = pil_img.size
    target_ratio = 4 / 3
    if w / h > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        return pil_img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = int((h - new_h) * 0.3)
        return pil_img.crop((0, top, w, top + new_h))


def render_posts(posts):
    """投稿文カードを表示＋コピーボタン"""
    for i, p in enumerate(posts):
        text = p["text"].strip()
        count = len(text)
        over = count > 140
        count_html = f'<div class="char-count {"char-over" if over else ""}">{count}字{"　⚠ やや長め" if over else ""}</div>'

        st.markdown(f"""
        <div class="post-card">
          <div class="post-card-header">
            <span class="pattern-num">PATTERN {i+1}</span>
            <span class="pattern-tone">{p['tone']}</span>
          </div>
          <div class="post-text">{text}</div>
          {count_html}
        </div>
        """, unsafe_allow_html=True)
        st.code(text, language=None)


# ─────────────────────────────────────────────
#  サイドバー：共通入力
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 APIキー設定")
    api_key_input = st.text_input(
        "Anthropic APIキー",
        type="password",
        placeholder="sk-ant-api03-...",
        help="最新話更新（AI画像分析）モードで必要です。他のテンプレートは不要。"
    )
    api_key = api_key_input or os.environ.get("ANTHROPIC_API_KEY", "")

    if api_key:
        st.success("✅ APIキー設定済み")
    else:
        st.info("💡 最新話更新（AIモード）を使う場合は入力してください")

    st.divider()
    st.markdown("### 📋 作品基本情報")
    title = st.text_input("作品名 *", placeholder="例：月光のソナタ")
    genre = st.text_input("ジャンル", placeholder="例：少女ファンタジー")

# ─────────────────────────────────────────────
#  メイン：テンプレート選択
# ─────────────────────────────────────────────
template = st.radio(
    "テンプレートを選択",
    list(TEMPLATE_PATTERNS.keys()),
    horizontal=True,
    label_visibility="collapsed",
)

st.divider()

# ─────────────────────────────────────────────
#  テンプレート別フォーム
# ─────────────────────────────────────────────

# ── 最新話更新 ──────────────────────────────
if template == "📖 最新話更新":
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div class="section-head">エピソード情報</div>', unsafe_allow_html=True)
        episode  = st.text_input("話数", placeholder="例：第12話")
        platform = st.text_input("掲載プラットフォーム", placeholder="例：マンガPark・LINEマンガ")

        st.markdown("**モードを選択**")
        mode = st.radio("", ["🤖 AI画像分析モード（おすすめ）", "✏️ 手入力モード"], label_visibility="collapsed")

        if mode == "✏️ 手入力モード":
            hook = st.text_area("この話で起きること・見どころ", height=80,
                placeholder="例：ゼノがフラムをかばって傷を負う。初めて「守りたい」と口にする瞬間。")
            cliff = st.text_area("引き・次回への期待（任意）", height=60,
                placeholder="例：でも、その言葉の続きは——まだ、誰も知らない。")

    with col2:
        st.markdown('<div class="section-head">投稿画像</div>', unsafe_allow_html=True)

        if mode == "🤖 AI画像分析モード（おすすめ）":
            uploaded_files = st.file_uploader(
                "マンガページ画像をアップロード（複数選択可・約12枚）",
                type=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
                help="ファイルを選択してCtrl+A（またはCmd+A）で全選択できます"
            )
            if uploaded_files:
                st.success(f"✅ {len(uploaded_files)}枚読み込み済み")
                # サムネイル表示（最初の3枚）
                thumb_cols = st.columns(min(3, len(uploaded_files)))
                for i, f in enumerate(uploaded_files[:3]):
                    with thumb_cols[i]:
                        st.image(f, use_container_width=True)
        else:
            uploaded_img = st.file_uploader("投稿用画像（1枚）", type=["jpg","jpeg","png","webp"])
            if uploaded_img:
                st.image(uploaded_img, use_container_width=True)

    st.markdown("")
    generate = st.button("✦ 投稿文を生成する", use_container_width=True)

    if generate:
        if not title:
            st.error("作品名を入力してください。")
        elif mode == "🤖 AI画像分析モード（おすすめ）":
            if not api_key:
                st.error("AIモードにはAPIキーが必要です。サイドバーに入力してください。")
            elif not uploaded_files:
                st.error("画像をアップロードしてください。")
            else:
                with st.spinner("🔍 Claudeが画像を分析中...（少々お待ちください）"):
                    try:
                        client = anthropic.Anthropic(api_key=api_key)
                        images_data = []
                        for f in sorted(uploaded_files, key=lambda x: x.name):
                            b64 = base64.standard_b64encode(f.read()).decode()
                            ext = f.name.split(".")[-1].lower()
                            mt  = "image/jpeg" if ext in ["jpg","jpeg"] else f"image/{ext}"
                            images_data.append((f.name, b64, mt))

                        result = analyze_images_with_ai(client, images_data, title, episode, genre)
                        idx = max(0, min(int(result["index"]) - 1, len(uploaded_files) - 1))

                        st.divider()
                        st.markdown("### 📋 生成結果")

                        r1, r2 = st.columns([1, 2])
                        with r1:
                            st.markdown('<div class="section-head">選ばれた画像</div>', unsafe_allow_html=True)
                            uploaded_files[idx].seek(0)
                            pil = Image.open(uploaded_files[idx])
                            cropped = crop_image(pil)
                            st.image(cropped, caption=f"{uploaded_files[idx].name}（4:3クロップ済み）", use_container_width=True)

                            # 保存ボタン
                            buf = BytesIO()
                            cropped.convert("RGB").save(buf, "JPEG", quality=85)
                            st.download_button(
                                "💾 画像をダウンロード",
                                data=buf.getvalue(),
                                file_name=f"{tag(title)}_{episode}_x_post.jpg",
                                mime="image/jpeg",
                                use_container_width=True,
                            )

                            st.markdown(f"""
                            <div class="info-box">
                            📝 <strong>シーン</strong>：{result['scene_summary']}<br>
                            💥 <strong>煽り文句</strong>：{result['hook_phrase']}<br>
                            💬 <strong>選んだ理由</strong>：{result['reason']}
                            </div>
                            """, unsafe_allow_html=True)

                        with r2:
                            st.markdown('<div class="section-head">投稿文 3パターン</div>', unsafe_allow_html=True)
                            render_posts(result["posts"])

                    except Exception as e:
                        st.error(f"エラーが発生しました：{e}")

        else:  # 手入力モード
            if not hook:
                st.error("この話で起きること・見どころを入力してください。")
            else:
                posts = []
                for p in TEMPLATE_PATTERNS[template]:
                    text = p["build"](title, genre, episode, hook, cliff if 'cliff' in dir() else "", platform)
                    posts.append({"tone": p["tone"], "text": text.strip()})

                st.divider()
                st.markdown("### 📋 生成結果")
                col_img, col_txt = st.columns([1, 2])
                with col_img:
                    if 'uploaded_img' in dir() and uploaded_img:
                        pil = Image.open(uploaded_img)
                        cropped = crop_image(pil)
                        st.image(cropped, caption="投稿用画像（4:3クロップ）", use_container_width=True)
                        buf = BytesIO()
                        cropped.convert("RGB").save(buf, "JPEG", quality=85)
                        st.download_button("💾 画像をダウンロード", buf.getvalue(),
                            file_name=f"{tag(title)}_{episode}_x_post.jpg", mime="image/jpeg", use_container_width=True)
                with col_txt:
                    render_posts(posts)


# ── 新刊告知 ────────────────────────────────
elif template == "📚 新刊告知":
    c1, c2 = st.columns([1, 1])
    with c1:
        vol  = st.text_input("発売巻数", placeholder="例：第3巻")
        date = st.text_input("発売日",  placeholder="例：4月25日（木）")
        hook = st.text_area("この巻の見どころ・引き *", height=90,
            placeholder="例：ゼノとフラムがついに二人きりに。秘密が明かされる衝撃の展開。")
    with c2:
        img = st.file_uploader("投稿用画像（任意）", type=["jpg","jpeg","png","webp"])
        if img: st.image(img, use_container_width=True)

    if st.button("✦ 投稿文を生成する", use_container_width=True):
        if not title or not hook:
            st.error("作品名とこの巻の見どころを入力してください。")
        else:
            posts = [{"tone": p["tone"], "text": p["build"](title, genre, vol, date, hook).strip()}
                     for p in TEMPLATE_PATTERNS[template]]
            st.divider()
            st.markdown("### 📋 生成結果")
            c_img, c_txt = st.columns([1, 2])
            with c_img:
                if img:
                    pil = crop_image(Image.open(img))
                    st.image(pil, use_container_width=True)
                    buf = BytesIO(); pil.convert("RGB").save(buf,"JPEG",quality=85)
                    st.download_button("💾 画像をダウンロード", buf.getvalue(),
                        file_name=f"{tag(title)}_x_post.jpg", mime="image/jpeg", use_container_width=True)
            with c_txt:
                render_posts(posts)


# ── 重版報告 ────────────────────────────────
elif template == "🔁 重版報告":
    c1, c2 = st.columns([1, 1])
    with c1:
        info = st.text_input("重版情報", placeholder="例：第5刷決定 / 累計10万部突破")
        hook = st.text_area("読者へのメッセージ・一言 *", height=90,
            placeholder="例：「続きが気になって眠れない」という声が何より励みです。")
    with c2:
        img = st.file_uploader("投稿用画像（任意）", type=["jpg","jpeg","png","webp"])
        if img: st.image(img, use_container_width=True)

    if st.button("✦ 投稿文を生成する", use_container_width=True):
        if not title or not hook:
            st.error("作品名とメッセージを入力してください。")
        else:
            posts = [{"tone": p["tone"], "text": p["build"](title, genre, info, hook).strip()}
                     for p in TEMPLATE_PATTERNS[template]]
            st.divider()
            st.markdown("### 📋 生成結果")
            c_img, c_txt = st.columns([1, 2])
            with c_img:
                if img:
                    pil = crop_image(Image.open(img))
                    st.image(pil, use_container_width=True)
                    buf = BytesIO(); pil.convert("RGB").save(buf,"JPEG",quality=85)
                    st.download_button("💾 画像をダウンロード", buf.getvalue(),
                        file_name=f"{tag(title)}_x_post.jpg", mime="image/jpeg", use_container_width=True)
            with c_txt:
                render_posts(posts)


# ── TVアニメ化速報 ──────────────────────────
elif template == "🎬 TVアニメ化速報":
    c1, c2 = st.columns([1, 1])
    with c1:
        info = st.text_input("放送時期・スタジオ（任意）", placeholder="例：2025年秋放送予定 / ○○アニメーション制作")
        hook = st.text_area("一言コメント・読者へのメッセージ *", height=90,
            placeholder="例：ずっとアニメ化を夢見ていました。応援してくれたみなさんのおかげです。")
    with c2:
        img = st.file_uploader("投稿用画像（任意）", type=["jpg","jpeg","png","webp"])
        if img: st.image(img, use_container_width=True)

    if st.button("✦ 投稿文を生成する", use_container_width=True):
        if not title or not hook:
            st.error("作品名とコメントを入力してください。")
        else:
            posts = [{"tone": p["tone"], "text": p["build"](title, genre, info, hook).strip()}
                     for p in TEMPLATE_PATTERNS[template]]
            st.divider()
            st.markdown("### 📋 生成結果")
            c_img, c_txt = st.columns([1, 2])
            with c_img:
                if img:
                    pil = crop_image(Image.open(img))
                    st.image(pil, use_container_width=True)
                    buf = BytesIO(); pil.convert("RGB").save(buf,"JPEG",quality=85)
                    st.download_button("💾 画像をダウンロード", buf.getvalue(),
                        file_name=f"{tag(title)}_x_post.jpg", mime="image/jpeg", use_container_width=True)
            with c_txt:
                render_posts(posts)


# ── note作品紹介 ────────────────────────────
elif template == "✍️ note作品紹介":
    c1, c2 = st.columns([1, 1])
    with c1:
        note_title = st.text_input("note記事タイトル（任意）", placeholder="例：なぜ私がこの作品を作ったか")
        hook = st.text_area("記事の内容・読んでほしいポイント *", height=90,
            placeholder="例：制作秘話、キャラへの思い、読者へのメッセージを書きました。")
    with c2:
        img = st.file_uploader("投稿用画像（任意）", type=["jpg","jpeg","png","webp"])
        if img: st.image(img, use_container_width=True)

    if st.button("✦ 投稿文を生成する", use_container_width=True):
        if not title or not hook:
            st.error("作品名と記事の内容を入力してください。")
        else:
            posts = [{"tone": p["tone"], "text": p["build"](title, genre, note_title, hook).strip()}
                     for p in TEMPLATE_PATTERNS[template]]
            st.divider()
            st.markdown("### 📋 生成結果")
            c_img, c_txt = st.columns([1, 2])
            with c_img:
                if img:
                    pil = crop_image(Image.open(img))
                    st.image(pil, use_container_width=True)
                    buf = BytesIO(); pil.convert("RGB").save(buf,"JPEG",quality=85)
                    st.download_button("💾 画像をダウンロード", buf.getvalue(),
                        file_name=f"{tag(title)}_x_post.jpg", mime="image/jpeg", use_container_width=True)
            with c_txt:
                render_posts(posts)

# ─────────────────────────────────────────────
#  フッター
# ─────────────────────────────────────────────
st.divider()
st.markdown("""
<div style="text-align:center; color:#bbb; font-size:11px; letter-spacing:2px; padding: 8px 0;">
  COMIC ROOM X POST GENERATOR　©2025 株式会社コミックルーム
</div>
""", unsafe_allow_html=True)
