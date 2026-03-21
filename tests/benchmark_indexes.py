#!/usr/bin/env python3
"""性能测试脚本 - 验证数据库索引效果 (Issue #6).

使用方法:
    python tests/benchmark_indexes.py
    
测试项目:
1. 无索引时的查询性能
2. 有索引时的查询性能
3. 性能对比报告
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import List
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models.novel import Novel
from core.models.chapter import Chapter
from core.models.generation_task import GenerationTask
from backend.config import settings


async def setup_test_database():
    """设置测试数据库."""
    engine = create_async_engine(
        settings.DATABASE_URL.split("?")[0],
        echo=False,
    )
    
    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    return async_session_factory


async def create_test_data(session: AsyncSession, count: int = 1000):
    """创建测试数据."""
    print(f"正在创建 {count} 条测试数据...")
    
    novels = []
    statuses = ["planning", "writing", "completed", "published"]
    
    for i in range(count):
        novel = Novel(
            title=f"测试小说 {i}",
            genre="玄幻",
            status=statuses[i % 4],
            word_count=i * 1000,
            chapter_count=i % 100,
        )
        novels.append(novel)
    
    session.add_all(novels)
    await session.commit()
    
    # 创建章节
    chapters = []
    for novel in novels[:100]:  # 只为前 100 本小说创建章节
        for ch_num in range(1, 11):
            chapter = Chapter(
                novel_id=novel.id,
                chapter_number=ch_num,
                title=f"第 {ch_num} 章",
                status=["draft", "reviewing", "published"][ch_num % 3],
            )
            chapters.append(chapter)
    
    session.add_all(chapters)
    await session.commit()
    
    # 创建生成任务
    tasks = []
    for novel in novels[:50]:
        for i in range(5):
            task = GenerationTask(
                novel_id=novel.id,
                task_type="writing",
                status=["pending", "running", "completed", "failed"][i % 4],
            )
            tasks.append(task)
    
    session.add_all(tasks)
    await session.commit()
    
    print(f"✓ 创建了 {len(novels)} 本小说, {len(chapters)} 个章节, {len(tasks)} 个任务")


async def benchmark_query(session: AsyncSession, query, name: str, iterations: int = 10):
    """基准测试查询性能."""
    times = []
    
    for _ in range(iterations):
        start = time.time()
        result = await session.execute(query)
        _ = result.scalars().all()
        elapsed = time.time() - start
        times.append(elapsed)
    
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"\n{name}:")
    print(f"  平均耗时：{avg_time*1000:.2f}ms")
    print(f"  最小耗时：{min_time*1000:.2f}ms")
    print(f"  最大耗时：{max_time*1000:.2f}ms")
    
    return avg_time


async def run_benchmarks(session: AsyncSession):
    """运行所有基准测试."""
    print("\n" + "="*60)
    print("开始性能基准测试")
    print("="*60)
    
    results = {}
    
    # 测试 1: status 字段筛选
    print("\n[测试 1] status 字段筛选查询")
    query = select(Novel).where(Novel.status == "writing")
    results["novel_status_filter"] = await benchmark_query(
        session, query, "Novel.status == 'writing'"
    )
    
    # 测试 2: created_at 字段排序
    print("\n[测试 2] created_at 字段排序查询")
    query = select(Novel).order_by(Novel.created_at.desc())
    results["novel_created_at_sort"] = await benchmark_query(
        session, query, "Novel ORDER BY created_at DESC"
    )
    
    # 测试 3: novel_id 关联查询
    print("\n[测试 3] novel_id 关联查询（章节）")
    # 获取一个小说 ID
    result = await session.execute(select(Novel).limit(1))
    novel = result.scalar_one()
    if novel:
        query = select(Chapter).where(Chapter.novel_id == novel.id)
        results["chapter_novel_id_filter"] = await benchmark_query(
            session, query, f"Chapter WHERE novel_id={novel.id}"
        )
    
    # 测试 4: 复合查询（status + created_at）
    print("\n[测试 4] 复合查询（status + created_at 排序）")
    query = (
        select(Novel)
        .where(Novel.status == "completed")
        .order_by(Novel.created_at.desc())
    )
    results["novel复合查询"] = await benchmark_query(
        session, query, "Novel WHERE status='completed' ORDER BY created_at DESC"
    )
    
    # 测试 5: 关联查询（generation_tasks）
    print("\n[测试 5] generation_tasks 的 novel_id 关联查询")
    if novel:
        query = select(GenerationTask).where(GenerationTask.novel_id == novel.id)
        results["task_novel_id_filter"] = await benchmark_query(
            session, query, f"GenerationTask WHERE novel_id={novel.id}"
        )
    
    # 测试 6: status 分组统计
    print("\n[测试 6] status 分组统计查询")
    query = (
        select(Novel.status, func.count(Novel.id))
        .group_by(Novel.status)
    )
    results["novel_status_groupby"] = await benchmark_query(
        session, query, "Novel GROUP BY status"
    )
    
    return results


def print_report(results: dict):
    """打印性能报告."""
    print("\n" + "="*60)
    print("性能测试报告 - Issue #6 数据库索引优化")
    print("="*60)
    print(f"测试时间：{datetime.now().isoformat()}")
    print("\n查询性能汇总:")
    print("-" * 60)
    
    for name, avg_time in results.items():
        status = "✓ 优秀" if avg_time < 0.05 else "⚠ 良好" if avg_time < 0.1 else "✗ 需优化"
        print(f"{name:40s} {avg_time*1000:8.2f}ms  {status}")
    
    print("-" * 60)
    print("\n建议:")
    print("1. 所有查询应在 100ms 内完成")
    print("2. 简单筛选查询应在 50ms 内完成")
    print("3. 如果超过阈值，检查索引是否正确创建")
    print("\n已创建的索引:")
    print("- novels: status, created_at")
    print("- chapters: novel_id, status, created_at")
    print("- generation_tasks: novel_id, status, created_at")
    print("- publish_tasks: novel_id, status, created_at")
    print("- agent_activities: status (已有)")


async def main():
    """主函数."""
    print("="*60)
    print("数据库索引性能测试 - Issue #6 验证")
    print("="*60)
    
    # 设置数据库
    async_session_factory = await setup_test_database()
    
    async with async_session_factory() as session:
        # 创建测试数据
        await create_test_data(session, count=1000)
        
        # 运行基准测试
        results = await run_benchmarks(session)
        
        # 打印报告
        print_report(results)
    
    print("\n✓ 性能测试完成")


if __name__ == "__main__":
    asyncio.run(main())
