"""
章节生成流程测试

测试编号: E2E-07
测试目标: 测试单章生成、批量生成、章节删除等章节相关功能

前置条件: 已存在测试小说
依赖测试: E2E-01 (小说创建)

注意: 测试会自动将小说状态更新为 writing 以绕过企划流程
"""
import pytest
from tests.e2e.pages.novel_list_page import NovelListPage
from tests.e2e.pages.novel_detail_page import NovelDetailPage
from tests.e2e.utils.data_generator import generate_novel_data


class TestChapterGenerationFlow:
    """章节生成流程测试类 (E2E-07)"""

    @pytest.fixture(autouse=True)
    def setup(self, page, base_url):
        """测试前置条件."""
        self.page = page
        self.base_url = base_url
        self.novel_list_page = NovelListPage(page)
        self.novel_detail_page = NovelDetailPage(page)
        self.novel_list_page.navigate()

    def _update_novel_status_to_writing(self, novel_id: str):
        """
        通过 API 将小说状态更新为 writing.
        用于测试目的，绕过企划流程。
        """
        import requests
        # 直接调用后端 API
        url = f"{self.base_url}/api/v1/novels/{novel_id}"
        response = requests.patch(
            url,
            json={"status": "writing"},
            timeout=10
        )
        if response.status_code == 200:
            # 刷新页面以获取最新状态
            self.page.reload()
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_timeout(1000)

    def _prepare_novel_for_chapter_generation(self):
        """
        准备小说以进行章节生成.
        新创建的小说是 planning 状态，需要先开始企划并等待完成。
        为简化测试，直接通过 API 更新状态。
        """
        # 从 URL 中提取小说 ID
        url = self.page.url
        novel_id = url.split("/novels/")[-1].split("?")[0].split("#")[0]
        
        # 直接更新状态为 writing
        self._update_novel_status_to_writing(novel_id)

    @pytest.mark.chapter
    @pytest.mark.regression
    @pytest.mark.e2e07
    def test_single_chapter_generation(self):
        """
        测试单章生成流程
        """
        # 创建测试小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in self.page.url

        # 准备小说（更新状态为 writing）
        self._prepare_novel_for_chapter_generation()

        # 点击生成单章按钮
        self.novel_detail_page.click_generate_single_chapter()

        # 填写章节数
        self.novel_detail_page.fill_chapter_generation_form(chapter_number=1)

        # 确认生成
        self.novel_detail_page.confirm_single_chapter_generation()

        # 切换到章节标签页验证
        self.novel_detail_page.switch_to_chapters()

        # 验证章节已生成
        chapter_count = self.novel_detail_page.get_chapter_count()
        assert chapter_count >= 1, "应该至少生成一章"

    @pytest.mark.chapter
    @pytest.mark.e2e07
    def test_batch_chapter_generation(self):
        """
        测试批量章节生成流程
        """
        # 创建测试小说
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in self.page.url

        # 准备小说（更新状态为 writing）
        self._prepare_novel_for_chapter_generation()

        # 点击批量生成按钮
        self.novel_detail_page.click_batch_generate()

        # 填写批量生成范围
        self.novel_detail_page.fill_batch_generation_form(
            start_chapter=1,
            end_chapter=3
        )

        # 确认生成
        self.novel_detail_page.confirm_batch_chapter_generation()

        # 等待生成完成
        self.novel_detail_page.wait_for_generation_complete()

        # 验证章节数量
        self.novel_detail_page.switch_to_chapters()
        chapter_count = self.novel_detail_page.get_chapter_count()
        assert chapter_count >= 3, "应该生成至少3章"

    @pytest.mark.chapter
    @pytest.mark.e2e07
    def test_chapter_deletion(self):
        """
        测试章节删除功能
        """
        # 创建小说并生成章节
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in self.page.url

        # 准备小说（更新状态为 writing）
        self._prepare_novel_for_chapter_generation()

        # 生成一章用于测试删除
        self.novel_detail_page.click_generate_single_chapter()
        self.novel_detail_page.fill_chapter_generation_form(chapter_number=1)
        self.novel_detail_page.confirm_single_chapter_generation()

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
    @pytest.mark.e2e07
    def test_chapter_title_display(self):
        """
        测试章节标题显示
        """
        # 创建小说并生成章节
        novel_data = generate_novel_data()
        self.novel_list_page.create_novel(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        assert "/novels/" in self.page.url

        # 准备小说（更新状态为 writing）
        self._prepare_novel_for_chapter_generation()

        # 生成几章测试数据
        self.novel_detail_page.click_batch_generate()
        self.novel_detail_page.fill_batch_generation_form(1, 3)
        self.novel_detail_page.confirm_batch_chapter_generation()
        self.novel_detail_page.wait_for_generation_complete()

        # 获取章节标题
        self.novel_detail_page.switch_to_chapters()
        chapter_titles = self.novel_detail_page.get_chapter_titles()

        # 验证标题存在且不为空
        assert len(chapter_titles) >= 3, "应该获取到至少3个章节标题"
        for title in chapter_titles[:3]:  # 检查前3章
            assert title and title.strip(), f"章节标题不应该为空: '{title}'"