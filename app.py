import streamlit as st
import sqlite3
import base64
import calendar
from datetime import date
from openai import OpenAI
from PIL import Image
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="📚 我家的AI错题本", page_icon="🌟", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.stApp { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.main .block-container { background: rgba(255,255,255,0.96); border-radius: 20px; padding: 2rem; margin: 1rem; box-shadow: 0 8px 32px rgba(0,0,0,0.12); }
.stButton>button { border-radius: 24px !important; font-weight: 700 !important; border: none !important; background: linear-gradient(135deg, #667eea, #764ba2) !important; color: white !important; padding: 0.5rem 2rem !important; transition: all 0.3s ease !important; }
.stButton>button:hover { transform: translateY(-2px) !important; box-shadow: 0 5px 15px rgba(102,126,234,0.4) !important; }
.title-main { font-size: 2.3rem; font-weight: 800; background: linear-gradient(135deg, #667eea, #f093fb); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; padding: 0.8rem 0; }
.stat-card { background: linear-gradient(135deg, #a8edea, #fed6e3); border-radius: 20px; padding: 1.2rem; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.08); margin-bottom: 1rem; }
.stat-number { font-size: 2.3rem; font-weight: 800; color: #5a189a; }
div[data-testid="stSidebar"] { background: linear-gradient(180deg, #2d1b69 0%, #11998e 100%) !important; }
div[data-testid="stSidebar"] * { color: white !important; }
</style>
""", unsafe_allow_html=True)

SUBJECTS = ['语文', '数学', '英语']
SUBJECT_ICONS = {'语文': '📖', '数学': '🔢', '英语': '🔤'}

CHILDREN = {
    "赵婉茹": {"grade": "小学五年级", "color": "#FF6B9D"},
    "赵中苧": {"grade": "小学一年级", "color": "#FFB347"},
    "宝贝1":  {"grade": "幼儿园大班",  "color": "#87CEEB"},
    "宝贝2":  {"grade": "小学五年级", "color": "#98FB98"},
    "宝贝3":  {"grade": "初中一年级", "color": "#DDA0DD"},
}

PASSWORDS = {
    "赵婉茹":  "8888",
    "赵中苧":  "8888",
    "宝贝1":  "8888",
    "宝贝2":  "8888",
    "宝贝3":  "8888",
    "家长":  "6666",
}

SUBJECTS = ["语文", "数学", "英语"]

ALL_USERS = list(CHILDREN.keys()) + ['家长']
DB = 'study.db'

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        'CREATE TABLE IF NOT EXISTS wrong_questions ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, child_name TEXT, subject TEXT, '
        'question TEXT, wrong_reason TEXT, ai_analysis TEXT, image_data TEXT, '
        'created_date TEXT, is_mastered INTEGER DEFAULT 0, review_count INTEGER DEFAULT 0)'
    )
    c.execute(
        'CREATE TABLE IF NOT EXISTS checkins ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, child_name TEXT, checkin_date TEXT, note TEXT)'
    )
    c.execute(
        'CREATE TABLE IF NOT EXISTS daily_content ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, content_date TEXT, content_type TEXT, content TEXT)'
    )
    conn.commit()
    conn.close()

init_db()

def get_deepseek():
    key = st.secrets.get('DEEPSEEK_API_KEY', '')
    if not key:
        return None
    return OpenAI(api_key=key, base_url='https://api.deepseek.com')

def get_doubao():
    key = st.secrets.get('DOUBAO_API_KEY', '')
    if not key:
        return None
    return OpenAI(api_key=key, base_url='https://ark.cn-beijing.volces.com/api/v3')

def doubao_analyze_image(image_bytes, child_name, grade):
    client = get_doubao()
    if not client:
        return '请先配置 DOUBAO_API_KEY', '未分类'
    img_b64 = base64.b64encode(image_bytes).decode()
    prompt = (
        f'你是一位耐心的老师，请看这道题的图片，完成以下任务：\n'
        f'1. 第一行必须输出：科目：语文 或 科目：数学 或 科目：英语（三选一）\n'
        f'2. 识别题目完整内容\n'
        f'3. 用小朋友能懂的话分析为什么容易做错\n'
        f'4. 给出解题思路或记忆方法\n'
        f'5. 给{child_name}一句鼓励的话\n'
        f'语言风格适合{grade}学生，多用emoji。'
    )
    try:
        resp = client.chat.completions.create(
            model=st.secrets.get('DOUBAO_VISION_MODEL', 'doubao-1-5-vision-pro-32k'),
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}'}},
                    {'type': 'text', 'text': prompt}
                ]
            }],
            max_tokens=900
        )
        content = resp.choices[0].message.content
        subject = '未分类'
        for s in SUBJECTS:
            if f'科目：{s}' in content or f'科目:{s}' in content:
                subject = s
                break
        return content, subject
    except Exception as e:
        return f'豆包分析失败：{e}', '未分类'

def deepseek_gen(prompt, max_tokens=700):
    client = get_deepseek()
    if not client:
        return '请先配置 DEEPSEEK_API_KEY'
    try:
        resp = client.chat.completions.create(
            model=st.secrets.get('DEEPSEEK_TEXT_MODEL', 'deepseek-chat'),
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f'DeepSeek生成失败：{e}'

def get_daily_words(grade):
    today = str(date.today())
    conn = sqlite3.connect(DB)
    row = conn.execute(
        'SELECT content FROM daily_content WHERE content_date=? AND content_type=?',
        (today, 'daily_words')
    ).fetchone()
    conn.close()
    if row:
        return row[0]
    prompt = (
        f'请为{grade}学生生成今天的学习内容：\n'
        '1. 🌟 好词3个（词语+简单解释+造句）\n'
        '2. ✨ 好句2句（优美句子+简短赏析）\n'
        '3. 📚 名著小故事1个（100字以内，适合小朋友）\n'
        '4. 💪 今日励志一句话\n'
        '风格活泼有趣，多用emoji。'
    )
    content = deepseek_gen(prompt, 700)
    conn = sqlite3.connect(DB)
    conn.execute(
        'INSERT INTO daily_content(content_date, content_type, content) VALUES(?,?,?)',
        (today, 'daily_words', content)
    )
    conn.commit()
    conn.close()
    return content

def gen_study_plan(child_name, mode):
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        'SELECT subject, question FROM wrong_questions '
        'WHERE child_name=? AND is_mastered=0 ORDER BY created_date DESC LIMIT 15',
        (child_name,)
    ).fetchall()
    conn.close()
    weak = '\n'.join([f'- {s}: {q[:30]}' for s, q in rows]) if rows else '暂无错题记录'
    grade = CHILDREN.get(child_name, {}).get('grade', '小学')
    prompt = (
        f'请为{child_name}（{grade}）制定一份{mode}每日学习计划。\n\n'
        f'近期未掌握的错题：\n{weak}\n\n'
        '请生成明天的安排，包含：\n'
        '- 上午：错题复习（针对弱点）\n'
        '- 下午：新知识预习\n'
        '- 晚上：阅读+好词好句\n'
        '- 每个时段注明预计时长\n'
        '语气温柔鼓励，适合小朋友阅读，多用emoji。'
    )
    return deepseek_gen(prompt, 800)

def page_login():
    st.markdown('<div class="title-main">📚 我家的AI错题本 🌟</div>', unsafe_allow_html=True)
    st.markdown('<br>', unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('### 👋 请选择账号登录')
        user = st.selectbox('选择你是谁', ALL_USERS)
        pwd = st.text_input('输入密码 🔑', type='password')
        if st.button('🚀 进入我的学习空间', use_container_width=True):
            if PASSWORDS.get(user) == pwd:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.session_state.auto_analysis = ''
                st.session_state.auto_subject = '数学'
                st.session_state.auto_img = ''
                st.rerun()
            else:
                st.error('密码不对哦，再试试！🙈')

def page_home(user):
    grade = CHILDREN.get(user, {}).get('grade', '')
    st.markdown(f'<div class="title-main">🌈 {user}的学习空间</div>', unsafe_allow_html=True)
    conn = sqlite3.connect(DB)
    today = str(date.today())
    if user in CHILDREN:
        total    = conn.execute('SELECT COUNT(*) FROM wrong_questions WHERE child_name=?', (user,)).fetchone()[0]
        mastered = conn.execute('SELECT COUNT(*) FROM wrong_questions WHERE child_name=? AND is_mastered=1', (user,)).fetchone()[0]
        month_n  = conn.execute('SELECT COUNT(*) FROM checkins WHERE child_name=? AND checkin_date LIKE ?', (user, today[:7]+'%')).fetchone()[0]
    else:
        total    = conn.execute('SELECT COUNT(*) FROM wrong_questions').fetchone()[0]
        mastered = conn.execute('SELECT COUNT(*) FROM wrong_questions WHERE is_mastered=1').fetchone()[0]
        month_n  = 0
    conn.close()
    c1, c2, c3, c4 = st.columns(4)
    for col, num, label in [(c1, total, '📝 总错题数'), (c2, mastered, '✅ 已掌握'), (c3, total - mastered, '🔥 待复习'), (c4, month_n, '📅 本月打卡')]:
        with col:
            st.markdown(f'<div class="stat-card"><div class="stat-number">{num}</div><div>{label}</div></div>', unsafe_allow_html=True)
    st.markdown('---')
    st.markdown('### 💡 今日好词好句')
    with st.spinner('正在生成今日内容...'):
        st.info(get_daily_words(grade or '小学'))

def page_upload(user):
    grade = CHILDREN.get(user, {}).get('grade', '小学')
    st.markdown('<div class="title-main">📸 拍照录错题</div>', unsafe_allow_html=True)
    st.markdown('**豆包 Vision 一步完成：识别题目 + 判断科目 + 分析错因**')
    left, right = st.columns([1, 1])
    with left:
        uploaded = st.file_uploader('拍照或选择图片', type=['jpg', 'jpeg', 'png'])
        if uploaded:
            st.image(Image.open(uploaded), caption='上传的题目', use_container_width=True)
            if st.button('🤖 豆包识别并分析', use_container_width=True):
                with st.spinner('豆包正在看题目...'):
                    analysis, subject = doubao_analyze_image(uploaded.getvalue(), user, grade)
                    st.session_state.auto_analysis = analysis
                    st.session_state.auto_subject = subject
                    st.session_state.auto_img = base64.b64encode(uploaded.getvalue()).decode()
                st.success(f'识别完成，科目：{subject}')
    with right:
        st.markdown('#### ✏️ 分析结果（可修改）')
        analysis_text = st.text_area('AI分析内容', value=st.session_state.get('auto_analysis', ''), height=260)
        subj_val = st.session_state.get('auto_subject', '数学')
        idx = SUBJECTS.index(subj_val) if subj_val in SUBJECTS else 0
        subject = st.selectbox('科目', SUBJECTS, index=idx)
        reason = st.text_area('我的错误原因（选填）', placeholder='比如：粗心算错，或者不懂这个知识点...')
        if st.button('💾 保存到错题本', use_container_width=True):
            if not analysis_text.strip():
                st.warning('请先上传图片并识别，或手动输入内容')
            else:
                conn = sqlite3.connect(DB)
                conn.execute(
                    'INSERT INTO wrong_questions(child_name,subject,question,wrong_reason,ai_analysis,image_data,created_date) VALUES(?,?,?,?,?,?,?)',
                    (user, subject, analysis_text, reason, analysis_text, st.session_state.get('auto_img', ''), str(date.today()))
                )
                conn.commit()
                conn.close()
                st.success(f'✅ 已保存到【{SUBJECT_ICONS[subject]} {subject}】错题本！')
                st.session_state.auto_analysis = ''
                st.session_state.auto_subject = '数学'
                st.session_state.auto_img = ''

def page_wrong_list(user):
    st.markdown('<div class="title-main">📖 我的错题本</div>', unsafe_allow_html=True)
    conn = sqlite3.connect(DB)
    tabs = st.tabs([f'{SUBJECT_ICONS[s]} {s}' for s in SUBJECTS])
    for tab, subject in zip(tabs, SUBJECTS):
        with tab:
            rows = conn.execute(
                'SELECT id,question,wrong_reason,ai_analysis,created_date,is_mastered FROM wrong_questions WHERE child_name=? AND subject=? ORDER BY id DESC',
                (user, subject)
            ).fetchall()
            if not rows:
                st.markdown(f'### 🎉 {subject}暂无错题，厉害！')
                continue
            mastered_count = sum(1 for r in rows if r[5])
            st.markdown(f'共 **{len(rows)}** 题 | 已掌握 **{mastered_count}** 题 🏆')
            show_mastered = st.checkbox('显示已掌握的题目', key=f'show_{subject}')
            for qid, q, reason, analysis, d, is_mastered in rows:
                if is_mastered and not show_mastered:
                    continue
                icon = '✅' if is_mastered else '❌'
                with st.expander(f'{icon} {d}  |  {q[:45]}...'):
                    st.markdown('**完整内容：**')
                    st.write(q)
                    if reason:
                        st.markdown(f'**我的错误原因：** {reason}')
                    st.markdown('---')
                    st.markdown(analysis)
                    col1, col2 = st.columns(2)
                    with col1:
                        if not is_mastered and st.button('✅ 标记已掌握', key=f'master_{qid}'):
                            conn.execute('UPDATE wrong_questions SET is_mastered=1 WHERE id=?', (qid,))
                            conn.commit()
                            st.rerun()
                    with col2:
                        if st.button('🗑️ 删除', key=f'del_{qid}'):
                            conn.execute('DELETE FROM wrong_questions WHERE id=?', (qid,))
                            conn.commit()
                            st.rerun()
    conn.close()

def page_checkin(user):
    st.markdown('<div class="title-main">✅ 今日打卡</div>', unsafe_allow_html=True)
    today = str(date.today())
    conn = sqlite3.connect(DB)
    exists = conn.execute('SELECT 1 FROM checkins WHERE child_name=? AND checkin_date=?', (user, today)).fetchone()
    if exists:
        st.success(f'🎉 {user}今天已经打卡啦！坚持就是胜利！')
        st.balloons()
    else:
        note = st.text_area('今天学了什么？有什么收获？（选填）', placeholder='今天复习了乘法口诀，还学了3个新词语...')
        if st.button('🌟 完成今日打卡！', use_container_width=True):
            conn.execute('INSERT INTO checkins(child_name,checkin_date,note) VALUES(?,?,?)', (user, today, note))
            conn.commit()
            st.success('🎉 打卡成功！你真棒！')
            st.balloons()
            st.rerun()
    st.markdown('---')
    st.markdown('### 📅 本月打卡记录')
    records = conn.execute('SELECT checkin_date FROM checkins WHERE child_name=? AND checkin_date LIKE ?', (user, today[:7]+'%')).fetchall()
    conn.close()
    checked_dates = {r[0] for r in records}
    today_dt = date.today()
    days_in_month = calendar.monthrange(today_dt.year, today_dt.month)[1]
    first_weekday = calendar.monthrange(today_dt.year, today_dt.month)[0]
    header_cols = st.columns(7)
    for i, h in enumerate(['一','二','三','四','五','六','日']):
        header_cols[i].markdown(f'<center><b>{h}</b></center>', unsafe_allow_html=True)
    day_index = first_weekday
    day_num = 1
    while day_num <= days_in_month:
        row_cols = st.columns(7)
        for col_i in range(7):
            if day_index % 7 == col_i and day_num <= days_in_month:
                day_str = f'{today_dt.year}-{today_dt.month:02d}-{day_num:02d}'
                if day_str in checked_dates:
                    row_cols[col_i].markdown(f'<center>✅<br><b>{day_num}</b></center>', unsafe_allow_html=True)
                elif day_str == today:
                    row_cols[col_i].markdown(f'<center>🌟<br><b>{day_num}</b></center>', unsafe_allow_html=True)
                elif day_str < today:
                    row_cols[col_i].markdown(f'<center>⬜<br>{day_num}</center>', unsafe_allow_html=True)
                else:
                    row_cols[col_i].markdown(f'<center><span style="color:#ccc">{day_num}</span></center>', unsafe_allow_html=True)
                day_index += 1
                day_num += 1

def page_plan(user):
    st.markdown('<div class="title-main">📅 假期学习计划</div>', unsafe_allow_html=True)
    mode = st.selectbox('选择计划类型', ['暑假计划', '寒假计划', '周末计划', '下学期预习计划'])
    if st.button('🤖 AI帮我生成今日学习计划', use_container_width=True):
        with st.spinner('DeepSeek正在为你量身定制...'):
            plan = gen_study_plan(user, mode)
        st.markdown('### 📋 你的专属学习计划')
        st.markdown(plan)
        conn = sqlite3.connect(DB)
        conn.execute('INSERT INTO daily_content(content_date,content_type,content) VALUES(?,?,?)', (str(date.today()), f'plan_{user}', plan))
        conn.commit()
        conn.close()
    st.markdown('---')
    st.markdown('### 📚 历史计划')
    conn = sqlite3.connect(DB)
    plans = conn.execute('SELECT content_date, content FROM daily_content WHERE content_type=? ORDER BY content_date DESC LIMIT 7', (f'plan_{user}',)).fetchall()
    conn.close()
    for p_date, p_content in plans:
        with st.expander(f'📅 {p_date} 的学习计划'):
            st.markdown(p_content)

def page_daily_words(user):
    st.markdown('<div class="title-main">🌟 今日好词好句</div>', unsafe_allow_html=True)
    grade = CHILDREN.get(user, {}).get('grade', '小学')
    with st.spinner('正在生成今日内容...'):
        content = get_daily_words(grade)
    st.markdown(content)
    st.markdown('---')
    if st.button('🔄 换一批新内容'):
        conn = sqlite3.connect(DB)
        conn.execute('DELETE FROM daily_content WHERE content_date=? AND content_type=?', (str(date.today()), 'daily_words'))
        conn.commit()
        conn.close()
        st.rerun()

def page_parent():
    st.markdown('<div class="title-main">👨‍👩‍👧‍👦 家长总览</div>', unsafe_allow_html=True)
    conn = sqlite3.connect(DB)
    today = str(date.today())
    cols = st.columns(len(CHILDREN))
    for col, (child, info) in zip(cols, CHILDREN.items()):
        total    = conn.execute('SELECT COUNT(*) FROM wrong_questions WHERE child_name=?', (child,)).fetchone()[0]
        mastered = conn.execute('SELECT COUNT(*) FROM wrong_questions WHERE child_name=? AND is_mastered=1', (child,)).fetchone()[0]
        checked  = conn.execute('SELECT COUNT(*) FROM checkins WHERE child_name=? AND checkin_date=?', (child, today)).fetchone()[0]
        color    = info['color']
        status   = '✅ 已打卡' if checked else '❌ 未打卡'
        with col:
            st.markdown(
                f'<div style="background:linear-gradient(135deg,{color}33,{color}11);border-left:4px solid {color};border-radius:15px;padding:1rem;text-align:center;">'
                f'<h3>{child}</h3><p>错题 {total} 题</p><p>掌握 {mastered} 题</p><p>{status}</p></div>',
                unsafe_allow_html=True
            )
    st.markdown('---')
    rows = conn.execute('SELECT child_name, subject, COUNT(*) FROM wrong_questions GROUP BY child_name, subject').fetchall()
    conn.close()
    if rows:
        df = pd.DataFrame(rows, columns=['孩子','科目','错题数'])
        fig = px.bar(df, x='孩子', y='错题数', color='科目', barmode='group', title='各孩子错题科目分布',
                    color_discrete_map={'语文':'#FF6B9D','数学':'#667eea','英语':'#11998e'})
        st.plotly_chart(fig, use_container_width=True)

def main_app():
    user = st.session_state.user
    is_parent = user == '家长'
    with st.sidebar:
        st.markdown(f'## 👤 {user}')
        if not is_parent:
            st.markdown(f'📚 {CHILDREN[user]["grade"]}')
        st.markdown('---')
        if is_parent:
            menu = ['🏠 首页', '👨‍👩‍👧‍👦 家长总览']
        else:
            menu = ['🏠 首页', '📸 拍照录题', '📖 错题本', '✅ 打卡', '📅 假期计划', '🌟 好词好句']
        page = st.radio('功能菜单', menu)
        st.markdown('---')
        if st.button('🚪 退出登录'):
            st.session_state.logged_in = False
            st.rerun()
    if   page == '🏠 首页':          page_home(user)
    elif page == '📸 拍照录题':       page_upload(user)
    elif page == '📖 错题本':         page_wrong_list(user)
    elif page == '✅ 打卡':           page_checkin(user)
    elif page == '📅 假期计划':       page_plan(user)
    elif page == '🌟 好词好句':       page_daily_words(user)
    elif page == '👨‍👩‍👧‍👦 家长总览': page_parent()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in     = False
    st.session_state.user          = ''
    st.session_state.auto_analysis = ''
    st.session_state.auto_subject  = '数学'
    st.session_state.auto_img      = ''

if not st.session_state.logged_in:
    page_login()
else:
    main_app()