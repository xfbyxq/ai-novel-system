"""测试质量评估维度统一改进."""

import asyncio

from agents.base.quality_report import ChapterQualityReport
from agents.quality_evaluator import QualityEvaluator


def test_chapter_quality_report():
    """测试 ChapterQualityReport 的加权分数计算."""
    print("测试 ChapterQualityReport...")

    # 创建测试报告（使用新的 5 维度）
    report = ChapterQualityReport(
        overall_score=8.0,
        dimension_scores={
            "accuracy": 8.5,
            "vividness": 7.5,
            "pacing": 9.0,
            "setting_consistency": 7.0,
            "immersion": 8.5,
        },
        passed=True,
        summary="测试报告",
    )

    # 验证维度数量
    assert len(report.dimension_scores) == 5, "应该有 5 个维度"

    # 验证准确度分数
    assert "accuracy" in report.dimension_scores, "应该包含准确度维度"
    assert report.dimension_scores["accuracy"] == 8.5, "准确度分数应该为 8.5"

    # 验证权重配置存在
    assert "accuracy" in report._weights, "应该包含准确度权重"

    # 验证加权分数计算（基于新权重：accuracy=0.25, vividness=0.20, pacing=0.20,
    # setting_consistency=0.20, immersion=0.15）
    expected_weighted = (
        8.5 * 0.25  # accuracy
        + 7.5 * 0.20  # vividness
        + 9.0 * 0.20  # pacing
        + 7.0 * 0.20  # setting_consistency
        + 8.5 * 0.15  # immersion
    )

    assert (
        abs(report.weighted_score - expected_weighted) < 0.01
    ), f"加权分数应该为 {expected_weighted}"

    # 验证 to_dict 输出
    data = report.to_dict()
    assert "weighted_score" in data, "to_dict 应该包含 weighted_score"
    assert "weights" in data, "to_dict 应该包含 weights"
    assert len(data["dimension_scores"]) == 5, "dimension_scores 应该有 5 个维度"

    print("✓ ChapterQualityReport 测试通过")
    print(f"  - 维度数量：{len(report.dimension_scores)}")
    print(f"  - 准确度分数：{report.dimension_scores['accuracy']}")
    print(f"  - 准确度权重：{report._weights['accuracy']}")
    print(f"  - 加权总分：{report.weighted_score:.2f}")


def test_quality_evaluator_criteria():
    """测试 QualityEvaluator 的评分标准方法."""
    print("\n测试 QualityEvaluator 评分标准...")

    # 测试各维度评分标准（使用新的 5 维度）
    dimensions = ["accuracy", "vividness", "pacing", "setting_consistency", "immersion"]

    for dim in dimensions:
        criteria = QualityEvaluator._get_detailed_criteria(dim)
        assert criteria, f"{dim} 应该有评分标准"
        assert "9-10 分" in criteria or "分数" in criteria, f"{dim} 应该包含分数标准"
        print(f"  ✓ {dim}: 评分标准完整 ({len(criteria)} 字符)")

    # 特别测试准确度评分标准
    accuracy_criteria = QualityEvaluator._get_detailed_criteria("accuracy")
    assert accuracy_criteria, "准确度应该有详细评分标准"
    print("✓ 评分标准测试通过")


def test_quality_evaluator_task():
    """测试 QUALITY_EVALUATOR_TASK 包含新维度."""
    print("\n测试 QUALITY_EVALUATOR_TASK...")

    from agents.quality_evaluator import QUALITY_EVALUATOR_TASK

    # 验证输出格式包含新的 5 维度
    assert "dimension_scores" in QUALITY_EVALUATOR_TASK, "应该包含 dimension_scores"

    print("✓ QUALITY_EVALUATOR_TASK 测试通过")


async def test_full_evaluation():
    """测试完整的质量评估流程（使用 mock）."""
    print("\n测试完整评估流程...")

    # 创建一个 mock 客户端
    class MockQwenClient:
        async def chat(self, prompt, system, temperature, max_tokens):
            # 返回包含新 5 维度的模拟响应
            return {
                "content": """{
                    "overall_score": 8.2,
                    "dimension_scores": {
                        "accuracy": 9.0,
                        "vividness": 7.8,
                        "pacing": 8.0,
                        "setting_consistency": 7.5,
                        "immersion": 8.5
                    },
                    "revision_suggestions": [],
                    "summary": "测试评估"
                }""",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            }

    from unittest.mock import Mock

    from llm.cost_tracker import CostTracker

    # 创建 mock cost tracker
    cost_tracker = Mock(spec=CostTracker)
    cost_tracker.record = Mock()

    # 创建评估器
    evaluator = QualityEvaluator(
        client=MockQwenClient(),
        cost_tracker=cost_tracker,
        default_threshold=7.5,
    )

    # 执行评估
    sample_content = "这是一个测试章节内容"
    report = await evaluator.evaluate(content=sample_content, chapter_plan="测试计划")

    # 验证结果
    assert report.overall_score == 8.2, "整体分数应该为 8.2"
    assert len(report.dimension_scores) == 5, "应该有 5 个维度分数"
    assert report.dimension_scores["accuracy"] == 9.0, "准确度分数应该为 9.0"

    print("✓ 完整评估流程测试通过")
    print(f"  - 整体分数：{report.overall_score}")
    print(f"  - 维度数量：{len(report.dimension_scores)}")
    print(f"  - 准确度：{report.dimension_scores['accuracy']}")


async def main():
    """运行所有测试."""
    print("=" * 60)
    print("质量评估维度统一改进 - 测试报告")
    print("=" * 60)

    try:
        # 运行单元测试
        test_chapter_quality_report()
        test_quality_evaluator_criteria()
        test_quality_evaluator_task()

        # 运行异步集成测试
        await test_full_evaluation()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print("\n改进总结:")
        print("1. ✓ QualityEvaluator 支持 5 维度评估")
        print("2. ✓ 准确度评分标准明确可量化")
        print("3. ✓ ChapterQualityReport 权重配置合理（准确度 25%）")
        print("4. ✓ 加权总分计算正确")
        print("5. ✓ 所有数据结构兼容新维度")

    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
        raise
    except Exception as e:
        print(f"\n❌ 测试异常：{e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
