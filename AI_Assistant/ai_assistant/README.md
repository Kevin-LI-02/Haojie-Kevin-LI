# EYES-T AI Assistant 智能助手系统

## 📋 项目简介

EYES-T AI Assistant 是一个基于大语言模型和 RAG（检索增强生成）技术的智能助手系统，专为铁路运营报警分析和处置而设计。

### 主要功能

1. **实时报警监控** - 自动监控 output_data 文件夹中的新报警信息
2. **智能分析** - 使用 LLM 分析报警原因和影响
3. **处置建议** - 基于 Work Instructions 提供专业的处置方案
4. **历史查询** - 查询 DAL Log 中的历史报警记录和统计
5. **对话交互** - 类似 ChatGPT 的自然语言问答界面

### 技术架构

- **前端**: HTML + CSS + JavaScript
- **后端**: Flask Web 框架
- **LLM 服务**: Ollama (本地部署)
- **向量数据库**: ChromaDB
- **嵌入模型**: sentence-transformers
- **RAG 框架**: 自研 Python 实现

## 🚀 快速开始

### 1. 环境要求

- Python 3.10 或更高版本
- Conda (推荐使用 eyes_t 环境)
- Ollama (用于运行大语言模型)
- 至少 8GB RAM
- （推荐）GPU 支持

### 2. 安装 Ollama

**Windows:**
1. 访问 https://ollama.ai/ 下载安装包
2. 安装完成后，打开终端运行:
```bash
ollama serve
```

3. 下载模型（在新终端中）:
```bash
# 推荐模型
ollama pull llama2        # 英文模型（7B）
ollama pull qwen:7b       # 中文优化模型
ollama pull mistral       # 另一个不错的选择
```

### 3. 安装依赖

```bash
# 激活 eyes_t 环境
conda activate eyes_t

# 切换到 ai_assistant 目录
cd C:\Users\16254\Desktop\MTR_EyesT\PaddleOCR\AI_Ass\ai_assistant

# 安装 Python 依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4. 准备数据

在 `data` 目录下准备以下数据：

**DAL Logs** (历史报警日志):
- 路径: `data/dal_logs/`
- 格式: CSV 文件
- 必需字段: timestamp, station, alarm_type, description, severity

**Work Instructions** (工作指令/处置方案):
- 路径: `data/work_instructions/`
- 格式: TXT, PDF, DOCX, CSV
- 内容: 各类报警的处置流程和操作步骤

**示例 DAL Log CSV:**
```csv
timestamp,station,alarm_type,description,severity
2024-01-01 10:30:00,LMC,列车超速,列车速度超过限制80km/h,high
2024-01-01 11:20:00,TWO,道岔故障,3号道岔无法转换,critical
```

**示例 Work Instruction TXT:**
```
报警类型：列车超速

处置步骤：
1. 立即通知列车司机减速
2. 检查信号系统是否正常
3. 如有异常，通知维护人员
4. 记录事件详情
5. 填写报警处理表单
```

### 5. 启动系统

**方法一：使用启动脚本（推荐）**
```bash
start.bat
```

**方法二：手动启动**
```bash
# 确保 Ollama 服务已运行
ollama serve

如果无法启动ollama serve，那么就运行：netstat -ano -p TCP | findstr :11434
                                    taskkill /F /IM ollama* 2>$null 
# 在另一个终端启动 AI Assistant
conda activate eyes_t
cd ai_assistant
python app.py
```

### 6. 访问界面

打开浏览器访问: http://127.0.0.1:5000

## 📖 使用指南

### 初始化知识库

首次使用前，需要初始化知识库：

1. 在 Web 界面点击"初始化知识库"按钮
2. 系统会自动加载 DAL Logs 和 Work Instructions
3. 建立向量索引，这可能需要几分钟

### 报警监控

系统会自动监控 `../output_data/` 文件夹：

- 每 5 秒检查一次新报警
- 自动分析并显示在界面上
- 提供 AI 分析和处置建议

### 对话交互

在对话框中输入问题，AI 助手会基于知识库回答：

**示例问题：**
- "过去一个月 LMC 站的列车超速报警发生了几次？"
- "道岔故障应该如何处理？"
- "请分析最近的报警趋势"
- "TWO 站 3号道岔故障的处置流程是什么？"

### 报警分析

点击任意报警项，系统会：
1. 检索相关历史记录
2. 查找对应的 Work Instructions
3. 使用 LLM 生成分析报告
4. 提供处置建议

## 🔧 配置说明

主要配置文件: `config.py`

### Ollama 配置
```python
OLLAMA_API_BASE = "http://localhost:11434"  # Ollama 服务地址
OLLAMA_MODEL = "llama2"                     # 使用的模型
OLLAMA_TIMEOUT = 120                        # 超时时间（秒）
```

### 向量数据库配置
```python
VECTOR_DB_TYPE = "chromadb"                 # 向量数据库类型
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 嵌入模型
CHUNK_SIZE = 500                            # 文档分块大小
TOP_K_RESULTS = 5                           # 检索结果数量
```

### Web 服务配置
```python
FLASK_HOST = "127.0.0.1"                    # 监听地址
FLASK_PORT = 5000                           # 监听端口
FLASK_DEBUG = True                          # 调试模式
```

## 📁 项目结构

```
ai_assistant/
├── app.py                   # Flask 主应用
├── config.py                # 配置文件
├── ollama_client.py         # Ollama API 客户端
├── vector_db.py             # 向量数据库管理
├── document_processor.py    # 文档处理器
├── rag_system.py            # RAG 系统核心
├── alarm_monitor.py         # 报警监控器
├── requirements.txt         # Python 依赖
├── start.bat                # 启动脚本
├── README.md                # 本文档
├── templates/               # HTML 模板
│   └── index.html          # Web 界面
└── data/                    # 数据目录
    ├── dal_logs/           # DAL Log 存储
    ├── work_instructions/  # Work Instructions 存储
    └── vector_store/       # 向量数据库存储
```

## 🔌 API 接口

### 系统状态
```
GET /api/status
返回系统运行状态和统计信息
```

### 对话接口
```
POST /api/chat
Body: {"question": "用户问题"}
返回 AI 生成的回答
```

### 最新报警
```
GET /api/alarms/latest?count=20
返回最近的报警列表
```

### 报警统计
```
GET /api/alarms/summary
返回报警统计摘要
```

### 报警分析
```
POST /api/alarms/analyze
Body: {"alarm_data": {...}}
返回详细的报警分析
```

### 报警频率查询
```
POST /api/alarms/frequency
Body: {"alarm_type": "类型", "station": "站点", "days": 30}
返回指定时间段的报警频率统计
```

### 获取处置指令
```
GET /api/instructions/{alarm_type}?station={station}
返回指定报警类型的处置指令
```

### 初始化知识库
```
POST /api/knowledge/init
Body: {"reload": true}
重新加载知识库
```

## 🎯 高级功能

### 自定义 System Prompt

在 `config.py` 中修改系统提示词:
```python
SYSTEM_PROMPT = """你的自定义提示词..."""
```

### 切换 LLM 模型

1. 下载其他模型:
```bash
ollama pull qwen:7b    # 中文优化
ollama pull codellama  # 代码优化
```

2. 修改配置:
```python
OLLAMA_MODEL = "qwen:7b"
```

### 多模型支持

系统支持在运行时切换模型，在 Web 界面或通过 API 修改。

### 数据持久化

- 向量数据库自动保存在 `data/vector_store/`
- 无需重复加载，除非数据更新

## ⚠️ 故障排除

### Ollama 连接失败
- 确保 Ollama 服务运行: `ollama serve`
- 检查端口是否被占用: `netstat -ano | findstr 11434`
- 查看 Ollama 日志

### 知识库初始化失败
- 检查 `data/dal_logs/` 和 `data/work_instructions/` 目录是否存在
- 确保 CSV 文件格式正确
- 查看终端错误信息

### 报警监控无数据
- 确认 `../output_data/` 目录存在且有 CSV 文件
- 检查文件权限
- 查看监控日志

### 向量检索结果不准确
- 增加 `TOP_K_RESULTS` 值
- 调整 `CHUNK_SIZE` 优化分块
- 考虑使用更好的嵌入模型

## 📊 性能优化

1. **使用 GPU 加速**
   - 安装 GPU 版本的 sentence-transformers
   - 配置 Ollama 使用 GPU

2. **调整批处理大小**
   - 在 `vector_db.py` 中调整 batch_size

3. **缓存策略**
   - 启用缓存: `ENABLE_CACHE = True`

## 🔐 安全建议

1. 不要在公网暴露服务
2. 修改默认 SECRET_KEY
3. 添加用户认证机制
4. 定期备份向量数据库

## 📝 开发计划

- [ ] 添加用户认证系统
- [ ] 支持更多文档格式
- [ ] 实现报警预测功能
- [ ] 多语言支持
- [ ] 移动端适配
- [ ] 报表生成功能

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目仅供 EYES-T 系统内部使用。

## 📞 联系方式

如有问题，请联系开发团队。

---

**最后更新**: 2025-11-27
**版本**: 1.0.0

