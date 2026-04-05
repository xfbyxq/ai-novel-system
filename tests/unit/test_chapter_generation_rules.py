"""
章节生成失败处理规则测试

验证章节生成失败时的安全处理机制
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.safe_chapter_generator import (
    SafeChapterGenerator,
    ChapterGenerationFailure,
)


async def test_single_chapter_failure():
    """测试单章生成失败处理."""
    print("=" * 60)
    print("测试 1: 单章生成失败处理")
    print("=" * 60)

    # 创建模拟数据库会话
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    # 创建生成器
    generator = SafeChapterGenerator(db)

    # 模拟生成函数（总是失败）
    async def failing_generation_func(novel_id, chapter_number):
        raise Exception("模拟生成失败")

    # 测试应该抛出 ChapterGenerationFailure
    try:
        await generator.generate_chapter_safely(
            novel_id=uuid4(),
            chapter_number=1,
            generation_func=failing_generation_func
        )
        print("❌ 测试失败：应该抛出异常")
        return False
    except ChapterGenerationFailure as e:
        print(f"✅ 测试通过：捕获到 ChapterGenerationFailure - {e}")
        return True
    except Exception as e:
        print(f"❌ 测试失败：捕获到未预期的异常 - {e}")
        return False


async def test_batch_generation_interrupt():
    """测试批量生成中断机制."""
    print("\n" + "=" * 60)
    print("测试 2: 批量生成中断机制（连续失败 2 章）")
    print("=" * 60)

    # 创建模拟数据库会话
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    generator = SafeChapterGenerator(db)

    # 模拟生成函数（总是失败）
    async def always_failing_func(novel_id, chapter_number):
        raise Exception(f"第{chapter_number}章生成失败")

    # 测试批量生成（应该在中途被中断）
    result = await generator.generate_batch_safely(
        novel_id=uuid4(),
        from_chapter=1,
        to_chapter=5,
        generation_func=always_failing_func
    )

    # 验证结果
    if result["interrupted"]:
        print(f"✅ 测试通过：批量生成被中断")
        print(f"   - 成功章节：{len(result['successful_chapters'])}")
        print(f"   - 失败章节：{len(result['failed_chapters'])}")
        print(f"   - 中断状态：{result['interrupted']}")
        return True
    else:
        print(f"❌ 测试失败：批量生成应该被中断")
        return False


async def test_partial_batch_failure():
    """测试批量生成部分失败（未达中断阈值）."""
    print("\n" + "=" * 60)
    print("测试 3: 批量生成部分失败（未达中断阈值）")
    print("=" * 60)

    # 创建模拟数据库会话
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    generator = SafeChapterGenerator(db)

    # 模拟生成函数（交替成功和失败）
    call_count = 0
    async def alternating_func(novel_id, chapter_number):
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:
            return {"final_content": "成功", "chapter_plan": {}, "quality_score": 8.0}
        else:
            raise Exception(f"第{chapter_number}章生成失败")

    # 测试批量生成
    result = await generator.generate_batch_safely(
        novel_id=uuid4(),
        from_chapter=1,
        to_chapter=4,
        generation_func=alternating_func
    )

    # 验证结果
    if not result["interrupted"] and len(result["failed_chapters"]) > 0:
        print(f"✅ 测试通过：批量生成完成但有失败章节")
        print(f"   - 成功章节：{result['successful_chapters']}")
        print(f"   - 失败章节：{result['failed_chapters']}")
        print(f"   - 中断状态：{result['interrupted']}")
        return True
    else:
        print(f"❌ 测试失败：结果不符合预期")
        return False


async def test_data_protection():
    """测试已生成章节数据保护."""
    print("\n" + "=" * 60)
    print("测试 4: 已生成章节数据保护")
    print("=" * 60)

    # 创建模拟数据库会话
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    generator = SafeChapterGenerator(db)

    # 模拟生成函数（前两章成功，第三章失败）
    call_count = 0
    async def mixed_func(novel_id, chapter_number):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return {
                "final_content": f"第{chapter_number}章内容",
                "chapter_plan": {"title": f"第{chapter_number}章"},
                "quality_score": 8.0,
                "cost": 0.001,
            }
        else:
            raise Exception("第三章生成失败")

    # 测试批量生成
    result = await generator.generate_batch_safely(
        novel_id=uuid4(),
        from_chapter=1,
        to_chapter=5,
        generation_func=mixed_func
    )

    # 验证
    success_count = len(result["successful_chapters"])

    if success_count == 2 and result["interrupted"]:
        print(f"✅ 测试通过：已生成的 2 章被保护，后续章节被中断")
        print(f"   - 成功章节：{success_count}")
        print(f"   - 中断状态：{result['interrupted']}")
        print(f"   - db.commit 调用次数：{db.commit.call_count} (应该 >= 2)")
        return True
    else:
        print(f"❌ 测试失败：结果不符合预期")
        return False


async def test_continuous_failure_counter():
    """测试连续失败计数器重置."""
    print("\n" + "=" * 60)
    print("测试 5: 连续失败计数器重置")
    print("=" * 60)

    # 创建模拟数据库会话
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    generator = SafeChapterGenerator(db)

    # 模拟生成函数（失败 - 成功 - 失败 - 成功）
    call_count = 0
    async def pattern_func(novel_id, chapter_number):
        nonlocal call_count
        call_count += 1
        if call_count in [1, 3]:  # 第 1、3 次调用失败
            raise Exception(f"第{chapter_number}章生成失败")
        else:  # 第 2、4 次调用成功
            return {
                "final_content": f"第{chapter_number}章内容",
                "chapter_plan": {},
                "quality_score": 8.0,
            }

    # 测试批量生成（应该不会中断，因为连续失败未达阈值）
    result = await generator.generate_batch_safely(
        novel_id=uuid4(),
        from_chapter=1,
        to_chapter=4,
        generation_func=pattern_func
    )

    # 验证
    if not result["interrupted"] and len(result["failed_chapters"]) == 2:
        print(f"✅ 测试通过：连续失败计数器正确重置")
        print(f"   - 成功章节：{result['successful_chapters']}")
        print(f"   - 失败章节：{result['failed_chapters']}")
        print(f"   - 中断状态：{result['interrupted']} (应该为 False)")
        return True
    else:
        print(f"❌ 测试失败：结果不符合预期")
        return False


async def main():
    """运行所有测试."""
    print("\n" + "=" * 60)
    print("章节生成失败处理规则测试")
    print("=" * 60)

    tests = [
        test_single_chapter_failure,
        test_batch_generation_interrupt,
        test_partial_batch_failure,
        test_data_protection,
        test_continuous_failure_counter,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if await test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ 测试异常：{e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试完成：通过 {passed}/{len(tests)}")
    print("=" * 60)

    if passed == len(tests):
        print("\n✅ 所有测试通过！章节生成失败处理规则验证成功")
        return 0
    else:
        print(f"\n❌ {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
