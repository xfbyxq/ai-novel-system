#!/usr/bin/env python3
"""测试浏览器爬虫服务"""
import asyncio
import logging

from backend.services.browser_crawler import browser_crawler_service

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_browser_crawler():
    """测试浏览器爬虫服务"""
    logger.info("开始测试浏览器爬虫服务...")
    
    try:
        # 测试爬取普通网站
        logger.info("测试爬取普通网站...")
        url = "https://www.example.com"
        content = await browser_crawler_service.crawl(url, simulate_behavior=False)
        if content:
            logger.info(f"成功爬取普通网站，内容长度: {len(content)}")
        else:
            logger.warning("未获取到普通网站内容")
        
        # 测试爬取需要JavaScript渲染的网站
        logger.info("测试爬取需要JavaScript渲染的网站...")
        url = "https://www.douyin.com/hot"
        content = await browser_crawler_service.crawl(url, simulate_behavior=True)
        if content:
            logger.info(f"成功爬取抖音热门，内容长度: {len(content)}")
        else:
            logger.warning("未获取到抖音热门内容")
        
        # 测试模拟用户行为
        logger.info("测试模拟用户行为...")
        url = "https://www.baidu.com"
        content = await browser_crawler_service.crawl(url, simulate_behavior=True)
        if content:
            logger.info(f"成功爬取百度，内容长度: {len(content)}")
        else:
            logger.warning("未获取到百度内容")
        
        logger.info("浏览器爬虫服务测试完成!")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
    finally:
        # 关闭所有爬虫
        await browser_crawler_service.close_all()
        logger.info("测试结束")


if __name__ == "__main__":
    asyncio.run(test_browser_crawler())
