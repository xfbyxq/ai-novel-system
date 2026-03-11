#!/usr/bin/env python3
"""
章节连贯性保障系统功能验证脚本

测试目标：
1. 验证所有模块可以正常导入
2. 测试约束推断功能
3. 测试上下文携带功能
4. 测试验证引擎功能
5. 测试完整的连贯性保障流程
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import (
    ContinuityAssuranceIntegration,
    ConstraintInferenceEngine,
    ContextPropagator,
    ValidationEngine,
    ContinuityConstraint,
)
from llm.qwen_client import QwenClient
from core.logging_config import logger


async def test_constraint_inference():
    """测试 1: 约束推断功能"""
    print("\n" + "="*60)
    print("测试 1: 约束推断功能")
    print("="*60)
    
    client = QwenClient()
    engine = ConstraintInferenceEngine(client)
    
    # 示例章节结尾（通用类型，不特定于某种小说）
    test_ending = """
    门缓缓打开，一股冷风扑面而来。林默深吸一口气，迈步走了进去。
    房间里很暗，只有窗外透进的微弱月光。他看到桌子上的那封信，
    静静地躺在那里，仿佛已经等待了一个世纪。
    
    他伸出手，指尖触碰到信封的瞬间，手机突然震动起来。
    屏幕上显示的是一个陌生号码。林默犹豫了一下，还是接通了。
    
    "你终于来了。"对方的声音低沉而沙哑，"东西拿到了吗？"
    """
    
    print("输入：章节结尾（80 字）")
    print(f"内容：{test_ending[:100]}...")
    
    # 推断约束
    constraints = await engine.infer_constraints(
        previous_chapter_ending=test_ending,
        min_priority=5,
        max_constraints=5
    )
    
    print(f"\n推断结果：{len(constraints)} 个约束")
    for i, c in enumerate(constraints, 1):
        print(f"\n{i}. [{c.constraint_type}] 优先级：{c.priority}")
        print(f"   描述：{c.description}")
        print(f"   验证：{c.validation_hint}")
    
    # 验证推断结果
    assert len(constraints) > 0, "应该推断出至少 1 个约束"
    assert all(1 <= c.priority <= 10 for c in constraints), "优先级应在 1-10 之间"
    assert all(c.description for c in constraints), "每个约束都应有描述"
    
    print("\n✅ 约束推断测试通过")
    return constraints


async def test_context_propagation():
    """测试 2: 上下文携带功能"""
    print("\n" + "="*60)
    print("测试 2: 上下文携带功能")
    print("="*60)
    
    propagator = ContextPropagator()
    
    # 使用上一个测试的约束
    constraints = [
        ContinuityConstraint(
            constraint_type="logical",
            description="需要揭示信的内容和来源",
            priority=8,
            source_text="桌子上的那封信，静静地躺在那里",
            validation_hint="检查是否描述了信的内容"
        ),
        ContinuityConstraint(
            constraint_type="narrative",
            description="需要回应电话中的神秘人",
            priority=7,
            source_text="你终于来了。东西拿到了吗？",
            validation_hint="检查是否有对电话对话的回应"
        ),
    ]
    
    next_outline = "林默与神秘人对话，得知信的重要性，决定展开调查。"
    previous_ending = "电话中的神秘声音询问：'东西拿到了吗？'"
    
    # 构建增强提示词
    enhanced_prompt = propagator.build_enhanced_prompt(
        next_chapter_outline=next_outline,
        constraints=constraints,
        previous_ending=previous_ending,
        include_fewshot=True
    )
    
    print("输入：下一章大纲 + 2 个约束")
    print(f"大纲：{next_outline}")
    print(f"约束数：{len(constraints)}")
    
    print("\n输出：增强提示词")
    print(f"长度：{len(enhanced_prompt)} 字符")
    print("-"*60)
    print(enhanced_prompt[:500] + "..." if len(enhanced_prompt) > 500 else enhanced_prompt)
    print("-"*60)
    
    # 验证提示词质量
    assert "读者期待" in enhanced_prompt, "提示词应包含读者期待说明"
    assert "创作自由度" in enhanced_prompt, "提示词应包含创作自由度说明"
    assert next_outline in enhanced_prompt, "提示词应包含原始大纲"
    
    print("\n✅ 上下文携带测试通过")
    return enhanced_prompt


async def test_validation():
    """测试 3: 验证引擎功能"""
    print("\n" + "="*60)
    print("测试 3: 验证引擎功能")
    print("="*60)
    
    client = QwenClient()
    engine = ValidationEngine(client)
    
    # 测试数据
    previous_ending = "电话中的神秘声音询问：'东西拿到了吗？'"
    
    # 好的过渡示例
    good_beginning = """
    林默握紧手机，声音有些颤抖："什么东西？你是谁？"
    对方沉默了片刻，然后低声说："别装傻了。那封信，你已经在路上了对吧？"
    林默的心跳加速，他看向桌上的信封，突然意识到事情并不简单。
    """
    
    # 差的过渡示例
    bad_beginning = """
    阳光明媚的早晨，小鸟在枝头欢快地歌唱。
    林默伸了个懒腰，开始准备今天的早餐。
    昨晚的事情仿佛只是一场梦。
    """
    
    constraints = [
        ContinuityConstraint(
            constraint_type="logical",
            description="需要回应电话对话",
            priority=9,
            source_text="东西拿到了吗？",
            validation_hint="检查是否有对电话内容的回应"
        ),
    ]
    
    print("测试 A: 好的过渡")
    print(f"上一章结尾：{previous_ending}")
    print(f"下一章开头：{good_beginning[:50]}...")
    
    report_good = await engine.validate(
        previous_ending=previous_ending,
        new_chapter_beginning=good_beginning,
        constraints=constraints
    )
    
    print(f"评估：{report_good.overall_assessment}")
    print(f"质量评分：{report_good.quality_score:.1f}")
    print(f"满足约束：{len(report_good.satisfied_constraints)} 个")
    
    print("\n测试 B: 差的过渡")
    print(f"下一章开头：{bad_beginning[:50]}...")
    
    report_bad = await engine.validate(
        previous_ending=previous_ending,
        new_chapter_beginning=bad_beginning,
        constraints=constraints
    )
    
    print(f"评估：{report_bad.overall_assessment}")
    print(f"质量评分：{report_bad.quality_score:.1f}")
    print(f"未满足约束：{len(report_bad.unsatisfied_constraints)} 个")
    
    # 验证结果
    assert report_good.quality_score > report_bad.quality_score, "好的过渡应得分更高"
    assert report_good.satisfied_constraints or report_good.artistic_breaking, "好的过渡应满足约束或合理打破"
    
    print("\n✅ 验证引擎测试通过")
    return report_good, report_bad


async def test_full_integration():
    """测试 4: 完整集成流程"""
    print("\n" + "="*60)
    print("测试 4: 完整集成流程（模拟）")
    print("="*60)
    
    integrator = ContinuityAssuranceIntegration()
    
    # 模拟章节内容
    previous_content = """
    门缓缓打开，林默走了进去。房间里很暗，只有桌上的信在月光下泛着白光。
    手机震动，他接起电话。"你终于来了。"对方说，"东西拿到了吗？"
    林默心跳加速，意识到事情不简单。
    """
    
    next_outline = "林默与神秘人对话，得知信的重要性。"
    
    # 模拟生成回调
    async def mock_generate(prompt: str) -> str:
        """模拟章节生成"""
        return """
        "什么东西？"林默问道。
        对方沉默片刻："那封信，关于你身世的秘密。"
        林默的手开始颤抖，他看向桌上的信封，深吸一口气。
        "告诉我一切。"他说。
        """
    
    print("输入：")
    print(f"- 上一章内容：{len(previous_content)} 字")
    print(f"- 下一章大纲：{next_outline}")
    print(f"- 生成回调：模拟函数")
    
    # 执行完整流程
    result = await integrator.enforce_continuity(
        novel_id="test-novel-001",
        chapter_number=3,
        previous_chapter_content=previous_content,
        next_chapter_outline=next_outline,
        generation_callback=mock_generate,
        max_regeneration_attempts=2,
        min_quality_score=60.0
    )
    
    print("\n输出：")
    print(f"- 质量评分：{result['quality_score']:.1f}")
    print(f"- 重新生成次数：{result['regeneration_count']}")
    print(f"- 应用约束数：{result['constraints_applied']}")
    print(f"- 最终决策：{result['transition_record'].final_decision}")
    print(f"- 修改说明：{result['transition_record'].modification_notes}")
    
    # 验证结果
    assert 'content' in result, "结果应包含生成内容"
    assert 'transition_record' in result, "结果应包含过渡记录"
    assert 'quality_score' in result, "结果应包含质量评分"
    assert result['quality_score'] >= 0, "质量评分应>=0"
    
    print("\n✅ 完整集成流程测试通过")
    return result


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("🧪 章节连贯性保障系统功能验证")
    print("="*60)
    
    try:
        # 测试 1: 约束推断
        constraints = await test_constraint_inference()
        
        # 测试 2: 上下文携带
        enhanced_prompt = await test_context_propagation()
        
        # 测试 3: 验证引擎
        reports = await test_validation()
        
        # 测试 4: 完整集成
        result = await test_full_integration()
        
        # 总结
        print("\n" + "="*60)
        print("✅ 所有测试通过！")
        print("="*60)
        print("\n测试摘要:")
        print("1. ✅ 约束推断功能正常")
        print("2. ✅ 上下文携带功能正常")
        print("3. ✅ 验证引擎功能正常")
        print("4. ✅ 完整集成流程正常")
        print("\n系统已准备就绪，可以投入使用！")
        print("="*60 + "\n")
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
        return False
    except Exception as e:
        print(f"\n❌ 测试异常：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
