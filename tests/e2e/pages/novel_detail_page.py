"""小说详情页面对象."""

from .base_page import BasePage


class NovelDetailPage(BasePage):
    """小说详情页面对象."""

    # 标签页选择器
    TAB_SELECTORS = {
        "overview": "[data-testid='tab-overview']",
        "world_setting": "[data-testid='tab-world-setting']",
        "characters": "[data-testid='tab-characters']",
        "plot_outline": "[data-testid='tab-plot-outline']",
        "outline_refinement": "[data-testid='tab-outline-refinement']",
        "chapter_decomposition": "[data-testid='tab-chapter-decomposition']",
        "chapters": "[data-testid='tab-chapters']",
        "generation_history": "[data-testid='tab-generation-history']",
        "relationship_graph": "[data-testid='tab-relationship-graph']",
    }

    # 概览标签页元素
    OVERVIEW_SELECTORS = {
        "start_planning_btn": "[data-testid='start-planning-btn']",
        "generate_single_chapter_btn": "[data-testid='generate-single-chapter-btn']",
        "batch_generate_btn": "[data-testid='batch-generate-btn']",
        "edit_novel_btn": "[data-testid='edit-novel-btn']",
        # 编辑小说模态框
        "edit_modal": "[data-testid='edit-novel-modal']",
        "edit_title_input": "[data-testid='edit-title-input']",
        "edit_genre_select": "[data-testid='edit-genre-select']",
        "edit_tags_input": "[data-testid='edit-tags-input']",
        "edit_synopsis_textarea": "[data-testid='edit-synopsis-textarea']",
        "save_edit_btn": "[data-testid='save-edit-btn']",
        "cancel_edit_btn": "[data-testid='cancel-edit-btn']",
        # 生成章节模态框
        "chapter_modal": "[data-testid='chapter-generation-modal']",
        "chapter_number_input": "[data-testid='chapter-number-input']",
        "batch_start_input": "[data-testid='batch-start-input']",
        "batch_end_input": "[data-testid='batch-end-input']",
        "confirm_generation_btn": "[data-testid='confirm-generation-btn']",
    }

    # 大纲梳理标签页元素
    OUTLINE_SELECTORS = {
        "core_conflict_input": "[data-testid='core-conflict-input']",
        "protagonist_goal_input": "[data-testid='protagonist-goal-input']",
        "antagonist_input": "[data-testid='antagonist-input']",
        "progression_path_input": "[data-testid='progression-path-input']",
        "emotional_arc_input": "[data-testid='emotional-arc-input']",
        "key_revelations_input": "[data-testid='key-revelations-input']",
        "character_growth_input": "[data-testid='character-growth-input']",
        "ending_description_input": "[data-testid='ending-description-input']",
        "save_outline_btn": "[data-testid='save-outline-btn']",
        "enhance_outline_btn": "[data-testid='enhance-outline-btn']",
        "preview_enhancement_btn": "[data-testid='preview-enhancement-btn']",
        # 增强预览模态框
        "enhancement_modal": "[data-testid='enhancement-preview-modal']",
        "apply_enhancement_btn": "[data-testid='apply-enhancement-btn']",
        "cancel_enhancement_btn": "[data-testid='cancel-enhancement-btn']",
        # 质量评估
        "quality_score": "[data-testid='quality-score']",
        "quality_dimensions": "[data-testid='quality-dimensions']",
    }

    # 章节标签页元素
    CHAPTERS_SELECTORS = {
        "chapter_table": "[data-testid='chapters-table']",
        "chapter_row": "[data-testid='chapter-row']",
        "chapter_title": "[data-testid='chapter-title']",
        "chapter_status": "[data-testid='chapter-status']",
        "chapter_quality": "[data-testid='chapter-quality']",
        "edit_chapter_btn": "[data-testid='edit-chapter-btn']",
        "delete_chapter_btn": "[data-testid='delete-chapter-btn']",
        "batch_delete_btn": "[data-testid='batch-delete-btn']",
        # 删除确认模态框
        "delete_confirm_modal": "[data-testid='delete-confirm-modal']",
        "confirm_delete_btn": "[data-testid='confirm-delete-btn']",
        "cancel_delete_btn": "[data-testid='cancel-delete-btn']",
    }

    def navigate_to_novel(self, novel_id: str):
        """
        导航到指定小说详情页.

        Args:
            novel_id: 小说ID
        """
        url = f"/novels/{novel_id}"
        self.page.goto(url)
        self.wait_for_load()

    def switch_to_tab(self, tab_name: str):
        """
        切换到指定标签页.

        Args:
            tab_name: 标签页名称 (overview, characters, outline等)
        """
        if tab_name in self.TAB_SELECTORS:
            self.click_element(self.TAB_SELECTORS[tab_name])
            # 等待标签页内容加载
            self.page.wait_for_timeout(1000)

    def get_current_tab(self) -> str:
        """
        获取当前激活的标签页.

        Returns:
            str: 当前标签页名称
        """
        for tab_name, selector in self.TAB_SELECTORS.items():
            if self.is_element_visible(f"{selector}.ant-tabs-tab-active"):
                return tab_name
        return ""

    # 概览标签页方法
    def click_start_planning(self):
        """点击开始企划按钮."""
        self.switch_to_tab("overview")
        self.click_element(self.OVERVIEW_SELECTORS["start_planning_btn"])

    def click_generate_single_chapter(self):
        """点击生成单章按钮."""
        self.switch_to_tab("overview")
        self.click_element(self.OVERVIEW_SELECTORS["generate_single_chapter_btn"])
        self.wait_for_element_visible(self.OVERVIEW_SELECTORS["chapter_modal"])

    def click_batch_generate(self):
        """点击批量生成按钮."""
        self.switch_to_tab("overview")
        self.click_element(self.OVERVIEW_SELECTORS["batch_generate_btn"])
        self.wait_for_element_visible(self.OVERVIEW_SELECTORS["chapter_modal"])

    def click_edit_novel(self):
        """点击编辑小说按钮."""
        self.switch_to_tab("overview")
        self.click_element(self.OVERVIEW_SELECTORS["edit_novel_btn"])
        self.wait_for_element_visible(self.OVERVIEW_SELECTORS["edit_modal"])

    def fill_chapter_generation_form(self, chapter_number: int):
        """
        填写单章生成表单.

        Args:
            chapter_number: 章节数
        """
        self.fill_input(
            self.OVERVIEW_SELECTORS["chapter_number_input"], str(chapter_number)
        )

    def fill_batch_generation_form(self, start_chapter: int, end_chapter: int):
        """
        填写批量生成表单.

        Args:
            start_chapter: 起始章节数
            end_chapter: 结束章节数
        """
        self.fill_input(
            self.OVERVIEW_SELECTORS["batch_start_input"], str(start_chapter)
        )
        self.fill_input(self.OVERVIEW_SELECTORS["batch_end_input"], str(end_chapter))

    def confirm_chapter_generation(self):
        """确认章节生成."""
        self.click_element(self.OVERVIEW_SELECTORS["confirm_generation_btn"])
        self.wait_for_element_hidden(self.OVERVIEW_SELECTORS["chapter_modal"])

    def fill_edit_novel_form(
        self, title: str, genre: str, tags: list = None, synopsis: str = None
    ):
        """
        填写编辑小说表单.

        Args:
            title: 标题
            genre: 类型
            tags: 标签列表
            synopsis: 简介
        """
        self.fill_input(self.OVERVIEW_SELECTORS["edit_title_input"], title)
        self.select_option(self.OVERVIEW_SELECTORS["edit_genre_select"], genre)

        if tags:
            tags_input = self.get_element(self.OVERVIEW_SELECTORS["edit_tags_input"])
            # 清空现有标签
            tags_input.press("Control+A")
            tags_input.press("Delete")
            # 添加新标签
            for tag in tags:
                tags_input.fill(tag)
                tags_input.press("Enter")

        if synopsis:
            self.fill_input(self.OVERVIEW_SELECTORS["edit_synopsis_textarea"], synopsis)

    def save_edit_novel(self):
        """保存小说编辑."""
        self.click_element(self.OVERVIEW_SELECTORS["save_edit_btn"])
        self.wait_for_element_hidden(self.OVERVIEW_SELECTORS["edit_modal"])

    # 大纲梳理标签页方法
    def switch_to_outline_refinement(self):
        """切换到大纲梳理标签页."""
        self.switch_to_tab("outline_refinement")

    def fill_outline_fields(self, outline_data: dict):
        """
        填写大纲字段.

        Args:
            outline_data: 大纲数据字典
        """
        self.switch_to_outline_refinement()

        field_mapping = {
            "core_conflict": self.OUTLINE_SELECTORS["core_conflict_input"],
            "protagonist_goal": self.OUTLINE_SELECTORS["protagonist_goal_input"],
            "antagonist": self.OUTLINE_SELECTORS["antagonist_input"],
            "progression_path": self.OUTLINE_SELECTORS["progression_path_input"],
            "emotional_arc": self.OUTLINE_SELECTORS["emotional_arc_input"],
            "key_revelations": self.OUTLINE_SELECTORS["key_revelations_input"],
            "character_growth": self.OUTLINE_SELECTORS["character_growth_input"],
            "ending_description": self.OUTLINE_SELECTORS["ending_description_input"],
        }

        for field, selector in field_mapping.items():
            if field in outline_data and outline_data[field]:
                self.fill_input(selector, outline_data[field])

    def save_outline(self):
        """保存大纲."""
        self.click_element(self.OUTLINE_SELECTORS["save_outline_btn"])

    def click_enhance_outline(self):
        """点击智能完善大纲按钮."""
        self.click_element(self.OUTLINE_SELECTORS["enhance_outline_btn"])

    def click_preview_enhancement(self):
        """点击预览增强按钮."""
        self.click_element(self.OUTLINE_SELECTORS["preview_enhancement_btn"])
        self.wait_for_element_visible(self.OUTLINE_SELECTORS["enhancement_modal"])

    def apply_enhancement(self):
        """应用大纲增强."""
        self.click_element(self.OUTLINE_SELECTORS["apply_enhancement_btn"])
        self.wait_for_element_hidden(self.OUTLINE_SELECTORS["enhancement_modal"])

    def get_outline_quality_score(self) -> float:
        """
        获取大纲质量评分.

        Returns:
            float: 质量评分
        """
        score_text = self.get_text(self.OUTLINE_SELECTORS["quality_score"])
        try:
            return float(score_text.replace("分", ""))
        except ValueError:
            return 0.0

    # 章节标签页方法
    def switch_to_chapters(self):
        """切换到章节标签页."""
        self.switch_to_tab("chapters")

    def get_chapter_count(self) -> int:
        """
        获取章节数量.

        Returns:
            int: 章节列表数量
        """
        self.switch_to_chapters()
        return self.get_element_count(self.CHAPTERS_SELECTORS["chapter_row"])

    def get_chapter_titles(self) -> list:
        """
        获取所有章节标题.

        Returns:
            list: 章节标题列表
        """
        self.switch_to_chapters()
        titles = []
        title_elements = self.get_element(
            self.CHAPTERS_SELECTORS["chapter_title"]
        ).all()
        for element in title_elements:
            titles.append(element.text_content() or "")
        return titles

    def delete_chapter(self, chapter_index: int = 0):
        """
        删除指定章节.

        Args:
            chapter_index: 章节索引
        """
        self.switch_to_chapters()
        # 点击删除按钮
        delete_buttons = self.get_element(
            self.CHAPTERS_SELECTORS["delete_chapter_btn"]
        ).all()
        if chapter_index < len(delete_buttons):
            delete_buttons[chapter_index].click()
            # 确认删除
            self.wait_for_element_visible(
                self.CHAPTERS_SELECTORS["delete_confirm_modal"]
            )
            self.click_element(self.CHAPTERS_SELECTORS["confirm_delete_btn"])
            self.wait_for_element_hidden(
                self.CHAPTERS_SELECTORS["delete_confirm_modal"]
            )

    def is_generation_running(self) -> bool:
        """
        检查是否有生成任务正在运行.

        Returns:
            bool: 是否有运行中的任务
        """
        # 检查是否存在运行中的任务指示器
        running_indicators = self.page.locator("[data-testid*='running-task']").all()
        return len(running_indicators) > 0

    def wait_for_generation_complete(self, timeout: int = 60000):
        """
        等待生成任务完成.

        Args:
            timeout: 超时时间(毫秒)
        """
        # 等待运行中的任务消失
        try:
            self.page.wait_for_selector(
                "[data-testid*='running-task']", state="detached", timeout=timeout
            )
        except:
            pass  # 超时或元素不存在都是正常的

    def refresh_page(self):
        """刷新当前页面."""
        self.page.reload()
        self.wait_for_load()
