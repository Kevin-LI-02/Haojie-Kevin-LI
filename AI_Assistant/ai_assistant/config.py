"""
AI Assistant 配置文件
Configuration for AI Assistant System
"""

import os
from pathlib import Path

# 基础路径配置
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
VECTOR_STORE_DIR = DATA_DIR / "vector_store"
DAL_LOGS_DIR = DATA_DIR / "dal_logs"
WORK_INSTRUCTIONS_DIR = DATA_DIR / "work_instructions"
OUTPUT_DATA_DIR = PROJECT_ROOT / "output_data"

# 创建必要的目录
for dir_path in [DATA_DIR, VECTOR_STORE_DIR, DAL_LOGS_DIR, WORK_INSTRUCTIONS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Ollama API 配置
OLLAMA_API_BASE = "http://localhost:11434"  # Ollama 默认地址
OLLAMA_MODEL = "qwen2.5:7b"  # 默认模型，可以改为 qwen, mistral 等
OLLAMA_TIMEOUT = 120  # API 超时时间（秒）

# 向量数据库配置
VECTOR_DB_TYPE = "chromadb"  # 可选: chromadb, faiss
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 嵌入模型
CHUNK_SIZE = 500  # 文档分块大小
CHUNK_OVERLAP = 50  # 分块重叠大小
TOP_K_RESULTS = 5  # 检索返回的相关文档数量

# Web 服务配置
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
FLASK_DEBUG = True
SECRET_KEY = "eyes-t-ai-assistant-secret-key-2025"

# 报警监控配置
ALARM_MONITOR_INTERVAL = 5  # 报警监控间隔（秒）
MAX_RECENT_ALARMS = 50  # 保留的最近报警数量

# 对话配置
MAX_CONVERSATION_HISTORY = 10  # 对话历史保留条数
SYSTEM_PROMPT = """你是 EYES-T 系统的智能助手，专门协助铁路运营人员处理报警信息。
你的职责包括：
1. 分析和解释报警信息
2. 提供基于历史数据的统计分析
3. 根据 Work Instructions 提供处置建议
4. 回答关于报警历史、频率、趋势的问题

请用专业、清晰、简洁的方式回答问题。如果不确定，请明确说明。
始终优先考虑安全和准确性。"""

# 日志配置
LOG_LEVEL = "INFO"
LOG_FILE = BASE_DIR / "ai_assistant.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# DAL Log 数据配置
DAL_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DAL_LOG_COLUMNS = ["timestamp", "station", "alarm_type", "description", "severity"]

# 支持的文件格式
SUPPORTED_DOC_FORMATS = [".txt", ".csv", ".pdf", ".docx", ".json"]

# 报警优先级配置
ALARM_PRIORITY_LEVELS = {
    "critical": "紧急",
    "high": "高",
    "medium": "中",
    "low": "低"
}

# API 配置
API_RATE_LIMIT = 100  # 每分钟最大请求数
API_RESPONSE_TIMEOUT = 30  # API 响应超时（秒）

# 缓存配置
ENABLE_CACHE = True
CACHE_TTL = 3600  # 缓存过期时间（秒）

# 前端配置
WEB_TITLE = "EYES-T AI Assistant"
WEB_DESCRIPTION = "智能报警分析与处置助手"
REFRESH_INTERVAL = 5000  # 前端刷新间隔（毫秒）

# 数据库配置（如果需要存储对话历史）
DB_TYPE = "sqlite"  # 可选: sqlite, postgresql
DB_PATH = DATA_DIR / "ai_assistant.db"

print(f"✓ 配置文件已加载")
print(f"  - 数据目录: {DATA_DIR}")
print(f"  - Ollama API: {OLLAMA_API_BASE}")
print(f"  - 向量数据库: {VECTOR_DB_TYPE}")

