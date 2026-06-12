# StudyCompanion v2.0 重构总结

> 从"功能堆砌"到"聚焦核心"的转型

---

## 📋 重构背景

原项目存在以下问题：
1. **架构过于复杂**：Ollama + RAGFlow + Chroma + Qwen API，依赖太多
2. **硬件门槛高**：需要 RTX 4070+ 显卡才能运行本地模型
3. **部署复杂度高**：Docker、GPU 驱动、模型下载等对用户不友好
4. **定位模糊**：功能太多但缺乏核心价值主张

---

## 🎯 重构目标

**新定位**：AI 学习私教 - 用语音对话帮你真正理解知识

**核心价值**：
1. **语音交互**：自然对话，无需打字
2. **费曼学习法**：引导式讲解，真正理解
3. **开箱即用**：只需 API Key，无需复杂配置

---

## 🗑️ 移除的功能

| 功能 | 移除原因 | 文件/模块 |
|------|----------|-----------|
| Ollama 本地模型 | GPU 门槛高，部署复杂 | `core/ai/ollama_client.py` |
| RAGFlow 知识库 | 运维复杂，非核心需求 | 未实现 |
| Chroma 向量存储 | 配合 RAGFlow 使用 | `core/memory/vector_store.py` |
| 智能路由器 | 配合多模型架构 | `core/ai/router.py` |
| Live2D 形象 | 开发成本高，非核心 | 前端计划中 |
| GPT-SoVITS 音色 | 部署复杂，非核心 | 未实现 |
| 错题本 OCR | 功能过重 | `features/mistake_book/` |
| 思维导图 | 非核心 | `features/mindmap/` |
| 睡前复盘 | 非核心 | `features/review/` |
| 情绪分析 | 非核心 | `features/emotion/` |
| 学习追踪（完整） | 简化为数据库记录 | `features/study/` |

---

## ✅ 保留并简化的功能

### 1. 语音交互（Qwen Realtime API）
- 保留：`core/audio/realtime_client.py`
- 优势：云端处理，无本地 GPU 要求
- 延迟：200ms 级别

### 2. 费曼学习法（新增核心）
- 新增：`features/feynman/engine.py`
- 功能：
  - 引导用户用自己的话解释概念
  - 识别知识薄弱点
  - 针对性提问和类比讲解
  - 四阶段：Explain → Identify → Simplify → Review

### 3. 日程管理（简化版）
- 保留：`features/schedule/manager.py`
- 简化：移除后台提醒服务，保留 CRUD 操作

### 4. 数据存储（单数据库）
- 原：3 个独立 SQLite 文件 + Chroma 向量库
- 新：单个 SQLite 文件（对话 + 日程 + 学习记录）

---

## 📁 重构后项目结构

```
StudyCompanion/
├── core/
│   ├── audio/
│   │   └── realtime_client.py    # Qwen 语音客户端
│   └── memory/
│       └── database.py            # 统一数据库管理
│
├── features/
│   ├── feynman/                   # 费曼学习法（新增）
│   │   ├── engine.py              # 费曼引擎
│   │   └── __init__.py
│   └── schedule/
│       ├── manager.py             # 日程管理器
│       └── tools.py               # Agent 工具（可选）
│
├── config/
│   ├── default_config.json        # 简化后的配置
│   └── prompts.py                 # 提示词模板
│
├── docs/
│   ├── TODO.md                    # 开发计划
│   └── REFACTOR_SUMMARY.md        # 本文档
│
├── main.py                        # 主入口（重写）
├── requirements.txt               # 依赖（精简）
└── README.md                      # 项目说明（更新）
```

**代码量对比**：
- 重构前：~2000 行 Python 代码
- 重构后：~1200 行 Python 代码
- 减少：40%

---

## 🔧 依赖简化

### 重构前（40+ 依赖）
```
fastapi, uvicorn, websockets, httpx,
ollama, chromadb, sentence-transformers,
pandas, numpy, aiosqlite, scikit-learn,
librosa, soundfile, plotly, graphviz,
apscheduler, plyer, loguru, tqdm, pyinstaller...
```

### 重构后（12 依赖）
```
fastapi, uvicorn, websockets, httpx,
aiosqlite, loguru, tqdm, pyinstaller
```

**核心依赖减少 70%**

---

## 🚀 部署流程对比

### 重构前（复杂）
```bash
1. 安装 Python 3.11+
2. 安装 NVIDIA 驱动 + CUDA
3. 安装 Ollama
4. 下载 3 个模型（11GB）
5. 部署 RAGFlow（Docker）
6. 配置 Chroma 向量库
7. 安装 Python 依赖（40+ 包）
8. 配置 API Key
9. 启动服务
```

**预计时间**：2-4 小时  
**硬件要求**：RTX 4070+, 32GB RAM, 100GB SSD

### 重构后（简单）
```bash
1. 安装 Python 3.11+
2. 安装 Python 依赖（12 包）
3. 配置 Qwen API Key
4. 启动服务
```

**预计时间**：15 分钟  
**硬件要求**：无特殊要求（云端 AI 处理）

---

## 💡 核心竞争力

### 差异化优势
1. **费曼学习法**：市面上少有的"引导式学习"AI 产品
2. **语音优先**：大多数学习工具是文字交互
3. **轻量化**：无需 GPU，任何电脑都能运行
4. **专注**：不做功能堆砌，深耕学习理解

### 目标用户
- 大学生（需要理解抽象概念）
- 自学者（缺乏系统性指导）
- 终身学习者（追求深度学习）

---

## 📊 开发路线图

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | 核心框架 + 数据库 | ✅ 完成 |
| Phase 2 | 费曼学习法引擎 | ✅ 完成 |
| Phase 3 | WebSocket 通信 | ✅ 完成 |
| Phase 4 | 前端界面 | 🚧 进行中（基础版） |
| Phase 5 | Qwen 语音集成 | 📋 待 API Key 配置 |
| Phase 6 | 学习追踪可视化 | 📋 计划中 |
| Phase 7 | 打包发布 | 📋 计划中 |

---

## ⚠️ 待解决问题

### 1. API 费用
- Qwen Realtime API 按 token 计费
- 解决方案：未来考虑本地模型作为可选配置

### 2. 前端简陋
- 当前只有基础测试页面
- 解决方案：Phase 4 完善 UI/UX

### 3. 语音功能未完全集成
- 需要用户配置 API Key 才能测试
- 解决方案：提供测试模式和文档

---

## 🎯 下一步行动

### 立即完成（本周）
1. [ ] 测试基础对话流程
2. [ ] 完善费曼学习法提示词
3. [ ] 添加更多学习场景示例

### 短期（1-2 周）
1. [ ] 前端界面美化
2. [ ] 学习数据可视化
3. [ ] WebSocket 消息处理完善

### 中期（1 个月）
1. [ ] Qwen 语音完整集成
2. [ ] 用户认证和数据同步
3. [ ] 打包成可执行文件

---

## 📝 总结

**重构前**：想做"全能 AI 助手"，但太复杂、太难用、定位模糊

**重构后**：专注"费曼学习法 + 语音交互"，轻量化、易部署、价值清晰

**核心理念**：少即是多。与其做 10 个 60 分的功能，不如做 2 个 90 分的功能。

---

**重构完成时间**：2026-05-14  
**版本**：v2.0.0  
**状态**：核心功能完成，前端优化中
