# 小说内容评估系统优化方案

## Context

用户提供了一份详细的小说评估报告示例，包含：
- 分项评估（连贯性★★★☆☆、合理性★★★☆☆、趣味性★★★★☆）
- 问题描述表格（位置、问题描述、具体表现）
- 分优先级的修订建议（影响阅读体验、提升精彩度、细节打磨）
- 总结评分表格

当前系统虽有审查循环机制（Writer-Editor），但评估报告输出过于简单，缺少：
1. 精确评估维度不足（现有5维度，需扩展到8维度）
2. 聚合维度评分展示（连贯性、合理性、趣味性）
3. 问题位置定位和具体表现描述
4. 优先级分类修订指导

**目标**：增强系统的评估能力，扩展精确维度、添加聚合维度展示、生成详细评估报告、更精准地指导修订。

---

## 评估维度设计

### 精确维度（8个）

| 维度 | 字段名 | 权重 | 说明 |
|-----|--------|------|------|
| 爽感设计 | satisfaction_design | 20% | 爽点设计、卡章效果 |
| 伏笔设计 | foreshadowing | **15%（新增）** | 伏笔埋设、铺垫、后续兑现 |
| 角色辨识度 | character_distinctiveness | **15%（新增）** | 主角特色、职业能力发挥 |
| 情节逻辑 | plot_logic | 12% | 情节逻辑、因果关系 |
| 角色一致性 | character_consistency | 12% | 角色称呼、行为矛盾 |
| 设定一致性 | setting_consistency | **10%（新增）** | 世界观、角色设定、时间线一致 |
| 节奏把控 | pacing | 8% | 场景节奏变化 |
| 语言流畅 | fluency | 8% | 语言流畅、衔接 |

### 聚合维度（3个）

从8个精确维度聚合计算，以星级格式展示：

| 聚合维度 | 聚合来源 | 展示格式 |
|---------|---------|---------|
| 连贯性 (coherence) | plot_logic(40%) + character_consistency(35%) + setting_consistency(25%) | ★★★☆☆ |
| 合理性 (plausibility) | plot_logic(35%) + character_consistency(30%) + setting_consistency(20%) + foreshadowing(15%) | ★★★☆☆ |
| 趣味性 (engagement) | satisfaction_design(50%) + foreshadowing(25%) + pacing(15%) + character_distinctiveness(10%) | ★★★★☆ |

---

## Implementation Steps

### Step 1: 新建详细问题数据结构

**文件**: `agents/base/detailed_issue.py` (新建)

创建以下数据结构：
```python
class PriorityCategory(Enum):
    READING_EXPERIENCE = "reading_experience"  # 影响阅读体验
    EXCITEMENT = "excitement"                  # 提升精彩度  
    POLISH = "polish"                          # 细节打磨

@dataclass
class IssueLocation:
    type: str          # "paragraph"/"scene"/"character"/"global"
    identifier: str    # 具体位置标识
    excerpt: str       # 问题片段摘录（可选）

@dataclass  
class DetailedIssue:
    location: IssueLocation
    description: str              # 问题描述（精炼概括）
    manifestation: List[str]      # 具体表现（原文中的具体表现）
    severity: str                 # "high"/"medium"/"low"
    priority_category: str        # 优先级分类
    suggestion: str               # 修订建议
    related_dimensions: List[str] # 关联维度
```

### Step 2: 扩展 ChapterQualityReport

**文件**: `agents/base/quality_report.py`

在 `ChapterQualityReport` 类中修改和添加：

1. **更新精确维度权重**：
```python
_weights: Dict[str, float] = {
    "satisfaction_design": 0.20,       # 爽感设计
    "foreshadowing": 0.15,             # 伏笔设计（新增）
    "character_distinctiveness": 0.15, # 角色辨识度（新增）
    "plot_logic": 0.12,                # 情节逻辑
    "character_consistency": 0.12,     # 角色一致性
    "setting_consistency": 0.10,       # 设定一致性（新增）
    "pacing": 0.08,                    # 节奏把控
    "fluency": 0.08,                   # 语言流畅
}
```

2. **新增聚合维度权重配置**：
```python
_aggregate_weights: Dict[str, Dict[str, float]] = {
    "coherence": {
        "plot_logic": 0.40,
        "character_consistency": 0.35,
        "setting_consistency": 0.25,
    },
    "plausibility": {
        "plot_logic": 0.35,
        "character_consistency": 0.30,
        "setting_consistency": 0.20,
        "foreshadowing": 0.15,
    },
    "engagement": {
        "satisfaction_design": 0.50,
        "foreshadowing": 0.25,
        "pacing": 0.15,
        "character_distinctiveness": 0.10,
    },
}
```

3. **新增字段**：
```python
detailed_issues: List[DetailedIssue] = field(default_factory=list)
revision_by_priority: Dict[str, List[str]] = field(default_factory=dict)
aggregate_dimension_ratings: Dict[str, str] = field(default_factory=dict)  # 星级格式
overall_assessment: str = ""
```

4. **聚合评分计算方法**：
```python
@property
def aggregate_scores(self) -> Dict[str, float]:
    """计算连贯性、合理性、趣味性评分"""

def _score_to_star(score: float) -> str:
    """将分数转换为星级表示 ★★★☆☆"""
```

### Step 3: 改进 Editor 提示词

**文件**: `agents/review_loop.py`

修改 `EDITOR_REVIEW_SYSTEM` 和 `EDITOR_REVIEW_TASK`：

1. **扩展精确评分维度说明**：
```
评分维度（1-10分）：
- satisfaction_design：爽感设计——是否有明确爽点（打脸/升级/逆转/揭秘）？
- foreshadowing：伏笔设计——伏笔是否埋设合理、是否有铺垫、后续是否兑现？
- character_distinctiveness：角色辨识度——主角是否有鲜明特征、职业能力是否发挥作用？
- plot_logic：情节逻辑——因果关系是否清晰、动机是否充分？
- character_consistency：角色一致性——称呼是否统一、行为是否矛盾？
- setting_consistency：设定一致性——世界观/角色设定/时间线是否前后一致？
- pacing：节奏把控——场景节奏是否有变化、是否过于相似？
- fluency：语言流畅度——表达是否流畅、衔接是否自然？
```

2. **添加聚合维度评分标准**：
```
【聚合维度评分标准】（根据精确维度计算，以星级展示）：
- 连贯性(coherence)：情节前后衔接、设定一致性、角色行为逻辑
- 合理性(plausibility)：动机合理性、事件因果关系、伏笔铺垫合理性
- 趣味性(engagement)：爽点设计、悬念布局、角色吸引力
```

3. **修改 JSON 输出格式**：
```json
{
    "overall_score": 7.5,
    "dimension_scores": {
        "satisfaction_design": 8.0,
        "foreshadowing": 6.5,
        "character_distinctiveness": 7.0,
        "plot_logic": 7.5,
        "character_consistency": 8.0,
        "setting_consistency": 7.0,
        "pacing": 7.5,
        "fluency": 8.0
    },
    "aggregate_dimension_ratings": {
        "coherence": "★★★☆☆",
        "plausibility": "★★★☆☆",
        "engagement": "★★★★☆"
    },
    "overall_assessment": "整体评价文本",
    "detailed_issues": [{
        "location": {"type": "paragraph", "identifier": "第3段", "excerpt": "..."},
        "description": "角色称呼不一致",
        "manifestation": ["开头称'李师姐'，中间称'李明月'"],
        "severity": "medium",
        "priority_category": "reading_experience",
        "suggestion": "统一使用一个称呼",
        "related_dimensions": ["coherence"]
    }],
    "revision_by_priority": {
        "reading_experience": ["建议1", "建议2"],
        "excitement": ["建议3"],
        "polish": ["建议4"]
    },
    "edited_content": "润色后的完整章节内容"
}
```

### Step 4: 更新 IssueTracker

**文件**: `agents/base/review_loop_base.py`

1. **扩展 IssueRecord**：
```python
@dataclass
class IssueRecord:
    # 现有字段...
    priority_category: str = "polish"
    location: Optional[Dict[str, str]] = None
    manifestation: List[str] = field(default_factory=list)
```

2. **修改 `_extract_issues()`**：支持提取 `detailed_issues` 字段

3. **修改 `format_for_builder()`**：按优先级分组输出，添加位置信息

### Step 5: 优化反馈构建方法

**文件**: `agents/review_loop.py`

修改 `_build_issues_text()` 方法：

```python
def _build_issues_text(self, report, review_data) -> str:
    """按优先级分组构建问题列表，包含位置定位"""
    
    # 分组输出
    lines.append("【优先级一：影响阅读体验 - 必须修改】")
    for issue in reading_experience_issues:
        lines.append(f"位置[{issue.location.identifier}]: {issue.description}")
        lines.append(f"  表现: {issue.manifestation}")
        lines.append(f"  建议: {issue.suggestion}")
    
    lines.append("【优先级二：提升精彩度 - 建议增强】")
    # ...
    
    lines.append("【优先级三：细节打磨 - 可考虑优化】")
    # ...
```

### Step 6: 扩展配置参数

**文件**: `backend/config.py`

添加功能开关：
```python
# --- 详细评估报告配置 ---
ENABLE_DETAILED_ISSUE_REPORT: bool = True  # 启用详细问题报告
ENABLE_PRIORITY_REVISION: bool = True      # 启用优先级分类修订
```

---

## Critical Files

| 文件路径 | 修改内容 |
|---------|---------|
| `agents/base/detailed_issue.py` | 新建：PriorityCategory, IssueLocation, DetailedIssue |
| `agents/base/quality_report.py` | 扩展ChapterQualityReport：聚合评分、详细问题字段 |
| `agents/review_loop.py` | 修改Editor提示词、反馈构建方法 |
| `agents/base/review_loop_base.py` | 扩展IssueRecord、IssueTracker |
| `backend/config.py` | 添加ENABLE_DETAILED_ISSUE_REPORT等配置 |

---

## Verification

### 单元测试

```bash
# 测试新数据结构
pytest tests/unit/test_detailed_issue.py -v

# 测试聚合评分计算
pytest tests/unit/test_quality_report.py -v -k "aggregate"

# 测试IssueTracker扩展
pytest tests/unit/test_issue_tracker.py -v
```

### 集成测试

```bash
# 测试完整审查循环
pytest tests/integration/test_review_loop.py -v

# 测试Editor输出新格式
pytest tests/integration/test_editor_output.py -v
```

### 手动验证

1. 启动开发环境：
```bash
./start_dev.sh
```

2. 调用章节生成API，检查评估报告输出格式：
```bash
curl -X POST http://localhost:8000/api/v1/generation/tasks \
  -H "Content-Type: application/json" \
  -d '{"novel_id": "xxx", "task_type": "writing", "chapter_number": 1}'
```

3. 查看日志确认新字段被正确解析：
```bash
docker-compose -f docker-compose.dev.yml logs -f backend | grep "detailed_issues"
```

---

## Backward Compatibility

- 保留原有字段 `dimension_scores`、`revision_suggestions`
- 新增字段为可选，不影响现有逻辑
- IssueTracker 同时支持旧格式和新格式
- 配置开关可关闭新功能回退到原有行为