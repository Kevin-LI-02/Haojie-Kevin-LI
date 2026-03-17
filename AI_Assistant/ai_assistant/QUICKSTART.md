# 🚀 EYES-T AI Assistant 快速入门

## 5分钟快速启动指南

### 前置条件检查

- ✅ Python 3.10+ 已安装
- ✅ Conda 已安装（eyes_t 环境）
- ✅ 至少 8GB RAM
- ✅ 20GB 可用硬盘空间

---

## 步骤 1: 安装 Ollama（5-10分钟）

### Windows

```cmd
# 1. 下载并安装 Ollama
# 访问 https://ollama.ai/download
# 运行安装程序

# 2. 启动 Ollama 服务（保持终端打开）
ollama serve

netatat -ano -p TCP | findstr :11434
taskkill /F /IM ollama* 2>$null

# 3. 在新终端下载模型
ollama pull qwen2.5:7b
```

✅ **验证**: 运行 `ollama list` 应该能看到 qwen:7b

---

## 步骤 2: 安装依赖（2-3分钟）

```cmd
# 1. 激活环境
conda activate eyes_t

# 2. 进入项目目录
cd C:\Users\16254\Desktop\MTR_EyesT\PaddleOCR\AI_Ass\ai_assistant

# 3. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

✅ **验证**: 运行 `python -c "import flask; print('OK')"` 应该输出 OK

---

## 步骤 3: 准备数据（可选，1分钟）

项目已包含示例数据，可以直接跳过此步骤。

如要使用自己的数据：

```cmd
# 复制 DAL Logs
copy ..\output_data\*.csv data\dal_logs\

# 添加 Work Instructions（TXT/PDF/DOCX 格式）
copy your_instructions\*.txt data\work_instructions\
```

---

## 步骤 4: 启动系统（1分钟）

### 方法一：使用启动脚本（推荐）

```cmd
start.bat
```

### 方法二：手动启动

```cmd
# 确保 Ollama 正在运行，然后：
python app.py
```

✅ **等待启动信息**:
```
✓ AI Assistant 系统已启动
✓ Web 界面地址: http://127.0.0.1:5000
✓ 报警监控: 已启动
✓ RAG 系统: 已就绪
```

---

## 步骤 5: 访问 Web 界面

1. 打开浏览器
2. 访问: **http://127.0.0.1:5000**
3. 你应该看到三个主要面板：
   - 📊 实时统计
   - 🚨 报警监控
   - 💬 AI 助手对话

---

## 步骤 6: 初始化知识库（首次使用）

1. 点击界面上的 **"初始化知识库"** 按钮
2. 等待 1-3 分钟（取决于数据量）
3. 看到成功提示

或者使用命令行：

```cmd
python -c "from rag_system import RAGSystem; rag = RAGSystem(); print(rag.initialize_knowledge_base(reload=True))"
```

---

## 步骤 7: 测试功能

### 测试 1: 对话功能

在对话框输入：
```
列车超速报警应该如何处理？
```

AI 应该返回详细的处置步骤。

### 测试 2: 查询功能

```
过去一周 LMC 站发生了几次列车超速报警？
```

AI 会基于 DAL Log 数据回答。

### 测试 3: 报警监控

如果 output_data 文件夹中有新的 CSV 文件，系统会自动检测并显示。

---

## 🎉 完成！

你现在可以：

✅ 通过对话框与 AI 助手交互
✅ 查看实时报警信息
✅ 获取处置建议
✅ 查询历史报警统计

---

## 常见问题快速解决

### Q: Ollama 连接失败？

```cmd
# 检查 Ollama 是否运行
tasklist | findstr ollama

# 如果没有，启动它
ollama serve
```

### Q: Web 界面打不开？

```cmd
# 检查端口是否被占用
netstat -ano | findstr 5000

# 如果被占用，修改 config.py 中的 FLASK_PORT
```

### Q: AI 回答不相关？

1. 点击"初始化知识库"重新加载数据
2. 检查 data 目录中是否有足够的数据
3. 尝试更换 Ollama 模型: `ollama pull llama2`

### Q: 报警不显示？

1. 确认 `../output_data/` 目录存在
2. 检查是否有新的 CSV 文件
3. 查看终端日志是否有错误信息

---

## 下一步

- 📖 阅读完整文档: [README.md](README.md)
- 🔧 详细安装指南: [INSTALL.md](INSTALL.md)
- 💡 了解配置选项: [config.py](config.py)
- 📊 查看项目结构: [README.md#项目结构](README.md#项目结构)

---

## 获取帮助

遇到问题？

1. 查看终端的错误信息
2. 检查 `ai_assistant.log` 日志文件
3. 参考 [故障排除](#常见问题快速解决)
4. 联系开发团队

---

**祝使用愉快！** 🚀

有任何问题都可以在对话框中询问 AI 助手！

