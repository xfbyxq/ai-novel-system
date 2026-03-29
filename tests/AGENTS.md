# TESTS 模块

**测试套件**: unit/integration/e2e/ai_e2e 四个层级

## OVERVIEW

完整的测试金字塔，77个测试文件。使用pytest + pytest-asyncio + Playwright。

## STRUCTURE

```
tests/
├── conftest.py              # 全局fixtures
├── unit/                    # 单元测试 (13 files)
├── integration/            # 集成测试
├── e2e/                     # 端到端测试 (Playwright)
│   ├── conftest.py          # E2E专用fixtures
│   ├── pages/               # Page Object
│   ├── components/          # 组件对象
│   ├── test_scenarios/      # 场景测试
│   └── utils/
├── ai_e2e/                  # AI驱动E2E测试
│   ├── agents/
│   ├── prompts/
│   ├── runners/
│   └── selectors/
├── performance/             # 性能测试
└── fixtures/                # 测试数据
```

## WHERE TO LOOK

| 任务 | 位置 | 说明 |
|------|------|------|
| 新增fixtures | `conftest.py` | 全局或子目录 |
| 单元测试 | `unit/test_*.py` | Mock所有外部依赖 |
| E2E测试 | `e2e/test_scenarios/` | Page Object模式 |
| AI测试 | `ai_e2e/runners/` | autonomous/heal模式 |

## FIXTURES

### 全局Fixtures (`tests/conftest.py`)

```python
@pytest.fixture(scope="function")
async def db_engine():
    """每个测试函数独立数据库"""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin():
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(db_engine):
    """隔离的异步session"""

@pytest.fixture
async def test_client(db_session):
    """FastAPI测试客户端"""
    app.dependency_overrides[get_db] = lambda: db_session
    async with httpx.AsyncClient(...) as client:
        yield client
```

### E2E Fixtures (`tests/e2e/conftest.py`)

```python
@pytest.fixture
def page(browser, base_url):
    """Playwright页面实例"""
    context = browser.new_context()
    page = context.new_page()
    page.goto(base_url)
    yield page
    context.close()
```

## PAGE OBJECT PATTERN

```python
class BasePage:
    def __init__(self, page):
        self.page = page
        self.timeout = 10000
    
    def click(self, selector):
        self.page.click(selector, timeout=self.timeout)

class NovelListPage(BasePage):
    SELECTORS = {
        "create_btn": ".ant-btn-primary",
        "title_input": "input[placeholder*='标题']",
    }
    
    def create_novel(self, title):
        self.click(self.SELECTORS["create_btn"])
        self.page.fill(self.SELECTORS["title_input"], title)
```

## MARKERS

```python
# pyproject.toml定义
@pytest.mark.smoke        # 冒烟测试
@pytest.mark.unit         # 单元测试
@pytest.mark.integration  # 集成测试
@pytest.mark.slow         # 慢测试
@pytest.mark.creation     # 创作流程测试
@pytest.mark.ui           # UI交互测试
```

## RUNNING TESTS

```bash
# 所有测试
pytest

# 按类型
pytest tests/unit/ -v
pytest tests/e2e/ -v
pytest tests/integration/ -v

# 按标记
pytest -m smoke -v
pytest -m "not slow" -v
pytest -m creation -v

# 生成覆盖率
pytest --cov=backend --cov-report=html
```

## CONVENTIONS

- **异步测试**: `@pytest.mark.asyncio`
- **环境隔离**: 测试前保存环境变量，测试后恢复
- **Mock模式**: 使用 `@patch` 装饰器
- **命名**: `test_*.py`, `Test*` 类, `test_*` 方法
- **Docstring**: 中文描述测试目的

## ANTI-PATTERNS

- **禁止删除失败测试**: 而非修复
- **禁止跳过数据库回滚**: 保持测试隔离
- **禁止裸except**: 必须指定异常类型
