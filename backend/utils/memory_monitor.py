"""内存监控工具.

提供内存使用情况的监控和泄漏检测功能。
用于识别和预防内存泄漏问题。

Usage:
    from backend.utils.memory_monitor import MemoryMonitor
    
    # 简单监控
    monitor = MemoryMonitor()
    monitor.log_usage("开始处理")
    # ... 执行操作 ...
    monitor.log_usage("处理完成")
    monitor.report()
    
    # 上下文管理器
    with MemoryMonitor().track("数据处理"):
        # ... 执行操作 ...
"""

import gc
import logging
import os
import resource
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """内存快照."""

    timestamp: datetime
    label: str
    rss_mb: float  # 常驻内存 (MB)
    shared_mb: float  # 共享内存 (MB)
    tracemalloc_mb: Optional[float] = None  # Python 对象内存 (MB)
    top_allocations: List[tuple] = field(default_factory=list)


class MemoryMonitor:
    """内存监控器."""

    def __init__(self, enable_tracemalloc: bool = True):
        """初始化内存监控器.

        Args:
            enable_tracemalloc: 是否启用 tracemalloc 追踪
        """
        self.enable_tracemalloc = enable_tracemalloc
        self.snapshots: List[MemorySnapshot] = []
        self._baseline: Optional[MemorySnapshot] = None
        
        if enable_tracemalloc and not tracemalloc.is_tracing():
            tracemalloc.start()
            logger.info("已启动 tracemalloc 内存追踪")

    def get_memory_usage(self) -> Dict[str, float]:
        """获取当前内存使用情况.

        Returns:
            内存使用字典 (MB)
        """
        usage = {}
        
        # 获取 RSS 内存（使用 resource 模块）
        try:
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            usage['rss_mb'] = rusage.ru_maxrss / 1024  # macOS 返回 KB，转换为 MB
        except Exception as e:
            logger.debug(f"获取 RSS 内存失败：{e}")
            usage['rss_mb'] = 0.0
        
        # 获取 tracemalloc 内存
        if self.enable_tracemalloc and tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            usage['python_current_mb'] = current / 1024 / 1024
            usage['python_peak_mb'] = peak / 1024 / 1024
        else:
            usage['python_current_mb'] = 0.0
            usage['python_peak_mb'] = 0.0
        
        return usage

    def take_snapshot(self, label: str = "") -> MemorySnapshot:
        """拍摄内存快照.

        Args:
            label: 快照标签

        Returns:
            MemorySnapshot 对象
        """
        usage = self.get_memory_usage()
        
        snapshot = MemorySnapshot(
            timestamp=datetime.now(),
            label=label,
            rss_mb=usage['rss_mb'],
            shared_mb=0.0,  # macOS 不提供此信息
            tracemalloc_mb=usage.get('python_current_mb'),
        )
        
        # 获取 top  allocations
        if self.enable_tracemalloc and tracemalloc.is_tracing():
            snapshot.top_allocations = tracemalloc.take_snapshot().statistics('lineno')[:10]
        
        self.snapshots.append(snapshot)
        
        logger.info(
            f"[内存] {label or '快照'}: "
            f"RSS={snapshot.rss_mb:.2f}MB, "
            f"Python={snapshot.tracemalloc_mb:.2f}MB"
        )
        
        return snapshot

    def log_usage(self, label: str):
        """记录内存使用情况（快捷方法）."""
        self.take_snapshot(label)

    def set_baseline(self, label: str = "baseline"):
        """设置内存基线.

        Args:
            label: 基线标签
        """
        self._baseline = self.take_snapshot(label)
        logger.info(f"已设置内存基线：{self._baseline.rss_mb:.2f}MB")

    def check_leak(self, threshold_mb: float = 50.0) -> bool:
        """检查是否存在内存泄漏.

        Args:
            threshold_mb: 泄漏阈值（MB）

        Returns:
            如果检测到泄漏返回 True
        """
        if not self.snapshots or len(self.snapshots) < 2:
            return False
        
        current = self.snapshots[-1]
        baseline = self._baseline or self.snapshots[0]
        
        increase = current.rss_mb - baseline.rss_mb
        
        if increase > threshold_mb:
            logger.warning(
                f"[内存泄漏检测] 内存增长 {increase:.2f}MB "
                f"(基线={baseline.rss_mb:.2f}MB, 当前={current.rss_mb:.2f}MB)"
            )
            return True
        
        return False

    def report(self) -> str:
        """生成内存使用报告.

        Returns:
            报告文本
        """
        if not self.snapshots:
            return "无内存快照数据"
        
        lines = ["=" * 60, "内存使用报告", "=" * 60]
        
        for i, snapshot in enumerate(self.snapshots):
            lines.append(
                f"[{i+1}] {snapshot.label or '快照'} @ {snapshot.timestamp.strftime('%H:%M:%S')}: "
                f"RSS={snapshot.rss_mb:.2f}MB, Python={snapshot.tracemalloc_mb:.2f}MB"
            )
        
        if len(self.snapshots) >= 2:
            first = self.snapshots[0]
            last = self.snapshots[-1]
            increase = last.rss_mb - first.rss_mb
            lines.append("-" * 60)
            lines.append(f"总增长：{increase:.2f}MB ({increase/first.rss_mb*100:.1f}%)")
        
        # Top allocations
        if self.snapshots[-1].top_allocations:
            lines.append("-" * 60)
            lines.append("Top 内存分配位置:")
            for stat in self.snapshots[-1].top_allocations[:5]:
                lines.append(f"  {stat.traceback.format()[:80]}: {stat.size/1024:.1f}KB")
        
        lines.append("=" * 60)
        return "\n".join(lines)

    def force_gc(self):
        """强制垃圾回收."""
        collected = gc.collect()
        logger.info(f"执行垃圾回收，回收 {collected} 个对象")
        return collected

    @contextmanager
    def track(self, label: str):
        """上下文管理器：追踪代码块内存使用.

        Usage:
            with monitor.track("数据处理"):
                # ... 执行操作 ...
        """
        self.log_usage(f"{label} - 开始")
        try:
            yield
        finally:
            self.log_usage(f"{label} - 结束")
            if self.check_leak():
                logger.warning(f"[{label}] 检测到内存泄漏")


@contextmanager
def memory_limit(max_mb: int):
    """上下文管理器：限制内存使用.

    Args:
        max_mb: 最大内存限制 (MB)

    Usage:
        with memory_limit(512):  # 限制 512MB
            # ... 执行操作 ...
    """
    # 获取当前限制
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    
    # 设置新限制
    max_bytes = max_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
    
    try:
        yield
    finally:
        # 恢复原有限制
        resource.setrlimit(resource.RLIMIT_AS, (soft, hard))


def get_process_memory_mb() -> float:
    """获取当前进程内存使用 (MB).

    Returns:
        内存使用量 (MB)
    """
    try:
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        return rusage.ru_maxrss / 1024  # macOS 返回 KB
    except Exception:
        return 0.0
