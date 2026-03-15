#!/usr/bin/env python3
"""
验证小说系统核心功能是否正常
"""

import requests
import time

BASE_URL = "http://localhost:8000"

def check_core_functions():
    print("🔍 验证小说系统核心功能...")
    
    # 1. 检查后端健康状态
    print("\n1. 检查后端服务...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            if health["status"] == "healthy":
                print("✅ 后端服务正常")
            else:
                print(f"❌ 后端服务异常: {health}")
                return False
        else:
            print(f"❌ 后端健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到后端: {e}")
        return False
    
    # 2. 检查小说列表API
    print("\n2. 检查小说列表API...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/novels/", timeout=5)
        if response.status_code == 200:
            novels = response.json()
            print(f"✅ 小说列表API正常，共有 {len(novels)} 本小说")
        else:
            print(f"❌ 小说列表API异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 小说列表API调用失败: {e}")
        return False
    
    # 3. 检查大纲相关API
    print("\n3. 检查大纲相关API...")
    try:
        # 获取一个测试小说的ID
        response = requests.get(f"{BASE_URL}/api/v1/novels/", timeout=5)
        novels = response.json()
        if novels:
            test_novel_id = novels[0]["id"]
            
            # 测试大纲获取
            response = requests.get(f"{BASE_URL}/api/v1/novels/{test_novel_id}/outline", timeout=5)
            if response.status_code in [200, 404]:  # 200表示有大纲，404表示无大纲但API正常
                print("✅ 大纲获取API正常")
            else:
                print(f"❌ 大纲获取API异常: {response.status_code}")
                return False
                
            # 测试质量评估API
            response = requests.get(f"{BASE_URL}/api/v1/novels/{test_novel_id}/outline/quality-report", timeout=10)
            if response.status_code in [200, 404]:
                print("✅ 质量评估API正常")
            else:
                print(f"❌ 质量评估API异常: {response.status_code}")
                return False
        else:
            print("⚠️  没有找到测试小说，跳过大纲API测试")
    except Exception as e:
        print(f"❌ 大纲API测试失败: {e}")
        return False
    
    print("\n🎉 所有核心功能验证通过！")
    print("\n📋 前端功能说明:")
    print("• 大纲梳理: 在小说详情页的'大纲梳理'标签页")
    print("• 章节拆分: 在小说详情页的'章节拆分'标签页") 
    print("• 智能完善: 在大纲梳理页面的'智能完善'按钮")
    print("• 质量评估: 在大纲梳理页面右侧的实时评估侧边栏")
    
    return True

if __name__ == "__main__":
    success = check_core_functions()
    exit(0 if success else 1)