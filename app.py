# ===== Windows UTF-8 编码修复 =====
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
# ===================================

import streamlit as st
import base64
import calendar
import os
import tempfile
import io
import re
from datetime import date, timedelta
from openai import OpenAI
from PIL import Image
import pandas as pd
import plotly.express as px
from gtts import gTTS
from database import db, init_tables, create_review_schedule, get_today_reviews, get_today_review_count, mark_review_done

# ========== 页面配置（移动端优化） ==========
st.set_page_config(
    page_title="📚 错题本",
    page_icon="🌟",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ========== 高端教培风格 CSS ==========
st.markdown("""
<style>
/* ---- 全局 ---- */
.stApp {
    background: #F0F2F5;
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    color: #1E293B !important;
}
/* 全局文字颜色修复 — 白底黑字 */
.stApp, .main, .block-container, p, span, div, li, label {
    color: #1E293B !important;
}
.stMarkdown, .stText, .stTextInput, .stSelectbox, .stTextArea {
    color: #1E293B !important;
}
/* info/warning/error 消息框 */
.stAlert { color: #1E293B !important; }
.stAlert p { color: #1E293B !important; }

/* 主内容区域 — 干净白底卡片 */
.main .block-container {
    background: #FFFFFF;
    border-radius: 24px 24px 0 0;
    padding: 1.5rem 1.2rem 2rem 1.2rem;
    margin: 0;
    box-shadow: 0 -2px 20px rgba(0,0,0,0.04);
    min-height: calc(100vh - 60px);
}

/* ---- 顶部导航栏 ---- */
.top-nav {
    background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
    padding: 0.6rem 0.8rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-radius: 0 0 20px 20px;
    box-shadow: 0 4px 20px rgba(79,70,229,0.25);
    position: sticky;
    top: 0;
    z-index: 100;
}
.top-nav-user {
    color: #fff;
    font-size: 0.9rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
}
.top-nav-user small {
    font-weight: 400;
    opacity: 0.8;
    font-size: 0.7rem;
}
.top-nav-logout {
    background: rgba(255,255,255,0.15) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    color: #fff !important;
    border-radius: 20px !important;
    padding: 0.2rem 0.8rem !important;
    font-size: 0.75rem !important;
    width: auto !important;
    min-width: 0 !important;
}
.top-nav-logout:hover {
    background: rgba(255,255,255,0.25) !important;
}

/* 顶部 Tab 导航 */
.top-tabs {
    display: flex;
    gap: 4px;
    padding: 0.8rem 0.2rem 0.2rem 0.2rem;
    overflow-x: auto;
    white-space: nowrap;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
}
.top-tabs::-webkit-scrollbar { display: none; }
.tab-item {
    flex: 1 0 auto;
    min-width: 60px;
    text-align: center;
    padding: 8px 6px;
    border-radius: 14px;
    font-size: 0.75rem;
    font-weight: 500;
    color: #64748B;
    transition: all 0.2s;
    cursor: pointer;
    user-select: none;
    background: transparent;
    border: none;
    line-height: 1.3;
}
.tab-item .tab-icon { font-size: 1.3rem; display: block; margin-bottom: 2px; }
.tab-item.active {
    background: #EEF2FF;
    color: #4F46E5;
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(79,70,229,0.12);
}

/* ---- 标题 ---- */
.title-main {
    font-size: 1.4rem;
    font-weight: 800;
    color: #1E293B;
    text-align: center;
    padding: 0.4rem 0 0.8rem 0;
    letter-spacing: 0.5px;
}

/* ---- 按钮 ---- */
.stButton>button {
    border-radius: 14px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    border: none !important;
    background: linear-gradient(135deg, #4F46E5, #7C3AED) !important;
    color: white !important;
    padding: 0.6rem 1.2rem !important;
    width: 100% !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 12px rgba(79,70,229,0.2) !important;
}
.stButton>button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(79,70,229,0.3) !important;
}
.stButton>button:active {
    transform: scale(0.97) !important;
}

/* ---- 统计卡片 ---- */
.stat-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 1rem;
}
.stat-card {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 1rem 0.8rem;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    border: 1px solid #F1F5F9;
}
.stat-number {
    font-size: 1.8rem;
    font-weight: 800;
    color: #4F46E5;
    line-height: 1.2;
}
.stat-label {
    font-size: 0.78rem;
    color: #64748B;
    margin-top: 4px;
}

/* ---- info 消息框 ---- */
.stAlert {
    border-radius: 16px !important;
    border: none !important;
}
.stAlert [data-testid="stAlertContainer"] {
    border-radius: 16px !important;
}

/* ---- 分割线 ---- */
hr {
    margin: 1rem 0 !important;
    border-color: #F1F5F9 !important;
}

/* ---- 输入框 ---- */
.stTextInput>div>input, .stSelectbox>div>div {
    border-radius: 14px !important;
    border: 1.5px solid #E2E8F0 !important;
    font-size: 0.9rem !important;
}
.stTextInput>div>input:focus, .stSelectbox>div>div:focus {
    border-color: #4F46E5 !important;
    box-shadow: 0 0 0 3px rgba(79,70,229,0.1) !important;
}

/* ---- 侧边栏隐藏 ---- */
div[data-testid="stSidebar"] { display: none !important; }

/* ---- Download 按钮 ---- */
.download-btn button {
    background: linear-gradient(135deg, #10B981, #059669) !important;
    box-shadow: 0 4px 12px rgba(16,185,129,0.2) !important;
}

/* ---- 打卡日历 ---- */
.calendar-header {
    text-align: center;
    font-weight: 600;
    font-size: 0.8rem;
    color: #64748B;
    padding: 4px 0;
}
.calendar-day {
    text-align: center;
    padding: 6px 0;
    font-size: 0.8rem;
    border-radius: 10px;
}

/* ---- expander ---- */
.streamlit-expanderHeader {
    border-radius: 14px !important;
    background: #F8FAFC !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
}
.streamlit-expanderContent {
    border-radius: 0 0 14px 14px !important;
    border: 1px solid #F1F5F9 !important;
    border-top: none !important;
}

/* ---- TTS 音频 ---- */
.stAudio { margin: 0.3rem 0; }

/* ---- 移动端 ---- */
@media (max-width: 640px) {
    .main .block-container { padding: 1rem 0.8rem 1.5rem 0.8rem; }
    .title-main { font-size: 1.15rem; }
    .stat-number { font-size: 1.5rem; }
    .tab-item { min-width: 52px; padding: 6px 4px; font-size: 0.7rem; }
    .tab-item .tab-icon { font-size: 1.1rem; }
    .top-nav { padding: 0.4rem 0.6rem; border-radius: 0 0 16px 16px; }
}
</style>
""", unsafe_allow_html=True)

# ========== 配置 ==========
SUBJECTS = ['语文', '数学', '英语']
SUBJECT_ICONS = {'语文': '📖', '数学': '🔢', '英语': '🔤'}
# 教材版本
SUBJECT_TEXTBOOKS = {
    '语文': '人教版',
    '数学': '苏教版',
    '英语': '译林版',
}
# 艾宾浩斯复习间隔（天）
EBBINGHAUS_INTERVALS = [1, 3, 7, 14, 30]

# 孩子信息：增加教材版本字段
CHILDREN = {
    "赵婉茹": {"grade": "小升初（原五年级）", "color": "#FF6B9D"},
    "赵中苧": {"grade": "小学二年级（原一年级）", "color": "#FFB347"},
    "宝贝1":  {"grade": "幼儿园大班",           "color": "#87CEEB"},
    "宝贝2":  {"grade": "小学五年级",           "color": "#98FB98"},
    "宝贝3":  {"grade": "初中一年级",           "color": "#DDA0DD"},
}

PASSWORDS = {
    "赵婉茹": "8888", "赵中苧": "8888", "宝贝1": "8888",
    "宝贝2": "8888", "宝贝3": "8888", "家长": "6666",
}

SUBJECTS = ["语文", "数学", "英语"]
ALL_USERS = list(CHILDREN.keys()) + ['家长']

# ========== 初始化数据库（自动检测 SQLite / TiDB） ==========
init_tables()

# ========== AI 客户端 ==========
def get_deepseek():
    key = st.secrets.get('DEEPSEEK_API_KEY', '')
    if not key:
        return None, 'DEEPSEEK_API_KEY 未配置'
    if not key.isascii():
        return None, 'DEEPSEEK_API_KEY 含中文字符，请填写有效的 Key'
    return OpenAI(api_key=key, base_url='https://api.deepseek.com'), None

def get_doubao():
    key = st.secrets.get('DOUBAO_API_KEY', '')
    if not key:
        return None, 'DOUBAO_API_KEY 未配置'
    if not key.isascii():
        return None, 'DOUBAO_API_KEY 含中文字符，请填写有效的 Key'
    return OpenAI(api_key=key, base_url='https://ark.cn-beijing.volces.com/api/v3'), None

# ========== 题目分析及讲解（豆包视觉） ==========
def doubao_analyze_image(image_bytes, child_name, grade):
    client, err = get_doubao()
    if err:
        return err, '未分类', True
    if not client:
        return 'DOUBAO_API_KEY 未配置', '未分类', True
    img_b64 = base64.b64encode(image_bytes).decode('utf-8')
    prompt = (
        f'你是一位极其认真负责的批改老师，请严格完成以下任务：\n\n'
        f'1. 第一行输出：**科目：** 语文 或 数学 或 英语（三选一）\n'
        f'2. 第二行输出：**正误：** 正确 或 错误（仔细判断答案是否正确，只有完全正确才算正确）\n'
        f'3. 第三行输出：**题目：** （抄写原题内容）\n'
        f'4. 然后空一行，输出 **讲解：** （用{child_name}能听懂的话详细讲解这道题，不管对错都要讲解）\n'
        f'   - 如果做对了：表扬并解释为什么对，巩固知识点\n'
        f'   - 如果做错了：指出错在哪里、为什么错、正确答案是什么、解题思路\n'
        f'5. 最后输出一句给{child_name}的鼓励语，多用emoji\n\n'
        f'注意事项：\n'
        f'- {child_name}是{grade}学生，语言要适合这个年龄段\n'
        f'- 批改要严格，不能放过任何小错误\n'
        f'- 讲解要详细，让{child_name}能听懂并学会\n'
        f'- 多用🌟🎉💪😊等emoji'
    )
    try:
        resp = client.chat.completions.create(
            model=st.secrets.get('DOUBAO_VISION_MODEL', 'Doubao-Seed-2.0-lite'),
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}'}},
                    {'type': 'text', 'text': prompt}
                ]
            }],
            max_tokens=1200
        )
        content = resp.choices[0].message.content
        # 提取科目
        subject = '未分类'
        for s in SUBJECTS:
            if f'科目：{s}' in content or f'科目:{s}' in content:
                subject = s
                break
        # 提取正误（默认错误，安全起见）
        is_correct = False
        if '正误：正确' in content or '正误:正确' in content:
            is_correct = True
        return content, subject, is_correct
    except Exception as e:
        err_msg = str(e).encode('ascii', errors='replace').decode('ascii')
        return f'分析失败: {err_msg}', '未分类', True

# ========== DeepSeek 文本生成 ==========
def deepseek_gen(prompt, max_tokens=700):
    client, err = get_deepseek()
    if err:
        return err
    if not client:
        return 'DEEPSEEK_API_KEY 未配置'
    try:
        resp = client.chat.completions.create(
            model=st.secrets.get('DEEPSEEK_TEXT_MODEL', 'deepseek-chat'),
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content
    except Exception as e:
        err_msg = str(e).encode('ascii', errors='replace').decode('ascii')
        return f'DeepSeek API 调用失败: {err_msg}'

# ========== 文字转语音（英语听力） ==========
def text_to_speech(text, lang='en'):
    """返回音频 bytes"""
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception as e:
        return None

# ========== 好词好句（含英语 + 中英双语） ==========
def get_daily_words(grade):
    today = str(date.today())
    row = db.fetchone(
        'SELECT content FROM daily_content WHERE content_date=? AND content_type=?',
        (today, 'daily_words_v2')
    )
    if row:
        return row[0]

    prompt = (
        f'请为{grade}学生生成今天的中英双语学习内容，要活泼有趣多用emoji！\n\n'
        '请用以下格式（用 >> 标记每种内容的开始）：\n\n'
        '=== 📖 语文 ===\n'
        '>>好词: 词语1（解释）（造句）\n'
        '>>好词: 词语2（解释）（造句）\n'
        '>>好词: 词语3（解释）（造句）\n'
        '>>好句: 句子（赏析）\n'
        '>>古诗: 古诗名和诗句（简单解释）\n\n'
        '=== 🔤 英语 ===\n'
        '>>单词: adventure（冒险；奇遇）例句:Reading a book is fun.\n'
        '>>单词: ocean（海洋）例句:I love the ocean.\n'
        '>>句子: Dont judge a book by its cover.（不要以貌取人）\n'
        '>>句子: Practice makes perfect.（熟能生巧）\n'
        '>>对话: A: Hello! B: Hi! How are you?\n\n'
        '=== 💪 今日励志 ===\n'
        '>>英文: Believe you can.\n'
        '>>中文: 相信自己。\n\n'
        '注意：英语内容要有中文翻译！句子必须是完整英文句子！'
    )
    content = deepseek_gen(prompt, 1000)
    db.execute(
        'INSERT INTO daily_content(content_date, content_type, content) VALUES(?,?,?)',
        (today, 'daily_words_v2', content)
    )
    db.commit()
    return content

# ========== 学习计划 ==========
def gen_study_plan(child_name, mode):
    rows = db.fetchall(
        'SELECT subject, question FROM wrong_questions '
        'WHERE child_name=? AND is_mastered=0 ORDER BY created_date DESC LIMIT 15',
        (child_name,)
    )
    weak = '\n'.join([f'- {s}: {str(q or "")[:30]}' for s, q in rows]) if rows else '暂无错题记录'
    grade = CHILDREN.get(child_name, {}).get('grade', '小学')
    prompt = (
        f'请为{child_name}（{grade}）制定一份有趣的{mode}每日学习计划。\n\n'
        f'近期未掌握的错题：\n{weak}\n\n'
        '请生成明天的安排（含中英文内容）：\n'
        '- 🌅 上午：错题复习（针对弱点）\n'
        '- ☀️ 下午：新知识学习\n'
        '- 🌙 晚上：阅读+好词好句+英语听力\n'
        '- 每个时段注明预计时长\n'
        '语气超级温柔鼓励，适合小朋友阅读，多用emoji！'
    )
    return deepseek_gen(prompt, 800)

# ========== 生成可打印 HTML（A4排版，答案分开） ==========
def generate_print_html(title, questions, answers=None):
    """生成 A4 打印用的 HTML，题目和答案分页"""
    q_html = ''
    for i, q in enumerate(questions, 1):
        q_html += f'<div class="q-item"><span class="q-num">{i}.</span> {q}</div>\n'

    a_html = ''
    if answers:
        for i, a in enumerate(answers, 1):
            a_html += f'<div class="a-item"><span class="a-num">{i}.</span> {a}</div>\n'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
@page {{ size: A4; margin: 1.5cm; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; color: #333; line-height: 1.8; padding: 20px; }}
h1 {{ text-align: center; font-size: 20px; color: #5a189a; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 3px solid #667eea; }}
h2 {{ font-size: 16px; color: #764ba2; margin: 15px 0 10px; }}
.header-info {{ text-align: center; color: #888; font-size: 12px; margin-bottom: 15px; }}
.q-item, .a-item {{ padding: 8px 0; border-bottom: 1px dashed #ddd; font-size: 14px; }}
.q-num, .a-num {{ display: inline-block; width: 28px; height: 28px; line-height: 28px; text-align: center; background: #667eea; color: #fff; border-radius: 50%; font-size: 12px; font-weight: bold; margin-right: 8px; }}
.a-num {{ background: #11998e; }}
.page-break {{ page-break-after: always; }}
.answer-page {{ page-break-before: always; }}
.answer-page h1 {{ color: #11998e; border-bottom-color: #11998e; }}
.footer {{ text-align: center; color: #aaa; font-size: 11px; margin-top: 30px; padding-top: 10px; border-top: 1px solid #eee; }}
@media print {{
    body {{ padding: 0; }}
    .no-print {{ display: none; }}
}}
</style>
</head>
<body>
<h1>🌟 {title}</h1>
<div class="header-info">📅 {date.today().strftime("%Y年%m月%d日")}</div>
<div class="page-break">
<h2>📝 题目</h2>
{q_html}
</div>
<div class="answer-page">
<h1>✅ 参考答案</h1>
{a_html if answers else '<p style="text-align:center;color:#aaa;">暂无答案</p>'}
<div class="footer">✨ 我家的AI错题本 — 加油，你是最棒的！</div>
</div>
</body>
</html>'''
    return html

# ========== 抽取英语内容用于听力 ==========
def extract_english_audio_pairs(content):
    """从今日内容中抽取出英语句子用于播放（支持 >> 前缀格式）"""
    pairs = []
    lines = content.split('\n')
    in_eng_section = False

    for line in lines:
        ls = line.strip()
        if not ls:
            continue
        # 检测英语区域
        if '=== 🔤 英语' in ls or ls.startswith('=== 英语'):
            in_eng_section = True
            continue
        if in_eng_section and ls.startswith('===') and '英语' not in ls:
            in_eng_section = False

        # >> 前缀格式解析（英语区内）
        if in_eng_section:
            # >>单词: adventure (翻译) 例句:...
            m = re.match(r'>>单词[：:]\s*(\w[\w\'-]*)\s*(.+?)(?:例句[：:]\s*(.*))?$', ls)
            if m:
                word = m.group(1)
                trans = m.group(2).strip()
                example = (m.group(3) or '').strip()
                # 清理翻译（去掉括号）
                trans = re.sub(r'[（(].*?[)）]', '', trans).strip()
                pairs.append(('word', word, trans, example))
                continue
            # >>句子: sentence（翻译）
            m = re.match(r'>>句子[：:]\s*(.+?[.!?])\s*[（(](.*?)[)）]', ls)
            if m:
                pairs.append(('sentence', m.group(1).strip(), m.group(2).strip(), ''))
                continue
            # >>对话: A: ... B: ...
            m = re.match(r'>>对话[：:]\s*(.*)', ls)
            if m:
                pairs.append(('dialogue', m.group(1).strip(), '', ''))

        # 全区域：励志名言
        m = re.match(r'>>英文[：:]\s*(.+)', ls)
        if m:
            pairs.append(('motto', m.group(1).strip(), '', ''))

    return pairs

# ========== 页面：登录 ==========
def page_login():
    st.markdown("""
    <div style="text-align:center;padding:2rem 0 1rem 0;">
        <div style="font-size:3rem;margin-bottom:0.5rem;">🌟</div>
        <div style="font-size:1.5rem;font-weight:800;color:#1E293B;letter-spacing:1px;">AI 错题本</div>
        <div style="font-size:0.85rem;color:#94A3B8;margin-top:4px;">每个孩子都有自己的学习空间</div>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 4, 1])
    with col:
        st.markdown('<div style="background:#F8FAFC;border-radius:20px;padding:1.5rem;">', unsafe_allow_html=True)
        user = st.selectbox('👤 选择孩子', ALL_USERS, label_visibility='collapsed')
        pwd = st.text_input('🔑', placeholder='输入密码', type='password', label_visibility='collapsed')
        st.markdown('<br>', unsafe_allow_html=True)
        if st.button('🚀 进入学习空间', use_container_width=True):
            if PASSWORDS.get(user) == pwd:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.session_state.auto_analysis = ''
                st.session_state.auto_subject = '数学'
                st.session_state.auto_is_correct = False
                st.session_state.auto_img = ''
                st.rerun()
            else:
                st.error('🙈 密码不对哦，再试试！')

# ========== 页面：首页 ==========
def page_home(user):
    grade = CHILDREN.get(user, {}).get('grade', '小学')
    st.markdown(f'<div class="title-main">🌈 {user} 的学习空间</div>', unsafe_allow_html=True)
    st.markdown(f'<p style="text-align:center;color:#888;">📚 {grade}</p>', unsafe_allow_html=True)

    today = str(date.today())
    if user in CHILDREN:
        total    = db.fetchone('SELECT COUNT(*) FROM wrong_questions WHERE child_name=?', (user,))[0]
        mastered = db.fetchone('SELECT COUNT(*) FROM wrong_questions WHERE child_name=? AND is_mastered=1', (user,))[0]
        month_n  = db.fetchone('SELECT COUNT(*) FROM checkins WHERE child_name=? AND checkin_date LIKE ?', (user, today[:7]+'%'))[0]
    else:
        total    = db.fetchone('SELECT COUNT(*) FROM wrong_questions')[0]
        mastered = db.fetchone('SELECT COUNT(*) FROM wrong_questions WHERE is_mastered=1')[0]
        month_n  = 0

    # 今日复习数量
    review_n = get_today_review_count(user)

    # 如果今天有复习任务，显示醒目提示
    if review_n > 0:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#EEF2FF,#E0E7FF);border-radius:16px;padding:1rem;text-align:center;margin-bottom:1rem;">'
            f'<div style="font-size:2rem;font-weight:800;color:#4F46E5;">{review_n}</div>'
            f'<div style="font-size:0.9rem;color:#4F46E5;">📋 今天有 {review_n} 道题需要复习（艾宾浩斯）</div>'
            f'<div style="font-size:0.75rem;color:#818CF8;margin-top:4px;">点击下方"复习"标签开始</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown('<div class="stat-grid">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{total}</div><div class="stat-label">📝 总错题</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-card"><div class="stat-number">{mastered}</div><div class="stat-label">✅ 已掌握</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{total - mastered}</div><div class="stat-label">🔥 待复习</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-card"><div class="stat-number">{month_n}</div><div class="stat-label">📅 本月打卡</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('---')
    st.markdown('### 💡 今日好词好句')
    with st.spinner('正在生成今日中英双语内容...'):
        result = get_daily_words(grade)
        st.info(result)

        # 英语听力播放
        pairs = extract_english_audio_pairs(result)
        if pairs:
            st.markdown('#### 🔈 英语听力')
            for item in pairs[:3]:
                ptype, text, trans, example = item
                audio_bytes = text_to_speech(text, 'en')
                if audio_bytes:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f'{text}')
                        if trans:
                            st.markdown(f'<small style="color:#888;">{trans}</small>', unsafe_allow_html=True)
                    with col2:
                        st.audio(audio_bytes, format='audio/mp3')

# ========== 页面：拍照录题 ==========
def page_upload(user):
    grade = CHILDREN.get(user, {}).get('grade', '小学')
    st.markdown('<div class="title-main">📸 拍照录错题</div>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center;color:#888;">🤖 豆包 Vision 自动识别 + 分析错因</p>', unsafe_allow_html=True)

    uploaded = st.file_uploader('📱 拍照上传作业', type=['jpg', 'jpeg', 'png'])
    if uploaded:
        st.image(Image.open(uploaded), caption='📷 上传的作业', use_container_width=True)
        if st.button('🤖 题目分析及讲解 🚀'):
            with st.spinner('正在批改和分析...'):
                analysis, subject, is_correct = doubao_analyze_image(uploaded.getvalue(), user, grade)
                st.session_state.auto_analysis = analysis
                st.session_state.auto_subject = subject
                st.session_state.auto_is_correct = is_correct
                st.session_state.auto_img = base64.b64encode(uploaded.getvalue()).decode('utf-8')

    st.markdown('---')
    analysis_text = st.session_state.get('auto_analysis', '')
    if analysis_text:
        is_correct = st.session_state.get('auto_is_correct', False)
        subj_val = st.session_state.get('auto_subject', '数学')

        # 显示对错结果
        if is_correct:
            st.success('🎉 这道题做对了！真棒！')
        else:
            st.error('❌ 这道题做错了，一起来看看怎么改正吧')

        # 显示分析内容
        st.markdown('### 📝 题目分析及讲解')
        st.markdown(analysis_text)

        # 只有做错的题才显示保存按钮
        if not is_correct:
            st.markdown('---')
            idx = SUBJECTS.index(subj_val) if subj_val in SUBJECTS else 0
            col1, col2 = st.columns(2)
            with col1:
                subject = st.selectbox('📚 科目', SUBJECTS, index=idx)
            with col2:
                reason = st.text_input('💭 错误原因（选填）', placeholder='粗心/不懂知识点...')
            if st.button('💾 保存到错题本（加入艾宾浩斯复习）'):
                qid = db.insert(
                    'INSERT INTO wrong_questions(child_name,subject,question,wrong_reason,ai_analysis,image_data,created_date) VALUES(?,?,?,?,?,?,?)',
                    (user, subject, analysis_text, reason, analysis_text, st.session_state.get('auto_img', ''), str(date.today()))
                )
                create_review_schedule(qid, user, subject, str(date.today()))
                st.success(f'✅ 已保存到错题本！已加入艾宾浩斯复习计划！')
                st.balloons()
                st.session_state.auto_analysis = ''
                st.session_state.auto_subject = '数学'
                st.session_state.auto_is_correct = False
                st.session_state.auto_img = ''
        else:
            st.markdown('---')
            st.markdown('💡 做对的题目不需要存入错题本，继续保持！🌟')

# ========== 页面：错题本 ==========
def page_wrong_list(user):
    st.markdown('<div class="title-main">📖 我的错题本</div>', unsafe_allow_html=True)
    tabs = st.tabs([f'{SUBJECT_ICONS[s]} {s}' for s in SUBJECTS])
    for tab, subject in zip(tabs, SUBJECTS):
        with tab:
            rows = db.fetchall(
                'SELECT id,question,wrong_reason,ai_analysis,created_date,is_mastered FROM wrong_questions WHERE child_name=? AND subject=? ORDER BY id DESC',
                (user, subject)
            )
            if not rows:
                st.markdown(f'### 🎉 {subject} 暂无错题，太棒了！')
                continue
            mastered_count = sum(1 for r in rows if r[5])
            st.markdown(f'共 **{len(rows)}** 题 | ✅ 已掌握 **{mastered_count}** 题')

            # 导出按钮
            q_list = [f'{r[4]}\n\n{str(r[1] or "")[:80]}...' for r in rows if not r[5]]
            a_list = [f'答案：{str(r[3] or "")[:100]}' for r in rows if not r[5]]
            if q_list:
                html = generate_print_html(
                    f'{user} {subject} 错题练习',
                    q_list,
                    a_list
                )
                st.download_button(
                    f'📥 导出{subject}错题练习（PDF打印）',
                    data=html.encode('utf-8'),
                    file_name=f'{user}_{subject}_错题练习.html',
                    mime='text/html',
                    key=f'pdf_{subject}'
                )
                st.markdown('<small>💡 下载后用浏览器打开 → 打印 → 另存为PDF</small>', unsafe_allow_html=True)

            show_mastered = st.checkbox('显示已掌握', key=f'show_{subject}')
            for qid, q, reason, analysis, d, is_mastered in rows:
                if is_mastered and not show_mastered:
                    continue
                icon = '✅' if is_mastered else '❌'
                with st.expander(f'{icon} {d} | {str(q or "")[:40]}...'):
                    st.markdown(f'**📝 题目：**\n{q}')
                    if reason:
                        st.markdown(f'**💭 错因：** {reason}')
                    st.markdown(f'**💡 分析：**\n{analysis}')
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if not is_mastered and st.button('✅ 已掌握', key=f'master_{qid}'):
                            db.execute('UPDATE wrong_questions SET is_mastered=1 WHERE id=?', (qid,))
                            db.commit()
                            st.rerun()
                    with col2:
                        if st.button('🔄 待复习', key=f'review_{qid}'):
                            db.execute('UPDATE wrong_questions SET is_mastered=0 WHERE id=?', (qid,))
                            db.commit()
                            st.rerun()
                    with col3:
                        if st.button('🗑️ 删除', key=f'del_{qid}'):
                            db.execute('DELETE FROM wrong_questions WHERE id=?', (qid,))
                            db.commit()
                            st.rerun()

# ========== 页面：打卡 ==========
def page_checkin(user):
    st.markdown('<div class="title-main">✅ 今日打卡</div>', unsafe_allow_html=True)
    today = str(date.today())
    exists = db.fetchone('SELECT 1 FROM checkins WHERE child_name=? AND checkin_date=?', (user, today))
    if exists:
        st.success(f'🎉 {user} 今天已打卡！坚持就是胜利！')
        st.balloons()
    else:
        note = st.text_area('今天学了什么？（选填）', placeholder='今天复习了乘法口诀，还学了3个英语单词...')
        if st.button('🌟 完成今日打卡！'):
            db.execute('INSERT INTO checkins(child_name,checkin_date,note) VALUES(?,?,?)', (user, today, note))
            db.commit()
            st.success('🎉 打卡成功！你真棒！')
            st.balloons()
            st.rerun()

    st.markdown('---')
    st.markdown('### 📅 本月打卡记录')
    records = db.fetchall('SELECT checkin_date FROM checkins WHERE child_name=? AND checkin_date LIKE ?', (user, today[:7]+'%'))
    checked_dates = {r[0] for r in records}
    today_dt = date.today()
    days_in_month = calendar.monthrange(today_dt.year, today_dt.month)[1]
    first_weekday = calendar.monthrange(today_dt.year, today_dt.month)[0]

    cols = st.columns(7)
    for i, h in enumerate(['一','二','三','四','五','六','日']):
        cols[i].markdown(f'<div class="calendar-header">{h}</div>', unsafe_allow_html=True)

    day_index = first_weekday
    day_num = 1
    while day_num <= days_in_month:
        row_cols = st.columns(7)
        for ci in range(7):
            if day_index % 7 == ci and day_num <= days_in_month:
                ds = f'{today_dt.year}-{today_dt.month:02d}-{day_num:02d}'
                if ds in checked_dates:
                    row_cols[ci].markdown(f'<div class="calendar-day" style="background:#a8edea;border-radius:50%;">✅<br>{day_num}</div>', unsafe_allow_html=True)
                elif ds == today:
                    row_cols[ci].markdown(f'<div class="calendar-day" style="background:#fed6e3;border-radius:50%;">🌟<br>{day_num}</div>', unsafe_allow_html=True)
                elif ds < today:
                    row_cols[ci].markdown(f'<div class="calendar-day">⬜<br>{day_num}</div>', unsafe_allow_html=True)
                else:
                    row_cols[ci].markdown(f'<div class="calendar-day" style="color:#ccc;">{day_num}</div>', unsafe_allow_html=True)
                day_index += 1
                day_num += 1

# ========== 页面：学习计划 ==========
def page_plan(user):
    st.markdown('<div class="title-main">📅 学习计划</div>', unsafe_allow_html=True)
    mode = st.selectbox('选择计划类型', ['暑假计划', '寒假计划', '周末计划', '预习计划'])
    if st.button('🤖 AI 生成今日学习计划'):
        with st.spinner('DeepSeek 正在为你量身定制...'):
            plan = gen_study_plan(user, mode)
        st.markdown('### 📋 你的专属计划')
        st.markdown(plan)
        db.execute('INSERT INTO daily_content(content_date,content_type,content) VALUES(?,?,?)',
                   (str(date.today()), f'plan_{user}', plan))
        db.commit()

        # PDF 导出
        html = generate_print_html(
            f'{user} {mode}',
            [plan],
            []
        )
        st.download_button('📥 导出计划（PDF打印）', data=html.encode('utf-8'),
                          file_name=f'{user}_学习计划.html', mime='text/html')

    st.markdown('---')
    st.markdown('### 📚 历史计划')
    plans = db.fetchall(
        'SELECT content_date, content FROM daily_content WHERE content_type=? ORDER BY content_date DESC LIMIT 7',
        (f'plan_{user}',)
    )
    for p_date, p_content in plans:
        with st.expander(f'📅 {p_date}'):
            st.markdown(str(p_content or ''))

# ========== 页面：好词好句 ==========
def page_daily_words(user):
    st.markdown('<div class="title-main">🌟 今日中英双语</div>', unsafe_allow_html=True)
    grade = CHILDREN.get(user, {}).get('grade', '小学')

    with st.spinner('正在生成今日内容...'):
        content = get_daily_words(grade)

    st.markdown(content)

    # 英语听力专区
    st.markdown('---')
    st.markdown('### 🔈 英语听力')
    pairs = extract_english_audio_pairs(content)
    if pairs:
        for item in pairs:
            ptype, text, trans, example = item
            audio_bytes = text_to_speech(text, 'en')
            if audio_bytes:
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    icon = '🔤' if ptype == 'word' else '💬' if ptype == 'sentence' else '🎯'
                    st.markdown(f'{icon} **{text}**')
                    if trans:
                        st.markdown(f'<small style="color:#888;">{trans}</small>', unsafe_allow_html=True)
                with c2:
                    st.audio(audio_bytes, format='audio/mp3')
    else:
        st.info('今日暂无英语内容，点击下方按钮刷新')

    st.markdown('---')
    if st.button('🔄 换一批新内容'):
        db.execute('DELETE FROM daily_content WHERE content_date=? AND content_type=?',
                   (str(date.today()), 'daily_words_v2'))
        db.commit()
        st.rerun()

    # PDF 导出
    html = generate_print_html(
        f'{user} 今日学习（{grade}）',
        [content],
        []
    )
    st.download_button('📥 导出今日内容（PDF打印）', data=html.encode('utf-8'),
                      file_name=f'{user}_今日学习_{date.today()}.html', mime='text/html')

# ========== 页面：今日复习（艾宾浩斯） ==========
def page_review(user):
    st.markdown('<div class="title-main">📋 今日复习</div>', unsafe_allow_html=True)
    grade = CHILDREN.get(user, {}).get('grade', '小学')

    reviews = get_today_reviews(user)
    if not reviews:
        st.success('🎉 今天没有到期的复习任务，太棒啦！')
        st.balloons()
        return

    st.info(f'📅 今天有 **{len(reviews)}** 道题需要复习（艾宾浩斯记忆法）')
    st.markdown('---')

    # 按科目分组
    by_subject = {}
    for r in reviews:
        rid, qid, subj, stage, orig_date, q_text, reason, analysis, img = r
        by_subject.setdefault(subj, []).append(r)

    all_questions = []
    all_answers = []

    for subj in SUBJECTS:
        if subj not in by_subject:
            continue
        st.markdown(f'### {SUBJECT_ICONS[subj]} {subj}（{len(by_subject[subj])}题）')
        for r in by_subject[subj]:
            rid, qid, subj_s, stage, orig_date, q_text, reason, analysis, img = r
            days_ago = (date.today() - date.fromisoformat(orig_date)).days
            stage_label = {1:'第1次',2:'第2次',3:'第3次',4:'第4次',5:'第5次'}.get(stage, f'第{stage}次')
            interval_label = {1:'1天后',2:'3天后',3:'7天后',4:'14天后',5:'30天后'}.get(stage, '')

            st.markdown(f'''
            <div style="background:#F8FAFC;border-radius:16px;padding:1rem;margin-bottom:0.8rem;border-left:4px solid {SUBJECT_ICONS.get(subj_s,"#4F46E5")};">
                <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#94A3B8;">
                    <span>📅 原题日期：{orig_date}（距今 {days_ago} 天）</span>
                    <span>🔄 {stage_label}（{interval_label}）</span>
                </div>
                <div style="margin:0.5rem 0;font-size:0.9rem;">{str(q_text or "")[:120]}</div>
            </div>
            ''', unsafe_allow_html=True)

            # 收集题目和答案用于 PDF
            all_questions.append(f'【{subj_s}】{orig_date}\n{str(q_text or "")[:120]}')
            all_answers.append(f'【{subj_s}】{orig_date}\n分析：{str(analysis or "")[:150]}')

            col1, col2 = st.columns([3, 1])
            with col1:
                with st.expander('💡 查看答案与解析'):
                    st.markdown(f'**📝 原题：**\n{q_text}')
                    if reason:
                        st.markdown(f'**💭 当初的错因：** {reason}')
                    st.markdown(f'**💡 解析：**\n{analysis}')
            with col2:
                if st.button('✅ 复习完成', key=f'review_done_{rid}', use_container_width=True):
                    mark_review_done(rid)
                    st.success('🎉 该题复习完成！')
                    st.rerun()

    # PDF 导出
    st.markdown('---')
    if all_questions:
        html = generate_print_html(
            f'{user} 今日艾宾浩斯复习（{date.today()}）',
            all_questions,
            all_answers
        )
        st.download_button('📥 导出今日复习题（PDF打印）',
                          data=html.encode('utf-8'),
                          file_name=f'{user}_今日复习_{date.today()}.html',
                          mime='text/html',
                          use_container_width=True)
        st.caption('💡 下载后用浏览器打开 → 打印 → 另存为PDF，题目和答案分页')

# ========== 页面：家长总览 ==========
def page_parent():
    st.markdown('<div class="title-main">👨‍👩‍👧‍👦 家长总览</div>', unsafe_allow_html=True)
    today = str(date.today())

    # 每个孩子的卡片
    for child, info in CHILDREN.items():
        total    = db.fetchone('SELECT COUNT(*) FROM wrong_questions WHERE child_name=?', (child,))[0]
        mastered = db.fetchone('SELECT COUNT(*) FROM wrong_questions WHERE child_name=? AND is_mastered=1', (child,))[0]
        checked  = db.fetchone('SELECT COUNT(*) FROM checkins WHERE child_name=? AND checkin_date=?', (child, today))[0]
        color    = info['color']
        status   = '✅ 已打卡' if checked else '❌ 未打卡'
        st.markdown(
            f'<div style="background:linear-gradient(135deg,{color}33,{color}11);border-left:4px solid {color};border-radius:15px;padding:0.8rem 1rem;margin-bottom:0.5rem;">'
            f'<h3 style="margin:0;">{child} <small style="color:#888;">{info["grade"]}</small></h3>'
            f'📝 错题 {total} 题 | ✅ 掌握 {mastered} 题 | {status}'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown('---')
    rows = db.fetchall('SELECT child_name, subject, COUNT(*) FROM wrong_questions GROUP BY child_name, subject')
    if rows:
        df = pd.DataFrame(rows, columns=['孩子','科目','错题数'])
        fig = px.bar(df, x='孩子', y='错题数', color='科目', barmode='group',
                     title='📊 各孩子错题分布',
                     color_discrete_map={'语文':'#FF6B9D','数学':'#667eea','英语':'#11998e'})
        fig.update_layout(font=dict(size=12))
        st.plotly_chart(fig, use_container_width=True)

# ========== 主流程 ==========
def main_app():
    user = st.session_state.user
    is_parent = user == '家长'
    grade = CHILDREN.get(user, {}).get('grade', '') if not is_parent else ''
    page = st.session_state.get('nav_page', '🏠 首页')

    # 短图标与完整 page key 的映射
    icon_page_map = {
        '🏠': '🏠 首页', '📸': '📸 拍照', '📖': '📖 错题本', '📋': '📋 复习',
        '✅': '✅ 打卡', '📅': '📅 计划', '🌟': '🌟 中英双语',
        '👨‍👩‍👧': '👨‍👩‍👧‍👦 总览',
    }
    reverse_map = {v: k for k, v in icon_page_map.items()}
    current_short = reverse_map.get(page, '🏠')

    if is_parent:
        items = [('🏠', '首页'), ('👨‍👩‍👧', '总览')]
    else:
        items = [('🏠', '首页'), ('📸', '拍照'), ('📖', '错题'), ('📋', '复习'), ('✅', '打卡'), ('📅', '计划'), ('🌟', '双语')]

    # ===== 顶部导航栏 =====
    grade_text = grade or ''
    textbook_info = f'📖{SUBJECT_TEXTBOOKS["语文"]} 🔢{SUBJECT_TEXTBOOKS["数学"]} 🔤{SUBJECT_TEXTBOOKS["英语"]}' if not is_parent else ''

    st.markdown(f'''
    <div class="top-nav">
        <div class="top-nav-user">🌟 {user} <small>{grade_text}</small></div>
        <small style="color:rgba(255,255,255,0.7);font-size:0.6rem;">{textbook_info}</small>
    </div>
    ''', unsafe_allow_html=True)

    # Tab 导航按钮
    cols = st.columns(len(items))
    for i, (icon, label) in enumerate(items):
        with cols[i]:
            is_active = (icon == current_short)
            if is_active:
                st.markdown(
                    f'<div style="text-align:center;background:#EEF2FF;border-radius:14px;padding:10px 4px;'
                    f'box-shadow:0 2px 8px rgba(79,70,229,0.12);">'
                    f'<div style="font-size:1.3rem;line-height:1.4;">{icon}</div>'
                    f'<div style="font-size:0.7rem;font-weight:700;color:#4F46E5;">{label}</div></div>',
                    unsafe_allow_html=True
                )
            else:
                if st.button(f'{icon}\n{label}', key=f'tab_{icon}', use_container_width=True):
                    st.session_state.nav_page = icon_page_map.get(icon, icon)
                    st.rerun()

    # ===== 页面路由 =====
    if   page == '🏠 首页':       page_home(user)
    elif page == '📸 拍照':        page_upload(user)
    elif page == '📖 错题本':      page_wrong_list(user)
    elif page == '📋 复习':        page_review(user)
    elif page == '✅ 打卡':        page_checkin(user)
    elif page == '📅 计划':        page_plan(user)
    elif page == '🌟 中英双语':    page_daily_words(user)
    elif page == '👨‍👩‍👧‍👦 总览':  page_parent()

# ========== 启动 ==========
if 'logged_in' not in st.session_state:
    st.session_state.logged_in     = False
    st.session_state.user          = ''
    st.session_state.auto_analysis   = ''
    st.session_state.auto_subject    = '数学'
    st.session_state.auto_is_correct = False
    st.session_state.auto_img        = ''

if not st.session_state.logged_in:
    page_login()
else:
    main_app()
