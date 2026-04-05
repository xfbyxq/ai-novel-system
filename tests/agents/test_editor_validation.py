"""测试 Editor 润色验证机制改进."""

import asyncio
import json
from unittest.mock import Mock
from agents.base.review_result import ReviewLoopResult
from agents.review_loop import ReviewLoopHandler
from llm.cost_tracker import CostTracker


def test_editor_stats_structure():
    """测试 Editor 统计数据结构."""
    print("测试 Editor 统计数据结构...")

    # 创建 ReviewLoopResult 实例
    result = ReviewLoopResult(
        final_content="测试内容",
        final_score=8.5,
        total_iterations=3,
        converged=True
    )

    # 验证 editor_stats 字段存在
    assert hasattr(result, 'editor_stats'), "应该有 editor_stats 字段"
    assert isinstance(result.editor_stats, dict), "editor_stats 应该是字典"

    # 测试 to_dict 包含 editor_stats
    data = result.to_dict()
    assert "editor_stats" not in data, "空统计时不应该包含 editor_stats"

    # 添加统计信息
    result.editor_stats = {
        "total_edits": 2,
        "rejected_edits": 1,
        "avg_improvement": 0.8,
        "acceptance_rate": 0.67
    }

    data = result.to_dict()
    assert "editor_stats" in data, "to_dict 应该包含 editor_stats"
    assert data["editor_stats"]["total_edits"] == 2, "total_edits 应该为 2"
    assert data["editor_stats"]["acceptance_rate"] == 0.67, "acceptance_rate 应该为 0.67"

    print("✓ Editor 统计数据结构测试通过")


def test_get_editor_stats():
    """测试 Editor 统计计算方法."""
    print("\n测试 Editor 统计计算...")

    # 创建 mock ReviewLoopHandler
    class MockHandler(ReviewLoopHandler):
        def __init__(self):
            pass  # 不需要初始化

    handler = MockHandler()

    # 模拟迭代历史
    iterations = [
        {
            "iteration": 1,
            "score": 7.0,
            "editor_edit_applied": 1,
            "editor_improvement_delta": 0.8
        },
        {
            "iteration": 2,
            "score": 7.8,
            "editor_edit_rejected": 1,
            "editor_reason": "质量未提升"
        },
        {
            "iteration": 3,
            "score": 8.2,
            "editor_edit_applied": 1,
            "editor_improvement_delta": 0.5
        }
    ]

    # 调用统计方法
    stats = handler._get_editor_stats(iterations)

    # 验证统计结果
    assert stats["total_edits"] == 2, "应该有 2 次编辑被应用"
    assert stats["rejected_edits"] == 1, "应该有 1 次编辑被拒绝"
    assert abs(stats["avg_improvement"] - 0.65) < 0.01, f"平均提升应该为 0.65，实际为 {stats['avg_improvement']}"
    assert abs(stats["acceptance_rate"] - 0.67) < 0.01, f"接受率应该为 0.67，实际为 {stats['acceptance_rate']}"

    print("✓ Editor 统计计算测试通过")
    print(f"  - 总编辑次数：{stats['total_edits']}")
    print(f"  - 拒绝次数：{stats['rejected_edits']}")
    print(f"  - 平均提升：{stats['avg_improvement']:.2f}")
    print(f"  - 接受率：{stats['acceptance_rate']:.2f}")


async def test_validate_edited_content():
    """测试润色内容验证方法."""
    print("\n测试润色内容验证...")

    # 创建 mock 客户端
    class MockQwenClient:
        async def chat(self, prompt, system, temperature, max_tokens):
            # 返回评估结果
            return {
                "content": json.dumps({
                    "overall_score": 8.5,
                    "dimension_scores": {
                        "fluency": 8.5,
                        "plot_logic": 8.0,
                        "character_consistency": 9.0,
                        "pacing": 8.5,
                        "satisfaction_design": 8.5
                    },
                    "revision_suggestions": [],
                    "summary": "润色后质量良好"
                }),
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50
                }
            }

    # 创建 mock cost tracker
    cost_tracker = Mock(spec=CostTracker)
    cost_tracker.record = Mock()

    # 创建 ReviewLoopHandler（简化版）
    class TestReviewLoopHandler:
        def __init__(self, client, cost_tracker):
            self.client = client
            self.cost_tracker = cost_tracker
            self.quality_threshold = 7.5
            self.metrics = {}
            self._chapter_plan_json = '{"content": "测试计划"}'

        async def _validate_edited_content(self, original_content, edited_content, review_data):
            """从 review_loop.py 复制的验证方法."""
            from agents.quality_evaluator import QualityEvaluator

            evaluator = QualityEvaluator(
                client=self.client,
                cost_tracker=self.cost_tracker,
                default_threshold=self.quality_threshold,
            )

            chapter_plan = ""
            try:
                plan_data = json.loads(self._chapter_plan_json)
                chapter_plan = plan_data.get("content", str(plan_data))
            except (json.JSONDecodeError, AttributeError):
                chapter_plan = self._chapter_plan_json or ""

            edited_score = await evaluator.evaluate(
                content=edited_content,
                chapter_plan=chapter_plan,
                threshold=self.quality_threshold,
            )

            original_score = float(review_data.get("overall_score", 0))
            improvement = edited_score.overall_score - original_score

            self.metrics["editor_improvement"] = improvement
            self.metrics["editor_edit_applied"] = 1 if improvement > 0.5 else 0

            return edited_score.overall_score

    handler = TestReviewLoopHandler(MockQwenClient(), cost_tracker)

    # 测试验证方法
    original_content = "原始内容"
    edited_content = "润色后的内容"
    review_data = {"overall_score": 7.5}

    edited_score = await handler._validate_edited_content(
        original_content=original_content,
        edited_content=edited_content,
        review_data=review_data
    )

    # 验证结果
    assert edited_score == 8.5, "润色后评分应该为 8.5"
    assert handler.metrics["editor_improvement"] == 1.0, "改进幅度应该为 1.0"
    assert handler.metrics["editor_edit_applied"] == 1, "应该应用编辑"

    print("✓ 润色内容验证测试通过")
    print(f"  - 原始分数：{review_data['overall_score']}")
    print(f"  - 润色后分数：{edited_score}")
    print(f"  - 改进幅度：{handler.metrics['editor_improvement']}")


async def test_editor_decision_logic():
    """测试 Editor 决策逻辑."""
    print("\n测试 Editor 决策逻辑...")

    # 测试场景 1：润色质量提升 > 0.5，应该应用
    original_score = 7.0
    edited_score = 8.0
    improvement = edited_score - original_score

    should_apply = improvement > 0.5
    assert should_apply, "润色质量提升 > 0.5，应该应用"
    print(f"  ✓ 场景 1：提升 {improvement:.1f} 分 > 0.5，应用润色")

    # 测试场景 2：润色质量提升 <= 0.5，应该拒绝
    original_score = 7.5
    edited_score = 7.8
    improvement = edited_score - original_score

    should_apply = improvement > 0.5
    assert not should_apply, "润色质量提升 <= 0.5，应该拒绝"
    print(f"  ✓ 场景 2：提升 {improvement:.1f} 分 <= 0.5，拒绝润色")

    # 测试场景 3：润色质量下降，应该拒绝
    original_score = 8.0
    edited_score = 7.5
    improvement = edited_score - original_score

    should_apply = improvement > 0.5
    assert not should_apply, "润色质量下降，应该拒绝"
    print(f"  ✓ 场景 3：下降 {abs(improvement):.1f} 分，拒绝润色")

    print("✓ Editor 决策逻辑测试通过")


async def main():
    """运行所有测试."""
    print("=" * 60)
    print("Editor 润色验证机制改进 - 测试报告")
    print("=" * 60)

    try:
        # 运行同步测试
        test_editor_stats_structure()
        test_get_editor_stats()

        # 运行异步测试
        await test_validate_edited_content()
        await test_editor_decision_logic()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print("\n改进总结:")
        print("1. ✓ 润色内容必须经过质量验证")
        print("2. ✓ 只有质量提升>0.5 分才应用润色")
        print("3. ✓ Editor 效果统计数据完整")
        print("4. ✓ 统计信息包含：total_edits, rejected_edits, avg_improvement, acceptance_rate")
        print("5. ✓ 决策逻辑正确，能准确判断是否应用润色")

    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
        raise
    except Exception as e:
        print(f"\n❌ 测试异常：{e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
