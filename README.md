# StudyCompanion - 考研 AI 学习私教

> 基于 DeepSeek / Qwen / OpenAI API 的智能学习伴侣，专注考研数学一

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![DeepSeek](https://img.shields.io/badge/AI-DeepSeek%2FQwen%2FOpenAI-orange.svg)](https://api.deepseek.com/)

---

## 核心功能

### 费曼学习法
用"讲解 — 识别 — 简化 — 复习"四个阶段引导你深入理解知识点

### 知识诊断
AI 自动出题，诊断薄弱点，生成个人评估报告

### 真题系统
收录 1987-2025 年数学一真题（655+ 道），支持按年份查看、PDF 解析、AI 去乱码

### 模拟考试与考情预测
按考频生成模拟卷，AI 命题趋势分析

### 学习路径规划
基于诊断结果推荐个性化学习路径，支持 30/60 天学习计划

### 多会话管理
类 ChatGPT 对话管理，消息持久化，刷新不丢失

### 人设系统
4 种 AI 角色：专业教师 / 温和导师 / 研友 / 极简模式

---

## 技术栈

- **后端**: Python + FastAPI + WebSocket
- **AI**: DeepSeek / Qwen / OpenAI（HTTP API，流式输出）
- **数据库**: SQLite (aiosqlite)
- **前端**: 内联 SPA，MathJax 3 渲染 LaTeX 公式

---

## 快速开始

### 1. 环境要求
- Python 3.11+
- DeepSeek / Qwen / OpenAI API Key

### 2. 安装

```bash
cd E:/AI/StudyCompanion

# 创建虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 API Key
# 支持 DeepSeek、Qwen、OpenAI 三种 provider
```

或者在 `config/default_config.json` 中修改配置。

### 4. 运行

```bash
python main.py
```

访问 `http://localhost:48911`

---

## 项目结构

```
StudyCompanion/
├── main.py              # 主入口 (FastAPI + 内联前端)
├── config/
│   ├── default_config.json  # 主配置
│   └── personas.py          # 人设系统
├── core/
│   ├── ai/              # AI 客户端 (OpenAI 兼容 API)
│   ├── knowledge/       # 知识库引擎
│   └── memory/          # SQLite 数据库
├── features/
│   ├── feynman/         # 费曼学习法
│   ├── diagnosis/       # 知识诊断
│   ├── exam/            # 模拟考试与考点预测
│   ├── roadmap/         # 学习路径规划
│   └── schedule/        # 日程管理 (待接入)
├── data/
│   ├── knowledge/       # 知识库 JSON
│   └── sqlite/          # 数据库文件
└── frontend/            # 前端资源目录
```

---

## 配置说明

`config/default_config.json` 支持：

- `ai.provider`: 切换 AI 服务商 (deepseek / qwen / openai)
- `features`: 功能开关 (feynman_learning, schedule_management 等)
- `server`: 主机、端口、WebSocket 路径设置

API Key 优先从 `.env` 环境变量读取，其次从配置文件读取。

---

## 许可证

MIT License
