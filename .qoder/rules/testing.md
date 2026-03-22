---
trigger: code_testing
---

# 测试规范

## 测试目录结构
```
tests/
├── unit/              # 单元测试
├── integration/       # 集成测试
├── e2e/               # 端到端测试
├── performance/       # 性能测试
├── real_scenario/     # 真实场景测试
├── fixtures/          # 测试数据
└── conftest.py        # pytest配置
```

## 测试标记规范

项目定义的pytest标记:

| 标记 | 说明 | 示例 |
|------|------|------|
| @pytest.mark.unit | 单元测试，使用mock数据 | `pytest -m unit` |
| @pytest.mark.network | 需要网络访问的测试 | `pytest -m network` |
| @pytest.mark.real_crawl | 真实爬虫场景测试 | `pytest -m real_crawl` |
| @pytest.mark.integration | 需要数据库的集成测试 | `pytest -m integration` |
| @pytest.mark.slow | 慢速测试 | `pytest -m slow` |
| @pytest.mark.smoke | 快速冒烟测试 | `pytest -m smoke` |
| @pytest.mark.regression | 回归测试 | `pytest -m regression` |
| @pytest.mark.ui | UI交互测试 | `pytest -m ui` |
| @pytest.mark.edge_case | 边界情况测试 | `pytest -m edge_case` |
| @pytest.mark.creation | 小说创建流程测试 | `pytest -m creation` |

## 运行测试

### 运行所有测试
```bash
pytest
```

### 按标记运行
```bash
# 只运行单元测试
pytest -m unit

# 运行单元测试和集成测试
pytest -m "unit or integration"

# 排除慢速测试
pytest -m "not slow"
```

### 生成覆盖率报告
```bash
# 运行测试并生成覆盖率
pytest --cov=. --cov-report=html

# 查看HTML报告
open htmlcov/index.html
```

## 单元测试规范

### 测试文件命名
- 测试文件必须以 `test_` 开头
- 测试类必须以 `Test` 开头
- 测试方法必须以 `test_` 开头

### 测试代码示例

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch

class TestUserService:
    """用户服务测试类"""

    @pytest.fixture
    def mock_session(self):
        """模拟数据库会话"""
        return AsyncMock()

    @pytest.mark.unit
    async def test_get_user_by_id(self, mock_session):
        """测试根据ID获取用户"""
        # Arrange - 准备测试数据
        user_id = 1
        expected_user = User(id=1, name="测试用户")

        # Act - 执行测试方法
        with patch('service.get_session', return_value=mock_session):
            mock_session.execute.return_value = Mock(scalars=Mock(return_value=Mock(first=Mock(return_value=expected_user))))
            result = await user_service.get_user_by_id(user_id)

        # Assert - 断言结果
        assert result.id == expected_user.id
        assert result.name == expected_user.name

    @pytest.mark.unit
    async def test_get_user_not_found(self, mock_session):
        """测试用户不存在的情况"""
        # Arrange
        user_id = 999

        # Act & Assert
        with pytest.raises(UserNotFoundError):
            await user_service.get_user_by_id(user_id)

    @pytest.mark.edge_case
    @pytest.mark.parametrize("user_id,expected", [
        (0, None),
        (-1, None),
        (None, None),
    ])
    async def test_get_user_invalid_id(self, user_id, expected):
        """测试无效用户ID的边界情况"""
        result = await user_service.get_user_by_id(user_id)
        assert result == expected
```

### E2E测试规范 (Playwright)

```python
import pytest
from playwright.sync_api import Page, expect

@pytest.mark.ui
class TestNovelCreation:
    """小说创建流程E2E测试"""

    def test_create_novel_flow(self, page: Page):
        """测试完整的小说创建流程"""
        # 1. 登录
        page.goto("/login")
        page.fill("#username", "testuser")
        page.fill("#password", "password")
        page.click("button[type='submit']")

        # 2. 创建小说
        page.click("text=创建小说")
        page.fill("#title", "测试小说")
        page.fill("#description", "这是一个测试小说")
        page.click("button:has-text('提交')")

        # 3. 验证创建成功
        expect(page.locator(".novel-title")).to_have_text("测试小说")

    @pytest.mark.smoke
    def test_home_page_loads(self, page: Page):
        """测试首页加载"""
        page.goto("/")
        expect(page.locator("h1")).to_contain_text("AI小说系统")
```

## 测试覆盖率要求

- **目标覆盖率**: 80%以上
- **核心业务**: 90%以上
- **新功能**: 必须有对应测试

## 测试数据管理

### 使用fixtures
```python
# conftest.py
import pytest

@pytest.fixture
def sample_novel():
    """返回示例小说数据"""
    return {
        "title": "测试小说",
        "description": "这是一个测试小说",
        "genre": "玄幻",
        "target_words": 100000
    }
```

## CI/CD集成

项目在GitHub Actions中自动运行:
1. 代码质量检查 (flake8, black, pydocstyle)
2. 单元测试 (pytest)
3. 覆盖率上传 (Codecov)
4. 安全扫描 (CodeQL)