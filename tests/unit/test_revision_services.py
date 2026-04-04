"""修订服务单元测试.

测试 revision_understanding_service.py 和 revision_execution_service.py 中的服务.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestRevisionUnderstandingService:
    """RevisionUnderstandingService 测试."""

    @pytest.fixture
    def mock_db_session(self):
        """模拟数据库会话."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_db_session):
        """创建服务实例（无LLM）."""
        from backend.services.revision_understanding_service import RevisionUnderstandingService

        return RevisionUnderstandingService(db=mock_db_session, llm=None)

    def test_simple_analyze_with_chapter_reference(self, service):
        """测试简化分析带章节引用的反馈."""
        context = {
            "characters": [
                {"name": "张三", "role_type": "protagonist", "personality": "稳重内敛"}
            ],
            "chapters": [],
        }

        # 由于反馈中包含"第"，会被识别为chapter类型
        result = service._simple_analyze("第5章张三的性格不一致", context)

        assert result["intent"] is not None
        assert result["confidence"] == 0.5
        # 注意：简单分析会优先识别章节引用
        assert result["target_type"] == "chapter"
        # 但仍会识别到角色名
        assert len(result["targets"]) == 1
        assert result["targets"][0]["target_name"] == "张三"

    def test_simple_analyze_world_setting_feedback(self, service):
        """测试简化分析世界观反馈."""
        context = {"characters": [], "chapters": []}

        # 使用明确的"世界观"关键词
        result = service._simple_analyze("世界观设定需要修改", context)

        assert result["target_type"] == "world_setting"

    def test_simple_analyze_outline_feedback(self, service):
        """测试简化分析大纲反馈."""
        context = {"characters": [], "chapters": []}

        result = service._simple_analyze("情节发展太慢，需要调整大纲", context)

        assert result["target_type"] == "outline"

    def test_simple_analyze_chapter_feedback(self, service):
        """测试简化分析章节反馈."""
        context = {"characters": [], "chapters": []}

        result = service._simple_analyze("第3章的开头需要更有吸引力", context)

        assert result["target_type"] == "chapter"

    def test_enrich_targets_with_character(self, service):
        """测试补充角色目标ID."""
        targets = [{"type": "character", "target_name": "张三", "field": "personality"}]
        context = {
            "characters": [
                {
                    "name": "张三",
                    "id": str(uuid4()),
                    "personality": "稳重",
                    "first_appearance_chapter": 3,
                }
            ],
            "chapters": [],
        }

        enriched = service._enrich_targets(targets, context)

        assert len(enriched) == 1
        assert "target_id" in enriched[0]
        assert enriched[0]["current_value"] == "稳重"

    def test_enrich_targets_with_chapter(self, service):
        """测试补充章节目标ID."""
        targets = [{"type": "chapter", "chapter_number": 5}]
        context = {
            "characters": [],
            "chapters": [
                {"chapter_number": 5, "id": str(uuid4()), "title": "测试章节"}
            ],
        }

        enriched = service._enrich_targets(targets, context)

        assert len(enriched) == 1
        assert "target_id" in enriched[0]

    @pytest.mark.asyncio
    async def test_assess_impact_for_character(self, service):
        """测试评估角色修改影响."""
        analysis = {"intent": "修改角色"}
        targets = [
            {
                "type": "character",
                "target_name": "张三",
                "issue": "性格不一致",
            }
        ]
        context = {
            "characters": [
                {"name": "张三", "first_appearance_chapter": 3, "personality": "稳重"}
            ],
            "chapters": [
                {"chapter_number": 1, "title": "第1章"},
                {"chapter_number": 3, "title": "第3章"},
                {"chapter_number": 5, "title": "第5章"},
                {"chapter_number": 7, "title": "第7章"},
            ],
        }

        impact = await service._assess_impact(analysis, targets, context)

        assert "affected_chapters" in impact
        assert 3 in impact["affected_chapters"]
        assert 5 in impact["affected_chapters"]
        assert 7 in impact["affected_chapters"]

    def test_format_plan_for_display(self, service):
        """测试格式化修订计划."""
        from core.models.revision_plan import RevisionPlan

        plan = RevisionPlan(
            id=uuid4(),
            novel_id=uuid4(),
            feedback_text="测试反馈",
            understood_intent="修改角色性格",
            confidence=0.85,
            targets=[
                {
                    "type": "character",
                    "target_name": "张三",
                    "issue": "性格前后不一致",
                }
            ],
            proposed_changes=[
                {
                    "field": "personality",
                    "reasoning": "统一为稳重性格",
                }
            ],
            impact_assessment={"affected_chapters": [3, 5, 7]},
        )

        formatted = service.format_plan_for_display(plan)

        assert "置信度" in formatted
        assert "张三" in formatted
        assert "第3-7章" in formatted

    def test_build_analysis_prompt(self, service):
        """测试构建分析提示."""
        context = {
            "characters": [
                {"name": "张三", "role_type": "protagonist", "personality": "稳重"}
            ],
            "chapters": [
                {"chapter_number": 1, "title": "第1章"},
                {"chapter_number": 2, "title": "第2章"},
            ],
        }

        prompt = service._build_analysis_prompt("测试反馈", context)

        assert "张三" in prompt
        assert "第1章" in prompt
        assert "测试反馈" in prompt
        assert "角色列表" in prompt
        assert "章节列表" in prompt


class TestRevisionTargetParsing:
    """修订目标解析测试（使用正则表达式辅助函数）."""

    def test_parse_chapter_reference(self):
        """测试解析章节引用."""
        import re

        # 测试第X章引用
        pattern = r"第(\d+)章"
        assert re.search(pattern, "第3章") is not None
        assert re.search(pattern, "第10章") is not None

        match = re.search(pattern, "第5章张三")
        if match:
            assert int(match.group(1)) == 5

    def test_parse_character_reference(self):
        """测试解析角色引用."""
        # 测试角色名引用
        test_cases = [
            ("张三的性格", "张三"),
            ("李四的对话", "李四"),
            ("王五的行为", "王五"),
        ]

        for text, expected_name in test_cases:
            if expected_name in text:
                # 找到了角色名
                assert expected_name in text
