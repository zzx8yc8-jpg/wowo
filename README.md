# 📚 我家的AI错题本

基于 **Streamlit** 的智能错题管理系统，支持多孩子账号、拍照录题、AI 分析错因、学习打卡、好词好句生成等功能。

## ✨ 功能特点

- 👨‍👩‍👧‍👦 **多孩子支持** — 每个孩子独立账号，各自管理错题
- 📸 **拍照录题** — 豆包 Vision 自动识别题目内容，判断科目，分析错因
- 🤖 **AI 好词好句** — 每日自动生成适合年级的学习内容（DeepSeek）
- 📅 **学习打卡** — 月度日历视图，记录每日学习
- 📖 **错题本** — 按科目分类，标记已掌握/待复习
- 📊 **家长总览** — 统计图表，掌握每个孩子的学习情况

## 🚀 本地运行

```powershell
# 方式一：使用启动脚本
.\start.ps1

# 方式二：手动设置编码后启动
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
streamlit run app.py
```

打开浏览器访问 http://localhost:8501

## 🗝️ 账号密码

| 孩子 | 密码 | 年级 |
|------|------|------|
| 赵婉茹 | wanru123 | 小学五年级 |
| 赵中苧 | zhongzhu123 | 小学一年级 |
| 宝贝1 | baby001 | 幼儿园大班 |
| 宝贝2 | baby002 | 小学五年级 |
| 宝贝3 | baby003 | 初中一年级 |
| **家长** | **parent888** | 总览所有孩子 |

## 🛠️ 技术栈

- **框架**: Streamlit
- **AI**: DeepSeek Chat（文本生成）、豆包 Vision（图片识别）
- **数据库**: SQLite
- **图表**: Plotly
- **图片处理**: Pillow

## ☁️ 部署到 Streamlit Cloud

1. 推送到 GitHub 公开仓库
2. 在 [share.streamlit.io](https://share.streamlit.io) 创建 App
3. 在 Settings → Secrets 中配置 API Key
