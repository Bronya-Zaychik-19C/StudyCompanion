# 📥 StudyCompanion 安装指南

> 详细的安装和配置教程

---

## 📋 目录

1. [系统要求](#系统要求)
2. [Python 环境配置](#python-环境配置)
3. [Ollama 安装与配置](#ollama-安装与配置)
4. [RAGFlow 安装（可选）](#ragflow-安装)
5. [项目安装](#项目安装)
6. [配置说明](#配置说明)
7. [运行测试](#运行测试)
8. [常见问题](#常见问题)

---

## 🖥️ 系统要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| **CPU** | Intel i5 / AMD Ryzen 5 | Intel i7 / AMD Ryzen 7+ |
| **GPU** | NVIDIA RTX 3060 (8GB) | NVIDIA RTX 4070+ (12GB+) |
| **内存** | 16GB | 32GB+ |
| **硬盘** | 50GB 可用空间 | 100GB+ SSD |

### 软件要求

- **操作系统**: Windows 10/11, Linux, macOS
- **Python**: 3.11 或 3.12
- **NVIDIA 驱动**: 最新版本
- **CUDA**: 11.8+ (自动随 Ollama 安装)

---

## 🐍 Python 环境配置

### 1. 安装 Python

#### Windows:
```bash
# 访问官网下载：https://www.python.org/downloads/
# 或使用 winget
winget install Python.Python.3.11

# 验证安装
python --version
```

#### Linux:
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

#### macOS:
```bash
brew install python@3.11
```

### 2. 创建虚拟环境

```bash
# 进入项目目录
cd E:\AI\StudyCompanion

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 验证
which python  # 应显示 venv 中的 python
```

### 3. 升级 pip
```bash
python -m pip install --upgrade pip
```

---

## 🦙 Ollama 安装与配置

### 1. 安装 Ollama

#### Windows:
```bash
# 访问官网下载安装包
https://ollama.ai/download/windows

# 或使用 winget
winget install Ollama.Ollama
```

#### Linux:
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

#### macOS:
```bash
# 下载 dmg 安装包
https://ollama.ai/download/mac
```

### 2. 验证安装
```bash
ollama --version
# 应显示版本号

# 启动服务
ollama serve  # 后台运行
```

### 3. 下载模型

```bash
# 主力模型（9GB，质量最高）
ollama pull qwen2.5:14b

# 快速分类模型（1GB）
ollama pull qwen2.5:1.5b

# Embedding 模型（1GB）
ollama pull bge-large-zh-v1.5

# 验证模型
ollama list
```

**预计下载时间**：
- 快速网络：15-20 分钟
- 普通网络：30-60 分钟

### 4. 测试模型
```bash
# 测试对话
ollama run qwen2.5:14b "你好，介绍一下你自己"

# 测试 Embedding
ollama run bge-large-zh-v1.5 "这是一个测试"
```

---

## 🔧 RAGFlow 安装（可选）

> RAGFlow 用于知识库管理，Phase 2 功能，可暂时跳过

### 使用 Docker 安装

```bash
# 1. 安装 Docker
# Windows: 下载 Docker Desktop
# Linux: apt install docker.io

# 2. 下载 RAGFlow
git clone https://github.com/infiniflow/ragflow.git
cd ragflow

# 3. 启动服务
docker-compose up -d

# 4. 访问
http://localhost:9380
```

### 配置 API

1. 登录 RAGFlow Web 界面
2. 创建 API Key
3. 复制到配置文件

---

## 📦 项目安装

### 1. 安装依赖

```bash
# 确保在虚拟环境中
cd E:\AI\StudyCompanion

# 安装所有依赖
pip install -r requirements.txt

# 可能需要较长时间（10-20分钟）
# 依赖总大小约 2-3GB
```

### 2. 安装可选依赖

```bash
# 如果需要 OCR 功能（错题本）
pip install paddleocr paddlepaddle

# 如果需要音频分析（情绪检测）
pip install librosa soundfile
```

### 3. 验证安装

```python
# 测试导入
python -c "import fastapi; import ollama; import chromadb; print('✅ 安装成功')"
```

---

## ⚙️ 配置说明

### 1. 获取 Qwen API Key

```bash
# 1. 访问阿里云百炼平台
https://bailian.console.aliyun.com/

# 2. 注册/登录账号

# 3. 创建 API Key
- 进入"API管理"
- 创建新的 API Key
- 复制保存
```

### 2. 配置文件

编辑 `config/default_config.json`:

```json
{
  "ai_services": {
    "qwen": {
      "api_key": "sk-your-qwen-api-key-here"  // 替换为你的 API Key
    }
  },
  "ollama": {
    "api_url": "http://localhost:11434",  // Ollama 地址
    "main_model": "qwen2.5:14b",          // 主模型
    "fast_model": "qwen2.5:1.5b",         // 快速模型
    "embedding_model": "bge-large-zh-v1.5"
  }
}
```

### 3. 验证配置

```bash
python -c "
import json
with open('config/default_config.json') as f:
    config = json.load(f)
    print('✅ 配置文件格式正确')
    print(f'API Key: {config['ai_services']['qwen']['api_key'][:10]}...')
"
```

---

## 🚀 运行测试

### 1. 启动服务

```bash
# 确保 Ollama 服务运行中
ollama serve

# 启动 StudyCompanion
python main.py
```

### 2. 访问界面

打开浏览器访问：
```
http://localhost:48911
```

应该看到欢迎页面。

### 3. 测试 API

```bash
# 测试健康检查
curl http://localhost:48911/api/health

# 应返回：
# {"status":"ok","project":"StudyCompanion","version":"1.0.0"}
```

### 4. 测试 Ollama 连接

```python
# 测试脚本
python << EOF
import asyncio
from core.ai.ollama_client import OllamaClient

async def test():
    client = OllamaClient({
        'api_url': 'http://localhost:11434',
        'main_model': 'qwen2.5:14b'
    })
    
    # 测试可用模型
    models = await client.get_available_models()
    print(f'可用模型: {models}')
    
    # 测试生成
    response = await client.generate('你好，介绍一下你自己')
    print(f'回复: {response[:100]}...')

asyncio.run(test())
EOF
```

---

## ❓ 常见问题

### Q1: Ollama 无法下载模型？

**A**: 使用国内镜像：
```bash
export OLLAMA_API_BASE=https://ollama.com  # 设置镜像
ollama pull qwen2.5:14b
```

### Q2: GPU 未被使用？

**A**: 检查 CUDA 安装：
```bash
nvidia-smi  # 查看 GPU 状态
ollama ps   # 查看 Ollama 进程
```

### Q3: 依赖安装失败？

**A**: 尝试使用国内源：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q4: 内存不足？

**A**: 调整模型配置：
```json
{
  "ollama": {
    "main_model": "qwen2.5:7b"  // 使用 7b 模型
  }
}
```

### Q5: 端口被占用？

**A**: 修改配置：
```json
{
  "server": {
    "port": 48912  // 改为其他端口
  }
}
```

---

## 📚 下一步

安装完成后：

1. ✅ 阅读 [README.md](../README.md) 了解项目
2. ✅ 查看 [TODO.md](TODO.md) 了解开发计划
3. ✅ 开始使用或参与开发

---

## 🆘 获取帮助

- 📖 文档问题：查看 [README.md](../README.md)
- 🐛 Bug 反馈：提交 Issue
- 💬 讨论交流：Discussion 区

---

**祝你使用愉快！** 🎉


