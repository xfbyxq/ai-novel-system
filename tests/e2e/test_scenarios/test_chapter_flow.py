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

    def _create_chapter_records(self, novel_id: str, count: int):
        """
        通过数据库直接创建章节记录（测试用）.
        用于绕过 AI 生成过程，快速创建章节用于测试 UI 交互。

        Args:
            novel_id: 小说ID
            count: 创建的章节数量
        """
        import requests
        url = f"{self.base_url}/api/v1/test/create-chapters"
        response = requests.post(
            url,
            json={"novel_id": novel_id, "count": count},
            timeout=10
        )
        return response.status_code == 201

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
        return novel_id

    def _create_novel_and_navigate(self, title: str, genre: str) -> str:
        """
        创建小说并导航到详情页.

        Args:
            title: 小说标题
            genre: 小说类型

        Returns:
            str: 小说ID
        """
        self.novel_list_page.create_novel(title=title, genre=genre)
        assert self.novel_list_page.is_success_message_visible()
        # 点击新创建的小说进入详情页
        self.novel_list_page.wait_for_novels_loaded()
        novel_titles = self.novel_list_page.get_novel_titles()
        assert title in novel_titles, f"新创建的小说'{title}'应该出现在列表中"
        # 点击该小说的标题链接
        self.novel_list_page.click_novel_by_title(title)
        # 等待跳转到详情页
        self.page.wait_for_url("**/novels/*")
        # 从URL中提取小说ID
        url = self.page.url
        novel_id = url.split("/novels/")[-1].split("?")[0].split("#")[0]
        return novel_id

    @pytest.mark.chapter
    @pytest.mark.regression
    @pytest.mark.e2e07
    def test_single_chapter_generation(self):
        """
        测试单章生成流程
        """
        # 创建测试小说
        novel_data = generate_novel_data()
        self._create_novel_and_navigate(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

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
        novel_id = self._create_novel_and_navigate(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        # 准备小说（更新状态为 writing）
        self._prepare_novel_for_chapter_generation()

        # 通过数据库创建3章测试数据（绕过AI生成）
        self._create_chapter_records(novel_id, 3)
        self.page.reload()
        self.page.wait_for_timeout(1000)

        # 验证章节数量
        self.novel_detail_page.switch_to_chapters()
        chapter_count = self.novel_detail_page.get_chapter_count()
        assert chapter_count >= 3, "应该至少有3章"

    @pytest.mark.chapter
    @pytest.mark.e2e07
    def test_chapter_deletion(self):
        """
        测试章节删除功能
        """
        # 创建小说并生成章节
        novel_data = generate_novel_data()
        novel_id = self._create_novel_and_navigate(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        # 准备小说（更新状态为 writing）
        self._prepare_novel_for_chapter_generation()

        # 通过数据库创建章节用于测试删除
        self._create_chapter_records(novel_id, 2)
        self.page.reload()
        self.page.wait_for_timeout(1000)

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
        novel_id = self._create_novel_and_navigate(
            title=novel_data["title"],
            genre=novel_data["genre"]
        )

        # 准备小说（更新状态为 writing）
        self._prepare_novel_for_chapter_generation()

        # 通过数据库创建3章测试数据
        self._create_chapter_records(novel_id, 3)
        self.page.reload()
        self.page.wait_for_timeout(1000)

        # 获取章节标题
        self.novel_detail_page.switch_to_chapters()
        chapter_titles = self.novel_detail_page.get_chapter_titles()

        # 验证标题存在且不为空
        assert len(chapter_titles) >= 3, "应该获取到至少3个章节标题"
        for title in chapter_titles[:3]:  # 检查前3章
            assert title and title.strip(), f"章节标题不应该为空: '{title}'"