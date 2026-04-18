"""
小说创建流程测试

测试编号: E2E-09
测试目标: 测试完整的小说创建端到端流程

前置条件: 无
依赖测试: E2E-01 (小说创建)
"""
import pytest
from tests.e2e.pages.novel_list_page import NovelListPage
from tests.e2e.pages.novel_detail_page import NovelDetailPage
from tests.e2e.utils.data_generator import generate_novel_data


class TestCreationFlow:
    """小说创建流程测试类."""

    @pytest.fixture(autouse=True)
    def setup(self, page):
        """测试前置条件."""
        self.novel_list_page = NovelListPage(page)
        self.novel_detail_page = NovelDetailPage(page)
        self.novel_list_page.navigate()

    @pytest.mark.smoke
    @pytest.mark.creation
    def test_successful_novel_creation(self, page):
        """
        测试成功创建小说的完整流程
        """
        # 准备测试数据
        novel_data = generate_novel_data()

        # 记录初始小说数量
        initial_count = self.novel_list_page.get_novel_count()
        self.novel_list_page.get_novel_titles()

        # 执行创建操作
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"],
            tags=novel_data["tags"],
            synopsis=novel_data["synopsis"],
            length_type=novel_data["length_type"]
        )

        # 验证成功消息
        assert self.novel_list_page.is_success_message_visible(), \
            "应该显示成功创建的消息"

        # 验证仍然在小说列表页
        assert "/novels" in page.url, \
            "应该停留在小说列表页面"

        # 验证新小说出现在列表中
        final_titles = self.novel_list_page.get_novel_titles()
        assert novel_data["title"] in final_titles, \
            f"新创建的小说'{novel_data['title']}'应该出现在列表中"

    @pytest.mark.creation
    def test_novel_creation_with_minimal_data(self, page):
        """
        测试使用最小数据创建小说
        """
        # 只提供必填字段
        novel_data = {
            "title": "最小数据测试小说",
            "genre": "仙侠"
        }

        initial_count = self.novel_list_page.get_novel_count()

        # 执行创建
        self.novel_list_page.click_create_button()
        self.novel_list_page.fill_create_form(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )
        self.novel_list_page.submit_create_form()

        # 验证成功
        assert self.novel_list_page.is_success_message_visible()
        # 返回列表页验证
        self.novel_list_page.navigate()
        self.novel_list_page.wait_for_novels_loaded()
        assert self.novel_list_page.get_novel_count() == initial_count + 1

    @pytest.mark.creation
    def test_novel_creation_form_validation(self, page):
        """
        测试小说创建表单验证
        """
        # 不填写任何数据直接提交
        self.novel_list_page.click_create_button()
        self.novel_list_page.submit_create_form()

        # 验证表单验证错误 - Ant Design 会显示内联错误消息
        # 模态框应该保持打开
        assert self.novel_list_page.is_create_modal_open(), \
            "表单验证失败后模态框应该保持打开"

    @pytest.mark.creation
    def test_cancel_novel_creation(self, page):
        """
        测试取消小说创建
        """
        # 打开创建表单
        self.novel_list_page.click_create_button()
        assert self.novel_list_page.is_create_modal_open()

        # 填写一些数据
        self.novel_list_page.fill_input(
            self.novel_list_page.SELECTORS["title_input"],
            "测试取消的小说"
        )

        # 取消创建
        self.novel_list_page.cancel_create_form()

        # 验证模态框关闭
        assert not self.novel_list_page.is_create_modal_open(), \
            "取消后模态框应该关闭"

        # 验证小说数量没有变化
        # 这里不需要刷新，因为没有实际创建

    @pytest.mark.creation
    def test_duplicate_novel_title(self, page):
        """
        测试重复小说标题处理
        """
        # 先创建一个小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        # 尝试创建同名小说
        self.novel_list_page.click_create_button()
        self.novel_list_page.fill_create_form(
            title=novel_data["title"],  # 使用相同标题
            genre=novel_data["genre"]
        )
        self.novel_list_page.submit_create_form()

        # 验证处理结果（可能是成功创建或显示警告）
        # 这里假设系统允许重复标题
        assert self.novel_list_page.is_success_message_visible() or \
               self.novel_list_page.is_error_message_visible()

    @pytest.mark.creation
    def test_novel_creation_with_all_tag_types(self, page):
        """
        测试使用各种标签类型创建小说
        """
        novel_data = generate_novel_data()
        # 使用所有标签类型
        all_tags = ["热血", "轻松", "虐心", "搞笑", "升级流", "系统流"]

        initial_count = self.novel_list_page.get_novel_count()

        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"],
            tags=all_tags,
            synopsis=novel_data["synopsis"]
        )

        assert self.novel_list_page.is_success_message_visible()
        self.novel_list_page.refresh_novels()
        assert self.novel_list_page.get_novel_count() == initial_count + 1

    @pytest.mark.regression
    @pytest.mark.creation
    def test_novel_list_refresh_functionality(self, page):
        """
        测试小说列表刷新功能
        """
        initial_count = self.novel_list_page.get_novel_count()

        # 创建一个小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        # 手动刷新列表
        self.novel_list_page.refresh_novels()

        # 验证数量正确更新
        final_count = self.novel_list_page.get_novel_count()
        assert final_count == initial_count + 1

    @pytest.mark.ui
    @pytest.mark.creation
    def test_novel_card_interaction(self, page):
        """
        测试小说卡片交互功能
        """
        # 确保至少有一个小说
        if self.novel_list_page.get_novel_count() == 0:
            novel_data = generate_novel_data()
            self.novel_list_page.create_novel(
                title=novel_data["title"],
                genre=novel_data["genre"]
            )

        # 点击第一个小说卡片
        initial_url = page.url
        self.novel_list_page.click_novel_card(0)

        # 验证页面跳转
        assert page.url != initial_url, "点击小说卡片应该跳转到详情页"
        assert "/novels/" in page.url, "URL应该包含小说详情路径"

    @pytest.mark.creation
    def test_novel_creation_edge_cases(self, page):
        """
        测试小说创建边界情况
        """
        test_cases = [
            # 标题很长的情况
            {"title": "A" * 100, "genre": "仙侠"},
            # 空简介
            {"title": "无简介测试", "genre": "玄幻", "synopsis": ""},
            # 英文标题
            {"title": "The Great Adventure", "genre": "奇幻"},
        ]

        initial_count = self.novel_list_page.get_novel_count()

        for i, test_case in enumerate(test_cases):
            self.novel_list_page.create_novel(**test_case)
            assert self.novel_list_page.is_success_message_visible(), \
                f"测试用例{i+1}应该成功创建小说"

        # 验证所有小说都创建成功
        self.novel_list_page.refresh_novels()
        assert self.novel_list_page.get_novel_count() == initial_count + len(test_cases)