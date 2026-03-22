"""章节连贯性保障系统单元测试.

测试目标：
1. 验证所有模块可以正常导入
2. 测试约束推断功能
3. 测试上下文携带功能
4. 测试验证引擎功能
5. 测试完整的连贯性保障流程

使用 Mock 避免真实 LLM 调用.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agents import (
    ContinuityAssuranceIntegration,
    ConstraintInferenceEngine,
    ContextPropagator,
    ValidationEngine,
    ContinuityConstraint,
)


class TestContinuityConstraint:
    """ContinuityConstraint 数据模型测试."""

    def test_create_constraint_with_valid_data(self):
        """测试创建有效约束."""
        constraint = ContinuityConstraint(
            constraint_type="logical",
            description="需要揭示信的内容",
            priority=8,
            source_text="桌子上的那封信",
            validation_hint="检查是否描述了信的内容",
        )
        assert constraint.constraint_type == "logical"
        assert constraint.priority == 8
        assert constraint.confidence == 0.9

    def test_create_constraint_with_custom_confidence(self):
        """测试创建自定义置信度的约束."""
        constraint = ContinuityConstraint(
            constraint_type="narrative",
            description="需要回应对话",
            priority=7,
            source_text="你终于来了",
            validation_hint="检查对话回应",
            confidence=0.75,
        )
        assert constraint.confidence == 0.75

    def test_constraint_priority_validation(self):
        """测试优先级验证."""
        with pytest.raises(ValueError, match="Priority must be between 1 and 10"):
            ContinuityConstraint(
                constraint_type="logical",
                description="测试",
                priority=0,
                source_text="测试",
                validation_hint="测试",
            )

    def test_constraint_confidence_validation(self):
        """测试置信度验证."""
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            ContinuityConstraint(
                constraint_type="logical",
                description="测试",
                priority=5,
                source_text="测试",
                validation_hint="测试",
                confidence=1.5,
            )

    def test_constraint_to_dict(self):
        """测试转换为字典."""
        constraint = ContinuityConstraint(
            constraint_type="logical",
            description="测试约束",
            priority=8,
            source_text="源文本",
            validation_hint="验证提示",
        )
        result = constraint.to_dict()
        assert result["constraint_type"] == "logical"
        assert result["description"] == "测试约束"
        assert result["priority"] == 8
        assert "inferred_at" in result

    def test_constraint_from_dict(self):
        """测试从字典创建."""
        data = {
            "constraint_type": "narrative",
            "description": "从字典创建",
            "priority": 6,
            "source_text": "源文本",
            "validation_hint": "验证提示",
            "confidence": 0.8,
        }
        constraint = ContinuityConstraint.from_dict(data)
        assert constraint.constraint_type == "narrative"
        assert constraint.priority == 6
        assert constraint.confidence == 0.8


class TestConstraintInferenceEngine:
    """约束推断引擎测试."""

    @pytest.fixture
    def mock_client(self):
        """创建 Mock QwenClient."""
        mock = MagicMock()
        mock.chat = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_infer_constraints_returns_list(self, mock_client):
        """测试推断约束返回列表."""
        mock_response = {
            "content": json.dumps(
                {
                    "inferred_constraints": [
                        {
                            "type": "logical",
                            "description": "需要揭示信的内容",
                            "priority": 8,
                            "source_text": "桌子上的那封信",
                            "validation_hint": "检查是否描述了信的内容",
                        }
                    ]
                }
            ),
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_client.chat.return_value = mock_response

        engine = ConstraintInferenceEngine(mock_client)
        result = await engine.infer_constraints(
            previous_chapter_ending="测试文本",
            min_priority=5,
            max_constraints=5,
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].constraint_type == "logical"

    @pytest.mark.asyncio
    async def test_infer_constraints_filters_by_priority(self, mock_client):
        """测试按优先级过滤约束."""
        mock_response = {
            "content": json.dumps(
                {
                    "inferred_constraints": [
                        {
                            "type": "logical",
                            "description": "高优先级",
                            "priority": 8,
                            "source_text": "源",
                            "validation_hint": "提示",
                        },
                        {
                            "type": "narrative",
                            "description": "低优先级",
                            "priority": 3,
                            "source_text": "源",
                            "validation_hint": "提示",
                        },
                    ]
                }
            ),
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_client.chat.return_value = mock_response

        engine = ConstraintInferenceEngine(mock_client)
        result = await engine.infer_constraints(
            previous_chapter_ending="测试文本",
            min_priority=5,
            max_constraints=5,
        )

        assert len(result) == 1
        assert result[0].priority == 8

    @pytest.mark.asyncio
    async def test_infer_constraints_empty_response(self, mock_client):
        """测试空响应处理."""
        mock_response = {
            "content": json.dumps({"inferred_constraints": []}),
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_client.chat.return_value = mock_response

        engine = ConstraintInferenceEngine(mock_client)
        result = await engine.infer_constraints(
            previous_chapter_ending="测试文本",
        )

        assert isinstance(result, list)
        assert len(result) == 0


class TestContextPropagator:
    """上下文携带器测试."""

    def test_build_enhanced_prompt_contains_outline(self):
        """测试增强提示词包含大纲."""
        propagator = ContextPropagator()
        constraints = [
            ContinuityConstraint(
                constraint_type="logical",
                description="需要揭示信的内容",
                priority=8,
                source_text="桌子上的那封信",
                validation_hint="检查信的内容",
            )
        ]

        result = propagator.build_enhanced_prompt(
            next_chapter_outline="林默与神秘人对话",
            constraints=constraints,
        )

        assert "林默与神秘人对话" in result

    def test_build_enhanced_prompt_contains_guidance(self):
        """测试增强提示词包含创作指导."""
        propagator = ContextPropagator()
        constraints = [
            ContinuityConstraint(
                constraint_type="logical",
                description="需要揭示信的内容",
                priority=8,
                source_text="桌子上的那封信",
                validation_hint="检查信的内容",
            )
        ]

        result = propagator.build_enhanced_prompt(
            next_chapter_outline="测试大纲",
            constraints=constraints,
        )

        assert "读者期待" in result or "期待" in result

    def test_build_enhanced_prompt_empty_constraints(self):
        """测试空约束列表."""
        propagator = ContextPropagator()

        result = propagator.build_enhanced_prompt(
            next_chapter_outline="测试大纲",
            constraints=[],
        )

        assert "测试大纲" in result

    def test_create_minimal_guidance(self):
        """测试创建最小化指导."""
        propagator = ContextPropagator()
        constraints = [
            ContinuityConstraint(
                constraint_type="logical",
                description="约束1",
                priority=9,
                source_text="源",
                validation_hint="提示",
            ),
            ContinuityConstraint(
                constraint_type="narrative",
                description="约束2",
                priority=7,
                source_text="源",
                validation_hint="提示",
            ),
            ContinuityConstraint(
                constraint_type="emotional",
                description="约束3",
                priority=5,
                source_text="源",
                validation_hint="提示",
            ),
        ]

        result = propagator.create_minimal_guidance(constraints, max_items=2)

        assert "约束1" in result or "约束2" in result
        assert "约束3" not in result

    def test_constraint_to_expectation(self):
        """测试约束转换为读者期待."""
        propagator = ContextPropagator()
        constraint = ContinuityConstraint(
            constraint_type="logical",
            description="需要揭示信的内容",
            priority=8,
            source_text="桌子上的那封信",
            validation_hint="检查信的内容",
        )

        result = propagator._constraint_to_expectation(constraint)

        assert isinstance(result, str)
        assert len(result) > 0


class TestValidationEngine:
    """验证引擎测试."""

    @pytest.fixture
    def mock_client(self):
        """创建 Mock QwenClient."""
        mock = MagicMock()
        mock.chat = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_validate_returns_report(self, mock_client):
        """测试验证返回报告."""
        mock_response = {
            "content": json.dumps(
                {
                    "overall_assessment": "通过",
                    "satisfied_constraints": [{"constraint": "测试", "how_satisfied": "满足"}],
                    "unsatisfied_constraints": [],
                    "artistic_breaking": [],
                    "quality_score": 85,
                }
            ),
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_client.chat.return_value = mock_response

        engine = ValidationEngine(mock_client)
        constraints = [
            ContinuityConstraint(
                constraint_type="logical",
                description="测试",
                priority=8,
                source_text="源",
                validation_hint="提示",
            )
        ]

        result = await engine.validate(
            previous_ending="上一章结尾",
            new_chapter_beginning="下一章开头",
            constraints=constraints,
        )

        assert result.overall_assessment == "通过"
        assert result.quality_score == 85

    @pytest.mark.asyncio
    async def test_validate_needs_regeneration(self, mock_client):
        """测试验证需要重新生成."""
        mock_response = {
            "content": json.dumps(
                {
                    "overall_assessment": "严重问题",
                    "satisfied_constraints": [],
                    "unsatisfied_constraints": [
                        {
                            "constraint": "测试",
                            "why_unsatisfied": "未满足",
                            "severity": "high",
                            "suggestion": "改进",
                        }
                    ],
                    "artistic_breaking": [],
                    "quality_score": 40,
                }
            ),
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_client.chat.return_value = mock_response

        engine = ValidationEngine(mock_client)
        constraints = [
            ContinuityConstraint(
                constraint_type="logical",
                description="测试",
                priority=8,
                source_text="源",
                validation_hint="提示",
            )
        ]

        result = await engine.validate(
            previous_ending="上一章结尾",
            new_chapter_beginning="下一章开头",
            constraints=constraints,
        )

        assert result.needs_regeneration is True


class TestContinuityAssuranceIntegration:
    """连贯性保障集成器测试."""

    @pytest.fixture
    def mock_client(self):
        """创建 Mock QwenClient."""
        mock = MagicMock()
        mock.chat = AsyncMock(
            return_value={
                "content": json.dumps(
                    {
                        "inferred_constraints": [
                            {
                                "type": "logical",
                                "description": "测试约束",
                                "priority": 8,
                                "source_text": "源",
                                "validation_hint": "提示",
                            }
                        ]
                    }
                ),
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            }
        )
        return mock

    @pytest.mark.asyncio
    async def test_enforce_continuity_returns_dict(self, mock_client):
        """测试强制执行连贯性返回字典."""
        integrator = ContinuityAssuranceIntegration(mock_client)

        async def mock_generate(prompt: str) -> str:
            return "生成的章节内容。"

        result = await integrator.enforce_continuity(
            novel_id=uuid4(),
            chapter_number=2,
            previous_chapter_content="上一章内容。",
            next_chapter_outline="下一章大纲。",
            generation_callback=mock_generate,
        )

        assert "content" in result
        assert "transition_record" in result
        assert "quality_score" in result

    @pytest.mark.asyncio
    async def test_extract_ending(self):
        """测试提取章节结尾."""
        integrator = ContinuityAssuranceIntegration()

        content = "这是章节内容。" + "。" * 50 + "这是结尾部分。"
        result = integrator._extract_ending(content, max_length=100)

        assert isinstance(result, str)
        assert len(result) <= 120

    @pytest.mark.asyncio
    async def test_extract_ending_empty_content(self):
        """测试提取空内容结尾."""
        integrator = ContinuityAssuranceIntegration()
        result = integrator._extract_ending("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_beginning(self):
        """测试提取章节开头."""
        integrator = ContinuityAssuranceIntegration()
        content = "这是开头。" * 50 + "这是结尾。"
        result = integrator._extract_beginning(content, max_length=50)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_add_improvement_suggestions(self):
        """测试添加改进建议."""
        integrator = ContinuityAssuranceIntegration()

        original = "原始提示词。"
        suggestions = ["建议1", "建议2"]

        result = integrator._add_improvement_suggestions(original, suggestions)

        assert "建议1" in result
        assert "建议2" in result
        assert "原始提示词" in result

    @pytest.mark.asyncio
    async def test_create_transition_record(self):
        """测试创建过渡记录."""
        from agents.continuity_models import ValidationReport

        integrator = ContinuityAssuranceIntegration()

        report = ValidationReport(
            overall_assessment="通过",
            quality_score=85,
            satisfied_constraints=[],
            unsatisfied_constraints=[],
            artistic_breaking=[],
        )

        result = integrator._create_transition_record(
            novel_id="test-novel",
            from_chapter=1,
            to_chapter=2,
            inferred_constraints=[],
            validation_report=report,
            final_content="生成的内容。",
            regeneration_count=0,
        )

        assert result.novel_id == "test-novel"
        assert result.from_chapter == 1
        assert result.to_chapter == 2


class TestContinuityModels:
    """连贯性模型单元测试."""

    def test_validation_report_creation(self):
        """测试创建验证报告."""
        from agents.continuity_models import ValidationReport

        report = ValidationReport(
            overall_assessment="通过",
            quality_score=85,
        )

        assert report.overall_assessment == "通过"
        assert report.quality_score == 85
        assert report.needs_regeneration is False

    def test_validation_report_auto_regeneration(self):
        """测试验证报告自动设置重新生成标志."""
        from agents.continuity_models import ValidationReport

        report = ValidationReport(
            overall_assessment="严重问题",
            quality_score=40,
        )

        assert report.needs_regeneration is True

    def test_chapter_transition_decision_validation(self):
        """测试章节过渡决策验证."""
        from agents.continuity_models import ChapterTransition, ValidationReport

        with pytest.raises(ValueError, match="Invalid decision"):
            ChapterTransition(
                novel_id="test",
                from_chapter=1,
                to_chapter=2,
                inferred_constraints=[],
                validation_report=ValidationReport(overall_assessment="通过", quality_score=80),
                final_decision="无效决策",
            )

    def test_chapter_transition_valid_decisions(self):
        """测试有效的过渡决策."""
        from agents.continuity_models import ChapterTransition, ValidationReport

        for decision in ["直接采用", "修改后采用", "重新生成"]:
            transition = ChapterTransition(
                novel_id="test",
                from_chapter=1,
                to_chapter=2,
                inferred_constraints=[],
                validation_report=ValidationReport(overall_assessment="通过", quality_score=80),
                final_decision=decision,
            )
            assert transition.final_decision == decision

    def test_validation_report_to_dict(self):
        """测试验证报告转字典."""
        from agents.continuity_models import ValidationReport

        report = ValidationReport(
            overall_assessment="通过",
            quality_score=85,
            suggestions=["建议1"],
        )

        result = report.to_dict()

        assert result["overall_assessment"] == "通过"
        assert result["quality_score"] == 85
        assert "建议1" in result["suggestions"]

    def test_chapter_transition_to_dict(self):
        """测试章节过渡转字典."""
        from agents.continuity_models import ChapterTransition, ValidationReport

        transition = ChapterTransition(
            novel_id="test-novel",
            from_chapter=1,
            to_chapter=2,
            inferred_constraints=[],
            validation_report=ValidationReport(overall_assessment="通过", quality_score=85),
            final_decision="直接采用",
        )

        result = transition.to_dict()

        assert result["novel_id"] == "test-novel"
        assert result["final_decision"] == "直接采用"
        assert "created_at" in result
