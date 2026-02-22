#!/usr/bin/env python3
"""测试千问 API Key 是否有效"""

import sys
from llm.qwen_client import QwenClient

def test_api_key():
    """测试 API key 是否可用"""
    print("🔍 开始测试千问 API Key...")
    
    try:
        client = QwenClient()
        print(f"📝 API Key: {client.api_key[:20]}...{client.api_key[-10:]}")
        print(f"🤖 模型: {client.model}")
        print("\n⏳ 发送测试请求...")
        
        # 发送一个简单的测试请求
        result = client.chat(
            prompt="请用一句话介绍你自己",
            temperature=0.7,
            max_tokens=100
        )
        
        print("✅ API Key 测试成功！")
        print(f"\n💬 回复内容: {result['content']}")
        print(f"\n📊 Token 使用情况:")
        print(f"   - 输入 tokens: {result['usage']['prompt_tokens']}")
        print(f"   - 输出 tokens: {result['usage']['completion_tokens']}")
        print(f"   - 总计 tokens: {result['usage']['total_tokens']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ API Key 测试失败！")
        print(f"错误信息: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_api_key()
    sys.exit(0 if success else 1)
