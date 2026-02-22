"""端到端测试：完整的小说企划 + 写作流程"""

import asyncio
import json
import logging
import sys
import uuid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("e2e_test")


async def main():
    # --- 导入 ---
    from core.database import async_session_factory
    from core.models.novel import Novel, NovelStatus
    from core.models.generation_task import GenerationTask, TaskStatus, TaskType
    from backend.services.generation_service import GenerationService
    from sqlalchemy import select

    logger.info("=" * 70)
    logger.info("  小说生成系统 - 端到端测试")
    logger.info("=" * 70)

    async with async_session_factory() as session:
        # ============================================================
        # Step 1: 创建测试小说
        # ============================================================
        logger.info("\n[Step 1] 创建测试小说...")
        novel = Novel(
            title="星辰大主宰",
            genre="玄幻",
            tags=["修炼", "升级", "系统"],
            synopsis="少年偶得星辰系统，踏上修炼之路，从废材逆袭成为大主宰的故事。",
            status=NovelStatus.planning,
        )
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id
        logger.info(f"  小说已创建: {novel.title} (ID: {novel_id})")

        # ============================================================
        # Step 2: 创建企划任务
        # ============================================================
        logger.info("\n[Step 2] 创建企划任务...")
        planning_task = GenerationTask(
            novel_id=novel_id,
            task_type=TaskType.planning,
            phase="planning",
            status=TaskStatus.pending,
            input_data={},
        )
        session.add(planning_task)
        await session.commit()
        await session.refresh(planning_task)
        task_id = planning_task.id
        logger.info(f"  企划任务已创建 (ID: {task_id})")

        # ============================================================
        # Step 3: 执行企划阶段
        # ============================================================
        logger.info("\n[Step 3] 开始执行企划阶段（调用通义千问 4 次）...")
        logger.info("  -> 主题分析师 -> 世界观架构师 -> 角色设计师 -> 情节架构师")

        service = GenerationService(session)
        try:
            planning_result = await service.run_planning(novel_id, task_id)
            logger.info("\n  企划阶段执行成功！")
        except Exception as e:
            logger.error(f"\n  企划阶段失败: {e}")
            import traceback
            traceback.print_exc()
            return

        # ============================================================
        # Step 4: 验证企划数据持久化
        # ============================================================
        logger.info("\n[Step 4] 验证企划数据持久化...")

        # 重新查询小说
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(Novel)
            .where(Novel.id == novel_id)
            .options(
                selectinload(Novel.world_setting),
                selectinload(Novel.characters),
                selectinload(Novel.plot_outline),
            )
        )
        novel = result.scalar_one()

        # 检查世界观
        ws = novel.world_setting
        if ws:
            logger.info(f"  [OK] 世界观已保存: {ws.world_name or '(unnamed)'}, 类型: {ws.world_type or '(none)'}")
        else:
            logger.error("  [FAIL] 世界观未保存！")

        # 检查角色
        chars = novel.characters
        logger.info(f"  [OK] 角色已保存: {len(chars)} 个")
        for c in chars:
            logger.info(f"       - {c.name} ({c.role_type.value if c.role_type else 'unknown'})")

        # 检查大纲
        po = novel.plot_outline
        if po:
            logger.info(f"  [OK] 情节大纲已保存: 结构类型={po.structure_type}, 卷数={len(po.volumes or [])}")
        else:
            logger.error("  [FAIL] 情节大纲未保存！")

        # 检查小说状态
        logger.info(f"  小说状态: {novel.status.value}")

        # 检查任务状态
        task_result = await session.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        task = task_result.scalar_one()
        logger.info(f"  任务状态: {task.status.value}, tokens: {task.token_usage}, 成本: ¥{task.cost}")

        # 检查 token 使用记录
        from core.models.token_usage import TokenUsage
        tu_result = await session.execute(
            select(TokenUsage).where(TokenUsage.task_id == task_id)
        )
        token_records = tu_result.scalars().all()
        logger.info(f"  Token 使用记录: {len(token_records)} 条")
        for tr in token_records:
            logger.info(f"       - {tr.agent_name}: {tr.total_tokens} tokens, ¥{tr.cost}")

        # ============================================================
        # Step 5: 执行写作阶段（第1章）
        # ============================================================
        logger.info("\n[Step 5] 创建写作任务并执行第1章写作...")
        writing_task = GenerationTask(
            novel_id=novel_id,
            task_type=TaskType.writing,
            phase="writing",
            status=TaskStatus.pending,
            input_data={"chapter_number": 1, "volume_number": 1},
        )
        session.add(writing_task)
        await session.commit()
        await session.refresh(writing_task)
        writing_task_id = writing_task.id
        logger.info(f"  写作任务已创建 (ID: {writing_task_id})")

        logger.info("  -> 章节策划师 -> 作家 -> 编辑 -> 连续性审查员")

        service2 = GenerationService(session)
        try:
            writing_result = await service2.run_chapter_writing(
                novel_id, writing_task_id, chapter_number=1, volume_number=1
            )
            logger.info("\n  第1章写作执行成功！")
        except Exception as e:
            logger.error(f"\n  第1章写作失败: {e}")
            import traceback
            traceback.print_exc()
            return

        # ============================================================
        # Step 6: 验证写作数据持久化
        # ============================================================
        logger.info("\n[Step 6] 验证写作数据持久化...")

        from core.models.chapter import Chapter
        ch_result = await session.execute(
            select(Chapter).where(Chapter.novel_id == novel_id)
        )
        chapters = ch_result.scalars().all()
        logger.info(f"  [OK] 章节已保存: {len(chapters)} 章")
        for ch in chapters:
            logger.info(f"       - 第{ch.chapter_number}章 {ch.title or ''}: {ch.word_count}字, 质量评分: {ch.quality_score}")
            if ch.content:
                logger.info(f"         内容预览: {ch.content[:100]}...")

        # 重新查询小说统计
        result2 = await session.execute(select(Novel).where(Novel.id == novel_id))
        novel2 = result2.scalar_one()
        logger.info(f"  小说总字数: {novel2.word_count}")
        logger.info(f"  小说总章数: {novel2.chapter_count}")
        logger.info(f"  总Token成本: ¥{novel2.token_cost}")

        # 查看写作任务状态
        wt_result = await session.execute(
            select(GenerationTask).where(GenerationTask.id == writing_task_id)
        )
        wt = wt_result.scalar_one()
        logger.info(f"  写作任务状态: {wt.status.value}, tokens: {wt.token_usage}, 成本: ¥{wt.cost}")

        # ============================================================
        # 总结
        # ============================================================
        logger.info("\n" + "=" * 70)
        logger.info("  端到端测试完成！")
        logger.info("=" * 70)
        logger.info(f"  小说: {novel2.title}")
        logger.info(f"  状态: {novel2.status.value}")
        logger.info(f"  世界观: {'已生成' if ws else '未生成'}")
        logger.info(f"  角色数: {len(chars)}")
        logger.info(f"  大纲: {'已生成' if po else '未生成'}")
        logger.info(f"  章节数: {novel2.chapter_count}")
        logger.info(f"  总字数: {novel2.word_count}")
        logger.info(f"  总成本: ¥{novel2.token_cost}")
        logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
