"""小说详情页面对象."""

from .base_page import BasePage


class NovelDetailPage(BasePage):
    """小说详情页面对象."""

    # 标签页选择器 (Ant Design Tabs)
    TAB_SELECTORS = {
        "overview": ".ant-tabs-tab:has-text('概览')",
        "world_setting": ".ant-tabs-tab:has-text('世界观')",
        "characters": ".ant-tabs-tab:has-text('角色')",
        "plot_outline": ".ant-tabs-tab:has-text('大纲')",
        "outline_refinement": ".ant-tabs-tab:has-text('大纲梳理')",
        "chapters": ".ant-tabs-tab:has-text('章节')",
        "generation_history": ".ant-tabs-tab:has-text('生成历史')",
    }

    # 概览标签页元素
    OVERVIEW_SELECTORS = {
        "start_planning_btn": "button:has-text('开始企划')",
        "generate_single_chapter_btn": "button:has-text('生成单章')",
        "batch_generate_btn": "button:has-text('批量生成章节')",
        "edit_novel_btn": "button:has-text('编辑小说')",
        # 生成单章模态框
        "chapter_modal": ".ant-modal:has-text('生成单章')",
        "chapter_number_input": ".ant-modal .ant-input-number input",
        "confirm_single_btn": ".ant-modal button:has-text('开始写作')",
        # 批量生成模态框
        "batch_modal": ".ant-modal:has-text('批量生成章节')",
        "batch_start_input": ".ant-modal .ant-input-number input >> nth=0",
        "batch_end_input": ".ant-modal .ant-input-number input >> nth=1",
        "confirm_batch_btn": ".ant-modal button:has-text('开始批量生成')",
        # 编辑小说模态框
        "edit_modal": ".ant-modal:has-text('编辑小说')",
    }

    # 大纲梳理标签页元素
    OUTLINE_SELECTORS = {
        "save_outline_btn": "button:has-text('保存大纲')",
        "enhance_outline_btn": "button:has-text('智能完善')",
        # 质量评估
        "quality_score": ".ant-progress-text",
    }

    # 章节标签页元素
    CHAPTERS_SELECTORS = {
        "chapter_table": ".ant-table",
        "chapter_row": ".ant-table-tbody tr",
        "chapter_title": ".ant-table-tbody a",
        "chapter_status": ".ant-table-tbody .ant-tag",
        "delete_chapter_btn": ".ant-btn-dangerous",
        "batch_delete_btn": "button:has-text('批量删除')",
        # 删除确认模态框
        "delete_confirm_modal": ".ant-modal:has-text('删除')",
        "confirm_delete_btn": ".ant-modal button:has-text('确认删除')",
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
        self.wait_for_element_visible(self.OVERVIEW_SELECTORS["batch_modal"])

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
        # 清空并填写章节号
        input_elem = self.get_element(self.OVERVIEW_SELECTORS["chapter_number_input"])
        input_elem.click()
        input_elem.fill(str(chapter_number))

    def fill_batch_generation_form(self, start_chapter: int, end_chapter: int):
        """
        填写批量生成表单.

        Args:
            start_chapter: 起始章节数
            end_chapter: 结束章节数
        """
        # Ant Design InputNumber 内部是 div，需要使用 click + type 方式
        start_input = self.get_element(self.OVERVIEW_SELECTORS["batch_start_input"])
        start_input.click()
        # 使用键盘全选并输入
        start_input.press("Control+A")
        start_input.type(str(start_chapter))
        
        end_input = self.get_element(self.OVERVIEW_SELECTORS["batch_end_input"])
        end_input.click()
        end_input.press("Control+A")
        end_input.type(str(end_chapter))

    def confirm_single_chapter_generation(self):
        """确认单章生成."""
        self.click_element(self.OVERVIEW_SELECTORS["confirm_single_btn"])
        self.wait_for_element_hidden(self.OVERVIEW_SELECTORS["chapter_modal"])

    def confirm_batch_chapter_generation(self):
        """确认批量生成."""
        self.click_element(self.OVERVIEW_SELECTORS["confirm_batch_btn"])
        self.wait_for_element_hidden(self.OVERVIEW_SELECTORS["batch_modal"])

    def confirm_chapter_generation(self):
        """确认章节生成 - 兼容方法，根据模态框类型自动选择."""
        if self.is_element_visible(self.OVERVIEW_SELECTORS.get("chapter_modal", "")):
            self.confirm_single_chapter_generation()
        elif self.is_element_visible(self.OVERVIEW_SELECTORS.get("batch_modal", "")):
            self.confirm_batch_chapter_generation()
        else:
            # 默认使用单章确认
            self.confirm_single_chapter_generation()

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
