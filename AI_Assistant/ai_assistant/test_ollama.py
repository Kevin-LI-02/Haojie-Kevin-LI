"""
测试 Ollama 连接
快速验证 Ollama API 是否正常工作
"""

import requests
import json
from config import OLLAMA_API_BASE, OLLAMA_MODEL

def test_ollama_connection():
    """测试 Ollama 连接"""
    print("=" * 60)
    print("测试 Ollama API 连接")
    print("=" * 60)
    
    # 1. 测试服务是否运行
    print(f"\n[1/3] 检查 Ollama 服务...")
    try:
        response = requests.get(f"{OLLAMA_API_BASE}/api/tags", timeout=5)
        if response.status_code == 200:
            print("✓ Ollama 服务正在运行")
            models = response.json().get('models', [])
            print(f"✓ 已安装的模型: {[m['name'] for m in models]}")
        else:
            print(f"✗ 服务返回错误: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 无法连接到 Ollama 服务: {e}")
        print(f"   请确保 Ollama 已启动")
        return False
    
    # 2. 检查配置的模型是否存在
    print(f"\n[2/3] 检查模型 '{OLLAMA_MODEL}'...")
    model_names = [m['name'] for m in models]
    if OLLAMA_MODEL in model_names:
        print(f"✓ 模型 '{OLLAMA_MODEL}' 已安装")
    else:
        print(f"✗ 模型 '{OLLAMA_MODEL}' 未找到")
        print(f"   可用模型: {model_names}")
        if model_names:
            print(f"\n   建议修改 config.py 中的 OLLAMA_MODEL 为: {model_names[0]}")
        else:
            print(f"\n   请运行: ollama pull {OLLAMA_MODEL}")
        return False
    
    # 3. 测试生成功能
    print(f"\n[3/3] 测试对话生成...")
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "user", "content": "你好，请简单介绍一下你自己"}
            ],
            "stream": False
        }
        
        response = requests.post(
            f"{OLLAMA_API_BASE}/api/chat",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            reply = result.get('message', {}).get('content', '')
            print(f"✓ 模型响应成功")
            print(f"\n模型回复: {reply[:100]}...")
            return True
        else:
            print(f"✗ API 返回错误: {response.status_code}")
            print(f"   响应内容: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False

def test_chat_endpoint():
    """测试 /api/chat 端点"""
    print("\n" + "=" * 60)
    print("测试 Chat API 端点")
    print("=" * 60)
    
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": "你是一个铁路系统的智能助手"},
                {"role": "user", "content": "列车超速了应该如何处理？"}
            ],
            "stream": False
        }
        
        response = requests.post(
            f"{OLLAMA_API_BASE}/api/chat",
            json=payload,
            timeout=30
        )
        
        print(f"\n请求 URL: {OLLAMA_API_BASE}/api/chat")
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Chat API 测试成功")
            print(f"\n完整响应: {json.dumps(result, ensure_ascii=False, indent=2)[:300]}...")
        else:
            print(f"✗ 请求失败")
            print(f"错误详情: {response.text[:300]}")
            
    except Exception as e:
        print(f"✗ 异常: {e}")


if __name__ == "__main__":
    success = test_ollama_connection()
    
    if success:
        test_chat_endpoint()
        print("\n" + "=" * 60)
        print("✓ 所有测试通过！AI Assistant 可以正常使用")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("✗ 测试失败，请按照上述提示修复问题")
        print("=" * 60)

