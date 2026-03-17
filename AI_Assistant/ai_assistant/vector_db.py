"""
向量数据库管理
使用 ChromaDB 进行向量存储和检索
"""

import logging
from typing import List, Dict, Optional
from pathlib import Path
import hashlib

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("ChromaDB 未安装，请运行: pip install chromadb")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("sentence-transformers 未安装，请运行: pip install sentence-transformers")

from config import (
    VECTOR_STORE_DIR,
    EMBEDDING_MODEL,
    TOP_K_RESULTS
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorDatabase:
    """向量数据库管理器"""
    
    def __init__(self, collection_name: str = "eyes_t_knowledge"):
        """
        初始化向量数据库
        
        Args:
            collection_name: 集合名称
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB 未安装")
        
        self.collection_name = collection_name
        self.persist_directory = str(VECTOR_STORE_DIR)
        
        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 使用 ChromaDB 默认嵌入函数（避免外部模型下载）
        try:
            from chromadb.utils import embedding_functions
            # 使用默认的嵌入函数（不需要外部模型）
            self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
            logger.info("✓ 使用 ChromaDB 默认嵌入函数")
        except Exception as e:
            logger.warning(f"无法加载默认嵌入函数: {e}，将使用集合默认配置")
            self.embedding_function = None
        
        # 获取或创建集合
        try:
            if self.embedding_function:
                self.collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
            else:
                self.collection = self.client.get_collection(name=collection_name)
            logger.info(f"✓ 使用现有集合: {collection_name}")
        except:
            if self.embedding_function:
                self.collection = self.client.create_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function,
                    metadata={"description": "EYES-T AI Assistant Knowledge Base"}
                )
            else:
                self.collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"description": "EYES-T AI Assistant Knowledge Base"}
                )
            logger.info(f"✓ 创建新集合: {collection_name}")
        
        # 加载嵌入模型（可选）- 已禁用以避免 HuggingFace 下载
        self.embedding_model = None
        # if SENTENCE_TRANSFORMERS_AVAILABLE:
        #     try:
        #         self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        #         logger.info(f"✓ 加载嵌入模型: {EMBEDDING_MODEL}")
        #     except Exception as e:
        #         logger.warning(f"无法加载嵌入模型: {e}")
        logger.info("✓ 使用 ChromaDB 内置向量化（跳过外部嵌入模型）")
    
    def add_documents(self, documents: List[Dict], batch_size: int = 100) -> int:
        """
        添加文档到向量数据库
        
        Args:
            documents: 文档列表，每个文档包含 'text' 和 'metadata'
            batch_size: 批处理大小
            
        Returns:
            添加的文档数量
        """
        if not documents:
            logger.warning("没有文档要添加")
            return 0
        
        try:
            total_added = 0
            
            # 分批处理
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                
                texts = []
                metadatas = []
                ids = []
                
                for doc in batch:
                    text = doc.get('text', '')
                    if not text:
                        continue
                    
                    # 生成唯一 ID
                    doc_id = self._generate_id(text, doc.get('metadata', {}))
                    
                    texts.append(text)
                    metadatas.append(doc.get('metadata', {}))
                    ids.append(doc_id)
                
                if texts:
                    # 添加到集合
                    self.collection.add(
                        documents=texts,
                        metadatas=metadatas,
                        ids=ids
                    )
                    total_added += len(texts)
            
            logger.info(f"✓ 成功添加 {total_added} 个文档到向量数据库")
            return total_added
            
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            return 0
    
    def search(
        self,
        query: str,
        n_results: int = TOP_K_RESULTS,
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        搜索相关文档
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            filter_metadata: 元数据过滤条件
            
        Returns:
            相关文档列表
        """
        try:
            # 执行查询
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_metadata
            )
            
            # 格式化结果
            documents = []
            if results and 'documents' in results and results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i] if 'metadatas' in results else {}
                    distance = results['distances'][0][i] if 'distances' in results else 0
                    
                    documents.append({
                        'content': doc,
                        'metadata': metadata,
                        'relevance_score': 1 - distance,  # 转换为相似度分数
                        'source': metadata.get('source', 'unknown')
                    })
            
            logger.info(f"✓ 检索到 {len(documents)} 个相关文档")
            return documents
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
    
    def search_by_alarm_type(self, alarm_type: str, n_results: int = 5) -> List[Dict]:
        """根据报警类型搜索相关文档"""
        return self.search(
            query=f"报警类型: {alarm_type}",
            n_results=n_results,
            filter_metadata={"alarm_type": alarm_type}
        )
    
    def search_by_station(self, station: str, n_results: int = 5) -> List[Dict]:
        """根据站点搜索相关文档"""
        return self.search(
            query=f"站点: {station}",
            n_results=n_results,
            filter_metadata={"station": station}
        )
    
    def get_collection_stats(self) -> Dict:
        """获取集合统计信息"""
        try:
            count = self.collection.count()
            return {
                'total_documents': count,
                'collection_name': self.collection_name,
                'persist_directory': self.persist_directory
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def clear_collection(self) -> bool:
        """清空集合"""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(name=self.collection_name)
            logger.info(f"✓ 已清空集合: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"清空集合失败: {e}")
            return False
    
    def _generate_id(self, text: str, metadata: Dict) -> str:
        """生成文档唯一 ID"""
        content = f"{text}{str(metadata)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def update_documents(self, documents: List[Dict]) -> int:
        """更新文档（如果 ID 已存在则更新，否则添加）"""
        return self.add_documents(documents)
    
    def delete_documents(self, ids: List[str]) -> bool:
        """删除指定 ID 的文档"""
        try:
            self.collection.delete(ids=ids)
            logger.info(f"✓ 已删除 {len(ids)} 个文档")
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False


class SimpleEmbedding:
    """简单的嵌入函数（如果 sentence-transformers 不可用）"""
    
    @staticmethod
    def embed(texts: List[str]) -> List[List[float]]:
        """简单的词频嵌入（仅用于测试）"""
        import numpy as np
        embeddings = []
        for text in texts:
            # 简单的字符级嵌入
            vec = np.zeros(384)  # 模拟 384 维向量
            for i, char in enumerate(text[:384]):
                vec[i] = ord(char) / 10000.0
            embeddings.append(vec.tolist())
        return embeddings


# 测试函数
def test_vector_db():
    """测试向量数据库"""
    if not CHROMADB_AVAILABLE:
        print("✗ ChromaDB 未安装，请运行: pip install chromadb")
        return
    
    print("测试向量数据库...")
    
    # 创建实例
    vdb = VectorDatabase()
    
    # 测试添加文档
    test_docs = [
        {
            'text': '列车超速报警：列车在LMC站超过限速80km/h',
            'metadata': {'station': 'LMC', 'alarm_type': '列车超速', 'source_type': 'dal_log'}
        },
        {
            'text': '道岔故障报警：TWO站3号道岔无法转换',
            'metadata': {'station': 'TWO', 'alarm_type': '道岔故障', 'source_type': 'dal_log'}
        },
        {
            'text': '处置方案：列车超速时应立即通知司机减速，并检查信号系统',
            'metadata': {'source_type': 'work_instruction'}
        }
    ]
    
    count = vdb.add_documents(test_docs)
    print(f"✓ 添加文档: {count} 个")
    
    # 测试搜索
    results = vdb.search("列车超速如何处理", n_results=2)
    print(f"✓ 搜索结果: {len(results)} 个")
    
    for i, result in enumerate(results, 1):
        print(f"\n结果 {i}:")
        print(f"  内容: {result['content'][:50]}...")
        print(f"  相关度: {result['relevance_score']:.3f}")
    
    # 统计信息
    stats = vdb.get_collection_stats()
    print(f"\n✓ 集合统计: {stats}")


if __name__ == "__main__":
    test_vector_db()

