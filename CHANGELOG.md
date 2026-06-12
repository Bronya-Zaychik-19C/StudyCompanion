# Changelog

## v3.6.0 (2026-06-12) — 真题库 + 真题卷 + 公式渲染修复

### 新增
- **真题索引库** `features/exam/question_bank.py`：39 年（1987-2025）× 655 题，每道题标注题号/题型/知识点/关键词
- **📋 真题卷**：按年份生成真题结构概览（题号 + 知识点映射 + 真实题数），结合 PDF 可对照做题
- **单题提取** `qbank_question`：从解析 PDF 提取指定年份/题号的解析原文，AI 修复 OCR 乱码
- **高频考点统计** `qbank_hot`：基于 39 年数据统计每个知识点的真题出现频率

### 改进
- 费曼引擎自动引用真题：学习某个知识点时，AI 上下文包含该知识点历年真题年份和题号
- 诊断 / 模拟 / 真题卷 / 考点预测等模块全部改用 `renderMath()` 渲染公式
- 真题卷**不编造题目**：展示的是真实真题结构 + 官方答案，想看原题直接打开对应 PDF

### 修复
- MathJax CDN 从 `cdn.jsdelivr.net`（可能被墙）改为 `unpkg.com` + `cdn.bootcdn.net` 国内双源
- `renderMath()` 加重试机制：MathJax 未就绪时最多重试 15 次 × 300ms
- 修复模拟卷/诊断/考点预测等模块公式不渲染的问题
- 修复编辑时产生的 JS 孤儿代码导致整个页面崩溃

### 涉及文件
- `features/exam/question_bank.py` — 新建，39 年真题索引
- `main.py` — 新增真题卷标签、真题生成/单题提取/高频统计 handler、MathJax 修复
- `data/knowledge/math_one.json` — 知识库扩充至 106 知识点 × 485 考点

---

## v3.5.0 (2026-06-12) — 多会话持久化

### 新增
- **多会话管理**：像 ChatGPT 一样的对话列表，可创建/切换/删除多个对话
- **数据库持久化**：`chat_sessions` + `chat_messages` 两张新表，消息实时存入 SQLite
- **REST API**：`GET/POST /api/sessions`、`GET/DELETE /api/sessions/{id}` 完整 CRUD
- **自动标题**：根据第一条消息内容自动生成对话标题
- **刷新不丢失**：重连后自动加载历史消息列表，点击即可恢复对话

### 改进
- 前端大改版：左侧对话列表 + 章节导航双栏布局
- WebSocket 增加 `session_load`/`session_new`/`session_delete` 消息类型
- 无会话时自动创建，首条消息自动命名

### 涉及文件
- `core/memory/database.py` — 新增会话表与方法
- `main.py` — 新增 REST API + WebSocket 会话管理 + 前端对话列表
- `CHANGELOG.md`

---

## v3.4.0 (2026-06-12) — 对话记忆

### 修复
- 费曼引擎历史窗口从 4 条扩大到 12 条，避免上下文丢失
- 普通对话增加历史记忆：保留最近 20 条消息（10 轮对话）
- 进入费曼模式时自动继承之前的 6 条对话历史
- 退出费曼模式时将费曼对话合并回聊天历史
- 修复连续对话时 AI "失忆"的问题

### 涉及文件
- `features/feynman/engine.py` — 扩大 history 窗口，`start_session_stream` 支持 `prior_history`
- `main.py` — `_handle_text` 加历史存储/传递，`_start_feynman` 传 prior，`_end_feynman` 合并历史

---

## v3.3.0 (2026-06-12) — 多服务商支持

### 新增
- 支持 DeepSeek API（默认），Qwen 和 OpenAI 可切换
- `config/default_config.json` 重构：`ai.provider` 选择服务商，各自独立配置 `api_key`/`base_url`/`model`
- API 请求失败时自动降级：流式不可用 → 非流式；高 token 不可用 → 降低 token

### 涉及文件
- `core/ai/qwen_client.py` — 构造函数支持 `base_url` 参数，`chat_stream` 自动降级
- `main.py` — 从 config 读取 `provider` 动态初始化客户端
- `config/default_config.json` — 多服务商配置结构

---

## v3.2.0 (2026-06-12) — 流式输出

### 新增
- `chat_stream()` 方法：SSE 流式接收，逐 token 推送到前端
- 前端流式渲染：`stream_start` → `stream_delta` → `stream_end`
- 费曼引擎 `start_session_stream` / `process_response_stream` 流式方法

### 修复
- 发送消息后长时间无响应的"卡住"问题（首 token < 1s）
- DeepSeek API 兼容（默认模型改为 `qwen-plus` → `deepseek-chat`）

### 涉及文件
- `core/ai/qwen_client.py` — 新增 `chat_stream`
- `features/feynman/engine.py` — 新增两个流式方法
- `main.py` — 前端新增流式消息处理，handler 全部改用流式

---

## v3.1.0 (2026-06-12) — 人设系统

### 新增
- 四种可切换的 AI 说话风格：专业教师 / 温和导师 / 研友 / 极简模式
- 前端左侧栏新增人设下拉选择器，切换即时生效
- `config/personas.py` 人设配置模块

### 涉及文件
- `config/personas.py` — 人设定义与查询
- `main.py` — `persona_set` 消息处理，前端 persona 选择器
- `features/feynman/engine.py` — 费曼引擎使用 persona 生成回复

---

## v3.0.0 (2026-05-28) — 考研知识库

### 新增
- **知识库引擎** `core/knowledge/engine.py`：加载、搜索、推荐知识点
- **数学一知识库** `data/knowledge/math_one.json`：23 章 × 80 知识点，含考点/易错点/难度/考频
- **知识点诊断** `features/diagnosis/engine.py`：AI 出题 → 答题 → 薄弱点分析
- **考点预测** `features/exam/engine.py`：高频考点分析 + 真题风格模拟卷
- **学习路径规划** `features/roadmap/engine.py`：按薄弱点 + 考频推荐学习顺序

### 改进
- 前端大改版：左侧章节导航 + 顶部标签页（费曼/诊断/模拟/路径）
- 费曼引擎升级为学科感知：自动匹配知识库，用考研真题语境引导
- 回复长度从 1024 → 4096 tokens

### 涉及文件
- `core/knowledge/engine.py` — 知识库引擎
- `data/knowledge/math_one.json` — 数学一完整知识库
- `features/diagnosis/engine.py` — 诊断引擎
- `features/exam/engine.py` — 考试引擎
- `features/roadmap/engine.py` — 路径规划引擎
- `main.py` — 完全重写，整合所有功能

---

## v2.1.0 (2026-05-14) — AI 真正接入

### 新增
- Qwen 文本聊天客户端 `core/ai/qwen_client.py`
- 意图分类：自动识别 feynman/schedule/chat/emotion
- 费曼引擎从模板匹配升级为 AI 驱动

### 修复
- 之前只有模板回复，无法理解用户意图
- 前端交互逻辑优化：文字输入自动检测学习意图

### 涉及文件
- `core/ai/qwen_client.py` — 新建
- `features/feynman/engine.py` — 重写为 AI 驱动
- `main.py` — 接入 AI，更新前端

---

## v2.0.0 (2026-05-14) — 架构简化

### 移除
- Ollama 本地模型（硬件门槛高）
- RAGFlow 知识库（部署复杂）
- Chroma 向量存储
- Live2D 虚拟形象
- GPT-SoVITS 音色定制
- 智能路由器、错题本、思维导图、情绪分析等非核心模块

### 保留
- Qwen Realtime 语音客户端
- SQLite 数据库（对话 + 日程 + 学习记录）
- 日程管理

### 变更
- 依赖从 40+ 减到 12（-70%）
- 代码从 ~2000 行减到 ~1200 行（-40%）
- 部署时间从 2-4 小时减到 15 分钟
- 定位从"全能 AI 助手"聚焦到"AI 学习私教"

### 涉及文件
- 删除：`core/ai/ollama_client.py`, `core/ai/router.py`, `core/memory/vector_store.py`, `features/{agent,emotion,knowledge,mindmap,mistake_book,review,study}/`
- 简化：`core/memory/database.py`, `features/schedule/manager.py`
- 新增：`features/feynman/engine.py`（费曼学习法引擎）
- 重写：`main.py`, `requirements.txt`, `config/default_config.json`

---

## v1.0.0 (2025-11-22) — 初始版本

- 项目初始化，Phase 1 核心框架
- 数据库、Ollama 客户端、Qwen Realtime 客户端、向量存储、智能路由、日程管理
- 11 个 Python 模块，~2000 行代码
