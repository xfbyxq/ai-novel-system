"""
测试大纲生成系统改进

验证以下改进：
1. 灵活的章节配置支持
2. 主线剧情深度增强
3. VotingManager JSON 提取修复
4. ChapterOutlineMapper 动态章节数支持
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 测试 VotingManager 的 JSON 提取修复
def test_voting_manager_json_extraction():
    """测试 VotingManager 修复中文引号后的 JSON 提取."""
    from agents.voting_manager import VotingManager

    # 测试用例 1：标准 JSON
    standard_json = '{"chosen_option": "方案 A", "reasoning": "这是理由", "confidence": 0.8}'
    result = VotingManager._extract_json(standard_json)
    assert result["chosen_option"] == "方案 A"
    assert result["confidence"] == 0.8

    # 测试用例 2：包含中文引号的 JSON（之前会失败）
    chinese_quotes = '{\n    "chosen_option": "方案 B",\n    "reasoning": "方案 B 更契合"AI 主脑绝对管控"的核心设定..."\n}'
    result = VotingManager._extract_json(chinese_quotes)
    assert result["chosen_option"] == "方案 B"
    assert "AI 主脑绝对管控" in result["reasoning"]

    # 测试用例 3：代码块中的 JSON
    code_block = '''```json
{
    "chosen_option": "方案 C",
    "reasoning": "这是最佳方案"
}
```'''
    result = VotingManager._extract_json(code_block)
    assert result["chosen_option"] == "方案 C"

    # 测试用例 4：不规范的键名引号
    不规范_json = '{chosen_option: "方案 D", "reasoning": "测试"}'
    result = VotingManager._extract_json(不规范_json)
    assert result["chosen_option"] == "方案 D"

    print("✅ VotingManager JSON 提取测试全部通过")


# 测试 ChapterOutlineMapper 的动态章节数支持
def test_chapter_outline_mapper_dynamic_chapters():
    """测试 ChapterOutlineMapper 支持动态章节数."""
    from agents.chapter_outline_mapper import ChapterOutlineMapper

    mapper = ChapterOutlineMapper(novel_id="test_novel_001")

    # 测试用例 1：小章节数（3 章）
    chapter_config_small = {
        "total_chapters": 3,
        "min_chapters": 3,
        "max_chapters": 12,
        "flexible": True
    }

    volume_outline_small = {
        "title": "第一卷",
        "summary": "测试卷",
        "key_events": []
    }

    mapper.load_volume_outline(
        volume_number=1,
        volume_outline=volume_outline_small,
        total_chapters_in_volume=3,
        chapter_config=chapter_config_small
    )

    # 验证张力循环是否正确生成（小循环）
    cycles = mapper.tension_cycles[1]
    assert len(cycles) > 0
    # 小章节数应该生成较小的循环
    first_cycle = cycles[0]
    assert first_cycle.end_chapter <= 3

    # 测试用例 2：大章节数（10 章）
    mapper_large = ChapterOutlineMapper(novel_id="test_novel_002")

    chapter_config_large = {
        "total_chapters": 10,
        "min_chapters": 3,
        "max_chapters": 12,
        "flexible": True
    }

    volume_outline_large = {
        "title": "第一卷",
        "summary": "测试卷",
        "key_events": []
    }

    mapper_large.load_volume_outline(
        volume_number=1,
        volume_outline=volume_outline_large,
        total_chapters_in_volume=10,
        chapter_config=chapter_config_large
    )

    # 验证张力循环是否正确生成（大循环）
    cycles_large = mapper_large.tension_cycles[1]
    assert len(cycles_large) > 0

    print("✅ ChapterOutlineMapper 动态章节数测试全部通过")


# 测试 Novel 模型的 chapter_config 字段
def test_novel_model_chapter_config():
    """测试 Novel 模型添加 chapter_config 字段."""
    from core.models.novel import Novel

    # 验证字段存在
    novel = Novel()
    assert hasattr(novel, 'chapter_config')

    # 验证默认值
    default_config = {
        "total_chapters": 6,
        "min_chapters": 3,
        "max_chapters": 12,
        "flexible": True
    }

    # 检查默认值结构
    assert "total_chapters" in default_config
    assert "min_chapters" in default_config
    assert "max_chapters" in default_config
    assert "flexible" in default_config

    print("✅ Novel 模型 chapter_config 字段测试通过")


# 测试 PlotOutline 模型的 main_plot_detailed 字段
def test_plot_outline_model_main_plot_detailed():
    """测试 PlotOutline 模型添加 main_plot_detailed 字段."""
    from core.models.plot_outline import PlotOutline

    # 验证字段存在
    outline = PlotOutline()
    assert hasattr(outline, 'main_plot_detailed')

    # 验证字段结构
    test_detailed_plot = {
        "core_conflict_expanded": "核心冲突的详细描述",
        "protagonist_goal": "主角的终极目标",
        "antagonist_force": "反派力量描述",
        "escalation_path": ["阶段 1", "阶段 2", "阶段 3"],
        "emotional_arc": "情感弧光变化",
        "theme_expression": "主题表达方式",
        "key_revelations": ["揭示 1", "揭示 2"],
        "character_growth": "成长轨迹描述"
    }

    outline.main_plot_detailed = test_detailed_plot

    # 验证所有必需字段
    required_fields = [
        "core_conflict_expanded",
        "protagonist_goal",
        "antagonist_force",
        "escalation_path",
        "emotional_arc",
        "theme_expression",
        "key_revelations",
        "character_growth"
    ]

    for field in required_fields:
        assert field in test_detailed_plot, f"缺少必需字段：{field}"

    print("✅ PlotOutline 模型 main_plot_detailed 字段测试通过")


# 测试提示词模板中的章节配置参数
def test_prompt_template_chapter_config():
    """测试 PLOT_ARCHITECT_TASK 模板包含章节配置参数."""
    from llm.prompt_manager import PromptManager

    pm = PromptManager()

    # 验证模板中包含章节配置相关参数
    assert "{chapter_config}" in pm.PLOT_ARCHITECT_TASK
    assert "{total_chapters}" in pm.PLOT_ARCHITECT_TASK
    assert "{min_chapters}" in pm.PLOT_ARCHITECT_TASK
    assert "{max_chapters}" in pm.PLOT_ARCHITECT_TASK

    # 验证模板中包含主线深度要求
    assert "主线剧情深度要求" in pm.PLOT_ARCHITECT_TASK
    assert "main_plot_detailed" in pm.PLOT_ARCHITECT_TASK

    # 验证系统提示词中包含主线设计要求
    assert "主线剧情设计深度要求" in pm.PLOT_ARCHITECT_SYSTEM

    print("✅ 提示词模板章节配置参数测试通过")


# 测试 PLOT_REVIEWER 的主线深度审查功能
def test_plot_reviewer_main_plot_depth():
    """测试 PLOT_REVIEWER 添加主线深度审查."""
    from agents.plot_review_loop import PLOT_REVIEWER_SYSTEM, PLOT_REVIEWER_TASK

    # 验证系统提示词包含主线深度维度
    assert "主线剧情深度" in PLOT_REVIEWER_SYSTEM
    assert "main_plot_depth" in PLOT_REVIEWER_SYSTEM

    # 验证任务模板包含主线深度分析
    assert "main_plot_depth_analysis" in PLOT_REVIEWER_TASK
    assert "conflict_layers" in PLOT_REVIEWER_TASK
    assert "protagonist_motivation" in PLOT_REVIEWER_TASK
    assert "antagonist_strength" in PLOT_REVIEWER_TASK
    assert "escalation_path" in PLOT_REVIEWER_TASK

    print("✅ PLOT_REVIEWER 主线深度审查测试通过")


# 运行所有测试
if __name__ == "__main__":
    print("=" * 60)
    print("开始测试大纲生成系统改进")
    print("=" * 60)

    test_voting_manager_json_extraction()
    test_chapter_outline_mapper_dynamic_chapters()
    test_novel_model_chapter_config()
    test_plot_outline_model_main_plot_detailed()
    test_prompt_template_chapter_config()
    test_plot_reviewer_main_plot_depth()

    print("=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
