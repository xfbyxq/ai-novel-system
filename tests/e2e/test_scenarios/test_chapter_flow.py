"""章节生成流程测试."""
import pytest
from tests.e2e.pages.novel_list_page import NovelListPage
from tests.e2e.pages.novel_detail_page import NovelDetailPage
from tests.e2e.utils.data_generator import generate_novel_data


class TestChapterGenerationFlow:
    """章节生成流程测试类."""

    @pytest.fixture(autouse=True)
    def setup(self, page):
        """测试前置条件."""
        self.novel_list_page = NovelListPage(page)
        self.novel_detail_page = NovelDetailPage(page)
        self.novel_list_page.navigate()

    @pytest.mark.chapter
    @pytest.mark.regression
    def test_single_chapter_generation(self, page):
        """
        测试单章生成流程
        """
        # 创建测试小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in page.url

        # 点击生成单章按钮
        self.novel_detail_page.click_generate_single_chapter()

        # 填写章节数
        self.novel_detail_page.fill_chapter_generation_form(chapter_number=1)

        # 确认生成
        self.novel_detail_page.confirm_chapter_generation()

        # 切换到章节标签页验证
        self.novel_detail_page.switch_to_chapters()

        # 验证章节已生成
        chapter_count = self.novel_detail_page.get_chapter_count()
        assert chapter_count >= 1, "应该至少生成一章"

    @pytest.mark.chapter
    def test_batch_chapter_generation(self, page):
        """
        测试批量章节生成流程
        """
        # 创建测试小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in page.url

        # 点击批量生成按钮
        self.novel_detail_page.click_batch_generate()

        # 填写批量生成范围
        self.novel_detail_page.fill_batch_generation_form(
            start_chapter=1,
            end_chapter=3
        )

        # 确认生成
        self.novel_detail_page.confirm_chapter_generation()

        # 等待生成完成
        self.novel_detail_page.wait_for_generation_complete()

        # 验证章节数量
        self.novel_detail_page.switch_to_chapters()
        chapter_count = self.novel_detail_page.get_chapter_count()
        assert chapter_count >= 3, "应该生成至少3章"

    @pytest.mark.chapter
    def test_chapter_deletion(self, page):
        """
        测试章节删除功能
        """
        # 创建小说并生成章节
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in page.url

        # 生成一章用于测试删除
        self.novel_detail_page.click_generate_single_chapter()
        self.novel_detail_page.fill_chapter_generation_form(chapter_number=1)
        self.novel_detail_page.confirm_chapter_generation()

        # 切换到章节标签页
        self.novel_detail_page.switch_to_chapters()

        # 记录删除前的章节数
        initial_count = self.novel_detail_page.get_chapter_count()
        assert initial_count >= 1, "应该至少有一章可删除"

        # 删除第一章
        self.novel_detail_page.delete_chapter(0)

        # 验证章节已删除
        final_count = self.novel_detail_page.get_chapter_count()
        assert final_count == initial_count - 1, "章节数量应该减少1"

    @pytest.mark.chapter
    def test_chapter_generation_while_existing(self, page):
        """
        测试在已有章节基础上继续生成
        """
        # 创建小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in page.url

        # 先生成前几章
        self.novel_detail_page.click_batch_generate()
        self.novel_detail_page.fill_batch_generation_form(1, 2)
        self.novel_detail_page.confirm_chapter_generation()
        self.novel_detail_page.wait_for_generation_complete()

        # 再生成后续章节
        self.novel_detail_page.click_batch_generate()
        self.novel_detail_page.fill_batch_generation_form(3, 5)
        self.novel_detail_page.confirm_chapter_generation()
        self.novel_detail_page.wait_for_generation_complete()

        # 验证总章节数
        self.novel_detail_page.switch_to_chapters()
        total_chapters = self.novel_detail_page.get_chapter_count()
        assert total_chapters >= 5, "应该总共生成至少5章"

    @pytest.mark.chapter
    def test_chapter_generation_concurrent_limit(self, page):
        """
        测试并发生成限制
        """
        # 创建小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in page.url

        # 启动第一次生成
        self.novel_detail_page.click_batch_generate()
        self.novel_detail_page.fill_batch_generation_form(1, 3)
        self.novel_detail_page.confirm_chapter_generation()

        # 检查是否有生成任务正在运行
        is_running = self.novel_detail_page.is_generation_running()
        assert is_running, "应该检测到有生成任务正在运行"

        # 等待生成完成
        self.novel_detail_page.wait_for_generation_complete()

        # 验证生成完成
        assert not self.novel_detail_page.is_generation_running(), "生成任务应该已完成"

    @pytest.mark.chapter
    def test_chapter_title_display(self, page):
        """
        测试章节标题显示
        """
        # 创建小说并生成章节
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in page.url

        # 生成几章测试数据
        self.novel_detail_page.click_batch_generate()
        self.novel_detail_page.fill_batch_generation_form(1, 3)
        self.novel_detail_page.confirm_chapter_generation()
        self.novel_detail_page.wait_for_generation_complete()

        # 获取章节标题
        self.novel_detail_page.switch_to_chapters()
        chapter_titles = self.novel_detail_page.get_chapter_titles()

        # 验证标题存在且不为空
        assert len(chapter_titles) >= 3, "应该获取到至少3个章节标题"
        for title in chapter_titles[:3]:  # 检查前3章
            assert title and title.strip(), f"章节标题不应该为空: '{title}'"

    @pytest.mark.chapter
    @pytest.mark.edge_case
    def test_chapter_generation_edge_cases(self, page):
        """
        测试章节生成边界情况
        """
        # 创建小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in page.url

        test_cases = [
            # 单章生成
            {"start": 1, "end": 1, "description": "单章生成"},
            # 大批量生成
            {"start": 1, "end": 10, "description": "大批量生成"},
            # 连续生成
            {"start": 5, "end": 8, "description": "连续章节生成"}
        ]

        for test_case in test_cases:
            self.novel_detail_page.click_batch_generate()
            self.novel_detail_page.fill_batch_generation_form(
                test_case["start"],
                test_case["end"]
            )
            self.novel_detail_page.confirm_chapter_generation()
            self.novel_detail_page.wait_for_generation_complete()

            # 验证每种情况都能成功生成
            self.novel_detail_page.switch_to_chapters()
            chapter_count = self.novel_detail_page.get_chapter_count()
            expected_min = test_case["end"]
            assert chapter_count >= expected_min, f"{test_case['description']}应该生成至少{expected_min}章"