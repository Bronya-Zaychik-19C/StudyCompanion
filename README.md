# 🎓 StudyCompanion - 你的 AI 学习私教

> 用语音对话的方式，帮你真正理解知识

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Qwen](https://img.shields.io/badge/Qwen-Realtime%20API-orange.svg)](https://bailian.console.aliyun.com/)

---

## ✨ 核心特性

### 🎤 语音对话学习
- **自然对话**：像和朋友聊天一样学习，无需打字
- **实时响应**：毫秒级延迟，流畅不等待
- **智能打断**：随时插话，自然交互
- **日程管理**：语音创建提醒，学习不遗漏

### 🧠 费曼学习法
- **引导式讲解**：AI 引导你用自己的话复述知识
- **针对性提问**：发现你的知识薄弱点
- **类比解释**：用生活中的例子帮你理解抽象概念
- **知识卡片**：自动生成复习要点

### 📊 学习追踪
- **时长统计**：记录每科学习时间
- **质量评分**：评估学习状态和效果
- **数据可视化**：清晰看到进步轨迹

---

## 🏗️ 架构设计

```
StudyCompanion - 精简架构：
├── Qwen Realtime API  # 语音交互（云端）
├── SQLite            # 数据持久化
└── 费曼学习引擎      # 核心算法
```

**设计理念**：
- ✅ 开箱即用：只需 API Key，无需复杂配置
- ✅ 轻量化：无 GPU 要求，无本地模型
- ✅ 专注核心：语音 + 费曼，不做功能堆砌

---

## 🚀 快速开始

### 1. 环境要求
- Python 3.11+
- Qwen API Key（阿里云百炼，免费注册）

### 2. 安装步骤

```bash
# 1. 克隆项目
cd E:/AI/StudyCompanion

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 API Key
# 编辑 config/default_config.json，填入你的 Qwen API Key
```

### 3. 运行

```bash
python main.py
```

访问：`http://localhost:48911`

---

## 📁 项目结构

```
StudyCompanion/
├── core/
│   ├── audio/         # 语音交互（Qwen Realtime）
│   ├── memory/        # 数据持久化（SQLite）
│   └── ai/            # AI 核心（费曼引擎）
│
├── features/
│   ├── feynman/       # 费曼学习法
│   ├── schedule/      # 日程管理
│   └── study/         # 学习追踪
│
├── frontend/          # 前端界面
├── config/            # 配置文件
└── main.py            # 主入口
```

---

## 🎯 使用场景

### 场景 1：理解抽象概念
```
你："我不太理解什么是导数"
小助："好的，我们一起来看看。先问问你，你觉得'变化'是什么意思？"
（引导你用自己的话复述，而不是直接给定义）
```

### 场景 2：复习备考
```
你："下周要考牛顿定律了"
小助："我来帮你复习。先说说，牛顿第一定律说的是什么？"
（发现薄弱点，针对性讲解）
```

### 场景 3：学习记录
```
你："刚才学了 2 小时英语"
小助："很棒！今天英语累计学习 2 小时了，继续保持~"
```

---

## 📊 路线图

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | 核心框架 + 语音交互 | ✅ 完成 |
| Phase 2 | 费曼学习法引擎 | 🚧 进行中 |
| Phase 3 | 学习追踪 + 数据分析 | 📋 计划中 |
| Phase 4 | 前端界面优化 | 📋 计划中 |

---

## 💡 设计理念

1. **少即是多**：不做功能堆砌，专注核心价值
2. **理解优先**：不追求答题正确率，追求真正理解
3. **陪伴为本**：不是冷冰冰的工具，是有温度的学习伙伴

---

## 📄 许可证

MIT License

---

**让学习更高效，让理解更深刻 🌱**
