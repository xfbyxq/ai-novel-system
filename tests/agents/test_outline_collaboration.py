"""
大纲协作完善功能测试用例
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List

from agents.outline_refiner import OutlineRefiner
from agents.outline_quality_evaluator import OutlineQualityEvaluator, OutlineQualityScore
from agents.outline_iteration_controller import OutlineIterationController
from agents.crew_manager import NovelCrewManager

class TestOutlineRefiner:
    """测试大纲细化器的协作完善功能."""

    @pytest.fixture
    def sample_outline(self) -> Dict[str, Any]:
        """提供样本大纲数据."""
        return {
            "structure_type": "三幕式",
            "main_plot": {
                "setup": "主角苏晴穿越到修仙世界",
                "conflict": "发现自己没有灵根，无法修炼",
                "climax": "意外获得上古传承，开启逆天之路",
                "resolution": "成为一代宗师，拯救苍生"
            },
            "volumes": [
                {
                    "number": 1,
                    "title": "初入仙途",
                    "chapters": [1, 20],
                    "summary": "苏晴穿越到修仙世界，发现自己没有灵根",
                    "core_conflict": "无法修炼的困境",
                    "tension_cycles": [
                        {
                            "chapters": [1, 7],
                            "suppress_events": ["被同门嘲笑", "测试无灵根"],
                            "release_event": "意外觉醒特殊体质"
                        }
                    ],
                    "key_events": [
                        {"chapter": 5, "event": "获得神秘玉佩", "impact": "开启修炼之门"}
                    ]
                }
            ],
            "key_turning_points": [
                {"chapter": 5, "event": "获得玉佩", "impact": "命运转折"},
                {"chapter": 15, "event": "拜入宗门", "impact": "正式踏上修仙路"}
            ],
            "climax_chapter": 45
        }

    @pytest.fixture
    def sample_world_setting(self) -> Dict[str, Any]:
        """提供样本世界观设定."""
        return {
            "world_name": "天玄大陆",
            "world_type": "东方玄幻",
            "power_system": {
                "name": "灵力修炼体系",
                "levels": ["练气", "筑基", "金丹", "元婴", "化神"],
                "special_mechanics": ["灵根", "体质", "功法"]
            },
            "factions": [
                {"name": "青云宗", "type": "正道", "power": "强大"},
                {"name": "血魔教", "type": "魔道", "power": "邪恶"}
            ],
            "geography": {
                "main_regions": ["东荒", "西漠", "南疆", "北原"],
                "special_places": ["万妖山", "幽冥海"]
            }
        }

    @pytest.fixture
    def sample_characters(self) -> List[Dict[str, Any]]:
        """提供样本角色数据."""
        return [
            {
                "name": "苏晴",
                "role": "主角",
                "importance": "main",
                "background": "现代大学生穿越者",
                "motivations": ["寻找回家之路", "变强保护自己"],
                "abilities": ["特殊体质", "现代知识"],
                "relationships": {"师父": "青云宗长老"}
            },
            {
                "name": "林逸",
                "role": "男配",
                "importance": "supporting",
                "background": "青云宗天才弟子",
                "motivations": ["追求武道巅峰"],
                "abilities": ["剑道天赋"],
                "relationships": {"师兄": "苏晴"}
            }
        ]

    @pytest.mark.asyncio
    async def test_enhance_outline_with_agent_collaboration(
        self,
        sample_outline: Dict[str, Any],
        sample_world_setting: Dict[str, Any],
        sample_characters: List[Dict[str, Any]]
    ):
        """测试基于Agent协作的大纲完善功能."""
        # 创建mock对象
        mock_client = Mock()
        mock_cost_tracker = Mock()
        mock_crew_manager = Mock()
        mock_team_context = Mock()

        # 配置mock返回值
        mock_review_result = Mock()
        mock_review_result.to_dict.return_value = {"score": 7.5}
        mock_crew_manager.plot_review_handler.execute.return_value = mock_review_result

        # 创建大纲协调器
        refiner = OutlineRefiner(client=mock_client, cost_tracker=mock_cost_tracker)

        # 执行测试
        result = await refiner.enhance_outline_with_agent_collaboration(
            initial_outline=sample_outline,
            world_setting=sample_world_setting,
            characters=sample_characters,
            crew_manager=mock_crew_manager,
            team_context=mock_team_context
        )

        # 验证结果
        assert "original_outline" in result
        assert "enhanced_outline" in result
        assert "consistency_report" in result
        assert "quality_report" in result

        # 验证mock调用次数（由于迭代优化可能会多次调用）
        assert mock_crew_manager.plot_review_handler.execute.call_count >= 1

class TestOutlineQualityEvaluator:
    """测试大纲质量评估器."""

    @pytest.mark.asyncio
    async def test_evaluate_outline_comprehensively(self):
        """测试综合大纲质量评估."""
        # 创建评估器
        evaluator = OutlineQualityEvaluator()

        # 准备测试数据
        outline = {
            "main_plot": {"setup": "开始", "conflict": "冲突", "climax": "高潮", "resolution": "结局"},
            "volumes": [
                {"number": 1, "title": "第一卷", "chapters": [1, 20]},
                {"number": 2, "title": "第二卷", "chapters": [21, 40]}
            ],
            "key_turning_points": [
                {"chapter": 10, "event": "转折1"},
                {"chapter": 30, "event": "转折2"}
            ]
        }

        world_setting = {
            "power_system": {"name": "修仙体系"},
            "factions": [{"name": "青云宗"}]
        }

        characters = [
            {"name": "主角", "importance": "main"},
            {"name": "配角", "importance": "supporting"}
        ]

        # 执行评估
        result = await evaluator.evaluate_outline_comprehensively(outline, world_setting, characters)

        # 验证结果类型
        assert isinstance(result, OutlineQualityScore)
        assert isinstance(result.overall_score, float)
        assert isinstance(result.dimension_scores, dict)
        assert isinstance(result.strengths, list)
        assert isinstance(result.weaknesses, list)
        assert isinstance(result.improvement_suggestions, list)

        # 验证评分范围
        assert 1.0 <= result.overall_score <= 10.0
        for score in result.dimension_scores.values():
            assert 1.0 <= score <= 10.0

class TestOutlineIterationController:
    """测试大纲迭代控制器."""

    def test_should_continue_basic_conditions(self):
        """测试基本继续条件."""
        controller = OutlineIterationController(
            quality_threshold=8.0,
            consistency_threshold=8.5,
            max_iterations=3
        )

        # 测试质量不达标应该继续
        assert controller.should_continue(quality_score=7.0, consistency_score=8.0) == True

        # 测试一致性不达标应该继续
        assert controller.should_continue(quality_score=8.5, consistency_score=8.0) == True

        # 测试都达标应该停止
        assert controller.should_continue(quality_score=8.5, consistency_score=9.0) == False

        # 测试超过最大迭代次数应该停止
        controller.current_iteration = 3
        assert controller.should_continue(quality_score=7.0, consistency_score=7.0) == False

    @pytest.mark.asyncio
    async def test_optimize_outline_iteratively(self):
        """测试迭代优化流程."""
        controller = OutlineIterationController(max_iterations=2)

        # 创建mock对象
        mock_quality_evaluator = AsyncMock()
        mock_consistency_checker = AsyncMock()

        # 配置mock返回值
        mock_quality_result = Mock()
        mock_quality_result.overall_score = 7.5
        mock_quality_result.weaknesses = ["结构需要完善"]
        mock_quality_evaluator.evaluate_outline_comprehensively.return_value = mock_quality_result

        mock_consistency_result = {"consistency_score": 7.0}
        mock_consistency_checker.check_outline_consistency.return_value = mock_consistency_result

        initial_outline = {"main_plot": "初始大纲"}
        world_setting = {}
        characters = []

        # 执行优化
        result = await controller.optimize_outline_iteratively(
            initial_outline=initial_outline,
            quality_evaluator=mock_quality_evaluator,
            consistency_checker=mock_consistency_checker,
            world_setting=world_setting,
            characters=characters
        )

        # 验证结果
        assert "optimized_outline" in result
        assert "optimization_summary" in result
        assert "iteration_history" in result
        assert result["process_completed"] == True

class TestCrewManagerIntegration:
    """测试CrewManager集成."""

    @pytest.mark.asyncio
    async def test_run_outline_enhancement_phase(self):
        """测试大纲完善阶段执行."""
        # 创建mock对象
        mock_client = Mock()
        mock_cost_tracker = Mock()
        mock_team_context = Mock()

        crew_manager = NovelCrewManager(
            qwen_client=mock_client,
            cost_tracker=mock_cost_tracker
        )

        # 准备测试数据
        novel_data = {
            "novel_id": "test-novel-123",
            "novel_title": "测试小说",
            "world_setting": {"name": "测试世界"},
            "characters": [{"name": "测试角色"}]
        }

        initial_outline = {"main_plot": "测试大纲"}

        # 执行测试
        with patch.object(crew_manager, '_setup_team_context') as mock_setup:
            with patch.object(crew_manager, '_perform_comprehensive_consistency_check') as mock_check:
                with patch.object(crew_manager, '_run_outline_refinement_loop') as mock_refine:
                    with patch.object(crew_manager, '_generate_enhancement_report') as mock_report:

                        # 配置mock返回值
                        mock_check.return_value = {"consistency_score": 8.0}
                        mock_refine.return_value = {"enhanced": "大纲"}
                        mock_report.return_value = {"final_score": 8.5}

                        result = await crew_manager.run_outline_enhancement_phase(
                            novel_data=novel_data,
                            initial_outline=initial_outline,
                            team_context=mock_team_context
                        )

                        # 验证结果
                        assert "enhancement_result" in result
                        assert "team_context" in result
                        assert "process_log" in result

                        # 验证mock调用
                        mock_setup.assert_called_once()
                        mock_check.assert_called_once()
                        mock_refine.assert_called_once()
                        mock_report.assert_called_once()

# 集成测试
class TestFullWorkflow:
    """完整的端到端工作流测试."""

    @pytest.mark.asyncio
    async def test_complete_outline_enhancement_workflow(self):
        """测试完整的大纲完善工作流."""
        # 这是一个高层次的集成测试，验证所有组件协同工作

        # 准备测试数据
        outline = {
            "structure_type": "三幕式",
            "main_plot": {
                "setup": "平凡少年获得神秘传承",
                "conflict": "面对各方势力追杀",
                "climax": "最终决战反派BOSS",
                "resolution": "重建秩序，成就传奇"
            },
            "volumes": [
                {
                    "number": 1,
                    "title": "觉醒之路",
                    "chapters": [1, 30]
                }
            ]
        }

        world_setting = {
            "world_name": "玄天大陆",
            "power_system": {"name": "灵气修炼"},
            "factions": [{"name": "天剑宗"}]
        }

        characters = [
            {"name": "李明", "importance": "main", "role": "主角"},
            {"name": "王芳", "importance": "supporting", "role": "女配"}
        ]

        novel_data = {
            "novel_id": "integration-test-001",
            "novel_title": "玄天传说",
            "world_setting": world_setting,
            "characters": characters
        }

        # 创建mock组件
        mock_client = Mock()
        mock_cost_tracker = Mock()
        mock_team_context = Mock()

        crew_manager = NovelCrewManager(mock_client, mock_cost_tracker)

        # 执行完整流程
        result = await crew_manager.run_outline_enhancement_phase(
            novel_data=novel_data,
            initial_outline=outline,
            team_context=mock_team_context
        )

        # 基本验证
        assert result is not None
        assert "enhancement_result" in result
        assert isinstance(result["enhancement_result"], dict)

if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])