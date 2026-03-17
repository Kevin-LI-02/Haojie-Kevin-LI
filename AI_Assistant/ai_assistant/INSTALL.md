# EYES-T AI Assistant 安装指南

## 🎯 安装步骤总览

1. 安装 Ollama
2. 安装 Python 依赖
3. 准备数据
4. 启动系统

---

## 1️⃣ 安装 Ollama

### Windows 安装

1. **下载 Ollama**
   - 访问: https://ollama.ai/download
   - 下载 Windows 安装包
   - 运行安装程序

2. **启动 Ollama 服务**
   ```cmd
   ollama serve
   ```
   保持此窗口打开

3. **下载模型**（在新终端中）
   ```cmd
   # 推荐：中文优化模型
   ollama pull qwen:7b
   
   # 或者：通用英文模型
   ollama pull llama2
   
   # 可选：其他模型
   ollama pull mistral
   ollama pull codellama
   ```

4. **验证安装**
   ```cmd
   ollama list
   ```
   应该能看到已下载的模型

### macOS/Linux 安装

```bash
# 安装 Ollama
curl https://ollama.ai/install.sh | sh

# 启动服务
ollama serve &

# 下载模型
ollama pull qwen:7b
```

---

## 2️⃣ 安装 Python 依赖

### 激活环境

```cmd
conda activate eyes_t
```

### 切换到项目目录

```cmd
cd C:\Users\16254\Desktop\MTR_EyesT\PaddleOCR\AI_Ass\ai_assistant
```

### 安装依赖

**方法一：使用清华镜像（推荐，速度快）**
```cmd
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**方法二：使用默认源**
```cmd
pip install -r requirements.txt
```

### 验证安装

```cmd
python -c "import flask, chromadb, sentence_transformers; print('✓ 依赖安装成功')"
```

---

## 3️⃣ 准备数据

### 创建数据目录

AI Assistant 会自动创建所需目录，但你也可以手动创建：

```cmd
mkdir data
mkdir data\dal_logs
mkdir data\work_instructions
mkdir data\vector_store
```

### 准备 DAL Log 数据

**位置**: `data/dal_logs/`

**格式**: CSV 文件

**示例**: 创建 `dal_log_2024.csv`
```csv
timestamp,station,alarm_type,description,severity
2024-01-15 08:30:00,LMC,列车超速,列车速度超过限制80km/h达到95km/h,high
2024-01-15 09:15:00,TWO,道岔故障,3号道岔转换失败无法完成,critical
2024-01-15 10:00:00,FOT,信号灯故障,进站信号灯显示异常,medium
2024-01-15 11:30:00,LMC,列车晚点,列车晚点5分钟,low
2024-01-15 13:00:00,ADM,平台门故障,1号平台门无法正常开启,high
```

**可以直接使用现有的 output_data 文件**:
```cmd
# 复制现有数据到 dal_logs
copy ..\output_data\*.csv data\dal_logs\
```

### 准备 Work Instructions

**位置**: `data/work_instructions/`

**格式**: TXT, PDF, DOCX, CSV

**示例**: 创建 `列车超速处理指南.txt`
```
报警类型：列车超速

定义：
列车实际运行速度超过该区段允许的最高限速值。

严重程度：高

处置步骤：

1. 立即行动（第一时间）
   - 通过无线电联系列车司机
   - 要求司机立即减速至限速以内
   - 确认司机收到指令

2. 情况评估
   - 记录超速时间、地点、速度值
   - 检查该区段的限速标志是否正常
   - 查看监控录像确认情况

3. 系统检查
   - 检查 ATP（列车自动防护）系统状态
   - 检查信号系统是否正常工作
   - 检查速度检测设备

4. 后续处理
   - 如系统正常但列车超速，记录司机违规
   - 如系统故障，立即通知维护人员
   - 填写事件报告表
   - 必要时启动应急预案

5. 预防措施
   - 加强司机培训
   - 定期检查 ATP 系统
   - 优化限速标志设置

注意事项：
- 列车超速可能导致严重事故，必须第一时间处理
- 保持与司机的持续通信
- 如多次出现同类问题，需深入调查原因
```

**示例**: 创建 `道岔故障处理指南.txt`
```
报警类型：道岔故障

定义：
道岔无法正常转换到指定位置，或转换后位置不正确。

严重程度：紧急

处置步骤：

1. 紧急响应
   - 立即暂停该区域列车调度
   - 通知所有相关列车减速或停车
   - 确认没有列车正在通过故障道岔

2. 现场检查
   - 通知维护人员前往现场
   - 检查道岔外观是否有异物
   - 检查道岔转辙机状态
   - 检查控制电路

3. 故障诊断
   常见原因：
   - 转辙机卡滞或损坏
   - 道岔夹有异物（石子、杂物）
   - 电气系统故障
   - 控制回路断线

4. 应急处理
   - 如能手动操作，在确保安全后手动转换
   - 清除影响道岔的异物
   - 临时修复电气故障
   - 无法修复时，调整列车路径

5. 修复确认
   - 测试道岔多次转换
   - 确认位置检测正常
   - 确认锁定装置有效
   - 恢复正常运营前需检查通过

6. 记录归档
   - 详细记录故障现象
   - 记录处理过程和时间
   - 分析故障原因
   - 提出改进建议

应急联系：
- 维护中心：xxxx
- 调度中心：xxxx
- 紧急热线：xxxx
```

---

## 4️⃣ 启动系统

### 方法一：使用启动脚本（最简单）

```cmd
start.bat
```

### 方法二：手动启动

**步骤 1**: 确保 Ollama 运行
```cmd
# 在终端 1
ollama serve
```

**步骤 2**: 启动 AI Assistant
```cmd
# 在终端 2
conda activate eyes_t
cd ai_assistant
python app.py
```

### 访问 Web 界面

打开浏览器，访问:
```
http://127.0.0.1:5000
```

---

## 5️⃣ 初始化知识库

### 首次使用

1. 打开 Web 界面
2. 点击"初始化知识库"按钮
3. 等待加载完成（可能需要几分钟）

### 命令行初始化

```cmd
python -c "from rag_system import RAGSystem; rag = RAGSystem(); stats = rag.initialize_knowledge_base(reload=True); print(stats)"
```

---

## ✅ 验证安装

### 1. 检查 Ollama

```cmd
curl http://localhost:11434/api/tags
```

应该返回模型列表的 JSON 数据

### 2. 检查 Python 模块

```cmd
python
>>> from rag_system import RAGSystem
>>> rag = RAGSystem()
>>> status = rag.get_system_status()
>>> print(status)
```

应该显示系统状态正常

### 3. 访问 Web 界面

打开 http://127.0.0.1:5000

应该能看到:
- 实时统计面板
- 报警监控面板
- AI 对话面板

---

## 🔧 常见问题

### Q1: Ollama 无法连接

**解决方案**:
```cmd
# 检查 Ollama 是否运行
tasklist | findstr ollama

# 如果没有运行，启动它
ollama serve

# 检查端口
netstat -ano | findstr 11434
```

### Q2: ChromaDB 初始化失败

**解决方案**:
```cmd
# 删除旧的向量数据库
rmdir /s /q data\vector_store

# 重新启动系统
python app.py
```

### Q3: 模型下载失败

**解决方案**:
```cmd
# 使用代理（如需要）
set http_proxy=http://your-proxy:port
set https_proxy=http://your-proxy:port

# 重新下载
ollama pull qwen:7b
```

### Q4: 依赖安装失败

**解决方案**:
```cmd
# 使用国内镜像
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 分步安装
pip install flask flask-cors
pip install pandas numpy
pip install chromadb
pip install sentence-transformers
```

---

## 📊 系统要求

### 最低配置

- CPU: 4核
- RAM: 8GB
- 硬盘: 20GB 可用空间
- 操作系统: Windows 10/11, macOS 10.15+, Linux

### 推荐配置

- CPU: 8核以上
- RAM: 16GB 以上
- GPU: NVIDIA GPU with 8GB+ VRAM
- 硬盘: 50GB 可用空间（SSD）
- 操作系统: Windows 11, Ubuntu 22.04+

---

## 🚀 下一步

安装完成后：

1. 阅读 [README.md](README.md) 了解详细功能
2. 查看 [示例数据](#3️⃣-准备数据) 准备你的数据
3. 探索 Web 界面的各项功能
4. 尝试提问并测试 AI 回答质量

---

## 📞 获取帮助

如果遇到问题：

1. 查看终端的错误信息
2. 检查 `ai_assistant.log` 日志文件
3. 参考 README.md 的故障排除部分
4. 联系开发团队

---

**祝使用愉快！** 🎉

