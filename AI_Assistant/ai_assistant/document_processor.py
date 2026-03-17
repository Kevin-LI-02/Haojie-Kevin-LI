"""
文档处理器
用于加载、处理和分块 DAL Log 和 Work Instructions
"""

import os
import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd

from config import (
    DAL_LOGS_DIR,
    WORK_INSTRUCTIONS_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    SUPPORTED_DOC_FORMATS,
    DAL_LOG_DATE_FORMAT
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentProcessor:
    """文档处理器"""
    
    def __init__(self):
        self.dal_logs_dir = Path(DAL_LOGS_DIR)
        self.work_instructions_dir = Path(WORK_INSTRUCTIONS_DIR)
        
    def load_dal_logs(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """
        加载 DAL Log 日志
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            日志记录列表
        """
        logs = []
        
        try:
            for file_path in self.dal_logs_dir.rglob("*.csv"):
                try:
                    df = pd.read_csv(file_path, encoding='utf-8-sig')
                    
                    # 日期过滤
                    if start_date or end_date:
                        if 'timestamp' in df.columns or 'date' in df.columns or 'time' in df.columns:
                            date_col = 'timestamp' if 'timestamp' in df.columns else ('date' if 'date' in df.columns else 'time')
                            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                            
                            if start_date:
                                df = df[df[date_col] >= start_date]
                            if end_date:
                                df = df[df[date_col] <= end_date]
                    
                    # 转换为字典列表
                    for _, row in df.iterrows():
                        log_entry = row.to_dict()
                        log_entry['source'] = str(file_path.name)
                        log_entry['source_type'] = 'dal_log'
                        logs.append(log_entry)
                        
                except Exception as e:
                    logger.error(f"读取 DAL Log 文件失败 {file_path}: {e}")
            
            logger.info(f"✓ 加载了 {len(logs)} 条 DAL Log 记录")
            return logs
            
        except Exception as e:
            logger.error(f"加载 DAL Logs 失败: {e}")
            return []
    
    def load_work_instructions(self) -> List[Dict]:
        """
        加载 Work Instructions
        
        Returns:
            工作指令列表
        """
        instructions = []
        
        try:
            for file_path in self.work_instructions_dir.rglob("*"):
                if file_path.suffix.lower() not in SUPPORTED_DOC_FORMATS:
                    continue
                
                try:
                    content = self._read_file(file_path)
                    if content:
                        instructions.append({
                            'content': content,
                            'source': str(file_path.name),
                            'source_type': 'work_instruction',
                            'path': str(file_path)
                        })
                except Exception as e:
                    logger.error(f"读取 Work Instruction 文件失败 {file_path}: {e}")
            
            logger.info(f"✓ 加载了 {len(instructions)} 个 Work Instructions")
            return instructions
            
        except Exception as e:
            logger.error(f"加载 Work Instructions 失败: {e}")
            return []
    
    def _read_file(self, file_path: Path) -> Optional[str]:
        """读取文件内容"""
        try:
            suffix = file_path.suffix.lower()
            
            if suffix == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            elif suffix == '.csv':
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                return df.to_string()
            
            elif suffix == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return json.dumps(data, ensure_ascii=False, indent=2)
            
            elif suffix == '.pdf':
                # 需要 PyMuPDF 或 pdfplumber
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(file_path)
                    text = ""
                    for page in doc:
                        text += page.get_text()
                    return text
                except ImportError:
                    logger.warning("PDF 支持需要安装 PyMuPDF")
                    return None
            
            elif suffix == '.docx':
                # 需要 python-docx
                try:
                    from docx import Document
                    doc = Document(file_path)
                    return '\n'.join([para.text for para in doc.paragraphs])
                except ImportError:
                    logger.warning("DOCX 支持需要安装 python-docx")
                    return None
            
            else:
                logger.warning(f"不支持的文件格式: {suffix}")
                return None
                
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
            return None
    
    def chunk_text(self, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
        """
        将文本分块
        
        Args:
            text: 原始文本
            chunk_size: 块大小
            overlap: 重叠大小
            
        Returns:
            文本块列表
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            chunk = text[start:end]
            
            # 尝试在句子边界处切分
            if end < text_length:
                # 查找最后一个句号、问号、感叹号或换行符
                last_period = max(
                    chunk.rfind('。'),
                    chunk.rfind('.'),
                    chunk.rfind('?'),
                    chunk.rfind('!'),
                    chunk.rfind('\n')
                )
                if last_period > chunk_size * 0.5:  # 至少保留一半的内容
                    chunk = chunk[:last_period + 1]
                    end = start + len(chunk)
            
            chunks.append(chunk.strip())
            start = end - overlap
        
        return [c for c in chunks if c]  # 过滤空块
    
    def process_dal_logs_for_rag(self, logs: List[Dict]) -> List[Dict]:
        """
        处理 DAL Logs 用于 RAG
        
        Args:
            logs: DAL Log 记录列表
            
        Returns:
            处理后的文档列表
        """
        documents = []
        
        for log in logs:
            # 构建文本表示
            text_parts = []
            for key, value in log.items():
                if key not in ['source', 'source_type'] and pd.notna(value):
                    text_parts.append(f"{key}: {value}")
            
            text = "\n".join(text_parts)
            
            # 分块
            chunks = self.chunk_text(text, chunk_size=300, overlap=30)
            
            for i, chunk in enumerate(chunks):
                documents.append({
                    'text': chunk,
                    'metadata': {
                        'source': log.get('source', 'unknown'),
                        'source_type': 'dal_log',
                        'chunk_id': i,
                        'timestamp': log.get('timestamp', ''),
                        'station': log.get('station', ''),
                        'alarm_type': log.get('alarm_type', '')
                    }
                })
        
        return documents
    
    def process_work_instructions_for_rag(self, instructions: List[Dict]) -> List[Dict]:
        """
        处理 Work Instructions 用于 RAG
        
        Args:
            instructions: Work Instruction 列表
            
        Returns:
            处理后的文档列表
        """
        documents = []
        
        # 报警类型关键词（用于自动标记）
        alarm_keywords = {
            '列车超速': ['列车超速', '超速'],
            '道岔故障': ['道岔故障', '道岔'],
            '电源故障': ['电源故障', '电源', '供电'],
            '信号故障': ['信号故障', '信号'],
            '通信故障': ['通信故障', '通信'],
            '进路故障': ['进路故障', '进路'],
        }
        
        for instruction in instructions:
            content = instruction.get('content', '')
            source = instruction.get('source', 'unknown')
            
            # 自动识别文档的报警类型（基于文件名）
            detected_alarm_type = None
            for alarm_type, keywords in alarm_keywords.items():
                if any(kw in source for kw in keywords):
                    detected_alarm_type = alarm_type
                    break
            
            # 分块
            chunks = self.chunk_text(content)
            
            for i, chunk in enumerate(chunks):
                # 为每个分块添加丰富的元数据
                metadata = {
                    'source': source,
                    'source_type': 'work_instruction',
                    'chunk_id': i,
                    'total_chunks': len(chunks),
                    'path': instruction.get('path', '')
                }
                
                # 添加报警类型标记（重要！）
                if detected_alarm_type:
                    metadata['alarm_type'] = detected_alarm_type
                
                documents.append({
                    'text': chunk,
                    'metadata': metadata
                })
        
        logger.info(f"✓ 处理完成: {len(instructions)} 个文件 → {len(documents)} 个文档块")
        
        return documents
    
    def analyze_alarm_frequency(
        self,
        logs: List[Dict],
        alarm_type: Optional[str] = None,
        station: Optional[str] = None,
        days: int = 30
    ) -> Dict:
        """
        分析报警频率
        
        Args:
            logs: DAL Log 记录
            alarm_type: 报警类型过滤
            station: 站点过滤
            days: 分析天数
            
        Returns:
            统计结果
        """
        try:
            df = pd.DataFrame(logs)
            
            if df.empty:
                return {'total': 0, 'daily_average': 0, 'details': []}
            
            # 确保有时间戳列
            date_col = None
            for col in ['timestamp', 'date', 'time']:
                if col in df.columns:
                    date_col = col
                    break
            
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                
                # 过滤最近N天
                cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=days)
                df = df[df[date_col] >= cutoff_date]
            
            # 过滤条件
            if alarm_type and 'alarm_type' in df.columns:
                df = df[df['alarm_type'] == alarm_type]
            
            if station and 'station' in df.columns:
                df = df[df['station'] == station]
            
            total = len(df)
            daily_avg = total / days if days > 0 else 0
            
            return {
                'total': total,
                'daily_average': round(daily_avg, 2),
                'period_days': days,
                'alarm_type': alarm_type,
                'station': station,
                'details': df.to_dict('records')[:10]  # 返回前10条详细记录
            }
            
        except Exception as e:
            logger.error(f"分析报警频率失败: {e}")
            return {'total': 0, 'daily_average': 0, 'error': str(e)}


# 测试函数
def test_document_processor():
    """测试文档处理器"""
    processor = DocumentProcessor()
    
    print("测试文档处理器...")
    
    # 测试 DAL Logs
    logs = processor.load_dal_logs()
    print(f"✓ 加载 DAL Logs: {len(logs)} 条记录")
    
    # 测试 Work Instructions
    instructions = processor.load_work_instructions()
    print(f"✓ 加载 Work Instructions: {len(instructions)} 个文档")
    
    # 测试文本分块
    test_text = "这是一个测试文本。" * 100
    chunks = processor.chunk_text(test_text)
    print(f"✓ 文本分块: {len(chunks)} 个块")


if __name__ == "__main__":
    test_document_processor()

