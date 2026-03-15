# UI自动化测试使用文档

## 快速开始

### 1. 环境准备

确保系统服务已启动：
```bash
# 启动数据库服务
docker-compose -f docker-compose.dev.yml up -d postgres redis

# 启动后端服务
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8001

# 启动前端服务
cd frontend
API_PROXY_TARGET=http://localhost:8001 npm run dev
```

### 2. 安装测试依赖

```bash
pip install pytest-playwright pytest-asyncio faker
playwright install chromium
```

### 3. 运行测试

```bash
# 运行所有测试
python -m pytest tests/e2e/ -v

# 运行特定测试模块
python -m pytest tests/e2e/test_scenarios/test_creation_flow.py -v

# 运行特定测试用例
python -m pytest tests/e2e/test_scenarios/test_creation_flow.py::TestCreationFlow::test_successful_novel_creation -v

# 按标记运行测试
python -m pytest tests/e2e/ -m creation -v  # 运行创建相关测试
python -m pytest tests/e2e/ -m outline -v   # 运行大纲相关测试
python -m pytest tests/e2e/ -m chapter -v   # 运行章节相关测试
```

## 测试结构说明

```
tests/e2e/
├── conftest.py                 # pytest配置和fixture
├── pages/                      # 页面对象模型
│   ├── base_page.py           # 基础页面类
│   ├── novel_list_page.py     # 小说列表页
│   └── novel_detail_page.py   # 小说详情页
├── utils/                     # 测试工具
│   └── data_generator.py      # 测试数据生成器
├── test_scenarios/            # 测试场景
│   ├── test_creation_flow.py  # 创建流程测试
│   ├── test_outline_flow.py   # 大纲流程测试
│   └── test_chapter_flow.py   # 章节流程测试
└── TEST_REPORT.md             # 测试报告
```

## 核心组件介绍

### 页面对象模型 (Page Object Model)

#### NovelListPage
```python
# 创建小说
novel_list_page.create_novel(
    title="测试小说",
    genre="仙侠",
    tags=["热血", "升级"],
    synopsis="这是一个测试小说"
)

# 获取小说数量
count = novel_list_page.get_novel_count()

# 点击创建按钮
novel_list_page.click_create_button()
```

#### NovelDetailPage
```python
# 切换标签页
novel_detail_page.switch_to_tab("outline_refinement")

# 填写大纲
outline_data = {
    "core_conflict": "世界危机",
    "protagonist_goal": "拯救世界"
}
novel_detail_page.fill_outline_fields(outline_data)

# 生成章节
novel_detail_page.click_generate_single_chapter()
novel_detail_page.fill_chapter_generation_form(1)
novel_detail_page.confirm_chapter_generation()
```

### 测试数据生成器

```python
from tests.e2e.utils.data_generator import generate_novel_data, generate_outline_data

# 生成小说数据
novel_data = generate_novel_data()
print(novel_data["title"])  # 自动生成的中文标题

# 生成大纲数据
outline_data = generate_outline_data()
print(outline_data["core_conflict"])  # 核心冲突内容
```

## 测试标记说明

| 标记 | 说明 | 示例 |
|------|------|------|
| `smoke` | 冒烟测试 | 核心功能快速验证 |
| `creation` | 创建流程 | 小说创建相关测试 |
| `outline` | 大纲流程 | 大纲梳理相关测试 |
| `chapter` | 章节流程 | 章节生成相关测试 |
| `regression` | 回归测试 | 防止功能退化 |
| `ui` | UI交互 | 界面操作测试 |
| `edge_case` | 边界测试 | 极端情况测试 |

## 常见问题解决

### 1. 测试超时问题
```python
# 增加等待时间
page.set_default_timeout(30000)  # 30秒超时

# 或在特定操作中指定超时
element.wait_for(timeout=15000)
```

### 2. 元素定位失败
```python
# 使用更稳定的选择器
# 推荐：基于文本内容定位
button:has-text('创建小说')

# 避免：基于动态属性定位
[data-row-key='dynamic-id']  # 不稳定
```

### 3. 异步操作处理
```python
# 等待特定元素出现
page.wait_for_selector(".success-message", timeout=10000)

# 等待页面加载完成
page.wait_for_load_state("networkidle")
```

### 4. 测试数据清理
```python
# 在测试前后清理数据
@pytest.fixture(autouse=True)
def cleanup_test_data():
    # 测试前准备
    yield
    # 测试后清理
    # 删除测试创建的数据
```

## 调试技巧

### 1. 查看测试执行过程
```bash
# 显示浏览器窗口
python -m pytest tests/e2e/ --headed -v

# 生成截图和视频
python -m pytest tests/e2e/ --screenshot=on --video=on -v
```

### 2. 逐步调试
```python
# 在测试中添加断点
import pdb; pdb.set_trace()

# 或使用Playwright的调试模式
page.pause()  # 暂停执行，手动操作
```

### 3. 日志输出
```python
# 启用详细日志
python -m pytest tests/e2e/ -v --tb=long --capture=no
```

## 最佳实践

### 1. 测试设计原则
- 每个测试用例只验证一个功能点
- 测试之间保持独立性
- 使用描述性的测试名称
- 合理使用setup和teardown

### 2. 选择器编写
- 优先使用用户可见的文本内容
- 避免使用过于具体的位置选择器
- 考虑元素的唯一性和稳定性

### 3. 等待策略
- 使用显式等待而非固定延时
- 根据具体条件设置等待
- 合理设置超时时间

### 4. 数据管理
- 使用随机但合理的测试数据
- 确保测试数据的可重现性
- 及时清理测试产生的数据

## 持续集成

### GitHub Actions配置示例
```yaml
name: UI Tests
on: [push, pull_request]
jobs:
  ui-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-playwright
          playwright install chromium
      - name: Run UI tests
        run: python -m pytest tests/e2e/ -v
```

这个文档提供了完整的UI自动化测试使用指南，帮助开发者快速上手和有效使用测试框架。