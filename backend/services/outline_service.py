"""大纲服务 - 大纲梳理和细化服务

功能：
1. 生成完整大纲（基于世界观设定）
2. 分解大纲为章节配置
3. 获取章节大纲任务
4. 验证章节大纲一致性
5. 管理大纲版本历史
"""
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.logging_config import logger
from core.models.novel import Novel
from core.models.plot_outline import PlotOutline
from core.models.token_usage import TokenUsage
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient


class OutlineService:
    """
    大纲梳理和细化服务

    核心功能：
    1. 使用 LLM 生成完整大纲
    2. 将卷级大纲分解为章节级任务
    3. 验证章节大纲与卷大纲的一致性
    4. 管理大纲版本历史
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = QwenClient()
        self.cost_tracker = CostTracker()

    async def generate_complete_outline(
        self,
        novel_id: UUID,
        world_setting_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成完整大纲

        基于世界观设定，使用 LLM 生成完整的剧情大纲，包括：
        - 主线剧情
        - 支线剧情
        - 卷级大纲（含张力循环）
        - 关键转折点

        Args:
            novel_id: 小说 ID
            world_setting_data: 世界观设定数据

        Returns:
            完整大纲数据
        """
        logger.info(f"Starting to generate complete outline for novel {novel_id}")

        # 1. 加载小说基本信息
        novel_result = await self.db.execute(
            select(Novel)
            .where(Novel.id == novel_id)
            .options(selectinload(Novel.plot_outline))
        )
        novel = novel_result.scalar_one_or_none()

        if not novel:
            raise ValueError(f"小说 {novel_id} 不存在")

        # 2. 构建 LLM 提示词
        prompt = self._build_outline_generation_prompt(
            novel=novel,
            world_setting=world_setting_data
        )

        # 3. 调用 LLM 生成大纲
        self.cost_tracker.reset()
        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一位专业的小说大纲架构师，擅长构建完整的故事大纲体系。",
                temperature=0.7,
                max_tokens=8192,
            )

            # 4. 解析 LLM 响应
            outline_data = self._parse_llm_outline_response(response["content"])

            # 5. 保存或更新大纲
            await self._save_outline(novel_id, outline_data)

            # 6. 记录 token 使用
            await self._record_token_usage(novel_id, "outline_generation")

            logger.info(
                f"Complete outline generated for novel {novel_id}, "
                f"{len(outline_data.get('volumes', []))} volumes, "
                f"cost {response['usage']['total_tokens']} tokens"
            )

            return outline_data

        except Exception as e:
            logger.error(f"Failed to generate outline for novel {novel_id}: {e}")
            raise

    def _build_outline_generation_prompt(
        self,
        novel: Novel,
        world_setting: Dict[str, Any]
    ) -> str:
        """构建大纲生成提示词"""
        world_name = world_setting.get("world_name", "未命名世界")
        world_type = world_setting.get("world_type", "未知类型")
        power_system = world_setting.get("power_system", {})
        factions = world_setting.get("factions", [])

        prompt = f"""
# 任务：为小说《{novel.title}》生成完整大纲

## 小说基本信息
- **书名**: {novel.title}
- **类型**: {novel.genre}
- **标签**: {", ".join(novel.tags or [])}
- **长度类型**: {novel.length_type if novel.length_type else "中等"}
- **简介**: {novel.synopsis or "暂无"}

## 世界观设定
- **世界名称**: {world_name}
- **世界类型**: {world_type}
- **力量体系**: {json.dumps(power_system, ensure_ascii=False)}
- **势力组织**: {json.dumps(factions, ensure_ascii=False)}

## 要求

请生成一个完整的剧情大纲，包含以下内容：

### 1. 主线剧情（main_plot）
- **开端（Setup）**: 主角的初始状态和触发事件
- **发展（Conflict）**: 主要冲突和升级
- **高潮（Climax）**: 最大冲突和转折点
- **结局（Resolution）**: 冲突解决和角色归宿

### 2. 支线剧情（sub_plots）
至少设计 2-3 条支线剧情，每项包含：
- 名称（如"感情线"、"成长线"、"复仇线"）
- 涉及角色
- 发展弧光

### 3. 卷级大纲（volumes）
根据小说长度，设计 3-5 卷内容，每卷包含：
- **卷号**: 第 X 卷
- **卷名**: 2-4 字标题
- **章节范围**: [起始章，结束章]
- **卷概述**: 200-300 字描述
- **核心冲突**: 本卷的主要矛盾
- **张力循环（tension_cycles）**: 2-3 个欲扬先抑循环，每个包含：
  - chapters: [起始章，结束章]
  - suppress_events: 压制期事件列表
  - release_event: 释放期事件
- **关键事件（key_events）**: 3-5 个重大事件，每项包含：
  - chapter: 章节号
  - event: 事件描述
  - impact: 影响

### 4. 关键转折点（key_turning_points）
列出 5-8 个关键转折点，每项包含：
- chapter: 章节号
- event: 转折事件
- impact: 对剧情的影响

### 5. 高潮章节（climax_chapter）
指定全书高潮所在的章节号

## 输出格式

请严格按照以下 JSON 格式输出（不要包含 markdown 标记）：

```json
{{
  "structure_type": "三幕式/英雄之旅/多线叙事",
  "main_plot": {{
    "setup": "...",
    "conflict": "...",
    "climax": "...",
    "resolution": "..."
  }},
  "sub_plots": [
    {{
      "name": "感情线",
      "characters": ["角色 A", "角色 B"],
      "arc": "..."
    }}
  ],
  "volumes": [
    {{
      "number": 1,
      "title": "卷名",
      "chapters": [1, 20],
      "summary": "...",
      "core_conflict": "...",
      "tension_cycles": [
        {{
          "chapters": [1, 7],
          "suppress_events": ["事件 1", "事件 2"],
          "release_event": "事件 3"
        }}
      ],
      "key_events": [
        {{
          "chapter": 3,
          "event": "...",
          "impact": "..."
        }}
      ]
    }}
  ],
  "key_turning_points": [
    {{
      "chapter": 5,
      "event": "...",
      "impact": "..."
    }}
  ],
  "climax_chapter": 45
}}
```

注意：
1. 确保张力循环符合"欲扬先抑"原则
2. 关键事件应分布在张力循环的释放期
3. 各卷之间应有清晰的递进关系
4. 支线剧情应与主线交织
"""
        return prompt

    def _parse_llm_outline_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM 返回的大纲内容"""
        try:
            # 尝试直接解析 JSON
            content = content.strip()

            # 移除可能的 markdown 标记
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            outline_data = json.loads(content)

            # 验证必要字段
            required_fields = ["structure_type", "main_plot", "volumes"]
            for field in required_fields:
                if field not in outline_data:
                    logger.warning(f"Missing required field: {field}")
                    outline_data[field] = {} if field in ["main_plot"] else []

            return outline_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM outline response: {e}")
            # 返回空大纲结构
            return {
                "structure_type": "三幕式",
                "main_plot": {},
                "sub_plots": [],
                "volumes": [],
                "key_turning_points": [],
                "climax_chapter": None,
            }

    async def _save_outline(self, novel_id: UUID, outline_data: Dict[str, Any]):
        """保存大纲到数据库"""
        # 检查是否已存在大纲
        result = await self.db.execute(
            select(PlotOutline).where(PlotOutline.novel_id == novel_id)
        )
        existing_outline = result.scalar_one_or_none()

        if existing_outline:
            # 更新现有大纲
            existing_outline.structure_type = outline_data.get("structure_type", "三幕式")
            existing_outline.volumes = outline_data.get("volumes", [])
            existing_outline.main_plot = outline_data.get("main_plot", {})
            existing_outline.sub_plots = outline_data.get("sub_plots", [])
            existing_outline.key_turning_points = outline_data.get("key_turning_points", [])
            existing_outline.climax_chapter = outline_data.get("climax_chapter")
            existing_outline.raw_content = json.dumps(outline_data, ensure_ascii=False)
            existing_outline.updated_at = datetime.now(timezone.utc)
            logger.info(f"Updated existing outline for novel {novel_id}")
        else:
            # 创建新大纲
            new_outline = PlotOutline(
                novel_id=novel_id,
                structure_type=outline_data.get("structure_type", "三幕式"),
                volumes=outline_data.get("volumes", []),
                main_plot=outline_data.get("main_plot", {}),
                sub_plots=outline_data.get("sub_plots", []),
                key_turning_points=outline_data.get("key_turning_points", []),
                climax_chapter=outline_data.get("climax_chapter"),
                raw_content=json.dumps(outline_data, ensure_ascii=False),
            )
            self.db.add(new_outline)
            logger.info(f"Created new outline for novel {novel_id}")

        await self.db.commit()

    async def decompose_outline(
        self,
        novel_id: UUID,
        outline_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        分解大纲为章节配置

        将卷级大纲分解为详细的章节配置，包括：
        - 每章的强制性事件
        - 张力循环位置
        - 伏笔分配

        Args:
            novel_id: 小说 ID
            outline_data: 大纲数据
            config: 分解配置（可选）
                {
                    "auto_split": 是否自动拆分章节，
                    "chapters_per_volume": 每卷章节数，
                    "flexible": 是否允许灵活调整
                }

        Returns:
            章节配置字典
        """
        logger.info(f"Decomposing outline for novel {novel_id}")

        config = config or {}
        auto_split = config.get("auto_split", True)
        flexible = config.get("flexible", True)

        # 1. 从大纲中提取卷信息
        volumes = outline_data.get("volumes", [])

        if not volumes:
            logger.warning(f"No volumes found in outline for novel {novel_id}")
            return {"chapters": [], "volumes": []}

        # 2. 为每卷生成章节配置
        chapter_configs = []

        for volume in volumes:
            volume_number = volume.get("number", 1)
            chapters_range = volume.get("chapters", [0, 0])

            if len(chapters_range) != 2:
                logger.warning(f"Invalid chapters range for volume {volume_number}")
                continue

            start_ch, end_ch = chapters_range
            total_chapters = end_ch - start_ch + 1

            # 3. 解析张力循环
            tension_cycles = volume.get("tension_cycles", [])

            # 4. 提取关键事件
            key_events = volume.get("key_events", [])

            # 5. 生成章节配置
            volume_chapter_configs = []

            # 获取全局高潮章节号
            global_climax_chapter = outline_data.get("climax_chapter")

            for ch_num in range(start_ch, end_ch + 1):
                chapter_config = self._generate_chapter_config(
                    chapter_number=ch_num,
                    volume_number=volume_number,
                    tension_cycles=tension_cycles,
                    key_events=key_events,
                    volume_summary=volume.get("summary", ""),
                    auto_split=auto_split,
                    end_ch=end_ch,
                    climax_chapter=global_climax_chapter,
                    volume_is_climax=volume.get("is_climax", False)
                )
                volume_chapter_configs.append(chapter_config)

            chapter_configs.extend(volume_chapter_configs)

        result = {
            "novel_id": str(novel_id),
            "volumes": [
                {
                    "number": v.get("number"),
                    "title": v.get("title"),
                    "chapters": v.get("chapters"),
                }
                for v in volumes
            ],
            "chapter_configs": chapter_configs,
            "total_chapters": len(chapter_configs),
        }

        logger.info(
            f"Outline decomposed into {len(chapter_configs)} chapters "
            f"for novel {novel_id}"
        )

        return result

    def _generate_chapter_config(
        self,
        chapter_number: int,
        volume_number: int,
        tension_cycles: List[Dict[str, Any]],
        key_events: List[Dict[str, Any]],
        volume_summary: str,
        auto_split: bool = True,
        end_ch: int = 0,
        climax_chapter: Optional[int] = None,
        volume_is_climax: bool = False
    ) -> Dict[str, Any]:
        """生成单章配置"""
        # 1. 找到当前章所属的张力循环
        current_cycle = None
        cycle_position = None

        for cycle in tension_cycles:
            chapters_range = cycle.get("chapters", [])
            if len(chapters_range) != 2:
                continue

            start_ch, end_ch = chapters_range

            if start_ch <= chapter_number <= end_ch:
                current_cycle = cycle
                # 判断在循环中的位置
                suppress_events = cycle.get("suppress_events", [])
                release_event = cycle.get("release_event", "")

                # 简化：前 70% 为压制期，最后为释放期
                cycle_length = end_ch - start_ch + 1
                suppress_length = int(cycle_length * 0.7)

                if chapter_number <= start_ch + suppress_length:
                    cycle_position = "suppress"
                else:
                    cycle_position = "release"
                break

        # 2. 检查是否有关键事件
        chapter_events = []
        for event in key_events:
            if event.get("chapter") == chapter_number:
                chapter_events.append(event)

        # 3. 生成配置
        config = {
            "chapter_number": chapter_number,
            "volume_number": volume_number,
            "mandatory_events": [],
            "optional_events": [],
            "emotional_tone": "",
            "is_milestone": len(chapter_events) > 0,
            "is_climax": False,
            "is_golden_chapter": chapter_number <= 3 and volume_number == 1,
            "tension_cycle_position": cycle_position,
        }

        # 4. 根据张力循环位置分配事件
        if current_cycle:
            if cycle_position == "suppress":
                config["mandatory_events"] = current_cycle.get("suppress_events", [])[:2]
                config["emotional_tone"] = "压抑、挫折、积累"
            elif cycle_position == "release":
                config["mandatory_events"] = [current_cycle.get("release_event", "")]
                config["emotional_tone"] = "爽快、胜利、爆发"
                config["is_milestone"] = True

        # 5. 添加关键事件
        for event in chapter_events:
            config["mandatory_events"].append(event.get("event", ""))
            config["is_milestone"] = True

        # 6. 检查是否是高潮章（优先级递减）
        # 优先级1：全局高潮章节号精确匹配
        if climax_chapter is not None and climax_chapter == chapter_number:
            config["is_climax"] = True
        # 优先级2：卷级别高潮标记
        elif volume_is_climax:
            config["is_climax"] = True
        # 优先级3：张力循环释放期的最后一章
        elif current_cycle and cycle_position == "release":
            cycle_chapters = current_cycle.get("chapters", [])
            if len(cycle_chapters) == 2 and chapter_number == cycle_chapters[1]:
                config["is_climax"] = True
        # 优先级4：卷末章且卷摘要包含高潮关键词
        elif end_ch > 0 and chapter_number == end_ch and volume_summary and "高潮" in volume_summary:
            config["is_climax"] = True

        return config

    async def get_chapter_outline_task(
        self,
        novel_id: UUID,
        chapter_number: int
    ) -> Dict[str, Any]:
        """
        获取章节大纲任务

        从大纲中提取指定章节的任务信息

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号

        Returns:
            章节大纲任务数据
        """
        logger.info(f"Getting chapter outline task for chapter {chapter_number}, novel {novel_id}")

        # 1. 加载大纲
        result = await self.db.execute(
            select(PlotOutline).where(PlotOutline.novel_id == novel_id)
        )
        outline = result.scalar_one_or_none()

        if not outline:
            logger.warning(f"No outline found for novel {novel_id}")
            return {
                "chapter_number": chapter_number,
                "error": "大纲不存在",
            }

        # 2. 找到章节所属的卷
        volumes = outline.volumes or []
        current_volume = None

        for volume in volumes:
            chapters_range = volume.get("chapters", [])
            if len(chapters_range) != 2:
                continue

            start_ch, end_ch = chapters_range

            if start_ch <= chapter_number <= end_ch:
                current_volume = volume
                break

        if not current_volume:
            logger.warning(f"Chapter {chapter_number} not found in any volume")
            return {
                "chapter_number": chapter_number,
                "error": "章节不在任何卷中",
            }

        # 3. 提取章节任务
        volume_number = current_volume.get("number", 1)
        tension_cycles = current_volume.get("tension_cycles", [])
        key_events = current_volume.get("key_events", [])

        # 4. 使用内部方法生成任务
        task_data = self._generate_chapter_config(
            chapter_number=chapter_number,
            volume_number=volume_number,
            tension_cycles=tension_cycles,
            key_events=key_events,
            volume_summary=current_volume.get("summary", "")
        )

        # 5. 添加卷信息
        task_data["volume_title"] = current_volume.get("title", "")
        task_data["volume_summary"] = current_volume.get("summary", "")

        logger.info(f"Chapter outline task retrieved for chapter {chapter_number}")

        return task_data

    async def validate_chapter_outline(
        self,
        novel_id: UUID,
        chapter_number: int,
        chapter_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证章节大纲一致性

        检查章节计划是否符合大纲要求

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            chapter_plan: 章节计划

        Returns:
            验证报告
        """
        logger.info(f"Validating chapter outline for chapter {chapter_number}, novel {novel_id}")

        # 1. 获取章节大纲任务
        task_data = await self.get_chapter_outline_task(novel_id, chapter_number)

        if "error" in task_data:
            return {
                "chapter_number": chapter_number,
                "passed": False,
                "error": task_data["error"],
            }

        # 2. 检查强制性事件
        mandatory_events = task_data.get("mandatory_events", [])
        completed_events = []
        missing_events = []

        chapter_text = json.dumps(chapter_plan, ensure_ascii=False).lower()

        for event in mandatory_events:
            if not event:
                continue

            event_lower = event.lower()
            # 关键词匹配
            keywords = [w for w in event_lower.split() if len(w) > 1][:3]

            if any(kw in chapter_text for kw in keywords):
                completed_events.append(event)
            else:
                missing_events.append(event)

        # 3. 计算完成率
        total_mandatory = len([e for e in mandatory_events if e])
        completed = len(completed_events)
        completion_rate = completed / total_mandatory if total_mandatory > 0 else 0

        # 4. 质量评分
        quality_score = completion_rate * 10

        # 5. 判断是否通过
        passed = completion_rate >= 0.8 and quality_score >= 7.0

        # 6. 生成建议
        suggestions = []
        if missing_events:
            suggestions.append(f"建议补充以下事件：{', '.join(missing_events)}")

        validation_report = {
            "chapter_number": chapter_number,
            "passed": passed,
            "completion": {
                "completed_events": completed_events,
                "missing_events": missing_events,
                "completion_rate": completion_rate,
            },
            "quality_score": quality_score,
            "suggestions": suggestions,
        }

        logger.info(
            f"Validation completed: passed={passed}, "
            f"completion_rate={completion_rate:.2f}"
        )

        return validation_report

    async def generate_field_suggestion(
        self,
        novel_id: UUID,
        field_name: str,
        context: Dict[str, Any],
        hints: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        为大纲字段生成AI建议

        Args:
            novel_id: 小说 ID
            field_name: 字段名
            context: 上下文信息
            hints: 额外提示

        Returns:
            包含建议的字典
        """
        logger.info(f"Generating AI suggestion for field '{field_name}', novel {novel_id}")

        # 字段特定的生成逻辑
        field_prompts = {
            "structure_type": "根据小说类型和目标字数，推荐适合的故事结构类型",
            "volumes": "根据故事结构和预计章节数，设计卷级划分方案",
            "main_plot": "根据世界观设定和角色，构思主线剧情框架",
            "sub_plots": "根据主线剧情和角色关系，设计支线剧情",
            "key_turning_points": "根据剧情发展，设计关键转折点",
            "climax_chapter": "根据故事结构，推荐高潮章节位置",
        }

        prompt_template = field_prompts.get(
            field_name,
            f"为大纲的 '{field_name}' 字段生成建议"
        )

        # 构建上下文描述
        context_desc = self._build_context_description(context)

        # 生成建议（基于规则的简单实现，可后续接入LLM）
        suggestion = await self._generate_suggestion_for_field(
            field_name, context, hints, prompt_template
        )

        return {
            "suggestion": suggestion,
            "confidence": 0.7,
            "reasoning": f"基于当前小说设定和{prompt_template}",
            "alternatives": [],
        }

    def _build_context_description(self, context: Dict[str, Any]) -> str:
        """构建上下文描述"""
        parts = []

        if "novel" in context:
            novel = context["novel"]
            parts.append(f"小说《{novel.get('title', '未命名')}》")
            if novel.get("genre"):
                parts.append(f"类型：{novel['genre']}")
            if novel.get("target_word_count"):
                parts.append(f"目标字数：{novel['target_word_count']}")

        if "world_setting" in context:
            world = context["world_setting"]
            if world.get("world_name"):
                parts.append(f"世界观：{world['world_name']}")
            if world.get("world_type"):
                parts.append(f"世界类型：{world['world_type']}")

        if "characters" in context:
            chars = context["characters"]
            if chars:
                names = [c.get("name", "") for c in chars[:5] if c.get("name")]
                if names:
                    parts.append(f"主要角色：{', '.join(names)}")

        return " | ".join(parts) if parts else "无上下文信息"

    async def _generate_suggestion_for_field(
        self,
        field_name: str,
        context: Dict[str, Any],
        hints: Optional[str],
        prompt_template: str
    ) -> str:
        """为特定字段生成建议"""

        novel = context.get("novel", {})
        world = context.get("world_setting", {})
        outline = context.get("outline", {})

        if field_name == "structure_type":
            genre = novel.get("genre", "")
            if genre in ["玄幻", "仙侠", "武侠"]:
                return "三幕式"
            elif genre in ["都市", "言情"]:
                return "三幕式"
            elif genre in ["悬疑", "推理"]:
                return "多线叙事"
            else:
                return "三幕式"

        elif field_name == "climax_chapter":
            # 根据目标字数估算章节数，高潮通常在70-80%位置
            target_words = novel.get("target_word_count", 100000)
            estimated_chapters = target_words // 3000  # 假设每章3000字
            climax_chapter = int(estimated_chapters * 0.75)
            return str(max(climax_chapter, 10))

        elif field_name == "volumes":
            # 根据目标字数估算卷数
            target_words = novel.get("target_word_count", 100000)
            estimated_chapters = target_words // 3000
            volumes_count = max(1, estimated_chapters // 20)  # 每卷约20章

            volumes = []
            chapters_per_volume = estimated_chapters // volumes_count

            for i in range(volumes_count):
                start_ch = i * chapters_per_volume + 1
                end_ch = (i + 1) * chapters_per_volume if i < volumes_count - 1 else estimated_chapters
                volumes.append({
                    "number": i + 1,
                    "title": f"第{i + 1}卷",
                    "chapters": [start_ch, end_ch],
                    "summary": ""
                })

            return json.dumps(volumes, ensure_ascii=False)

        elif field_name == "main_plot":
            world_name = world.get("world_name", "这个世界")
            world_type = world.get("world_type", "奇幻")

            return json.dumps({
                "setup": f"主角在{world_name}中成长，展现{world_type}世界的独特魅力",
                "conflict": "主角面临重大挑战，遭遇强敌或困境",
                "climax": "主角突破自我，战胜最强敌人",
                "resolution": "故事结局，主角达成目标或开启新篇章"
            }, ensure_ascii=False)

        elif field_name == "sub_plots":
            characters = context.get("characters", [])
            sub_plots = []

            for char in characters[:3]:
                if char.get("name"):
                    sub_plots.append({
                        "name": f"{char['name']}成长线",
                        "characters": [char["name"]],
                        "arc": "角色成长与蜕变"
                    })

            return json.dumps(sub_plots, ensure_ascii=False)

        elif field_name == "key_turning_points":
            target_words = novel.get("target_word_count", 100000)
            estimated_chapters = target_words // 3000

            return json.dumps([
                {"chapter": estimated_chapters // 4, "event": "主角觉醒", "impact": "获得核心能力"},
                {"chapter": estimated_chapters // 2, "event": "重大挫折", "impact": "实力受损"},
                {"chapter": int(estimated_chapters * 0.75), "event": "突破瓶颈", "impact": "实力飞跃"},
            ], ensure_ascii=False)

        else:
            return f"请根据{prompt_template}填写此字段"

    async def get_outline_versions(
        self,
        novel_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        获取大纲版本历史

        从数据库查询大纲的修改历史

        Args:
            novel_id: 小说 ID

        Returns:
            版本历史列表
        """
        logger.info(f"Getting outline versions for novel {novel_id}")

        # 目前实现：返回当前大纲信息
        # 后续可扩展：添加版本控制表记录历史

        result = await self.db.execute(
            select(PlotOutline).where(PlotOutline.novel_id == novel_id)
        )
        outline = result.scalar_one_or_none()

        if not outline:
            return []

        # 返回当前版本信息
        versions = [
            {
                "version": 1,
                "created_at": outline.created_at.isoformat(),
                "updated_at": outline.updated_at.isoformat(),
                "structure_type": outline.structure_type,
                "volumes_count": len(outline.volumes or []),
                "total_chapters": self._calculate_total_chapters(outline.volumes),
            }
        ]

        logger.info(f"Found {len(versions)} outline version(s) for novel {novel_id}")

        return versions

    def _calculate_total_chapters(self, volumes: Optional[List[Dict[str, Any]]]) -> int:
        """计算总章节数"""
        if not volumes:
            return 0

        total = 0
        for volume in volumes:
            chapters_range = volume.get("chapters", [])
            if len(chapters_range) == 2:
                total += chapters_range[1] - chapters_range[0] + 1

        return total

    async def _record_token_usage(self, novel_id: UUID, task_type: str):
        """记录 token 使用"""
        cost_summary = self.cost_tracker.get_summary()

        for record in self.cost_tracker.records:
            token_usage = TokenUsage(
                novel_id=novel_id,
                task_id=None,
                agent_name=f"outline_{task_type}",
                prompt_tokens=record["prompt_tokens"],
                completion_tokens=record["completion_tokens"],
                total_tokens=record["total_tokens"],
                cost=record["cost"],
            )
            self.db.add(token_usage)

        # 更新小说成本
        novel_result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        novel = novel_result.scalar_one_or_none()

        if novel:
            novel.token_cost = (novel.token_cost or Decimal("0")) + Decimal(str(cost_summary["total_cost"]))

        await self.db.commit()


# 便捷函数
def get_outline_service(db: AsyncSession) -> OutlineService:
    """获取大纲服务实例"""
    return OutlineService(db)
