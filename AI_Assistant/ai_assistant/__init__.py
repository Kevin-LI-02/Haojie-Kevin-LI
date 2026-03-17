"""
EYES-T AI Assistant 智能助手系统
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "EYES-T Development Team"
__description__ = "智能报警分析与处置助手系统"

from .rag_system import RAGSystem
from .alarm_monitor import AlarmMonitor
from .ollama_client import OllamaClient
from .vector_db import VectorDatabase
from .document_processor import DocumentProcessor

__all__ = [
    'RAGSystem',
    'AlarmMonitor',
    'OllamaClient',
    'VectorDatabase',
    'DocumentProcessor',
]

