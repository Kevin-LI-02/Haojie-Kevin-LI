"""
Ollama API 客户端
用于与 Ollama 本地 LLM 服务交互
"""

import requests
import json
import logging
from typing import List, Dict, Optional, Generator
from config import OLLAMA_API_BASE, OLLAMA_MODEL, OLLAMA_TIMEOUT, SYSTEM_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama API 客户端"""
    
    def __init__(self, base_url: str = OLLAMA_API_BASE, model: str = OLLAMA_MODEL):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = OLLAMA_TIMEOUT
        
    def check_connection(self) -> bool:
        """检查 Ollama 服务是否可用"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"无法连接到 Ollama 服务: {e}")
            return False
    
    def list_models(self) -> List[str]:
        """列出可用的模型"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return []
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[str] = None,
        stream: bool = False
    ) -> str:
        """
        生成回复
        
        Args:
            prompt: 用户提问
            system: 系统提示词
            context: 上下文信息（RAG检索结果）
            stream: 是否流式输出
            
        Returns:
            生成的回复文本
        """
        try:
            # 构建完整的提示词
            full_prompt = self._build_prompt(prompt, system, context)
            
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": stream
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
                stream=stream
            )
            
            if response.status_code == 200:
                if stream:
                    return self._handle_stream_response(response)
                else:
                    result = response.json()
                    return result.get('response', '')
            else:
                logger.error(f"API 请求失败: {response.status_code}")
                return "抱歉，生成回复时出现错误。"
                
        except requests.exceptions.Timeout:
            logger.error("API 请求超时")
            return "抱歉，请求超时，请稍后重试。"
        except Exception as e:
            logger.error(f"生成回复失败: {e}")
            return f"抱歉，发生错误: {str(e)}"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False
    ) -> str:
        """
        对话模式（支持多轮对话）
        
        Args:
            messages: 对话历史 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            stream: 是否流式输出
            
        Returns:
            生成的回复文本
        """
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": stream
            }
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
                stream=stream
            )
            
            if response.status_code == 200:
                if stream:
                    return self._handle_stream_response(response)
                else:
                    result = response.json()
                    return result.get('message', {}).get('content', '')
            else:
                logger.error(f"Chat API 请求失败: {response.status_code}")
                return "抱歉，生成回复时出现错误。"
                
        except Exception as e:
            logger.error(f"Chat 失败: {e}")
            return f"抱歉，发生错误: {str(e)}"
    
    def chat_general(
        self,
        question: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """
        通用对话（不限制答案范围，像 ChatGPT 一样）
        
        Args:
            question: 用户问题
            conversation_history: 对话历史
            
        Returns:
            生成的回复文本
        """
        try:
            # 构建消息列表
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业、友好、有帮助的 AI 助手。你可以回答各种问题，提供准确的信息和建议。"
                }
            ]
            
            # 添加对话历史（保留上下文）
            if conversation_history:
                messages.extend(conversation_history)
            
            # 添加当前问题
            messages.append({"role": "user", "content": question})
            
            # 调用 chat 接口
            return self.chat(messages)
            
        except Exception as e:
            logger.error(f"通用对话失败: {e}")
            return f"抱歉，发生错误: {str(e)}"
    
    def chat_stream(self, messages: List[Dict], system_prompt: str = None):
        """流式对话生成（边生成边返回）"""
        url = f"{self.base_url}/api/chat"
        
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True  # 启用流式响应
        }
        
        try:
            response = requests.post(url, json=payload, stream=True, timeout=300)
            
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if 'message' in chunk:
                        yield chunk['message'].get('content', '')
                        
        except Exception as e:
            logger.error(f"流式对话失败: {e}")
            yield f"Error: {str(e)}"

    def _build_prompt(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[str] = None
    ) -> str:
        """构建完整的提示词"""
        parts = []
        
        # 添加系统提示词
        if system:
            parts.append(f"系统: {system}")
        else:
            parts.append(f"系统: {SYSTEM_PROMPT}")
        
        # 添加上下文（RAG检索结果）
        if context:
            parts.append(f"\n相关知识库信息:\n{context}")
        
        # 添加用户提问
        parts.append(f"\n用户提问: {prompt}")
        parts.append("\n请基于以上信息回答用户的问题:")
        
        return "\n".join(parts)
    
    def _handle_stream_response(self, response) -> Generator[str, None, None]:
        """处理流式响应"""
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if 'response' in data:
                        yield data['response']
                    elif 'message' in data:
                        yield data['message'].get('content', '')
                except json.JSONDecodeError:
                    continue
    
    def generate_with_rag(
        self,
        question: str,
        retrieved_docs: List[Dict],
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """
        使用 RAG 增强的生成
        
        Args:
            question: 用户问题
            retrieved_docs: RAG 检索到的相关文档
            conversation_history: 对话历史
            
        Returns:
            生成的回复
        """
        # 构建上下文
        context_parts = []
        for i, doc in enumerate(retrieved_docs, 1):
            content = doc.get('content', doc.get('text', ''))
            source = doc.get('source', '未知来源')
            context_parts.append(f"[文档 {i}] (来源: {source})\n{content}")
        
        context = "\n\n".join(context_parts)
        
        # 如果有对话历史，使用 chat 模式
        if conversation_history:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            messages.extend(conversation_history)
            
            # 添加当前问题和上下文
            user_message = f"基于以下信息回答:\n\n{context}\n\n问题: {question}"
            messages.append({"role": "user", "content": user_message})
            
            return self.chat(messages)
        else:
            return self.generate(question, context=context)
    
    def analyze_alarm(self, alarm_data: Dict) -> str:
        """
        分析报警信息
        
        Args:
            alarm_data: 报警数据字典
            
        Returns:
            分析结果
        """
        alarm_text = f"""
报警信息:
- 时间: {alarm_data.get('timestamp', 'N/A')}
- 站点: {alarm_data.get('station', 'N/A')}
- 类型: {alarm_data.get('alarm_type', 'N/A')}
- 描述: {alarm_data.get('description', 'N/A')}
- 严重程度: {alarm_data.get('severity', 'N/A')}
"""
        
        prompt = f"""请分析以下报警信息，并提供:
1. 报警原因分析
2. 可能的影响
3. 紧急程度评估
4. 建议的处置步骤

{alarm_text}"""
        
        return self.generate(prompt)


# 测试函数
def test_ollama_connection():
    """测试 Ollama 连接"""
    client = OllamaClient()
    
    print("测试 Ollama 连接...")
    if client.check_connection():
        print("✓ Ollama 服务连接成功")
        
        models = client.list_models()
        if models:
            print(f"✓ 可用模型: {', '.join(models)}")
        else:
            print("✗ 未找到可用模型")
            print("  请先使用 'ollama pull llama2' 下载模型")
    else:
        print("✗ 无法连接到 Ollama 服务")
        print("  请确保 Ollama 已启动: 'ollama serve'")


if __name__ == "__main__":
    test_ollama_connection()

