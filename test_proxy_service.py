#!/usr/bin/env python3
"""测试代理池管理服务"""
import asyncio
import logging

from backend.services.proxy_service import ProxyService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_proxy_service():
    """测试代理池管理服务"""
    logger.info("开始测试代理池管理服务...")
    
    # 创建代理服务实例
    proxy_service = ProxyService()
    
    try:
        # 初始化代理服务
        logger.info("初始化代理服务...")
        await proxy_service.initialize()
        
        # 获取代理统计信息
        stats = await proxy_service.get_stats()
        logger.info(f"代理池统计信息: {stats}")
        
        # 测试获取代理
        logger.info("测试获取代理...")
        proxy = await proxy_service.get_proxy()
        if proxy:
            logger.info(f"成功获取代理: {proxy}")
        else:
            logger.warning("未获取到代理")
        
        # 测试获取不同协议的代理
        logger.info("测试获取HTTP代理...")
        http_proxy = await proxy_service.get_proxy("http")
        if http_proxy:
            logger.info(f"成功获取HTTP代理: {http_proxy}")
        else:
            logger.warning("未获取到HTTP代理")
        
        # 测试标记代理使用结果
        logger.info("测试标记代理使用结果...")
        if proxy:
            await proxy_service.mark_proxy_result(proxy, True)
            logger.info("成功标记代理使用结果")
        
        # 再次获取代理统计信息
        stats = await proxy_service.get_stats()
        logger.info(f"更新后的代理池统计信息: {stats}")
        
        logger.info("代理池管理服务测试完成!")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
    finally:
        logger.info("测试结束")


if __name__ == "__main__":
    asyncio.run(test_proxy_service())
