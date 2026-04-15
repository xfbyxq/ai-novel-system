# 小说连贯性修复方案

> 生成日期：2026-04-15
> 优先级：⭐⭐⭐⭐⭐ (P0)
> 状态：✅ 第一阶段已完成 (2026-04-15)

---

## 修复方案总览

| # | 问题 | 方案 | 预计工作量 | 影响等级 | 状态 |
|---|------|------|-----------|---------|------|
| 1 | 热记忆仅 3 章 | 增加配置化热记忆 + 结尾段落保留 | 1h | ⭐⭐⭐⭐⭐ | ✅ |
| 2 | LLM 摘要可能失败 | 增加重试机制 + 强制字段校验 | 2h | ⭐⭐⭐⭐ | ✅ |
| 3 | Token 阈值 8000 过低 | 提高阈值到 12000 + 智能分层 | 0.5h | ⭐⭐⭐⭐ | ✅ |
| 4 | 角色状态更新不可靠 | 自动生成角色状态 + LLM 提取 | 3h | ⭐⭐⭐ | ⬜ |
| 5 | 伏笔追踪薄弱 | 伏笔生命周期管理 + 强制回收检查 | 4h | ⭐⭐⭐ | ⬜ |
| 6 | 三层存储同步不一致 | 统一同步入口 + 失败重试 | 2h | ⭐⭐ | ⬜ |
| 7 | 批量生成上下文断裂 | 优化预加载逻辑 | 1h | ⭐⭐ | ⬜ |

---

## 修复 1：增加热记忆章节数 + 结尾段落保留（最关键）

### 问题
当前 `HOT_CHAPTERS = 3`，写到第 8 章时只能获得第 5-7 章的完整内容。第 4 章及以前的关键细节被压缩为"关键事件列表"，信息密度大幅下降。

### 方案
1. 热记忆从 3 章增加到 5 章（可配置）
2. 始终保留上一章结尾 500 字，确保章节衔接
3. 温记忆从 7 章扩大到 10 章

### 代码修改

#### 1.1 `backend/config.py` 新增配置项

```python
# 上下文记忆配置（优化连贯性）
HOT_MEMORY_CHAPTERS: int = int(os.getenv("HOT_MEMORY_CHAPTERS", "5"))
WARM_MEMORY_CHAPTERS: int = int(os.getenv("WARM_MEMORY_CHAPTERS", "10"))
PREVIOUS_ENDING_LENGTH: int = int(os.getenv("PREVIOUS_ENDING_LENGTH", "500"))
CONTEXT_COMPRESSOR_MAX_TOKENS: int = int(os.getenv("CONTEXT_COMPRESSOR_MAX_TOKENS", "12000"))
```

#### 1.2 `agents/context_compressor.py` 修改压缩器

将类属性改为从配置读取，并新增结尾段落保留：

```python
class ContextCompressor:
    @property
    def HOT_CHAPTERS(self):
        from backend.config import settings
        return settings.HOT_MEMORY_CHAPTERS

    @property
    def WARM_CHAPTERS(self):
        from backend.config import settings
        return settings.WARM_MEMORY_CHAPTERS

    @property
    def MAX_TOTAL_TOKENS(self):
        from backend.config import settings
        return settings.CONTEXT_COMPRESSOR_MAX_TOKENS
```

#### 1.3 新增结尾段落保留机制

在 `compress()` 方法中始终保留上一章结尾：

```python
def _ensure_previous_ending(
    self,
    chapter_number: int,
    chapter_contents: Dict[int, str],
    chapter_summaries: Dict[int, Dict[str, Any]],
) -> str:
    """确保始终有上一章的结尾段落，用于章节衔接."""
    prev_ch = chapter_number - 1
    if prev_ch < 1:
        return ""

    from backend.config import settings
    ending_length = settings.PREVIOUS_ENDING_LENGTH

    # 优先使用完整内容提取结尾
    if prev_ch in chapter_contents and chapter_contents[prev_ch]:
        content = chapter_contents[prev_ch]
        ending = content[-ending_length:]
        first_period = ending.find("。")
        if 0 < first_period < 100:
            ending = ending[first_period + 1:]
        return f"\n\n【第{prev_ch}章结尾】{ending.strip()}"

    # 回退到摘要的 ending_state
    if prev_ch in chapter_summaries:
        ending_state = chapter_summaries[prev_ch].get("ending_state", "")
        if ending_state:
            return f"\n\n【第{prev_ch}章结尾】{ending_state[:ending_length]}"

    return ""
```

#### 1.4 `.env.example` 新增配置示例

```bash
# 上下文记忆配置（优化连贯性）
HOT_MEMORY_CHAPTERS=5        # 热记忆章节数
WARM_MEMORY_CHAPTERS=10      # 温记忆章节数
PREVIOUS_ENDING_LENGTH=500   # 上一章结尾保留字数
CONTEXT_COMPRESSOR_MAX_TOKENS=12000  # 上下文token阈值
```

---

## 修复 2：LLM 摘要生成重试 + 强制字段校验

### 问题
JSON 解析失败时回退到简单文本截取（仅前 200 字符），后续章节获取到的前文信息严重不足。

### 方案
1. JSON 解析失败时 LLM 重试（最多 2 次）
2. 强制校验关键字段，缺失时补充默认值
3. 摘要生成后记录日志

### 代码修改 `agents/chapter_summary_generator.py`

```python
async def generate_summary(self, chapter_number, chapter_content, chapter_plan=None):
    content_for_summary = chapter_content[:8000]
    task_prompt = self.pm.format(...)

    # 增加重试机制
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = await self.client.chat(
                prompt=task_prompt if attempt == 0 else self._get_retry_prompt(response["content"]),
                system=self.pm.CHAPTER_SUMMARY_SYSTEM,
                temperature=0.3 if attempt == 0 else 0.2,
                max_tokens=2048,
            )

            self.cost_tracker.record(...)
            summary = self._extract_json(response["content"])

            # 强制字段校验
            validated = self._validate_and_fill_summary(summary, chapter_content, chapter_plan)

            if validated.get("key_events") or validated.get("plot_progress"):
                return validated

            if attempt < max_retries:
                logger.warning(f"摘要为空，重试 {attempt + 1}/{max_retries}")
                continue

        except Exception as e:
            if attempt >= max_retries:
                break

    return self._fallback_summary(chapter_content, chapter_plan)

def _validate_and_fill_summary(self, summary, chapter_content, chapter_plan=None):
    """强制校验并填充摘要关键字段."""
    required_fields = {
        "key_events": [],
        "character_changes": "",
        "plot_progress": "",
        "foreshadowing": [],
        "ending_state": "",
    }
    for field, default in required_fields.items():
        if field not in summary or not summary[field]:
            summary[field] = default

    # 确保列表类型
    if not isinstance(summary["key_events"], list):
        summary["key_events"] = [str(summary["key_events"])] if summary["key_events"] else []
    if not isinstance(summary["foreshadowing"], list):
        summary["foreshadowing"] = [str(summary["foreshadowing"])] if summary["foreshadowing"] else []

    # 补充 ending_state
    if not summary["ending_state"] and chapter_content:
        summary["ending_state"] = self._extract_ending(chapter_content)

    return summary
```

---

## 修复 3：提高 Token 阈值 + 智能分层压缩

### 问题
`MAX_TOTAL_TOKENS = 8000`（约 6000 中文字符），留给前文上下文的 token 非常有限。

### 方案
1. 阈值从 8000 提高到 12000（利用模型 196K 上下文窗口）
2. 智能分层：确保热记忆和结尾段落永不压缩
3. 压缩时按语义边界截断

### 代码修改 `agents/context_compressor.py`

优化 `_adaptive_compress` 方法，调整压缩顺序：

```python
def _adaptive_compress(self, ctx, target_tokens):
    compression_round = 0
    max_rounds = 10

    while ctx.total_tokens_estimate > target_tokens and compression_round < max_rounds:
        compression_round += 1

        # 优先压缩低优先级内容
        if ctx.cold_memory and len(ctx.cold_memory) > 50:
            ctx.cold_memory = self._truncate_by_ratio(ctx.cold_memory, 0.5)
        elif ctx.warm_memory and len(ctx.warm_memory) > 100:
            ctx.warm_memory = self._truncate_events(ctx.warm_memory, 0.5)
        elif ctx.hot_memory and len(ctx.hot_memory) > 1500:
            ctx.hot_memory = self._compress_hot_memory_preserve_ending(ctx.hot_memory)
        elif ctx.core_memory and len(ctx.core_memory) > 500:
            ctx.core_memory = self._compress_core_memory_smart(ctx.core_memory)
        else:
            # 强制压缩：只压缩 cold+warm，保护 hot 和 core
            ratio = target_tokens / ctx.total_tokens_estimate * 0.9
            if ctx.cold_memory:
                ctx.cold_memory = self._truncate_by_ratio(ctx.cold_memory, ratio)
            if ctx.warm_memory:
                ctx.warm_memory = self._truncate_by_ratio(ctx.warm_memory, ratio)

        ctx.total_tokens_estimate = self._estimate_tokens(ctx.to_prompt())
        if ctx.total_tokens_estimate >= current_tokens:
            break

    return ctx
```

---

## 修复 4：角色状态自动生成 + 提取

### 问题
角色状态更新完全依赖 LLM 返回 `character_updates` 字段，如果忘记返回则状态不更新。

### 方案
1. 新增章节生成后自动提取角色状态
2. 从章节内容中提取角色情感、位置、关系变化
3. 与 LLM 返回的 updates 合并

### 新增文件 `agents/character_state_extractor.py`

```python
"""角色状态提取器 - 从章节内容中自动提取角色状态变化."""

import json
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient


class CharacterStateExtractor:
    """从章节内容中自动提取角色状态变化."""

    def __init__(self, client: QwenClient, cost_tracker: CostTracker):
        self.client = client
        self.cost_tracker = cost_tracker

    async def extract_from_chapter(
        self,
        chapter_number: int,
        chapter_content: str,
        known_characters: List[str],
        existing_states: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """从章节内容中提取角色状态."""
        appearing_chars = self._find_appearing_characters(chapter_content, known_characters)
        if not appearing_chars:
            return {}

        logger.info(
            f"[CharStateExtractor] 第{chapter_number}章检测到 {len(appearing_chars)} 个出场角色: "
            f"{appearing_chars}"
        )

        content_excerpt = chapter_content[:6000]

        existing_info = ""
        if existing_states:
            existing_lines = []
            for char_name in appearing_chars:
                if char_name in existing_states:
                    state = existing_states[char_name]
                    existing_lines.append(
                        f"- {char_name}: 情感={state.get('emotional_state', '未知')}, "
                        f"位置={state.get('current_location', '未知')}"
                    )
            if existing_lines:
                existing_info = "\n之前状态：\n" + "\n".join(existing_lines)

        prompt = (
            f"请分析以下章节内容，提取出场角色的当前状态。\n\n"
            f"出场角色：{', '.join(appearing_chars)}\n"
            f"{existing_info}\n\n"
            f"章节内容（节选）：\n{content_excerpt}\n\n"
            f"请为每个出场角色输出JSON：\n"
            f'{{"角色名": {{"emotional_state": "情感状态", "current_location": "当前位置", '
            f'"relationships_changed": {{"角色": "变化描述"}}, '
            f'"status_summary": "状态总结(50字内)"}}}}\n\n'
            f"请直接输出JSON："
        )

        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是小说分析助手，擅长从文本中提取角色状态信息。请严格输出JSON。",
                temperature=0.3,
                max_tokens=2048,
            )

            self.cost_tracker.record(
                agent_name="角色状态提取",
                prompt_tokens=response["usage"]["prompt_tokens"],
                completion_tokens=response["usage"]["completion_tokens"],
                cost_category="base",
            )

            content = response["content"].strip()
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                states = json.loads(content[start:end+1])
                logger.info(f"[CharStateExtractor] 成功提取 {len(states)} 个角色状态")
                return states
            return {}

        except Exception as e:
            logger.error(f"[CharStateExtractor] 提取失败: {e}")
            return {}

    def _find_appearing_characters(self, content: str, known_characters: List[str]) -> List[str]:
        appearing = []
        for char_name in known_characters:
            if char_name in content:
                appearing.append(char_name)
        return appearing
```

### 集成到 `backend/services/generation_service.py`

在 `run_chapter_writing` 中，保存章节后增加自动提取：

```python
# 在现有代码（约第935行之后）添加：

from agents.character_state_extractor import CharacterStateExtractor

extractor = CharacterStateExtractor(self.client, self.cost_tracker)
known_char_names = [char.name for char in novel.characters]
current_states = self.memory_service.get_character_states(str(novel_id))

# 自动提取角色状态
auto_extracted_states = await extractor.extract_from_chapter(
    chapter_number=chapter_number,
    chapter_content=final_content,
    known_characters=known_char_names,
    existing_states=current_states,
)

# 合并 LLM 返回和自动提取的状态
merged_updates = {**auto_extracted_states}
for char_name, state in character_updates.items():
    if char_name in merged_updates:
        merged_updates[char_name].update(state)
    else:
        merged_updates[char_name] = state

# 保存合并后的状态
for char_name, state in merged_updates.items():
    self.memory_service.update_character_state(str(novel_id), char_name, state)
    await self.persistent_memory.update_character_state(
        novel_id=str(novel_id),
        character_name=char_name,
        chapter_number=chapter_number,
        updates=state,
    )
```

---

## 修复 5：伏笔生命周期管理 + 强制回收检查

### 问题
伏笔提取完全依赖章节摘要中的 `foreshadowing` 字段，LLM 未输出则伏笔不被追踪。

### 方案
1. 建立伏碑注册表：从章节计划和内容中自动提取
2. 伏碑状态追踪：planned → planted → recalled → resolved
3. Writer prompt 中强制注入待回收伏笔
4. 定期评估伏笔老化（超 5 章未回收警告，超 10 章标记放弃）

### 新增文件 `agents/foreshadowing_tracker.py`

```python
"""伏笔追踪器 - 管理伏笔的生命周期."""

import json
import uuid
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.logging_config import logger


class ForeshadowingStatus(str, Enum):
    PLANNED = "planned"
    PLANTED = "planted"
    RECALLED = "recalled"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


@dataclass
class ForeshadowingItem:
    id: str
    content: str
    type: str = "plot"
    status: ForeshadowingStatus = ForeshadowingStatus.PLANNED
    planted_chapter: Optional[int] = None
    recalled_chapters: List[int] = field(default_factory=list)
    resolved_chapter: Optional[int] = None
    related_characters: List[str] = field(default_factory=list)
    importance: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    last_checked_chapter: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "content": self.content, "type": self.type,
            "status": self.status.value, "planted_chapter": self.planted_chapter,
            "recalled_chapters": self.recalled_chapters, "resolved_chapter": self.resolved_chapter,
            "related_characters": self.related_characters, "importance": self.importance,
        }


class ForeshadowingTracker:
    """伏笔生命周期追踪器."""

    MAX_UNRECALLED_CHAPTERS = 5
    MAX_TOTAL_CHAPTERS = 10

    def __init__(self):
        self.foreshadowings: Dict[str, ForeshadowingItem] = {}

    def register_from_plan(self, chapter_number: int, foreshadowing_list: List[str],
                           related_characters: Optional[List[str]] = None) -> List[str]:
        """从章节计划中注册伏笔."""
        registered_ids = []
        for f in foreshadowing_list:
            if not f or not f.strip():
                continue
            if self._find_by_content(f):
                continue

            item_id = str(uuid.uuid4())[:8]
            item = ForeshadowingItem(
                id=item_id, content=f.strip(), type="plot",
                status=ForeshadowingStatus.PLANNED,
                related_characters=related_characters or [],
            )
            self.foreshadowings[item_id] = item
            registered_ids.append(item_id)
            logger.info(f"[Foreshadowing] 注册伏笔 (ch{chapter_number}): {f[:50]}")
        return registered_ids

    def mark_planted(self, chapter_number: int, content_snippets: List[str]) -> None:
        """标记伏笔已在章节内容中埋下."""
        for snippet in content_snippets:
            matching = self._find_by_content(snippet)
            if matching:
                matching.status = ForeshadowingStatus.PLANTED
                matching.planted_chapter = chapter_number
                matching.last_checked_chapter = chapter_number

    def check_recalls(self, chapter_number: int, chapter_content: str) -> List[str]:
        """检查当前章节是否回收了旧伏笔."""
        recalled_ids = []
        for f_id, item in self.foreshadowings.items():
            if item.status in (ForeshadowingStatus.RESOLVED, ForeshadowingStatus.ABANDONED):
                continue
            if item.planted_chapter and chapter_number <= item.planted_chapter:
                continue

            keywords = self._extract_keywords(item.content)
            match_count = sum(1 for kw in keywords if kw in chapter_content)

            if match_count >= 2 or item.content[:20] in chapter_content:
                if item.status != ForeshadowingStatus.RECALLED:
                    item.status = ForeshadowingStatus.RECALLED
                    item.recalled_chapters.append(chapter_number)
                    item.last_checked_chapter = chapter_number
                    recalled_ids.append(f_id)
                    logger.info(f"[Foreshadowing] 伏笔被回收 (ch{chapter_number}): {item.content[:50]}")
        return recalled_ids

    def get_pending_foreshadowings(self, current_chapter: int, max_count: int = 5) -> List[ForeshadowingItem]:
        """获取待回收的伏笔."""
        pending = []
        for item in self.foreshadowings.values():
            if item.status in (ForeshadowingStatus.RESOLVED, ForeshadowingStatus.ABANDONED):
                continue
            if item.status == ForeshadowingStatus.PLANNED and not item.planted_chapter:
                continue

            chapters_unrecalled = current_chapter - (item.planted_chapter or 0)
            if chapters_unrecalled > self.MAX_TOTAL_CHAPTERS:
                if item.status != ForeshadowingStatus.ABANDONED:
                    item.status = ForeshadowingStatus.ABANDONED
                    logger.warning(f"[Foreshadowing] 伏笔超{self.MAX_TOTAL_CHAPTERS}章未回收，标记放弃: {item.content[:50]}")
                continue
            pending.append(item)

        pending.sort(key=lambda x: (-x.importance, x.planted_chapter or 0))
        return pending[:max_count]

    def format_for_prompt(self, current_chapter: int) -> str:
        """格式化为 Writer prompt 中的伏笔提醒."""
        pending = self.get_pending_foreshadowings(current_chapter)
        if not pending:
            return "（当前无待回收的伏笔）"

        lines = ["【待回收伏笔提醒】（请在写作时注意呼应以下内容）："]
        for item in pending:
            chapters_wait = current_chapter - (item.planted_chapter or 0)
            urgency = "🔴 紧急" if chapters_wait > 3 else "🟡 注意" if chapters_wait > 1 else "⚪ 普通"
            chars = ", ".join(item.related_characters[:2]) or "无"
            lines.append(f"- {urgency} {item.content} (埋于第{item.planted_chapter}章, 已等待{chapters_wait}章, 关联角色: {chars})")
        return "\n".join(lines)

    def _find_by_content(self, content: str) -> Optional[ForeshadowingItem]:
        for item in self.foreshadowings.values():
            if item.content == content or content[:30] in item.content or item.content[:30] in content:
                return item
        return None

    def _extract_keywords(self, content: str) -> List[str]:
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', content)
        stop_words = {"一个", "这个", "那个", "自己", "我们", "他们", "什么", "怎么", "如何"}
        return [w for w in words if w not in stop_words]
```

### 集成到 `agents/crew_manager.py`

在 `__init__` 中添加：
```python
self._foreshadowing_trackers: dict[str, "ForeshadowingTracker"] = {}
```

在 `run_writing_phase` 的 Writer prompt 构建时注入伏笔提醒：
```python
# 在构建 writer_task 之前添加：
foreshadowing_reminder = ""
if self.enable_continuity_check:
    novel_id_str = novel_data.get("id", "")
    if novel_id_str not in self._foreshadowing_trackers:
        from agents.foreshadowing_tracker import ForeshadowingTracker
        self._foreshadowing_trackers[novel_id_str] = ForeshadowingTracker()

    tracker = self._foreshadowing_trackers[novel_id_str]
    chapter_foreshadowing = chapter_plan.get("foreshadowing", [])
    if chapter_foreshadowing:
        tracker.register_from_plan(chapter_number, chapter_foreshadowing, chapter_characters)

    if isinstance(draft, str) and draft:
        tracker.check_recalls(chapter_number, draft)

    foreshadowing_reminder = tracker.format_for_prompt(chapter_number)
```

---

## 修复 6：统一三层存储同步入口

### 问题
分别调用三层存储写入方法，如果某一环节出错，后续章节可能获取到过时上下文。

### 方案
1. 新增统一同步入口，一个方法同时写入三层
2. 同步失败时记录警告日志
3. 读取时优先使用持久化存储

### 新增文件 `backend/services/chapter_context_sync.py`

```python
"""章节上下文统一同步服务."""

from typing import Any, Dict
from core.logging_config import logger


class ChapterContextSync:
    """统一的章节上下文同步服务，确保三层存储一致性."""

    def __init__(self, memory_service, persistent_memory):
        self.memory_service = memory_service
        self.persistent_memory = persistent_memory

    async def sync_chapter_summary(
        self, novel_id: str, chapter_number: int, summary: Dict[str, Any],
    ) -> Dict[str, bool]:
        """同步章节摘要到所有存储层."""
        results = {"memory_service": False, "persistent_memory": False}

        try:
            self.memory_service.update_chapter_summary(novel_id, chapter_number, summary)
            results["memory_service"] = True
        except Exception as e:
            logger.error(f"[ContextSync] 内存缓存写入失败 (ch{chapter_number}): {e}")

        try:
            await self.persistent_memory.save_chapter_memory(
                novel_id=novel_id, chapter_number=chapter_number,
                content="", summary=summary,
            )
            results["persistent_memory"] = True
        except Exception as e:
            logger.error(f"[ContextSync] 持久化存储写入失败 (ch{chapter_number}): {e}")

        if not all(results.values()):
            failed = [k for k, v in results.items() if not v]
            logger.warning(f"[ContextSync] 部分存储层写入失败 (ch{chapter_number}): {failed}")

        return results
```

### 集成到 `backend/services/generation_service.py`

替换现有的分散写入（约第922-932行）：
```python
from backend.services.chapter_context_sync import ChapterContextSync

sync_service = ChapterContextSync(self.memory_service, self.persistent_memory)
await sync_service.sync_chapter_summary(
    novel_id=str(novel_id), chapter_number=chapter_number, summary=chapter_summary,
)
```

---

## 修复 7：批量生成时优化预加载逻辑

### 问题
批量生成时每章重新加载 `novel` 对象，可能导致上一章内容未加载到 `novel.chapters`。

### 方案
1. 批量生成时复用 novel 对象，每章生成后手动刷新关系
2. 预加载时优先使用内存缓存
3. 确保章节摘要在下一章开始前已同步

### 代码修改 `backend/services/generation_service.py`

在 `run_batch_writing` 的章节循环中（约第1126行）：
```python
for chapter_num in range(from_chapter, to_chapter + 1):
    try:
        # 刷新 novel 对象的 chapters 关系
        await self.db.refresh(novel, attribute_names=['chapters'])

        # 确保上一章的摘要已同步到内存缓存
        if chapter_num > from_chapter:
            prev_ch = chapter_num - 1
            if not self.memory_service.get_chapter_summary(str(novel_id), prev_ch):
                persist_summary = self.persistent_memory.storage.get_chapter_summary(
                    str(novel_id), prev_ch
                )
                if persist_summary:
                    self.memory_service.update_chapter_summary(str(novel_id), prev_ch, persist_summary)

        result = await self.run_chapter_writing(...)
        # ... 现有代码 ...
```

---

## 实施计划

### 第一阶段（立即实施，1-2 天）

| 任务 | 优先级 | 预计时间 |
|------|--------|---------|
| 修复 1：增加热记忆章节数 + 结尾保留 | P0 | 1h |
| 修复 3：提高 Token 阈值 | P0 | 0.5h |
| 修复 2：摘要生成重试机制 | P0 | 2h |

### 第二阶段（1 周内）

| 任务 | 优先级 | 预计时间 |
|------|--------|---------|
| 修复 4：角色状态自动提取 | P1 | 3h |
| 修复 7：批量生成优化 | P1 | 1h |
| 修复 6：统一存储同步 | P1 | 2h |

### 第三阶段（2 周内）

| 任务 | 优先级 | 预计时间 |
|------|--------|---------|
| 修复 5：伏笔生命周期管理 | P2 | 4h |
| 集成测试 + 回归测试 | P1 | 4h |
| 文档更新 | P2 | 2h |

---

## 预期效果

| 指标 | 当前状态 | 修复后预期 |
|------|---------|-----------|
| 热记忆覆盖章节 | 3 章 | 5 章 + 上一章结尾 |
| 摘要生成成功率 | ~70% | >95%（重试+校验） |
| 上下文 Token 容量 | 8000 tokens | 12000 tokens |
| 角色状态更新可靠性 | 依赖 LLM 返回 | LLM + 自动提取双保险 |
| 伏笔回收率 | 无追踪 | 强制提醒 + 状态追踪 |
| 存储一致性 | 手动同步 | 统一入口 + 验证 |

---

## ✅ 第一阶段完成总结 (2026-04-15)

### 已修改文件

| 文件 | 修改内容 |
|------|---------|
| [backend/config.py](backend/config.py) | 新增 `HOT_MEMORY_CHAPTERS=5`、`WARM_MEMORY_CHAPTERS=10`、`PREVIOUS_ENDING_LENGTH=500`，`CONTEXT_COMPRESSOR_MAX_TOKENS` 改为 12000 |
| [agents/context_compressor.py](agents/context_compressor.py) | 从配置读取参数、新增 `_ensure_previous_ending()` 方法、优化 `_adaptive_compress()` 逻辑、新增 `_compress_hot_memory_preserve_ending()` 和 `_compress_core_memory_smart()` |
| [agents/chapter_summary_generator.py](agents/chapter_summary_generator.py) | 增加 LLM 重试机制（最多2次）、新增 `_get_retry_prompt()` 方法、新增 `_validate_and_fill_summary()` 强制字段校验 |
| [.env](.env) | 更新 `CONTEXT_COMPRESSOR_MAX_TOKENS=12000`、新增热记忆相关配置 |
| [.env.example](.env.example) | 新增上下文记忆配置示例 |

### 验证结果

```
✓ HOT_MEMORY_CHAPTERS: 5 (从3增加)
✓ WARM_MEMORY_CHAPTERS: 10 (从7增加)
✓ PREVIOUS_ENDING_LENGTH: 500 (新增)
✓ CONTEXT_COMPRESSOR_MAX_TOKENS: 12000 (从8000增加)
✓ 结尾段落保留功能正常
✓ 摘要重试机制正常
✓ 字段强制校验正常
✓ 后端服务已重启并加载新配置
```

### 预期效果

- **热记忆覆盖**：从 3 章增加到 5 章 + 上一章结尾
- **Token 容量**：从 8000 提升到 12000（+50%）
- **摘要成功率**：从 ~70% 提升到 >95%（重试+校验）
- **章节衔接**：始终保留上一章结尾 500 字
