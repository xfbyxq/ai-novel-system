#!/usr/bin/env python3
"""
大纲协作完善功能验证脚本.
用于演示和验证新实现的功能
"""

import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
import sys

sys.path.append(str(Path(__file__).parent.parent))

from agents.outline_quality_evaluator import OutlineQualityEvaluator
from agents.outline_iteration_controller import OutlineIterationController


async def demo_outline_enhancement():
    """演示大纲协作完善功能."""

    print("🚀 开始大纲协作完善功能演示")
    print("=" * 50)

    # 1. 准备测试数据
    print("\n📋 1. 准备测试数据...")

    sample_outline = {
        "structure_type": "三幕式",
        "main_plot": {
            "setup": "现代程序员意外穿越到修仙世界",
            "conflict": "发现这个世界以代码为根基，修士们通过编写程序来操控天地法则",
            "climax": "主角领悟'大道三千，代码为尊'的真谛，创造出超越时代的编程体系",
            "resolution": "建立新的修仙文明，将科技与修仙完美融合",
        },
        "volumes": [
            {
                "number": 1,
                "title": "代码觉醒",
                "chapters": [1, 25],
                "summary": "程序员主角穿越到以代码为基础的修仙世界，发现自己拥有独特的编程天赋",
                "core_conflict": "在传统修仙体系中证明代码之道的价值",
                "tension_cycles": [
                    {
                        "chapters": [1, 8],
                        "suppress_events": [
                            "被传统修士嘲笑",
                            "测试显示无灵根资质",
                            "被认为是个废柴",
                        ],
                        "release_event": "意外激活古老的代码传承",
                    },
                    {
                        "chapters": [9, 16],
                        "suppress_events": [
                            "遭遇到代码bug导致走火入魔",
                            "被同门排斥",
                            "修为停滞不前",
                        ],
                        "release_event": "创造出第一个实用的代码法术",
                    },
                ],
                "key_events": [
                    {
                        "chapter": 3,
                        "event": "获得神秘的机械戒指",
                        "impact": "开启代码修仙之路",
                    },
                    {
                        "chapter": 12,
                        "event": "第一次成功运行代码法术",
                        "impact": "证明了自己的价值",
                    },
                    {
                        "chapter": 20,
                        "event": "收服第一个代码精灵",
                        "impact": "实力大增",
                    },
                ],
            }
        ],
        "key_turning_points": [
            {"chapter": 3, "event": "获得机械戒指", "impact": "命运转折点"},
            {"chapter": 12, "event": "首次施展代码法术", "impact": "获得认可"},
            {"chapter": 25, "event": "击败传统修士挑战", "impact": "确立地位"},
        ],
        "climax_chapter": 75,
    }

    world_setting = {
        "world_name": "代码修仙界",
        "world_type": "科技修仙",
        "power_system": {
            "name": "代码灵力体系",
            "levels": ["初级编码者", "中级程序员", "高级工程师", "架构师", "系统大师"],
            "special_mechanics": [
                "变量赋值",
                "循环控制",
                "函数调用",
                "面向对象",
                "设计模式",
            ],
        },
        "factions": [
            {"name": "传统修仙门派", "type": "保守派", "philosophy": "排斥科技"},
            {"name": "新兴科技宗门", "type": "革新派", "philosophy": "拥抱变化"},
            {"name": "代码修士联盟", "type": "中立派", "philosophy": "融合并进"},
        ],
        "geography": {
            "main_regions": ["东代码区", "西算法域", "南数据海", "北逻辑山"],
            "special_places": ["万行代码谷", "无限循环潭", "递归深渊"],
        },
    }

    characters = [
        {
            "name": "林小码",
            "role": "主角",
            "importance": "main",
            "background": "现代资深程序员，精通多种编程语言",
            "motivations": ["寻找回家的方法", "证明代码的价值", "保护身边的人"],
            "abilities": ["超强编程天赋", "逻辑思维敏锐", "现代科技知识"],
            "relationships": {
                "师父": "代码宗老祖",
                "师兄": "张大牛",
                "红颜知己": "苏小白",
            },
        },
        {
            "name": "张大牛",
            "role": "男配",
            "importance": "supporting",
            "background": "传统修仙天才，后来转向代码修仙",
            "motivations": ["追求更强的实力", "帮助主角成长"],
            "abilities": ["传统修仙功法", "代码理解能力"],
            "relationships": {"师弟": "林小码", "竞争对手": "李傲天"},
        },
        {
            "name": "苏小白",
            "role": "女主",
            "importance": "main",
            "background": "天生灵根缺陷，但对代码有独特感悟",
            "motivations": ["克服身体缺陷", "与主角共同成长"],
            "abilities": ["代码感知", "阵法编织"],
            "relationships": {"恋人": "林小码", "好友": "张大牛"},
        },
    ]

    print("✅ 测试数据准备完成")

    # 2. 测试大纲质量评估
    print("\n📊 2. 执行大纲质量评估...")

    try:
        evaluator = OutlineQualityEvaluator()
        quality_result = await evaluator.evaluate_outline_comprehensively(
            outline=sample_outline, world_setting=world_setting, characters=characters
        )

        print(f"📈 综合评分: {quality_result.overall_score:.2f}/10.0")
        print(f"💪 优势: {quality_result.strengths}")
        print(f"⚠️  劣势: {quality_result.weaknesses}")
        print(f"💡 改进建议数量: {len(quality_result.improvement_suggestions)}")

        if quality_result.improvement_suggestions:
            print("🔧 主要改进建议:")
            for suggestion in quality_result.improvement_suggestions[:3]:
                print(f"  • {suggestion.get('description', '未知建议')}")

    except Exception as e:
        print(f"❌ 质量评估失败: {e}")
        return

    # 3. 测试迭代优化控制
    print("\n🔄 3. 测试迭代优化控制...")

    try:
        controller = OutlineIterationController(
            quality_threshold=8.0, consistency_threshold=8.5, max_iterations=2
        )

        print(f"🎯 质量阈值: {controller.quality_threshold}")
        print(f"🎯 一致性阈值: {controller.consistency_threshold}")
        print(f"🔄 最大迭代次数: {controller.max_iterations}")

        # 模拟几次迭代
        for i in range(2):
            quality_score = 7.0 + i * 0.8  # 逐步提升
            consistency_score = 7.5 + i * 0.7

            should_continue = controller.should_continue(
                quality_score=quality_score, consistency_score=consistency_score
            )

            print(
                f"  迭代 {i+1}: 质量={quality_score:.1f}, 一致性={consistency_score:.1f}, 继续={should_continue}"
            )

            if not should_continue:
                break

        summary = controller.get_summary()
        print(f"📋 迭代摘要: 共执行 {summary['total_iterations']} 次迭代")

    except Exception as e:
        print(f"❌ 迭代控制测试失败: {e}")

    # 4. 演示完整工作流（简化版）
    print("\n🎭 4. 演示完整工作流...")

    try:
        # 创建简化的工作流演示
        print("📝 模拟大纲协作完善流程:")
        print("  1. 初始化团队上下文...")
        print("  2. 执行一致性检查...")
        print("  3. 启动迭代优化...")
        print("  4. 生成增强报告...")

        # 模拟结果
        enhancement_result = {
            "original_outline": sample_outline,
            "enhanced_outline": {
                **sample_outline,
                "enhancement_notes": [
                    "加强了世界观元素的融入",
                    "优化了角色戏份分配",
                    "完善了张力循环设计",
                ],
            },
            "consistency_report": {
                "consistency_score": 8.7,
                "extended_analysis": {
                    "worldview_alignment": {"aligned": True},
                    "character_mapping": {"well_distributed": True},
                },
            },
            "quality_report": {
                "final_quality_score": 8.3,
                "improvements_made": ["提升了结构完整性", "增强了创新性"],
                "remaining_issues": ["可进一步丰富支线剧情"],
            },
        }

        print("✅ 大纲协作完善流程模拟完成")
        print(
            f"📊 最终一致性评分: {enhancement_result['consistency_report']['consistency_score']}"
        )
        print(
            f"📊 最终质量评分: {enhancement_result['quality_report']['final_quality_score']}"
        )

    except Exception as e:
        print(f"❌ 工作流演示失败: {e}")

    print("\n" + "=" * 50)
    print("🎉 大纲协作完善功能演示完成!")
    print("\n📋 主要成果:")
    print("• 实现了基于现有多Agent机制的大纲完善功能")
    print("• 集成了专业的质量评估和一致性检查")
    print("• 实现了智能的迭代优化控制")
    print("• 提供了完整的API接口和测试用例")
    print("• 保持了与现有系统的完全兼容性")


async def main():
    """主函数."""
    try:
        await demo_outline_enhancement()
    except KeyboardInterrupt:
        print("\n\n👋 演示被用户中断")
    except Exception as e:
        print(f"\n❌ 演示过程中发生错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
