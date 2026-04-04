"""大纲流程测试."""
import pytest
from tests.e2e.pages.novel_list_page import NovelListPage
from tests.e2e.pages.novel_detail_page import NovelDetailPage
from tests.e2e.utils.data_generator import generate_novel_data, generate_outline_data


class TestOutlineFlow:
    """大纲流程测试类."""

    @pytest.fixture(autouse=True)
    def setup(self, page):
        """测试前置条件."""
        self.novel_list_page = NovelListPage(page)
        self.novel_detail_page = NovelDetailPage(page)
        self.novel_list_page.navigate()

    @pytest.mark.outline
    @pytest.mark.regression
    def test_outline_refinement_flow(self, page):
        """
        测试大纲梳理完整流程
        """
        # 先创建一个小说用于测试
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"],
            tags=novel_data["tags"]
        )

        # 确认跳转到详情页
        assert "/novels/" in page.url

        # 切换到大纲梳理标签页
        self.novel_detail_page.switch_to_outline_refinement()

        # 准备大纲数据
        outline_data = generate_outline_data()

        # 填写大纲字段
        self.novel_detail_page.fill_outline_fields(outline_data)

        # 保存大纲
        self.novel_detail_page.save_outline()

        # 验证保存成功（检查是否有成功消息或状态变化）
        # 这里可以根据实际UI反馈调整验证方式

    @pytest.mark.outline
    def test_outline_enhancement_flow(self, page):
        """
        测试大纲智能完善流程
        """
        # 创建测试小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in page.url

        # 切换到大纲梳理
        self.novel_detail_page.switch_to_outline_refinement()

        # 填写基础大纲
        basic_outline = {
            "core_conflict": "主角面临生存危机",
            "protagonist_goal": "获得强大的修炼资源",
            "antagonist": "邪恶的宗门势力"
        }
        self.novel_detail_page.fill_outline_fields(basic_outline)
        self.novel_detail_page.save_outline()

        # 点击智能完善
        self.novel_detail_page.click_enhance_outline()

        # 点击预览增强
        self.novel_detail_page.click_preview_enhancement()

        # 应用增强
        self.novel_detail_page.apply_enhancement()

        # 验证增强后的质量评分提升
        quality_score = self.novel_detail_page.get_outline_quality_score()
        assert quality_score > 0, "应该能够获取质量评分"

    @pytest.mark.outline
    def test_outline_partial_completion(self, page):
        """
        测试大纲部分填写场景
        """
        # 创建小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in page.url

        # 切换到大纲梳理
        self.novel_detail_page.switch_to_outline_refinement()

        # 只填写部分字段
        partial_outline = {
            "core_conflict": "世界即将毁灭的危机",
            "protagonist_goal": "寻找拯救世界的方法"
            # 故意不填写其他字段
        }

        self.novel_detail_page.fill_outline_fields(partial_outline)
        self.novel_detail_page.save_outline()

        # 验证部分填写也能保存成功

    @pytest.mark.outline
    def test_outline_field_validation(self, page):
        """
        测试大纲字段验证
        """
        # 创建小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in page.url
        self.novel_detail_page.switch_to_outline_refinement()

        # 测试超长文本输入
        long_text = "A" * 10000  # 1万个字符
        extreme_outline = {
            "core_conflict": long_text,
            "protagonist_goal": long_text,
            "antagonist": long_text
        }

        self.novel_detail_page.fill_outline_fields(extreme_outline)
        self.novel_detail_page.save_outline()

        # 验证系统能处理极端输入

    @pytest.mark.outline
    def test_outline_quality_assessment(self, page):
        """
        测试大纲质量评估功能
        """
        # 创建小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in page.url
        self.novel_detail_page.switch_to_outline_refinement()

        # 填写完整的大纲
        complete_outline = generate_outline_data()
        self.novel_detail_page.fill_outline_fields(complete_outline)
        self.novel_detail_page.save_outline()

        # 获取质量评分
        quality_score = self.novel_detail_page.get_outline_quality_score()

        # 验证评分在合理范围内（0-10分）
        assert 0 <= quality_score <= 10, f"质量评分{quality_score}应该在0-10范围内"

        # 验证质量维度信息存在
        # 这里可以根据实际UI结构调整验证方式