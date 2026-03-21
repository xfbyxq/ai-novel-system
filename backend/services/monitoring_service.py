"""监控服务 - 负责系统监控和自动调优"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

import psutil
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.generation_task import GenerationTask, TaskStatus
from core.models.publish_task import PublishTask, PublishTaskStatus
from core.models.token_usage import TokenUsage

# 模拟Agent状态数据，实际项目中应该从Agent系统获取
AGENTS = [
    {
        "agent_id": "market_analyzer",
        "agent_name": "市场分析Agent",
        "status": "idle",
        "last_activity": "2026-02-24T07:00:00",
        "current_task": None,
        "error_message": None,
    },
    {
        "agent_id": "content_planner",
        "agent_name": "内容策划Agent",
        "status": "idle",
        "last_activity": "2026-02-24T07:00:00",
        "current_task": None,
        "error_message": None,
    },
    {
        "agent_id": "writer",
        "agent_name": "写作Agent",
        "status": "idle",
        "last_activity": "2026-02-24T07:00:00",
        "current_task": None,
        "error_message": None,
    },
    {
        "agent_id": "editor",
        "agent_name": "编辑Agent",
        "status": "idle",
        "last_activity": "2026-02-24T07:00:00",
        "current_task": None,
        "error_message": None,
    },
    {
        "agent_id": "publisher",
        "agent_name": "发布Agent",
        "status": "idle",
        "last_activity": "2026-02-24T07:00:00",
        "current_task": None,
        "error_message": None,
    },
]

logger = logging.getLogger(__name__)


class MonitoringService:
    """监控服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.start_time = time.time()
        self.metrics_history = []

    async def get_agent_statuses(self) -> List[Dict[str, Any]]:
        """获取Agent状态

        Returns:
            Agent状态列表
        """
        # 实际项目中应该从Agent系统获取实时状态
        # 这里使用模拟数据
        return AGENTS

    async def get_agent_history(self, agent_id: str) -> List[Dict[str, Any]]:
        """获取Agent历史任务

        Args:
            agent_id: Agent ID

        Returns:
            Agent历史任务列表
        """
        # 实际项目中应该从数据库或日志系统获取历史任务
        # 这里使用模拟数据
        import random
        from datetime import datetime, timedelta

        task_types = ["内容生成", "市场分析", "发布任务", "编辑任务", "角色分析"]
        statuses = ["completed", "failed", "running", "pending"]

        history = []
        for i in range(10):
            start_time = datetime.now() - timedelta(hours=random.randint(1, 100))
            duration = random.randint(10, 300)
            end_time = start_time + timedelta(seconds=duration)

            task = {
                "task_id": f"task_{random.randint(1000, 9999)}",
                "agent_name": next(
                    (a["agent_name"] for a in AGENTS if a["agent_id"] == agent_id),
                    "未知Agent",
                ),
                "task_type": random.choice(task_types),
                "status": random.choice(statuses),
                "start_time": start_time.isoformat(),
                "end_time": (
                    end_time.isoformat() if random.choice([True, False]) else None
                ),
                "duration": duration if random.choice([True, False]) else None,
                "error_message": (
                    "模拟错误信息"
                    if random.choice([True, False])
                    and random.choice(statuses) == "failed"
                    else None
                ),
            }
            history.append(task)

        return history

    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态

        Returns:
            系统状态信息
        """
        # 获取系统资源使用情况
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        network = psutil.net_io_counters()

        # 获取系统启动时间
        uptime = time.time() - self.start_time

        # 获取数据库连接状态
        db_status = await self._check_database_status()

        # 获取任务状态
        task_status = await self._get_task_status()

        # 获取Agent状态
        agent_statuses = await self.get_agent_statuses()

        # 构建系统状态
        system_status = {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "uptime_seconds": uptime,
                "cpu_percent": cpu_percent,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "percent": memory.percent,
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent,
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv,
                },
            },
            "database": db_status,
            "tasks": task_status,
            "agents": agent_statuses,
            "health": self._assess_system_health(
                cpu_percent, memory.percent, disk.percent, db_status
            ),
        }

        # 记录指标历史
        self._record_metrics(system_status)

        return system_status

    async def get_performance_metrics(
        self,
        days: int = 7,
    ) -> Dict[str, Any]:
        """获取性能指标

        Args:
            days: 分析天数

        Returns:
            性能指标分析
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # 获取Token使用情况
        token_usage_result = await self.db.execute(
            select(
                func.sum(TokenUsage.prompt_tokens),
                func.sum(TokenUsage.completion_tokens),
                func.sum(TokenUsage.total_tokens),
                func.sum(TokenUsage.estimated_cost),
            ).where(
                TokenUsage.created_at >= cutoff_date,
            )
        )
        token_usage = token_usage_result.first()

        # 获取生成任务状态
        generation_tasks_result = await self.db.execute(
            select(
                func.count(GenerationTask.id),
                func.sum(
                    case((GenerationTask.status == TaskStatus.completed, 1), else_=0)
                ),
                func.sum(
                    case((GenerationTask.status == TaskStatus.failed, 1), else_=0)
                ),
            ).where(
                GenerationTask.created_at >= cutoff_date,
            )
        )
        generation_stats = generation_tasks_result.first()

        # 获取发布任务状态
        publish_tasks_result = await self.db.execute(
            select(
                func.count(PublishTask.id),
                func.sum(
                    case(
                        (PublishTask.status == PublishTaskStatus.completed, 1), else_=0
                    )
                ),
                func.sum(
                    case((PublishTask.status == PublishTaskStatus.failed, 1), else_=0)
                ),
            ).where(
                PublishTask.created_at >= cutoff_date,
            )
        )
        publish_stats = publish_tasks_result.first()

        # 模拟爬虫任务状态
        crawler_stats = (0, 0, 0)

        # 构建性能指标
        performance_metrics = {
            "analysis_period": f"最近{days}天",
            "token_usage": {
                "prompt_tokens": int(token_usage[0] or 0),
                "completion_tokens": int(token_usage[1] or 0),
                "total_tokens": int(token_usage[2] or 0),
                "estimated_cost": float(token_usage[3] or 0),
            },
            "generation_tasks": {
                "total": int(generation_stats[0] or 0),
                "completed": int(generation_stats[1] or 0),
                "failed": int(generation_stats[2] or 0),
                "success_rate": self._calculate_success_rate(
                    generation_stats[1], generation_stats[0]
                ),
            },
            "publish_tasks": {
                "total": int(publish_stats[0] or 0),
                "completed": int(publish_stats[1] or 0),
                "failed": int(publish_stats[2] or 0),
                "success_rate": self._calculate_success_rate(
                    publish_stats[1], publish_stats[0]
                ),
            },
            "crawler_tasks": {
                "total": int(crawler_stats[0] or 0),
                "completed": int(crawler_stats[1] or 0),
                "failed": int(crawler_stats[2] or 0),
                "success_rate": self._calculate_success_rate(
                    crawler_stats[1], crawler_stats[0]
                ),
            },
        }

        return performance_metrics

    async def get_error_analysis(
        self,
        days: int = 7,
    ) -> Dict[str, Any]:
        """获取错误分析

        Args:
            days: 分析天数

        Returns:
            错误分析结果
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # 获取失败的生成任务
        failed_generation_result = await self.db.execute(
            select(GenerationTask)
            .where(
                GenerationTask.status == TaskStatus.failed,
                GenerationTask.created_at >= cutoff_date,
                GenerationTask.error_message.isnot(None),
            )
            .order_by(GenerationTask.created_at.desc())
        )
        failed_generation_tasks = failed_generation_result.scalars().all()

        # 获取失败的发布任务
        failed_publish_result = await self.db.execute(
            select(PublishTask)
            .where(
                PublishTask.status == PublishTaskStatus.failed,
                PublishTask.created_at >= cutoff_date,
                PublishTask.error_message.isnot(None),
            )
            .order_by(PublishTask.created_at.desc())
        )
        failed_publish_tasks = failed_publish_result.scalars().all()

        # 模拟失败的爬虫任务
        failed_crawler_tasks = []

        # 分析错误类型
        error_analysis = {
            "analysis_period": f"最近{days}天",
            "total_errors": len(failed_generation_tasks)
            + len(failed_publish_tasks)
            + len(failed_crawler_tasks),
            "error_distribution": {
                "generation": len(failed_generation_tasks),
                "publish": len(failed_publish_tasks),
                "crawler": len(failed_crawler_tasks),
            },
            "recent_errors": [],
            "error_patterns": [],
        }

        # 收集最近的错误
        for task in failed_generation_tasks[:5]:
            error_analysis["recent_errors"].append(
                {
                    "type": "generation",
                    "task_id": str(task.id),
                    "created_at": task.created_at.isoformat(),
                    "error_message": (
                        task.error_message[:200] + "..."
                        if len(task.error_message) > 200
                        else task.error_message
                    ),
                }
            )

        for task in failed_publish_tasks[:5]:
            error_analysis["recent_errors"].append(
                {
                    "type": "publish",
                    "task_id": str(task.id),
                    "created_at": task.created_at.isoformat(),
                    "error_message": (
                        task.error_message[:200] + "..."
                        if len(task.error_message) > 200
                        else task.error_message
                    ),
                }
            )

        for task in failed_crawler_tasks[:5]:
            error_analysis["recent_errors"].append(
                {
                    "type": "crawler",
                    "task_id": str(task.id),
                    "created_at": task.created_at.isoformat(),
                    "error_message": (
                        task.error_message[:200] + "..."
                        if len(task.error_message) > 200
                        else task.error_message
                    ),
                }
            )

        # 生成错误模式分析
        error_analysis["error_patterns"] = self._analyze_error_patterns(
            failed_generation_tasks,
            failed_publish_tasks,
            failed_crawler_tasks,
        )

        return error_analysis

    async def get_auto_optimization_suggestions(self) -> Dict[str, Any]:
        """获取自动调优建议

        Returns:
            自动调优建议
        """
        # 获取系统状态
        system_status = await self.get_system_status()

        # 获取性能指标
        performance_metrics = await self.get_performance_metrics(days=3)

        # 获取错误分析
        error_analysis = await self.get_error_analysis(days=3)

        # 生成调优建议
        suggestions = {
            "timestamp": datetime.now().isoformat(),
            "system_suggestions": self._generate_system_optimization_suggestions(
                system_status
            ),
            "performance_suggestions": self._generate_performance_optimization_suggestions(
                performance_metrics
            ),
            "error_suggestions": self._generate_error_optimization_suggestions(
                error_analysis
            ),
            "priority_suggestions": self._prioritize_suggestions(
                system_status,
                performance_metrics,
                error_analysis,
            ),
        }

        return suggestions

    async def get_system_health_check(self) -> Dict[str, Any]:
        """获取系统健康检查

        Returns:
            系统健康检查结果
        """
        # 获取系统状态
        system_status = await self.get_system_status()

        # 获取性能指标
        performance_metrics = await self.get_performance_metrics(days=1)

        # 获取错误分析
        error_analysis = await self.get_error_analysis(days=1)

        # 综合健康评估
        health_check = {
            "timestamp": datetime.now().isoformat(),
            "status": system_status.get("health", {}).get("status", "unknown"),
            "score": system_status.get("health", {}).get("score", 0),
            "details": {
                "system": system_status.get("system", {}),
                "database": system_status.get("database", {}),
                "tasks": system_status.get("tasks", {}),
                "performance": performance_metrics,
                "errors": error_analysis,
            },
            "recommendations": system_status.get("health", {}).get(
                "recommendations", []
            ),
        }

        return health_check

    async def _check_database_status(self) -> Dict[str, Any]:
        """检查数据库状态

        Returns:
            数据库状态
        """
        try:
            # 执行简单的数据库查询来检查连接
            await self.db.execute(select(1))
            return {
                "status": "healthy",
                "message": "数据库连接正常",
            }
        except Exception as e:
            logger.error(f"数据库连接检查失败: {e}")
            return {
                "status": "unhealthy",
                "message": f"数据库连接异常: {str(e)}",
            }

    async def _get_task_status(self) -> Dict[str, Any]:
        """获取任务状态

        Returns:
            任务状态统计
        """
        # 获取生成任务状态
        generation_result = await self.db.execute(
            select(
                func.count(GenerationTask.id),
                func.sum(
                    case((GenerationTask.status == TaskStatus.pending, 1), else_=0)
                ),
                func.sum(
                    case((GenerationTask.status == TaskStatus.running, 1), else_=0)
                ),
                func.sum(
                    case((GenerationTask.status == TaskStatus.completed, 1), else_=0)
                ),
                func.sum(
                    case((GenerationTask.status == TaskStatus.failed, 1), else_=0)
                ),
            )
        )
        gen_stats = generation_result.first()

        # 获取发布任务状态
        publish_result = await self.db.execute(
            select(
                func.count(PublishTask.id),
                func.sum(
                    case((PublishTask.status == PublishTaskStatus.pending, 1), else_=0)
                ),
                func.sum(
                    case((PublishTask.status == PublishTaskStatus.running, 1), else_=0)
                ),
                func.sum(
                    case(
                        (PublishTask.status == PublishTaskStatus.completed, 1), else_=0
                    )
                ),
                func.sum(
                    case((PublishTask.status == PublishTaskStatus.failed, 1), else_=0)
                ),
            )
        )
        pub_stats = publish_result.first()

        # 模拟爬虫任务状态
        crawler_stats = (0, 0, 0, 0, 0)

        return {
            "generation": {
                "total": gen_stats[0],
                "pending": gen_stats[1],
                "running": gen_stats[2],
                "completed": gen_stats[3],
                "failed": gen_stats[4],
            },
            "publish": {
                "total": pub_stats[0],
                "pending": pub_stats[1],
                "running": pub_stats[2],
                "completed": pub_stats[3],
                "failed": pub_stats[4],
            },
            "crawler": {
                "total": crawler_stats[0],
                "pending": crawler_stats[1],
                "running": crawler_stats[2],
                "completed": crawler_stats[3],
                "failed": crawler_stats[4],
            },
        }

    def _assess_system_health(
        self,
        cpu_percent: float,
        memory_percent: float,
        disk_percent: float,
        db_status: Dict[str, Any],
    ) -> Dict[str, Any]:
        """评估系统健康状态

        Args:
            cpu_percent: CPU使用率
            memory_percent: 内存使用率
            disk_percent: 磁盘使用率
            db_status: 数据库状态

        Returns:
            系统健康评估
        """
        # 计算健康分数
        health_score = 100

        # CPU使用率扣分
        if cpu_percent > 80:
            health_score -= min((cpu_percent - 80) * 2, 30)
        elif cpu_percent > 60:
            health_score -= min((cpu_percent - 60), 10)

        # 内存使用率扣分
        if memory_percent > 80:
            health_score -= min((memory_percent - 80) * 2, 30)
        elif memory_percent > 60:
            health_score -= min((memory_percent - 60), 10)

        # 磁盘使用率扣分
        if disk_percent > 80:
            health_score -= min((disk_percent - 80) * 2, 30)
        elif disk_percent > 60:
            health_score -= min((disk_percent - 60), 10)

        # 数据库状态扣分
        if db_status.get("status") != "healthy":
            health_score -= 40

        # 确定健康状态
        if health_score >= 80:
            status = "healthy"
        elif health_score >= 60:
            status = "warning"
        else:
            status = "critical"

        # 生成建议
        recommendations = []

        if cpu_percent > 80:
            recommendations.append("CPU使用率过高，建议优化任务调度或增加服务器资源")

        if memory_percent > 80:
            recommendations.append("内存使用率过高，建议增加内存或优化内存使用")

        if disk_percent > 80:
            recommendations.append("磁盘使用率过高，建议清理磁盘空间或增加存储")

        if db_status.get("status") != "healthy":
            recommendations.append("数据库状态异常，建议检查数据库连接和配置")

        return {
            "status": status,
            "score": max(0, health_score),
            "recommendations": recommendations,
        }

    def _generate_system_optimization_suggestions(
        self,
        system_status: Dict[str, Any],
    ) -> List[str]:
        """生成系统调优建议

        Args:
            system_status: 系统状态

        Returns:
            系统调优建议
        """
        suggestions = []

        system = system_status.get("system", {})
        cpu_percent = system.get("cpu_percent", 0)
        memory = system.get("memory", {})
        memory_percent = memory.get("percent", 0)
        disk = system.get("disk", {})
        disk_percent = disk.get("percent", 0)

        if cpu_percent > 70:
            suggestions.append("CPU使用率较高，建议优化任务并发数或增加CPU资源")

        if memory_percent > 70:
            suggestions.append("内存使用率较高，建议优化内存缓存策略或增加内存")

        if disk_percent > 70:
            suggestions.append("磁盘使用率较高，建议清理临时文件或增加磁盘空间")

        return suggestions

    def _generate_performance_optimization_suggestions(
        self,
        performance_metrics: Dict[str, Any],
    ) -> List[str]:
        """生成性能调优建议

        Args:
            performance_metrics: 性能指标

        Returns:
            性能调优建议
        """
        suggestions = []

        # 分析Token使用情况
        token_usage = performance_metrics.get("token_usage", {})
        estimated_cost = token_usage.get("estimated_cost", 0)

        if estimated_cost > 100:
            suggestions.append(
                "Token使用成本较高，建议优化提示词和生成参数以减少Token消耗"
            )

        # 分析任务成功率
        generation_tasks = performance_metrics.get("generation_tasks", {})
        publish_tasks = performance_metrics.get("publish_tasks", {})
        crawler_tasks = performance_metrics.get("crawler_tasks", {})

        if generation_tasks.get("success_rate", 0) < 80:
            suggestions.append("生成任务成功率较低，建议检查LLM API配置和网络连接")

        if publish_tasks.get("success_rate", 0) < 80:
            suggestions.append("发布任务成功率较低，建议检查平台账号状态和API稳定性")

        if crawler_tasks.get("success_rate", 0) < 80:
            suggestions.append("爬虫任务成功率较低，建议检查网络连接和网站反爬策略")

        return suggestions

    def _generate_error_optimization_suggestions(
        self,
        error_analysis: Dict[str, Any],
    ) -> List[str]:
        """生成错误调优建议

        Args:
            error_analysis: 错误分析

        Returns:
            错误调优建议
        """
        suggestions = []

        total_errors = error_analysis.get("total_errors", 0)
        error_distribution = error_analysis.get("error_distribution", {})

        if total_errors > 10:
            suggestions.append("错误数量较多，建议检查系统配置和网络连接")

        if error_distribution.get("generation", 0) > 5:
            suggestions.append("生成错误较多，建议检查LLM API密钥和配额")

        if error_distribution.get("publish", 0) > 5:
            suggestions.append("发布错误较多，建议检查平台账号权限和API限制")

        if error_distribution.get("crawler", 0) > 5:
            suggestions.append("爬虫错误较多，建议调整爬虫策略和请求频率")

        return suggestions

    def _prioritize_suggestions(
        self,
        system_status: Dict[str, Any],
        performance_metrics: Dict[str, Any],
        error_analysis: Dict[str, Any],
    ) -> List[str]:
        """优先级排序建议

        Args:
            system_status: 系统状态
            performance_metrics: 性能指标
            error_analysis: 错误分析

        Returns:
            优先级排序的建议
        """
        # 收集所有建议
        all_suggestions = []

        all_suggestions.extend(
            system_status.get("health", {}).get("recommendations", [])
        )
        all_suggestions.extend(
            self._generate_system_optimization_suggestions(system_status)
        )
        all_suggestions.extend(
            self._generate_performance_optimization_suggestions(performance_metrics)
        )
        all_suggestions.extend(
            self._generate_error_optimization_suggestions(error_analysis)
        )

        # 去重
        unique_suggestions = list(set(all_suggestions))

        # 优先级排序（简单实现，实际可以更复杂）
        priority_suggestions = []

        # 优先处理严重问题
        for suggestion in unique_suggestions:
            if any(
                keyword in suggestion
                for keyword in ["异常", "过高", "失败率", "错误较多"]
            ):
                priority_suggestions.append(suggestion)

        # 然后处理一般建议
        for suggestion in unique_suggestions:
            if suggestion not in priority_suggestions:
                priority_suggestions.append(suggestion)

        return priority_suggestions[:10]  # 限制建议数量

    def _record_metrics(self, system_status: Dict[str, Any]):
        """记录指标历史

        Args:
            system_status: 系统状态
        """
        # 只保留最近100条记录
        if len(self.metrics_history) > 100:
            self.metrics_history.pop(0)

        # 记录关键指标
        metrics = {
            "timestamp": system_status.get("timestamp"),
            "cpu_percent": system_status.get("system", {}).get("cpu_percent", 0),
            "memory_percent": system_status.get("system", {})
            .get("memory", {})
            .get("percent", 0),
            "disk_percent": system_status.get("system", {})
            .get("disk", {})
            .get("percent", 0),
            "health_score": system_status.get("health", {}).get("score", 0),
            "health_status": system_status.get("health", {}).get("status", "unknown"),
        }

        self.metrics_history.append(metrics)

    def _calculate_success_rate(self, success_count: int, total_count: int) -> float:
        """计算成功率

        Args:
            success_count: 成功数量
            total_count: 总数量

        Returns:
            成功率
        """
        if total_count == 0:
            return 0.0
        return (success_count / total_count) * 100

    def _analyze_error_patterns(
        self,
        failed_generation_tasks: List,
        failed_publish_tasks: List,
        failed_crawler_tasks: List,
    ) -> List[Dict[str, Any]]:
        """分析错误模式

        Args:
            failed_generation_tasks: 失败的生成任务
            failed_publish_tasks: 失败的发布任务
            failed_crawler_tasks: 失败的爬虫任务

        Returns:
            错误模式分析
        """
        patterns = []

        # 分析生成错误模式
        generation_errors = [
            t.error_message for t in failed_generation_tasks if t.error_message
        ]
        if generation_errors:
            error_counts = {}
            for error in generation_errors:
                # 简单的错误模式提取
                error_key = error[:100]  # 取前100个字符作为错误模式
                error_counts[error_key] = error_counts.get(error_key, 0) + 1

            # 提取频率最高的错误模式
            top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[
                :3
            ]
            for error_pattern, count in top_errors:
                patterns.append(
                    {
                        "type": "generation",
                        "pattern": error_pattern,
                        "count": count,
                    }
                )

        # 分析发布错误模式
        publish_errors = [
            t.error_message for t in failed_publish_tasks if t.error_message
        ]
        if publish_errors:
            error_counts = {}
            for error in publish_errors:
                error_key = error[:100]
                error_counts[error_key] = error_counts.get(error_key, 0) + 1

            top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[
                :3
            ]
            for error_pattern, count in top_errors:
                patterns.append(
                    {
                        "type": "publish",
                        "pattern": error_pattern,
                        "count": count,
                    }
                )

        # 分析爬虫错误模式
        crawler_errors = [
            t.error_message for t in failed_crawler_tasks if t.error_message
        ]
        if crawler_errors:
            error_counts = {}
            for error in crawler_errors:
                error_key = error[:100]
                error_counts[error_key] = error_counts.get(error_key, 0) + 1

            top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[
                :3
            ]
            for error_pattern, count in top_errors:
                patterns.append(
                    {
                        "type": "crawler",
                        "pattern": error_pattern,
                        "count": count,
                    }
                )

        return patterns
