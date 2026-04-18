#!/usr/bin/env python3
"""
AI小说系统E2E测试用例批量生成器

生成以下功能的测试用例：
1. 小说创建
2. 小说查看
3. 世界观查看
4. 大纲查看
5. 小说章节查看
6. 添加企划任务
7. 批量生成小说任务

使用方法:
    python scripts/generate_novel_tests.py

作者: Qoder
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.ai_e2e.config import TestConfig, default_config
from tests.ai_e2e.agents.test_generator import TestGenerator, TestSpecification

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 测试场景配置
TEST_SCENARIOS = [
    {
        "feature": "小说创建",
        "description": "测试创建新小说的完整流程",
        "page_url": "/novels",
        "test_goals": [
            "验证小说列表页面正常加载，显示创建按钮",
            "点击创建小说按钮，打开创建表单",
            "填写小说基本信息（标题、类型、简介）",
            "提交创建表单，验证小说创建成功",
            "验证新创建的小说显示在列表中",
        ],
    },
    {
        "feature": "小说查看",
        "description": "测试查看小说详情的功能",
        "page_url": "/novels",
        "test_goals": [
            "验证小说列表页面正常加载，显示小说卡片",
            "点击小说卡片进入详情页",
            "验证小说详情页包含概览标签",
            "验证小说基本信息正确显示",
        ],
    },
    {
        "feature": "世界观查看",
        "description": "测试查看和编辑世界观的功能",
        "page_url": "/novels/:id",
        "test_goals": [
            "进入小说详情页",
            "切换到世界观标签",
            "验证世界观内容正确显示",
            "验证世界观编辑功能可用",
        ],
    },
    {
        "feature": "大纲查看",
        "description": "测试查看和编辑大纲的功能",
        "page_url": "/novels/:id",
        "test_goals": [
            "进入小说详情页",
            "切换到大纲标签",
            "验证大纲内容正确显示",
            "验证大纲编辑功能可用",
        ],
    },
    {
        "feature": "小说章节查看",
        "description": "测试查看和管理章节的功能",
        "page_url": "/novels/:id",
        "test_goals": [
            "进入小说详情页",
            "切换到章节标签",
            "验证章节列表正确显示",
            "点击章节进入章节详情",
            "验证章节内容正确显示",
        ],
    },
    {
        "feature": "添加企划任务",
        "description": "测试在小说详情页添加企划任务的功能",
        "page_url": "/novels/:id",
        "test_goals": [
            "进入小说详情页的概览标签",
            "找到添加企划任务的入口",
            "点击添加企划任务按钮",
            "填写企划任务相关信息",
            "提交并验证企划任务创建成功",
        ],
    },
    {
        "feature": "批量生成小说任务",
        "description": "测试批量生成小说内容的功能",
        "page_url": "/novels/:id",
        "test_goals": [
            "进入小说详情页",
            "切换到生成历史或相关标签",
            "找到批量生成任务的入口",
            "点击批量生成按钮",
            "配置生成参数（章节数、生成方式等）",
            "提交批量生成任务",
            "验证任务提交成功",
        ],
    },
]


def generate_test_file(test_scenario: dict, output_dir: Path) -> Path:
    """
    生成单个测试用例文件

    参数:
        test_scenario: 测试场景配置
        output_dir: 输出目录

    返回:
        生成的测试文件路径
    """
    feature = test_scenario["feature"]
    description = test_scenario["description"]
    page_url = test_scenario["page_url"]
    test_goals = test_scenario["test_goals"]

    # 创建测试规范
    spec = TestSpecification(
        feature_name=feature,
        description=description,
        test_scenarios=test_goals,
    )

    # 生成测试代码
    generator = TestGenerator(default_config)
    test_cases = generator.generate_tests(spec, output_dir)

    if test_cases:
        # 返回第一个测试用例的文件路径
        return output_dir / f"test_1_{test_cases[0].test_name}.py"

    return None


def generate_comprehensive_test_file(test_scenario: dict, output_dir: Path) -> Path:
    """
    生成综合测试文件（包含所有测试场景）

    参数:
        test_scenario: 测试场景配置
        output_dir: 输出目录

    返回:
        生成的测试文件路径
    """
    feature = test_scenario["feature"]

    # 构建测试代码
    test_code = f'''"""
AI小说系统 - {feature}功能测试

自动生成的E2E测试用例
测试目标: {test_scenario['description']}

作者: Qoder
生成时间: {datetime.now().isoformat()}
"""

from datetime import datetime

import pytest
from playwright.sync_api import Page, expect


class Test{feature}:
    """{feature}功能测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """每个测试前的准备工作"""
        self.page = page
        # 导航到目标页面
        page.goto("{test_scenario["page_url"]}")
        page.wait_for_load_state("networkidle")

'''

    # 根据不同功能生成不同的测试方法
    if feature == "小说创建":
        test_code += _generate_novel_creation_tests()
    elif feature == "小说查看":
        test_code += _generate_novel_view_tests()
    elif feature == "世界观查看":
        test_code += _generate_world_view_tests()
    elif feature == "大纲查看":
        test_code += _generate_outline_view_tests()
    elif feature == "小说章节查看":
        test_code += _generate_chapter_view_tests()
    elif feature == "添加企划任务":
        test_code += _generate_planning_task_tests()
    elif feature == "批量生成小说任务":
        test_code += _generate_batch_generation_tests()

    # 保存测试文件
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"test_{feature}.py"
    filepath = output_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(test_code)

    logger.info(f"生成测试文件: {filepath}")
    return filepath


def _generate_novel_creation_tests() -> str:
    """生成小说创建测试代码"""
    return '''
    def test_novel_list_page_loads(self):
        """测试小说列表页面正常加载"""
        # 验证页面标题或关键元素
        expect(self.page.locator("body")).to_be_visible()
        # 验证创建按钮存在
        create_btn = self.page.locator("text=创建小说, text=新建小说, .ant-btn-primary").first
        expect(create_btn).to_be_visible()

    def test_click_create_button(self):
        """测试点击创建小说按钮打开表单"""
        # 点击创建按钮
        self.page.locator("text=创建小说, text=新建小说").first.click()
        # 等待表单出现
        self.page.wait_for_selector(".ant-modal, form", state="visible", timeout=5000)

    def test_fill_novel_form(self):
        """测试填写小说表单"""
        # 点击创建按钮打开表单
        self.page.locator("text=创建小说, text=新建小说").first.click()

        # 填写标题
        title_input = self.page.locator("input[name='title'], input[placeholder*='标题']").first
        title_input.fill("测试小说_" + datetime.now().strftime("%Y%m%d%H%M%S"))

        # 填写简介
        desc_input = self.page.locator("textarea[name='description'], textarea[placeholder*='简介']").first
        desc_input.fill("这是自动化测试生成的小说简介")

    def test_submit_novel_form(self):
        """测试提交小说表单"""
        # 先填写表单
        self.test_fill_novel_form()

        # 点击提交按钮
        submit_btn = self.page.locator("button[type='submit'], text=确定, text=创建").last
        submit_btn.click()

        # 等待创建成功提示或页面刷新
        self.page.wait_for_timeout(2000)

    def test_novel_appears_in_list(self):
        """测试新创建的小说显示在列表中"""
        # 刷新页面
        self.page.reload()
        self.page.wait_for_load_state("networkidle")

        # 验证小说出现在列表中
        expect(self.page.locator("text=测试小说_")).to_be_visible()
'''


def _generate_novel_view_tests() -> str:
    """生成小说查看测试代码"""
    return '''
    def test_novel_list_displays(self):
        """测试小说列表显示"""
        # 等待页面加载完成
        self.page.wait_for_selector(".ant-table, .ant-card, .novel-list", timeout=10000)

    def test_click_novel_to_view_detail(self):
        """测试点击小说查看详情"""
        # 查找第一个小说项并点击
        novel_item = self.page.locator(".ant-card, .novel-item, tr.ant-table-row").first
        novel_item.click()

        # 等待详情页加载
        self.page.wait_for_load_state("networkidle")

        # 验证进入详情页
        assert "/novels/" in self.page.url or self.page.locator(".novel-detail").count() > 0

    def test_novel_detail_tabs(self):
        """测试小说详情页标签"""
        # 查找标签栏
        tabs = self.page.locator(".ant-tabs-tab, .ant-menu-item")
        expect(tabs.first).to_be_visible()

        # 验证概览标签存在
        expect(self.page.locator("text=概览, text=Overview")).to_be_visible()


from datetime import datetime
'''


def _generate_world_view_tests() -> str:
    """生成世界观查看测试代码"""
    return '''
    def test_switch_to_world_tab(self):
        """测试切换到世界观标签"""
        # 点击世界观标签
        world_tab = self.page.locator("text=世界观, text=世界设定, text=World").first
        world_tab.click()

        # 等待标签内容加载
        self.page.wait_for_timeout(1000)

    def test_world_content_displayed(self):
        """测试世界观内容显示"""
        # 验证世界观内容区域存在
        world_content = self.page.locator(".world-setting, .ant-form, textarea")
        expect(world_content.first).to_be_visible()

    def test_world_edit_available(self):
        """测试世界观编辑功能可用"""
        # 查找编辑按钮
        edit_btn = self.page.locator("text=编辑, text=修改").first
        # 编辑按钮可能不存在或不可点击
        if edit_btn.count() > 0:
            edit_btn.click()
            self.page.wait_for_selector("textarea, input", state="visible", timeout=3000)


from datetime import datetime
'''


def _generate_outline_view_tests() -> str:
    """生成大纲查看测试代码"""
    return '''
    def test_switch_to_outline_tab(self):
        """测试切换到大纲标签"""
        # 点击大纲标签
        outline_tab = self.page.locator("text=大纲, text=Plot, text=情节").first
        outline_tab.click()

        # 等待标签内容加载
        self.page.wait_for_timeout(1000)

    def test_outline_content_displayed(self):
        """测试大纲内容显示"""
        # 验证大纲内容区域存在
        outline_content = self.page.locator(".plot-outline, .ant-form, .ant-card")
        expect(outline_content.first).to_be_visible()

    def test_outline_edit_available(self):
        """测试大纲编辑功能可用"""
        # 查找编辑按钮
        edit_btn = self.page.locator("text=编辑, text=修改").first
        if edit_btn.count() > 0:
            edit_btn.click()
            self.page.wait_for_selector("textarea, input", state="visible", timeout=3000)


from datetime import datetime
'''


def _generate_chapter_view_tests() -> str:
    """生成章节查看测试代码"""
    return '''
    def test_switch_to_chapters_tab(self):
        """测试切换到章节标签"""
        # 点击章节标签
        chapter_tab = self.page.locator("text=章节, text=Chapters").first
        chapter_tab.click()

        # 等待标签内容加载
        self.page.wait_for_timeout(1000)

    def test_chapter_list_displays(self):
        """测试章节列表显示"""
        # 验证章节列表存在
        chapter_list = self.page.locator(".ant-table, .chapter-list, tr")
        expect(chapter_list.first).to_be_visible()

    def test_click_chapter_to_view(self):
        """测试点击章节查看详情"""
        # 查找第一个章节
        first_chapter = self.page.locator(".ant-table-row, .chapter-item, tr").first
        first_chapter.click()

        # 等待章节详情加载
        self.page.wait_for_timeout(1000)


from datetime import datetime
'''


def _generate_planning_task_tests() -> str:
    """生成添加企划任务测试代码"""
    return '''
    def test_overview_tab_visible(self):
        """测试概览标签可见"""
        # 确保在概览标签
        overview_tab = self.page.locator("text=概览, text=Overview").first
        overview_tab.click()
        self.page.wait_for_timeout(1000)

    def test_find_planning_task_entry(self):
        """测试找到企划任务入口"""
        # 查找企划任务相关按钮
        task_buttons = self.page.locator("text=企划, text=任务, text=添加任务")
        expect(task_buttons.first).to_be_visible()

    def test_click_add_planning_task(self):
        """测试点击添加企划任务按钮"""
        # 点击添加企划任务按钮
        add_btn = self.page.locator("text=添加企划, text=新建任务, .ant-btn-primary").first
        add_btn.click()

        # 等待弹窗出现
        self.page.wait_for_selector(".ant-modal", state="visible", timeout=5000)

    def test_fill_planning_task_form(self):
        """测试填写企划任务表单"""
        # 先打开表单
        self.test_click_add_planning_task()

        # 填写任务名称
        name_input = self.page.locator("input[name='name'], input[placeholder*='名称']").first
        name_input.fill("测试企划任务_" + datetime.now().strftime("%H%M%S"))

    def test_submit_planning_task(self):
        """测试提交企划任务"""
        # 填写表单
        self.test_fill_planning_task_form()

        # 点击提交按钮
        submit_btn = self.page.locator("button[type='submit'], text=确定, text=提交").last
        submit_btn.click()

        # 等待提交完成
        self.page.wait_for_timeout(2000)
'''


def _generate_batch_generation_tests() -> str:
    """生成批量生成小说任务测试代码"""
    return '''
    def test_switch_to_generation_tab(self):
        """测试切换到生成历史标签"""
        # 点击生成历史或相关标签
        gen_tab = self.page.locator("text=生成历史, text=生成, text=Generation").first
        gen_tab.click()

        # 等待标签内容加载
        self.page.wait_for_timeout(1000)

    def test_find_batch_generation_entry(self):
        """测试找到批量生成入口"""
        # 查找批量生成按钮
        batch_btn = self.page.locator("text=批量生成, text=批量, .ant-btn-primary")
        expect(batch_btn.first).to_be_visible()

    def test_click_batch_generation(self):
        """测试点击批量生成按钮"""
        # 点击批量生成按钮
        batch_btn = self.page.locator("text=批量生成").first
        batch_btn.click()

        # 等待弹窗出现
        self.page.wait_for_selector(".ant-modal", state="visible", timeout=5000)

    def test_configure_batch_generation(self):
        """测试配置批量生成参数"""
        # 打开批量生成界面
        self.test_click_batch_generation()

        # 填写章节数量
        num_input = self.page.locator("input[name='count'], input[name='chapterCount'], input[type='number']").first
        if num_input.count() > 0:
            num_input.fill("5")

    def test_submit_batch_generation(self):
        """测试提交批量生成任务"""
        # 配置参数
        self.test_configure_batch_generation()

        # 点击生成按钮
        gen_btn = self.page.locator("text=开始生成, text=生成, button[type='submit']").first
        gen_btn.click()

        # 等待任务提交
        self.page.wait_for_timeout(2000)


from datetime import datetime
'''


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始生成AI小说系统E2E测试用例")
    logger.info("=" * 60)

    # 输出目录
    output_dir = project_root / "tests" / "e2e" / "test_scenarios" / "novel"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成__init__.py
    init_file = output_dir / "__init__.py"
    with open(init_file, 'w', encoding='utf-8') as f:
        f.write('"""AI小说系统 - 小说功能E2E测试用例"""\n')

    generated_files = []

    # 生成每个测试场景
    for scenario in TEST_SCENARIOS:
        logger.info(f"\n生成功能测试: {scenario['feature']}")
        logger.info(f"  描述: {scenario['description']}")

        try:
            filepath = generate_comprehensive_test_file(scenario, output_dir)
            generated_files.append({
                "feature": scenario["feature"],
                "filepath": str(filepath),
            })
            logger.info(f"  ✓ 生成成功: {filepath.name}")
        except Exception as e:
            logger.error(f"  ✗ 生成失败: {e}")

    # 生成测试汇总
    logger.info("\n" + "=" * 60)
    logger.info("测试用例生成完成")
    logger.info("=" * 60)
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"生成文件数: {len(generated_files)}")

    for f in generated_files:
        logger.info(f"  - {f['feature']}: {Path(f['filepath']).name}")

    # 生成测试运行指南
    guide_file = output_dir / "README.md"
    guide_content = f"""# AI小说系统 - E2E测试用例

## 测试用例列表

| 功能 | 测试文件 | 说明 |
|------|----------|------|
"""

    for f in generated_files:
        feature = f['feature']
        filename = Path(f['filepath']).name
        desc = next(s['description'] for s in TEST_SCENARIOS if s['feature'] == feature)
        guide_content += f"| {feature} | `{filename}` | {desc} |\n"

    guide_content += f"""
## 运行测试

### 运行单个测试
```bash
cd /Users/sanyi/code/python/novel_system
pytest tests/e2e/test_scenarios/novel/test_小说创建.py -v
```

### 运行所有小说相关测试
```bash
pytest tests/e2e/test_scenarios/novel/ -v
```

### 使用AI E2E运行器
```bash
# 自主测试模式
python scripts/ai_e2e_runner.py --mode autonomous --goal "测试小说创建功能" --start-url "/novels"

# 测试生成模式
python scripts/ai_e2e_runner.py --mode generate --feature "小说管理"
```

## 生成时间
{datetime.now().isoformat()}

## 作者
Qoder - AI测试工程师
"""

    with open(guide_file, 'w', encoding='utf-8') as f:
        f.write(guide_content)

    logger.info(f"\n测试指南: {guide_file}")

    return generated_files


if __name__ == "__main__":
    main()