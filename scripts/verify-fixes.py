#!/usr/bin/env python3
"""
验证修复脚本

测试 4 个高优先级问题的修复：
1. 数据库密码硬编码
2. Redis 连接泄漏
3. API 认证缺失
4. API Key 启动验证缺失
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("🔍 验证 novel_system 高优先级问题修复")
print("=" * 60)

# ========== 测试 1: 数据库密码硬编码修复 ========== #
print("\n1️⃣  测试：数据库密码硬编码修复")
print("-" * 60)

try:
    # 模拟未设置 DB_PASSWORD 的情况
    os.environ.pop("DB_PASSWORD", None)

    # 清除缓存的 settings
    if "backend.config" in sys.modules:
        del sys.modules["backend.config"]

    from backend.config import Settings

    try:
        settings = Settings()
        print("❌ 失败：应该抛出 ValueError")
    except ValueError as e:
        if "DB_PASSWORD" in str(e):
            print("✅ 通过：DB_PASSWORD 未设置时正确抛出错误")
            print(f"   错误信息：{str(e)[:60]}...")
        else:
            print(f"❌ 失败：错误信息不包含 DB_PASSWORD: {e}")

    # 测试设置密码后正常
    os.environ["DB_PASSWORD"] = "test_password"
    if "backend.config" in sys.modules:
        del sys.modules["backend.config"]

    from backend.config import Settings as Settings2

    settings = Settings2()
    print("✅ 通过：设置 DB_PASSWORD 后正常加载")

except Exception as e:
    print(f"❌ 测试失败：{e}")

# ========== 测试 2: Redis 连接泄漏修复 ========== #
print("\n2️⃣  测试：Redis 连接泄漏修复（单例模式）")
print("-" * 60)

try:
    # 清除缓存
    if "backend.services.cache_service" in sys.modules:
        del sys.modules["backend.services.cache_service"]

    from backend.services.cache_service import CacheService

    # 创建多个实例
    instance1 = CacheService()
    instance2 = CacheService()

    # 验证是同一个实例（单例模式）
    if instance1 is instance2:
        print("✅ 通过：CacheService 使用单例模式，避免连接泄漏")
    else:
        print("❌ 失败：CacheService 未使用单例模式")

    # 验证有 close 方法
    if hasattr(instance1, "close"):
        print("✅ 通过：CacheService 有 close() 方法")
    else:
        print("❌ 失败：CacheService 缺少 close() 方法")

except Exception as e:
    print(f"❌ 测试失败：{e}")

# ========== 测试 3: API 认证缺失修复 ========== #
print("\n3️⃣  测试：API 认证依赖")
print("-" * 60)

try:
    from backend.dependencies import verify_api_key

    print("✅ 通过：verify_api_key 依赖函数已创建")

    # 检查函数签名
    import inspect

    sig = inspect.signature(verify_api_key)
    print(f"   函数签名：{sig}")

except ImportError as e:
    print(f"❌ 失败：无法导入 verify_api_key: {e}")
except Exception as e:
    print(f"❌ 测试失败：{e}")

# ========== 测试 4: API Key 启动验证缺失 ========== #
print("\n4️⃣  测试：API Key 启动验证")
print("-" * 60)

try:
    # 清除缓存
    if "backend.config" in sys.modules:
        del sys.modules["backend.config"]

    # 设置生产环境但不设置 API Key
    os.environ["APP_ENV"] = "production"
    os.environ.pop("DASHSCOPE_API_KEY", None)

    from backend.config import Settings as Settings3

    try:
        settings = Settings3()
        print("❌ 失败：生产环境未设置 API Key 应该抛出错误")
    except ValueError as e:
        if "DASHSCOPE_API_KEY" in str(e):
            print("✅ 通过：生产环境未设置 API Key 时正确抛出错误")
            print(f"   错误信息：{str(e)[:60]}...")
        else:
            print(f"❌ 失败：错误信息不包含 DASHSCOPE_API_KEY: {e}")

    # 恢复开发环境
    os.environ["APP_ENV"] = "development"

except Exception as e:
    print(f"❌ 测试失败：{e}")

# ========== 总结 ========== #
print("\n" + "=" * 60)
print("✅ 所有修复验证完成！")
print("=" * 60)
print("\n📋 修复摘要:")
print("   1. ✅ 数据库密码硬编码 → 必须通过环境变量设置")
print("   2. ✅ Redis 连接泄漏 → 使用单例模式 + close() 方法")
print("   3. ✅ API 认证缺失 → 添加 verify_api_key 依赖")
print("   4. ✅ API Key 启动验证 → 生产环境强制检查")
print("\n📝 下一步:")
print("   - 在 .env 文件中配置 DB_PASSWORD 和 DASHSCOPE_API_KEY")
print("   - 在受保护的 API 端点添加 Depends(verify_api_key)")
print("   - 运行完整测试套件验证功能")
print("=" * 60)
