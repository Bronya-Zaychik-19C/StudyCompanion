# 🚀 StudyCompanion 快速上手指南

> 从零开始，1-2小时内完成环境搭建和基础测试

---

## 📝 准备工作检查清单

在开始之前，确保你有：
- [ ] Windows 10/11 操作系统
- [ ] Python 3.11 或 3.12
- [ ] 良好的网络连接（需下载约 11GB 模型）
- [ ] 至少 50GB 可用硬盘空间
- [ ] Qwen API Key（免费注册）

---

## 🔧 步骤一：安装 Python 依赖（15 分钟）

### 1. 打开 PowerShell

```powershell
# 按 Win + X，选择 "Windows PowerShell"
```

### 2. 进入项目目录

```powershell
cd E:\AI\StudyCompanion
```

### 3. 创建并激活虚拟环境

```powershell
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate

# 看到 (venv) 前缀表示激活成功
```

### 4. 安装依赖包

```powershell
# 升级 pip
python -m pip install --upgrade pip

# 安装所有依赖（约 15 分钟）
pip install -r requirements.txt

# 使用国内镜像加速（可选）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 5. 验证安装

```powershell
python -c "import fastapi; import chromadb; print('✅ 依赖安装成功！')"
```

---

## 🦙 步骤二：安装 Ollama 和模型（30-60 分钟）

### 1. 安装 Ollama

**方法 A：使用 winget（推荐）**
```powershell
winget install Ollama.Ollama
```

**方法 B：手动下载**
- 访问：https://ollama.ai/download/windows
- 下载并安装 OllamaSetup.exe

### 2. 验证安装

```powershell
ollama --version
# 应显示版本号，如：ollama version is 0.x.x
```

### 3. 启动 Ollama 服务

```powershell
# 打开新的 PowerShell 窗口
ollama serve

# 保持这个窗口运行，不要关闭
```

### 4. 下载 AI 模型（回到原窗口）

```powershell
# 下载主力模型（约 9GB，20-40 分钟）
ollama pull qwen2.5:14b

# 下载快速分类模型（约 1GB，2-5 分钟）
ollama pull qwen2.5:1.5b

# 下载 Embedding 模型（约 1GB，2-5 分钟）
ollama pull bge-large-zh-v1.5
```

### 5. 验证模型

```powershell
# 查看已下载的模型
ollama list

# 应该看到三个模型：
# qwen2.5:14b
# qwen2.5:1.5b
# bge-large-zh-v1.5
```

### 6. 测试模型

```powershell
# 测试对话功能
ollama run qwen2.5:14b "你好，介绍一下你自己"

# 按 Ctrl+D 或输入 /bye 退出
```

---

## 🔑 步骤三：获取 Qwen API Key（5 分钟）

### 1. 注册阿里云账号

访问：https://bailian.console.aliyun.com/

### 2. 创建 API Key

1. 登录后，点击左侧 **"API-KEY 管理"**
2. 点击 **"创建新的API-KEY"**
3. 复制生成的 API Key（格式：`sk-xxxxxxxxxxxxxx`）

### 3. 配置到项目

编辑 `E:\AI\StudyCompanion\config\default_config.json`：

```json
{
  "ai_services": {
    "qwen": {
      "api_key": "sk-你的真实API-Key粘贴到这里"
    }
  }
}
```

**⚠️ 注意**：
- 保存后确认 JSON 格式正确（逗号、引号）
- 不要将 API Key 上传到 GitHub

---

## ✅ 步骤四：测试核心功能（10 分钟）

### 1. 测试 Ollama 连接

```powershell
# 确保在虚拟环境中（看到 (venv) 前缀）
cd E:\AI\StudyCompanion

# 运行测试脚本
python << 'EOF'
import asyncio
import httpx

async def test_ollama():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get('http://localhost:11434/api/tags')
            models = response.json()
            print("✅ Ollama 连接成功！")
            print(f"可用模型数量: {len(models.get('models', []))}")
            for model in models.get('models', []):
                print(f"  - {model['name']}")
    except Exception as e:
        print(f"❌ Ollama 连接失败: {e}")

asyncio.run(test_ollama())
EOF
```

### 2. 测试数据库

```powershell
python << 'EOF'
from core.memory.database import DatabaseManager

try:
    db = DatabaseManager()
    print("✅ 数据库初始化成功！")
    print(f"数据库路径: data/sqlite/")
except Exception as e:
    print(f"❌ 数据库初始化失败: {e}")
EOF
```

### 3. 测试配置文件

```powershell
python << 'EOF'
import json

with open('config/default_config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
    api_key = config['ai_services']['qwen']['api_key']
    
    if api_key.startswith('sk-') and len(api_key) > 20:
        print(f"✅ API Key 配置正确: {api_key[:10]}...")
    else:
        print("❌ 请检查 API Key 配置")
EOF
```

---

## 🎉 完成！接下来做什么？

### ✅ 如果所有测试都通过

恭喜！你的环境已经完全就绪。接下来可以：

**选项 A：等待 Phase 1 完成**
- 目前项目完成度 80%
- 还需要完善 WebSocket 服务器和前端界面
- 预计 1-2 天完成

**选项 B：参与开发**
- 查看 `docs/TODO.md` 了解待办任务
- 选择感兴趣的模块进行开发
- 参考 `docs/INSTALL.md` 了解架构

**选项 C：部署 RAGFlow（可选）**
- 用于 Phase 2 的知识库功能
- 查看 `docs/INSTALL.md` 中的 RAGFlow 章节

### ❌ 如果遇到问题

#### 问题 1：Ollama 下载模型失败

**解决方案**：
```powershell
# 使用代理或更换网络
# 或分次下载
ollama pull qwen2.5:14b --verbose
```

#### 问题 2：Python 依赖安装失败

**解决方案**：
```powershell
# 使用清华源镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或单独安装失败的包
pip install 包名 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### 问题 3：GPU 未被使用

**解决方案**：
```powershell
# 检查 NVIDIA 驱动
nvidia-smi

# 确认 Ollama 使用 GPU
ollama ps  # 查看运行的模型
```

#### 问题 4：端口被占用

**解决方案**：
```powershell
# 检查 11434 端口（Ollama）
netstat -ano | findstr :11434

# 如果被占用，修改 config/default_config.json 中的端口
```

---

## 📚 下一步学习

1. **了解项目架构**
   - 阅读 `README.md`
   - 查看 `docs/PROJECT_SUMMARY.md`

2. **查看开发计划**
   - 阅读 `docs/TODO.md`
   - 了解 7 个开发阶段

3. **学习核心代码**
   - `core/ai/ollama_client.py` - LLM 客户端
   - `core/memory/database.py` - 数据库管理
   - `core/audio/realtime_client.py` - 语音交互

---

## 🆘 获取帮助

- 📖 查看完整安装文档：`docs/INSTALL.md`
- 📋 查看开发计划：`docs/TODO.md`
- 📊 查看项目总结：`docs/PROJECT_SUMMARY.md`

---

**预计总时间**: 1-2 小时  
**难度**: ⭐⭐☆☆☆（中等）  
**完成后**: 环境完全就绪，可运行测试 ✅

