# StudyCompanion 快速上手

> 5 分钟完成配置，即刻开始 AI 学习

---

## 前置条件

- Python 3.11+
- DeepSeek / Qwen / OpenAI API Key（任选一个）
- 无需 GPU，无需本地模型

---

## 安装步骤

### 1. 安装依赖

```powershell
cd E:\AI\StudyCompanion
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置 API Key

**方式一（推荐）：环境变量**

```powershell
copy .env.example .env
# 编辑 .env，填入你的 Key
```

```ini
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-你的key
```

**方式二：配置文件**

编辑 `config/default_config.json`，在对应 provider 下填入 `api_key`。

### 3. 启动

```powershell
python main.py
```

浏览器打开 `http://localhost:48911`

---

## 功能一览

| 标签页 | 功能 | 使用方式 |
|--------|------|----------|
| 费曼 | 费曼学习法 | 输入知识点，AI 引导你讲解 |
| 诊断 | 知识诊断 | 点击按钮开始，AI 出题测试 |
| 真题 | 真题系统 | 选择年份，查看真题结构与答案 |
| 模拟 | 模拟考试 | 生成模拟卷 + 考点预测 |
| 路径 | 学习规划 | 获取推荐路径和 N 天计划 |

左侧边栏可切换会话和人设，右侧章节栏可选择具体章节针对性学习。

---

## 获取 API Key

- **DeepSeek**: https://platform.deepseek.com/
- **Qwen**: https://bailian.console.aliyun.com/
- **OpenAI**: https://platform.openai.com/
