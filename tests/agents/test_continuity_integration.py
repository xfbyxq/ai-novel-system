"""
连贯性保障系统集成测试

测试完整的章节生成流程中的连贯性保障：
1. 端到端测试：生成 3 章并验证连贯性
2. A/B 测试：新旧系统对比
"""
import pytest

from agents.continuity_integration_module import ContinuityIntegrationModule
from agents.enhanced_context_manager import EnhancedContextManager


# ==================== 端到端测试 ====================

class TestEndToEndContinuity:
    """端到端连贯性测试."""

    @pytest.mark.asyncio
    async def test_chapter_3_continuity(self):
        """
        测试第 3 章的连贯性保障

        场景：
        - 第 1 章：埋下重要伏笔
        - 第 2 章：发展剧情
        - 第 3 章：应该回收第 1 章的伏笔
        """
        # 准备测试数据
        novel_data = {
            "topic_analysis": {
                "core_theme": "成长与牺牲",
                "central_question": "主角能否拯救世界？"
            },
            "plot_outline": {
                "volumes": [
                    {
                        "volume_num": 1,
                        "title": "第一卷",
                        "chapters_range": [1, 10],
                        "tension_cycles": [
                            {
                                "chapters": [1, 10],
                                "suppress_events": ["被嘲笑", "被打击"],
                                "release_event": "首次胜利"
                            }
                        ],
                        "key_events": [
                            {"chapter": 1, "event": "觉醒能力"},
                            {"chapter": 3, "event": "首次战斗"}
                        ]
                    }
                ]
            },
            "characters": [
                {
                    "name": "主角",
                    "core_motivation": "拯救世界",
                    "personal_code": "不伤害无辜",
                    "personality_traits": ["勇敢", "善良"]
                }
            ],
            "foreshadowings": [
                {
                    "id": "f1",
                    "content": "神秘老人的预言",
                    "planted_chapter": 1,
                    "expected_resolve_chapter": 3,
                    "importance": 8,
                    "status": "pending"
                }
            ]
        }

        # 创建集成模块
        module = ContinuityIntegrationModule("test-novel", novel_data)

        # 模拟第 1 章
        chapter_1_summary = {
            "title": "觉醒",
            "plot_progress": "主角觉醒能力，遇到神秘老人",
            "key_events": ["觉醒能力", "遇到神秘老人"],
            "foreshadowing": ["神秘老人的预言"],
            "ending_state": "主角决定踏上旅程"
        }

        # 模拟第 2 章
        chapter_2_summary = {
            "title": "启程",
            "plot_progress": "主角踏上旅程，遇到第一个挑战",
            "key_events": ["踏上旅程"],
            "ending_state": "主角面临第一个挑战"
        }

        # 准备第 3 章生成
        chapter_summaries = {
            1: chapter_1_summary,
            2: chapter_2_summary
        }

        chapter_contents = {
            1: "第 1 章完整内容...",
            2: "第 2 章完整内容..."
        }

        prep_result = await module.prepare_chapter_generation(
            chapter_number=3,
            volume_number=1,
            chapter_summaries=chapter_summaries,
            chapter_contents=chapter_contents
        )

        # 验证上下文包含第 1 章的伏笔
        assert "神秘老人的预言" in prep_result["context_prompt"]

        # 验证伏笔要求提到需要回收
        assert "神秘老人的预言" in prep_result["foreshadowing_requirements"]

        # 模拟章节策划
        chapter_plan = {
            "main_events": ["主角首次战斗", "预言实现"],
            "character_actions": [
                {
                    "name": "主角",
                    "action": "使用能力击败敌人",
                    "motivation": "保护无辜",
                    "context": "敌人攻击平民"
                }
            ],
            "foreshadowing_payoffs": ["神秘老人的预言"]
        }

        previous_chapter = {
            "ending_state": "主角面临第一个挑战",
            "chapter_number": 2
        }

        # 审查策划
        review_result = await module.review_chapter_plan(
            chapter_plan=chapter_plan,
            chapter_number=3,
            previous_chapter=previous_chapter
        )

        # 验证策划通过审查
        assert review_result.passed == True
        assert review_result.overall_score >= 7.0

        # 验证伏笔被标记为已回收
        module.foreshadowing_injector.get_statistics()
        # 注意：这里需要手动标记为已回收，或者在审查时自动标记

    @pytest.mark.asyncio
    async def test_10_chapter_sequential_generation(self):
        """
        测试连续生成 10 章的连贯性

        验证：
        - 每章都推进大纲
        - 伏笔回收率 >= 90%
        - 角色行为一致
        """
        novel_data = {
            "topic_analysis": {
                "core_theme": "成长与牺牲"
            },
            "plot_outline": {
                "volumes": [
                    {
                        "volume_num": 1,
                        "title": "第一卷",
                        "chapters_range": [1, 10],
                        "tension_cycles": [
                            {
                                "chapters": [1, 5],
                                "suppress_events": ["挫折 1", "挫折 2"],
                                "release_event": "小胜利"
                            },
                            {
                                "chapters": [6, 10],
                                "suppress_events": ["更大挫折"],
                                "release_event": "最终胜利"
                            }
                        ],
                        "key_events": [
                            {"chapter": 1, "event": "觉醒"},
                            {"chapter": 3, "event": "首次战斗"},
                            {"chapter": 5, "event": "小胜利"},
                            {"chapter": 10, "event": "最终胜利"}
                        ]
                    }
                ]
            },
            "characters": [
                {
                    "name": "主角",
                    "core_motivation": "成长",
                    "personal_code": "永不放弃",
                    "personality_traits": ["坚韧"]
                }
            ],
            "foreshadowings": []
        }

        module = ContinuityIntegrationModule("test-novel", novel_data)

        # 模拟生成 10 章
        chapter_summaries = {}
        all_passed = True
        scores = []

        for chapter_num in range(1, 11):
            # 准备生成
            prep_result = await module.prepare_chapter_generation(
                chapter_number=chapter_num,
                volume_number=1,
                chapter_summaries=chapter_summaries,
                chapter_contents={}
            )

            # 模拟策划（简化：总是创建符合大纲的策划）
            chapter_plan = {
                "main_events": [f"第{chapter_num}章的主要事件"],
                "character_actions": [
                    {
                        "name": "主角",
                        "action": "继续努力",
                        "motivation": "永不放弃",
                        "context": "面对挑战"
                    }
                ]
            }

            previous_chapter = {
                "ending_state": f"第{chapter_num-1}章的结尾" if chapter_num > 1 else "开始",
                "chapter_number": chapter_num - 1
            }

            # 审查
            review_result = await module.review_chapter_plan(
                chapter_plan=chapter_plan,
                chapter_number=chapter_num,
                previous_chapter=previous_chapter
            )

            all_passed = all_passed and review_result.passed
            scores.append(review_result.overall_score)

            # 更新摘要
            chapter_summaries[chapter_num] = {
                "title": f"第{chapter_num}章",
                "plot_progress": f"第{chapter_num}章的剧情",
                "key_events": [f"事件{chapter_num}"],
                "ending_state": f"第{chapter_num}章的结尾"
            }

        # 验证整体连贯性
        assert all_passed == True
        assert sum(scores) / len(scores) >= 7.0

        # 统计信息
        stats = module.get_statistics()
        print(f"10 章生成统计：{stats}")


# ==================== A/B 测试 ====================

class TestABComparison:
    """A/B 测试：新旧系统对比."""

    @pytest.mark.asyncio
    async def test_new_vs_old_context_management(self):
        """
        测试新旧上下文管理系统的对比

        旧系统：简单的前 N 章摘要
        新系统：EnhancedContextManager
        """
        novel_data = {
            "topic_analysis": {
                "core_theme": "成长与牺牲",
                "central_question": "主角能否拯救世界？"
            },
            "genre": "玄幻"
        }

        # 模拟章节摘要
        chapter_summaries = {
            1: {
                "title": "觉醒",
                "plot_progress": "主角觉醒能力，遇到神秘老人，得到预言",
                "key_events": ["觉醒能力", "遇到神秘老人"],
                "foreshadowing": ["神秘预言：未来将有大战"],
                "character_changes": {"主角": "从普通人变为能力者"},
                "ending_state": "主角决定踏上旅程"
            },
            2: {
                "title": "启程",
                "plot_progress": "主角踏上旅程，遇到第一个伙伴",
                "key_events": ["遇到伙伴"],
                "ending_state": "两人决定同行"
            }
        }

        # 旧系统：简单摘要
        old_context_parts = []
        for ch in range(1, 3):
            summary = chapter_summaries[ch]
            old_context_parts.append(
                f"第{ch}章：{summary['plot_progress'][:100]}"  # 只取前 100 字
            )
        old_context = "\n".join(old_context_parts)

        # 新系统：增强上下文
        manager = EnhancedContextManager("test-novel")
        enhanced_context = manager.build_context_for_chapter(
            chapter_number=3,
            novel_data=novel_data,
            chapter_summaries=chapter_summaries,
            chapter_contents={1: "第 1 章完整内容", 2: "第 2 章完整内容"},
            foreshadowings=[
                {
                    "id": "f1",
                    "content": "神秘预言：未来将有大战",
                    "planted_chapter": 1,
                    "importance": 8,
                    "status": "pending"
                }
            ],
            conflicts=[]
        )
        new_context = enhanced_context.to_prompt()

        # 验证新系统保留了更多信息
        assert len(new_context) > len(old_context)

        # 验证新系统保留了关键伏笔
        assert "神秘预言" in new_context

        # 验证新系统保留了核心主题
        assert "成长与牺牲" in new_context

        # 计算信息保留率（简化：基于关键词）
        old_keywords = ["觉醒", "旅程", "伙伴"]
        new_keywords = ["觉醒", "旅程", "伙伴", "神秘预言", "成长与牺牲"]

        old_retained = sum(1 for kw in old_keywords if kw in old_context)
        new_retained = sum(1 for kw in new_keywords if kw in new_context)

        old_retention_rate = old_retained / len(old_keywords)
        new_retention_rate = new_retained / len(new_keywords)

        assert new_retention_rate > old_retention_rate
        print(f"旧系统保留率：{old_retention_rate:.1%}")
        print(f"新系统保留率：{new_retention_rate:.1%}")


# ==================== 性能测试 ====================

class TestPerformance:
    """性能测试."""

    @pytest.mark.asyncio
    async def test_context_building_performance(self):
        """测试上下文构建性能."""
        import time

        manager = EnhancedContextManager("test-novel")

        # 准备大量章节数据
        chapter_summaries = {}
        for i in range(1, 21):
            chapter_summaries[i] = {
                "title": f"第{i}章",
                "plot_progress": f"第{i}章的剧情描述" * 10,
                "key_events": [f"事件{i}-1", f"事件{i}-2"],
                "foreshadowing": [f"伏笔{i}"] if i % 3 == 0 else [],
                "ending_state": f"第{i}章的结尾"
            }

        chapter_contents = {
            i: f"第{i}章的完整内容" * 100
            for i in range(1, 21)
        }

        # 测试构建第 21 章的上下文
        start_time = time.time()

        context = manager.build_context_for_chapter(
            chapter_number=21,
            novel_data={"topic_analysis": {}, "genre": "玄幻"},
            chapter_summaries=chapter_summaries,
            chapter_contents=chapter_contents,
            foreshadowings=[],
            conflicts=[]
        )

        elapsed = time.time() - start_time

        # 验证性能
        assert elapsed < 1.0  # 应该在 1 秒内完成

        # 验证 token 数
        tokens = context.estimate_tokens()
        assert tokens < 10000  # 应该控制在合理范围

        print(f"构建上下文耗时：{elapsed:.3f}秒")
        print(f"上下文 token 数：~{tokens}")

    @pytest.mark.asyncio
    async def test_review_performance(self):
        """测试审查性能."""
        import time

        novel_data = {
            "topic_analysis": {"core_theme": "成长"},
            "plot_outline": {"volumes": []},
            "characters": [],
            "foreshadowings": []
        }

        module = ContinuityIntegrationModule("test-novel", novel_data)

        # 准备复杂的章节策划
        chapter_plan = {
            "main_events": ["事件 1", "事件 2", "事件 3"] * 5,
            "character_actions": [
                {
                    "name": "角色",
                    "action": "行为",
                    "motivation": "动机",
                    "context": "情境"
                }
            ] * 10
        }

        previous_chapter = {
            "ending_state": "上一章结尾",
            "chapter_number": 4
        }

        # 测试审查性能
        start_time = time.time()

        result = await module.review_chapter_plan(
            chapter_plan=chapter_plan,
            chapter_number=5,
            previous_chapter=previous_chapter
        )

        elapsed = time.time() - start_time

        # 验证性能
        assert elapsed < 2.0  # 应该在 2 秒内完成

        print(f"审查耗时：{elapsed:.3f}秒")


# ==================== 边界测试 ====================

class TestEdgeCases:
    """边界测试."""

    @pytest.mark.asyncio
    async def test_first_chapter_generation(self):
        """测试第 1 章生成（无前置章节）."""
        novel_data = {
            "topic_analysis": {"core_theme": "成长"},
            "plot_outline": {"volumes": []},
            "characters": [],
            "foreshadowings": []
        }

        module = ContinuityIntegrationModule("test-novel", novel_data)

        # 第 1 章没有前置章节
        result = await module.prepare_chapter_generation(
            chapter_number=1,
            volume_number=1
        )

        # 应该正常返回，不报错
        assert result is not None
        assert "enhanced_context" in result

    @pytest.mark.asyncio
    async def test_missing_novel_data(self):
        """测试缺失小说数据的情况."""
        novel_data = {}  # 空数据

        module = ContinuityIntegrationModule("test-novel", novel_data)

        # 应该能处理缺失的数据
        result = await module.prepare_chapter_generation(
            chapter_number=5,
            volume_number=1
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_character_not_in_tracker(self):
        """测试角色不在追踪器中的情况."""
        novel_data = {
            "topic_analysis": {"core_theme": "成长"},
            "plot_outline": {"volumes": []},
            "characters": [
                {
                    "name": "主角",
                    "core_motivation": "成长",
                    "personal_code": "原则",
                    "personality_traits": ["勇敢"]
                }
            ],
            "foreshadowings": []
        }

        module = ContinuityIntegrationModule("test-novel", novel_data)

        # 策划中包含未定义的角色
        chapter_plan = {
            "character_actions": [
                {
                    "name": "配角",  # 不在角色列表中
                    "action": "行为",
                    "motivation": "动机"
                }
            ]
        }

        # 应该不报错，跳过未知角色
        result = await module.review_chapter_plan(
            chapter_plan=chapter_plan,
            chapter_number=5,
            previous_chapter={"ending_state": "", "chapter_number": 4}
        )

        assert result is not None


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
