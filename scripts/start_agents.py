#!/usr/bin/env python3
"""Agent启动脚本"""
import asyncio
import logging
import time
import signal
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, '/Users/sanyi/code/python/novel_system')

from agents.agent_communicator import AgentCommunicator, agent_communicator
from agents.agent_scheduler import AgentScheduler
from agents.specific_agents import (
    MarketAnalysisAgent,
    ContentPlanningAgent,
    WritingAgent,
    EditingAgent,
    PublishingAgent,
)
from llm.qwen_client import QwenClient
from llm.cost_tracker import CostTracker

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/sanyi/code/python/novel_system/logs/agent_system.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class AgentSystem:
    """Agent系统管理类"""
    
    def __init__(self):
        self.running = False
        self.scheduler = None
        self.agents = []
        self.qwen_client = None
        self.cost_tracker = None
    
    async def initialize(self):
        """初始化Agent系统"""
        logger.info("🚀 初始化Agent系统...")
        
        try:
            # 创建必要的目录
            import os
            os.makedirs('/Users/sanyi/code/python/novel_system/logs', exist_ok=True)
            
            # 初始化客户端和成本跟踪器
            self.qwen_client = QwenClient()
            self.cost_tracker = CostTracker()
            
            # 初始化调度器
            self.scheduler = AgentScheduler(agent_communicator)
            
            # 创建并注册Agent
            market_agent = MarketAnalysisAgent(
                "市场分析Agent",
                agent_communicator,
                self.qwen_client,
                self.cost_tracker,
            )
            
            content_agent = ContentPlanningAgent(
                "内容策划Agent",
                agent_communicator,
                self.qwen_client,
                self.cost_tracker,
            )
            
            writing_agent = WritingAgent(
                "创作Agent",
                agent_communicator,
                self.qwen_client,
                self.cost_tracker,
            )
            
            editing_agent = EditingAgent(
                "编辑Agent",
                agent_communicator,
                self.qwen_client,
                self.cost_tracker,
            )
            
            publishing_agent = PublishingAgent(
                "发布Agent",
                agent_communicator,
                self.qwen_client,
                self.cost_tracker,
            )
            
            # 注册Agent
            await self.scheduler.register_agent(market_agent)
            await self.scheduler.register_agent(content_agent)
            await self.scheduler.register_agent(writing_agent)
            await self.scheduler.register_agent(editing_agent)
            await self.scheduler.register_agent(publishing_agent)
            
            self.agents = [
                market_agent,
                content_agent,
                writing_agent,
                editing_agent,
                publishing_agent
            ]
            
            # 等待Agent启动
            await asyncio.sleep(3)
            
            logger.info(f"✅ 成功启动 {len(self.agents)} 个Agent")
            for agent in self.agents:
                logger.info(f"   - {agent.name}")
            
            self.running = True
            
        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def run(self):
        """运行Agent系统"""
        logger.info("🔄 Agent系统开始运行...")
        
        try:
            while self.running:
                # 检查系统状态
                await asyncio.sleep(5)
                
                # 打印系统状态
                if time.time() % 30 < 1:  # 每30秒打印一次状态
                    logger.info(f"📊 Agent系统运行状态 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    for agent in self.agents:
                        status_val = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)
                        logger.info(f"   - {agent.name}: {status_val}")
                        
        except asyncio.CancelledError:
            logger.info("⚠️  Agent系统被取消")
        except Exception as e:
            logger.error(f"❌ 运行错误: {e}")
            import traceback
            traceback.print_exc()
    
    async def shutdown(self):
        """关闭Agent系统"""
        logger.info("🛑 关闭Agent系统...")
        
        try:
            self.running = False
            
            # 关闭Agent
            for agent in self.agents:
                try:
                    await agent.stop()
                    logger.info(f"   - {agent.name} 已关闭")
                except Exception as e:
                    logger.error(f"   - 关闭 {agent.name} 失败: {e}")
            
            # 打印成本
            if self.cost_tracker:
                logger.info(f"💰 总token消耗: {self.cost_tracker.get_total_tokens()}")
                logger.info(f"💰 总成本: ¥{self.cost_tracker.get_total_cost():.2f}")
            
            logger.info("✅ Agent系统已关闭")
            
        except Exception as e:
            logger.error(f"❌ 关闭失败: {e}")
            import traceback
            traceback.print_exc()

async def main():
    """主函数"""
    agent_system = AgentSystem()
    
    # 注册信号处理
    def signal_handler(sig, frame):
        logger.info("⚠️  收到终止信号")
        # 创建一个任务来关闭系统
        asyncio.create_task(agent_system.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 初始化系统
        await agent_system.initialize()
        
        # 运行系统
        await agent_system.run()
        
    finally:
        # 确保系统关闭
        await agent_system.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
