# 文档字符串风格指南

本文档定义 novel_system 项目的 Python 文档字符串（docstring）规范。

## 风格选择

本项目采用 **Google Style** 文档字符串格式。

### 为什么选择 Google Style？

1. **简洁易读**：格式清晰，不过于冗长
2. **广泛支持**：被主流工具（Sphinx、pydocstyle、IDE）支持
3. **适合中文**：对中文文档友好
4. **团队熟悉**：团队成员更容易上手

## 基本规则

### 1. 模块文档字符串

每个模块（`.py` 文件）应在文件开头包含模块级文档字符串，简要说明模块用途。

```python
"""
配置模块 - 管理系统配置和验证.

本模块提供 Settings 类，用于加载、验证和访问系统配置。
支持开发环境和生产环境的自动检测。
"""
```

### 2. 类文档字符串

每个公共类应包含类级文档字符串，说明类的用途和主要功能。

```python
class NovelException(Exception):
    """
    小说系统异常基类.
    
    所有自定义异常都应继承此类，便于统一捕获和处理。
    
    Attributes:
        message: 错误消息
        code: 错误代码（可选）
        details: 额外详细信息（可选）
    """
```

### 3. 函数/方法文档字符串

所有公共函数和方法应包含文档字符串，包括：
- 简短描述（一行）
- 详细描述（可选，多行）
- Args 部分（参数说明）
- Returns 部分（返回值说明）
- Raises 部分（异常说明，可选）
- Example 部分（示例，可选）

#### 无参数函数

```python
def get_current_time() -> str:
    """获取当前时间字符串."""
    return datetime.now().isoformat()
```

#### 有参数函数

```python
def create_novel(
    title: str,
    genre: str,
    author_id: UUID,
    description: Optional[str] = None,
) -> Novel:
    """
    创建新小说.
    
    在数据库中创建新的小说记录，并初始化相关配置。
    
    Args:
        title: 小说标题，必须唯一
        genre: 小说类型，如"玄幻"、"都市"等
        author_id: 作者 ID
        description: 小说简介，可选
    
    Returns:
        Novel: 创建的小说对象
    
    Raises:
        NovelError: 当小说标题已存在时
        ValidationError: 当参数验证失败时
    
    Example:
        >>> novel = create_novel("星际穿越", "科幻", author_id)
        >>> print(novel.title)
        '星际穿越'
    """
```

#### 类方法

```python
class NovelService:
    """小说服务类."""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelService":
        """
        从字典创建服务实例.
        
        Args:
            data: 包含服务配置的字典
        
        Returns:
            NovelService: 服务实例
        """
```

### 4. 参数格式

Args 部分使用以下格式：

```
Args:
    param_name: 参数描述，可以跨多行
        如果需要详细说明，可以缩进 continuation
    another_param: 另一个参数描述
```

### 5. 返回值格式

Returns 部分使用以下格式：

```
Returns:
    类型：返回值描述
```

或对于命名返回值：

```
Returns:
    result: 处理结果
        - success: 是否成功
        - data: 返回数据
```

### 6. 异常格式

Raises 部分使用以下格式：

```
Raises:
    ExceptionType: 异常描述，说明在什么情况下会抛出
```

## 特殊场景

### 1. 属性（Properties）

```python
@property
def novel_count(self) -> int:
    """
    小说总数.
    
    Returns:
        int: 数据库中的小说记录数
    """
```

### 2. 私有方法

私有方法（以 `_` 开头）可以选择性添加文档字符串，但建议添加以方便维护。

```python
def _validate_config(self) -> None:
    """验证配置项的有效性."""
```

### 3. 覆盖方法

覆盖父类方法时，如果行为完全相同，可以使用简短文档字符串引用父类。

```python
def save(self) -> None:
    """保存对象到数据库。见父类文档."""
```

如果行为有差异，应详细说明差异。

### 4. 装饰器

带装饰器的函数，文档字符串应描述函数的功能，而非装饰器的行为。

```python
@retry(max_attempts=3)
def fetch_data(url: str) -> Dict:
    """
    从 URL 获取数据.
    
    自动重试最多 3 次。
    
    Args:
        url: 数据源 URL
    
    Returns:
        解析后的 JSON 数据
    """
```

## 工具集成

### 1. pydocstyle 检查

项目已配置 pydocstyle 进行文档字符串检查：

```bash
# 运行检查
pydocstyle backend/ core/ agents/

# 在 CI 中
make lint  # 包含 pydocstyle 检查
```

### 2. IDE 支持

- **VS Code**: 安装 Python 扩展，自动提示文档字符串模板
- **PyCharm**: 内置支持，输入 `"""` 自动生成模板

### 3. 自动生成

使用 `interrogate` 检查文档覆盖率：

```bash
interrogate -v backend/ core/
```

## 中文文档指南

### 1. 标点符号

- 中文描述使用中文标点（。！？）
- 英文术语保持英文（如 API、URL、ID）
- 代码引用使用反引号：`param_name`

### 2. 术语一致性

- 统一使用"小说"而非"作品"、"书籍"
- 统一使用"章节"而非"回"、"节"
- 统一使用"角色"而非"人物"、"人设"

### 3. 翻译规范

- Exception → 异常
- Error → 错误
- Warning → 警告
- Debug → 调试
- Config → 配置

## 示例模板

### 完整函数示例

```python
async def generate_chapter(
    novel_id: UUID,
    chapter_number: int,
    context: GenerationContext,
    retry_count: int = 3,
) -> Chapter:
    """
    生成小说章节.
    
    基于世界观、角色、大纲等上下文信息，使用 LLM 生成章节内容。
    包含自动重试和质量检查机制。
    
    Args:
        novel_id: 小说 ID
        chapter_number: 章节编号，从 1 开始
        context: 生成上下文，包含世界观、角色等信息
        retry_count: 最大重试次数，默认为 3
    
    Returns:
        Chapter: 生成的章节对象，包含内容和元数据
    
    Raises:
        ChapterError: 当章节生成失败时
        LLMError: 当 LLM API 调用失败时
        ValidationError: 当参数验证失败时
    
    Example:
        >>> context = GenerationContext(novel_id)
        >>> chapter = await generate_chapter(novel_id, 1, context)
        >>> print(chapter.title)
        '第一章：初遇'
    
    Note:
        - 生成过程可能需要 10-30 秒
        - 质量检查未通过时会自动重试
        - 超过重试次数后抛出 ChapterError
    """
```

## 检查清单

在提交代码前，请确认：

- [ ] 所有公共函数/方法都有文档字符串
- [ ] 所有公共类都有文档字符串
- [ ] 模块文件有模块级文档字符串
- [ ] 参数描述清晰准确
- [ ] 返回值类型和描述完整
- [ ] 异常情况有说明
- [ ] 使用中文描述（技术术语除外）
- [ ] 遵循 Google Style 格式
- [ ] 通过 pydocstyle 检查

## 参考资料

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [Sphinx Documentation](https://www.sphinx-doc.org/en/master/)
- [pydocstyle](http://www.pydocstyle.org/en/stable/)
