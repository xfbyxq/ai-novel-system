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
        "save_outline_btn": "button:has-text('保存草稿')",
        "enhance_outline_btn": "button:has-text('智能完善')",
        "confirm_outline_btn": "button:has-text('确认大纲')",
        # 质量评估
        "quality_score": ".ant-progress-text",
        # 大纲字段输入框（与实际前端placeholder匹配）
        "core_conflict_input": "textarea[placeholder*='主要矛盾']",
        "protagonist_goal_input": "textarea[placeholder*='主角想要']",
        "antagonist_input": "textarea[placeholder*='反派角色']",
        "progression_path_input": "textarea[placeholder*='力量体系']",
        "emotional_arc_input": "textarea[placeholder*='情感变化']",
        "key_revelations_input": "textarea[placeholder*='重要揭示']",
        "character_growth_input": "textarea[placeholder*='成长和变化']",
        "ending_description_input": "textarea[placeholder*='故事的结局']",
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

    def click_preview_enhancement(self, timeout: int = 60000):
        """
        等待智能完善模态框出现.

        Args:
            timeout: 超时时间(毫秒)，默认60秒（AI生成需要较长时间）
        """
        # 智能完善打开的是 SmartEnhanceModal，等待其出现
        self.wait_for_element_visible(".ant-modal:has-text('智能完善')", timeout=timeout)

    def apply_enhancement(self):
        """应用大纲增强."""
        # 在 SmartEnhanceModal 中点击确认/应用
        self.click_element(".ant-modal button:has-text('应用')")
        self.wait_for_element_hidden(".ant-modal:has-text('智能完善')")

    def get_outline_quality_score(self) -> float:
        """
        获取大纲质量评分.

        Returns:
            float: 质量评分 (0-100 百分比)
        """
        # 大纲完成度显示为 "X% (N/M)" 格式
        try:
            score_text = self.page.locator(".ant-progress-text").first.text_content(timeout=5000)
            if score_text:
                # 提取百分比数字
                import re
                match = re.search(r"(\d+)%", score_text)
                if match:
                    return float(match.group(1))
        except Exception:
            pass
        return 0.0

    # 章节标签页方法
    def switch_to_chapters(self):
        """切换到章节标签页."""
        self.switch_to_tab("chapters")

    def get_chapter_count(self) -> int:
        """
        获取章节总数（从分页组件读取）.

        Returns:
            int: 章节总数
        """
        self.switch_to_chapters()
        self.page.wait_for_timeout(500)  # 等待标签页内容加载
        # 读取分页组件中的总数文本 "共 X 章"
        pagination_elem = self.page.locator(".ant-pagination-total-text")
        if pagination_elem.count() > 0:
            pagination_text = pagination_elem.text_content()
            if pagination_text:
                import re
                match = re.search(r"共\s*(\d+)", pagination_text)
                if match:
                    return int(match.group(1))
        # 回退：如果找不到分页总数，返回可见行数
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
        # 检查生成历史中是否有运行中的任务
        running_indicators = self.page.locator("[data-testid*='running-task']").all()
        return len(running_indicators) > 0

    def wait_for_generation_complete(self, timeout: int = 60000):
        """
        等待生成任务完成.

        Args:
            timeout: 超时时间(毫秒)
        """
        # 生成任务通过 FastAPI BackgroundTasks 异步执行，需要等待一段时间
        # 轮询检查章节数量变化
        import time
        start = time.time()
        initial_count = self._get_visible_chapter_count()
        while time.time() - start < timeout / 1000:
            current_count = self._get_visible_chapter_count()
            if current_count > initial_count:
                # 章节数量增加，说明有章节已创建
                self.page.wait_for_timeout(1000)  # 额外等待确保数据稳定
                return
            self.page.wait_for_timeout(2000)
        # 超时后仍然返回，由测试断言处理

    def _get_visible_chapter_count(self) -> int:
        """获取当前可见的章节行数（内部方法，无超时）."""
        try:
            return self.get_element_count(self.CHAPTERS_SELECTORS["chapter_row"])
        except Exception:
            return 0

    def refresh_page(self):
        """刷新当前页面."""
        self.page.reload()
        self.wait_for_load()
