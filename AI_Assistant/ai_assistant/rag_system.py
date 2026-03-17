"""
RAG (Retrieval-Augmented Generation) 系统
整合文档检索和大语言模型生成
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from document_processor import DocumentProcessor
from vector_db import VectorDatabase
from ollama_client import OllamaClient
from config import TOP_K_RESULTS
from advanced_rag import AdvancedRAG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGSystem:
    """RAG 系统"""
    
    def __init__(self):
        """初始化 RAG 系统"""
        self.doc_processor = DocumentProcessor()
        self.vector_db = VectorDatabase()
        self.llm_client = OllamaClient()
        self.conversation_history = []
        
        logger.info("✓ RAG 系统初始化完成")
    
    def initialize_knowledge_base(self, reload: bool = False) -> Dict:
        """
        初始化知识库
        
        Args:
            reload: 是否重新加载所有文档
            
        Returns:
            初始化统计信息
        """
        logger.info("开始初始化知识库...")
        stats = {
            'dal_logs': 0,
            'work_instructions': 0,
            'total_documents': 0,
            'status': 'success'
        }
        
        try:
            # 如果需要重新加载，清空现有数据
            if reload:
                self.vector_db.clear_collection()
                logger.info("已清空现有知识库")
            
            # 加载 DAL Logs
            logger.info("正在加载 DAL Logs...")
            dal_logs = self.doc_processor.load_dal_logs()
            if dal_logs:
                dal_docs = self.doc_processor.process_dal_logs_for_rag(dal_logs)
                dal_count = self.vector_db.add_documents(dal_docs)
                stats['dal_logs'] = dal_count
                logger.info(f"✓ 加载 DAL Logs: {dal_count} 个文档块")
            
            # 加载 Work Instructions
            logger.info("正在加载 Work Instructions...")
            work_instructions = self.doc_processor.load_work_instructions()
            if work_instructions:
                wi_docs = self.doc_processor.process_work_instructions_for_rag(work_instructions)
                wi_count = self.vector_db.add_documents(wi_docs)
                stats['work_instructions'] = wi_count
                logger.info(f"✓ 加载 Work Instructions: {wi_count} 个文档块")
            
            # 更新总计
            stats['total_documents'] = stats['dal_logs'] + stats['work_instructions']
            
            # 获取向量数据库统计信息
            db_stats = self.vector_db.get_collection_stats()
            stats.update(db_stats)
            
            logger.info(f"✓ 知识库初始化完成，共 {stats['total_documents']} 个文档")
            
        except Exception as e:
            logger.error(f"初始化知识库失败: {e}")
            stats['status'] = 'error'
            stats['error'] = str(e)
        
        return stats
    
    def query(
        self,
        question: str,
        use_history: bool = True,
        n_results: int = TOP_K_RESULTS,
        mode: str = "auto"
    ) -> Dict:
        """
        查询系统（支持通用问答）
        
        Args:
            question: 用户问题
            use_history: 是否使用对话历史
            n_results: 检索文档数量
            mode: 问答模式 - "auto"(自动), "strict"(严格-仅知识库), "general"(通用-任意问题)
            
        Returns:
            回答结果
        """
        try:
            # 1. 智能判断问题类型（用于 auto 模式）
            classification = AdvancedRAG.classify_question(question)
            logger.info(f"✓ 问题分类: {classification['description']}")
            logger.info(f"  类型: {classification['type']}, 报警: {classification.get('alarm_type', 'None')}")
            
            # 2. 根据模式决定是否检索文档
            if mode == 'strict':
                # 专业模式：强制使用知识库
                should_use_kb = True
                logger.info("✓ 专业模式：强制使用知识库")
            elif mode == 'auto':
                # 智能模式：根据问题分类自动决定
                professional_types = ['procedure', 'statistics', 'recent_event', 'definition']
                if classification['type'] in professional_types or classification.get('alarm_type'):
                    should_use_kb = True
                    mode = "strict"
                    logger.info(f"✓ 智能模式：检测到专业问题，自动切换到知识库模式")
                else:
                    should_use_kb = False
                    mode = "general"
                    logger.info(f"✓ 智能模式：检测到通用问题，使用通用模式")
            else:
                # 通用模式：不使用知识库
                should_use_kb = False
                mode = "general"
                logger.info("⊙ 通用模式：不使用知识库")
            
            # 3. 如果需要使用知识库，执行检索
            retrieved_docs = None
            doc_contents = []
            
            if should_use_kb:
                logger.info(f"检索相关文档: {question}")
                
                # 使用高级 RAG 智能检索
                retrieved_docs = AdvancedRAG.smart_retrieve(
                    self.vector_db, 
                    question, 
                    n_results=n_results
                )
                
                # 提取文档内容
                if retrieved_docs and isinstance(retrieved_docs, list):
                    for doc_dict in retrieved_docs:
                        content = doc_dict.get('content', '')
                        if content and content.strip():
                            doc_contents.append(content)
                
                logger.info(f"✓ 提取到 {len(doc_contents)} 个有效文档内容")
                
                # 如果没有检索到文档，降级到通用模式
                if len(doc_contents) == 0:
                    mode = "general"
                    retrieved_docs = None
                    logger.warning("⚠️ 未检索到文档，降级到通用模式")
            
            # 4. 构建对话历史
            history = self.conversation_history if use_history else []
            
            # 5. 根据模式生成回答
            logger.info(f"生成回答 (模式: {mode})...")
            
            if mode == "general":
                # 通用模式：不限制答案范围，像 ChatGPT 一样回答
                answer = self.llm_client.chat_general(
                    question=question,
                    conversation_history=history
                )
            else:
                # 严格模式：基于知识库回答
                answer = self.llm_client.generate_with_rag(
                    question=question,
                    retrieved_docs=retrieved_docs,
                    conversation_history=history
                )
            
            # 6. 更新对话历史
            if use_history:
                self.conversation_history.append({"role": "user", "content": question})
                self.conversation_history.append({"role": "assistant", "content": answer})
                
                # 限制历史长度
                from config import MAX_CONVERSATION_HISTORY
                if len(self.conversation_history) > MAX_CONVERSATION_HISTORY * 2:
                    self.conversation_history = self.conversation_history[-MAX_CONVERSATION_HISTORY * 2:]
            
            return {
                'answer': answer,
                'sources': retrieved_docs,
                'question': question,
                'mode': mode,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"查询失败: {e}")
            return {
                'answer': f"抱歉，查询时发生错误: {str(e)}",
                'sources': [],
                'question': question,
                'error': str(e)
            }
    
    def _is_relevant(self, question: str, doc_contents: List[str]) -> bool:
        """
        判断检索到的文档是否与问题相关（更严格的判断）
        
        Args:
            question: 用户问题
            doc_contents: 检索到的文档内容列表
            
        Returns:
            是否相关
        """
        if not doc_contents:
            logger.warning("没有检索到任何文档")
            return False
        
        question_lower = question.lower()
        
        # EYES-T 专业关键词（更全面）
        professional_keywords = [
            # 中文关键词
            "报警", "列车", "道岔", "电源", "超速", "故障", "处理", "处置",
            "信号", "轨道", "站台", "进路", "闭塞", "联锁", "atp", "ats",
            # 英文关键词
            "alarm", "train", "turnout", "power", "signal", "track",
            "platform", "route", "overspeed", "fault", "failure",
            # 站点关键词
            "lmc", "低窝", "shs", "上水", "low", "罗湖", "sheung shui",
            # 操作关键词
            "如何", "怎么", "应该", "处理", "解决", "操作", "步骤"
        ]
        
        # 1. 检查是否包含专业关键词
        has_keywords = any(kw in question_lower for kw in professional_keywords)
        
        # 2. 检查文档内容质量
        doc_text = " ".join(doc_contents).lower()
        
        # 统计文档中包含的专业关键词数量
        keywords_in_docs = sum(1 for kw in professional_keywords if kw in doc_text)
        
        # 3. 判断逻辑
        if has_keywords:
            # 如果问题包含专业关键词
            if keywords_in_docs >= 3:
                # 文档中也有足够的专业关键词，认为相关
                logger.info(f"✓ 专业问题匹配，检索到 {keywords_in_docs} 个关键词，使用知识库")
                return True
            else:
                # 文档相关性不足，但仍使用知识库（避免误判）
                logger.info(f"⚠️ 专业问题但文档相关性低 ({keywords_in_docs} 个关键词)，仍使用知识库")
                return True
        else:
            # 非专业问题，使用通用模式
            logger.info("× 非专业问题，使用通用模式")
            return False
    
    def analyze_alarm(self, alarm_data: Dict) -> Dict:
        """
        分析报警信息
        
        Args:
            alarm_data: 报警数据
            
        Returns:
            分析结果
        """
        try:
            # 1. 构建查询
            alarm_type = alarm_data.get('alarm_type', '')
            station = alarm_data.get('station', '')
            description = alarm_data.get('description', '')
            
            query = f"报警类型: {alarm_type}, 站点: {station}, 描述: {description}"
            
            # 2. 检索相关历史记录和处置方案
            retrieved_docs = self.vector_db.search(query, n_results=5)
            
            # 3. 使用 LLM 分析
            analysis = self.llm_client.analyze_alarm(alarm_data)
            
            # 4. 获取相关 Work Instructions
            work_instructions = [
                doc for doc in retrieved_docs 
                if doc.get('metadata', {}).get('source_type') == 'work_instruction'
            ]
            
            return {
                'alarm_data': alarm_data,
                'analysis': analysis,
                'work_instructions': work_instructions,
                'related_history': retrieved_docs,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"报警分析失败: {e}")
            return {
                'alarm_data': alarm_data,
                'analysis': f"分析失败: {str(e)}",
                'error': str(e)
            }
    
    def query_alarm_frequency(
        self,
        alarm_type: Optional[str] = None,
        station: Optional[str] = None,
        days: int = 30
    ) -> Dict:
        """
        查询报警频率
        
        Args:
            alarm_type: 报警类型
            station: 站点
            days: 查询天数
            
        Returns:
            频率统计
        """
        try:
            # 加载 DAL Logs
            logs = self.doc_processor.load_dal_logs()
            
            # 分析频率
            stats = self.doc_processor.analyze_alarm_frequency(
                logs=logs,
                alarm_type=alarm_type,
                station=station,
                days=days
            )
            
            # 生成自然语言描述
            if alarm_type and station:
                desc = f"在过去 {days} 天内，{station} 站的 {alarm_type} 类型报警"
            elif alarm_type:
                desc = f"在过去 {days} 天内，{alarm_type} 类型报警"
            elif station:
                desc = f"在过去 {days} 天内，{station} 站的报警"
            else:
                desc = f"在过去 {days} 天内的报警"
            
            desc += f"共发生 {stats['total']} 次，日均 {stats['daily_average']} 次。"
            
            stats['description'] = desc
            return stats
            
        except Exception as e:
            logger.error(f"查询报警频率失败: {e}")
            return {
                'error': str(e),
                'description': "查询失败"
            }
    
    def get_处置建议(self, alarm_type: str, station: Optional[str] = None) -> List[Dict]:
        """
        获取处置建议
        
        Args:
            alarm_type: 报警类型
            station: 站点（可选）
            
        Returns:
            处置建议列表
        """
        try:
            # 构建查询
            query = f"{alarm_type} 处置方案 操作步骤"
            if station:
                query += f" {station}站"
            
            # 检索 Work Instructions
            docs = self.vector_db.search(query, n_results=5)
            
            # 过滤出 Work Instructions
            instructions = [
                doc for doc in docs 
                if doc.get('metadata', {}).get('source_type') == 'work_instruction'
            ]
            
            return instructions
            
        except Exception as e:
            logger.error(f"获取处置建议失败: {e}")
            return []
    
    def clear_conversation_history(self):
        """清空对话历史"""
        self.conversation_history = []
        logger.info("✓ 对话历史已清空")
    
    def get_system_status(self) -> Dict:
        """获取系统状态"""
        try:
            # 检查 Ollama 连接
            ollama_status = self.llm_client.check_connection()
            
            # 获取向量数据库统计
            vdb_stats = self.vector_db.get_collection_stats()
            
            # 获取可用模型
            models = self.llm_client.list_models()
            
            return {
                'ollama_connected': ollama_status,
                'available_models': models,
                'current_model': self.llm_client.model,
                'vector_db': vdb_stats,
                'conversation_turns': len(self.conversation_history) // 2,
                'status': 'healthy' if ollama_status else 'ollama_disconnected'
            }
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }


# 测试函数
def test_rag_system():
    """测试 RAG 系统"""
    print("=" * 60)
    print("测试 RAG 系统")
    print("=" * 60)
    
    # 创建 RAG 系统
    rag = RAGSystem()
    
    # 获取系统状态
    print("\n1. 系统状态:")
    status = rag.get_system_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    # 初始化知识库
    print("\n2. 初始化知识库:")
    stats = rag.initialize_knowledge_base()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # 测试查询
    if status.get('ollama_connected'):
        print("\n3. 测试查询:")
        question = "列车超速报警应该如何处理？"
        print(f"   问题: {question}")
        result = rag.query(question)
        print(f"   回答: {result['answer'][:200]}...")
        print(f"   来源数量: {len(result.get('sources', []))}")
    else:
        print("\n3. Ollama 未连接，跳过查询测试")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_rag_system()

