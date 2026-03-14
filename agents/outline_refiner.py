"""大纲细化和完善 Agent

功能：
1. 细化完整大纲
2. 生成详细主线剧情
3. 生成带张力循环的卷大纲
4. 确保结局连贯性
"""
import json
from typing import Any, Dict, List, Optional

from llm.qwen_client import QwenClient
from llm.cost_tracker import CostTracker

from core.logging_config import logger


class OutlineRefiner:
    """大纲细化 Agent"""
    
    def __init__(self, client: Optional[QwenClient] = None, cost_tracker: Optional[CostTracker] = None):
        """初始化大纲细化 Agent
        
        Args:
            client: LLM 客户端
            cost_tracker: 成本跟踪器
        """
        self.client = client or QwenClient()
        self.cost_tracker = cost_tracker or CostTracker()
    
    async def refine_complete_outline(
        self,
        world_setting_data: Dict[str, Any],
        genre: str,
        tags: List[str],
        total_chapters: int = 100
    ) -> Dict[str, Any]:
        """细化完整大纲
        
        基于世界观设定，生成包含主线、支线、卷大纲的完整大纲
        
        Args:
            world_setting_data: 世界观设定数据
            genre: 小说类型
            tags: 标签列表
            total_chapters: 总章节数
        
        Returns:
            完整大纲数据
        """
        logger.info("开始细化完整大纲")
        
        prompt = self._build_refine_outline_prompt(
            world_setting_data=world_setting_data,
            genre=genre,
            tags=tags,
            total_chapters=total_chapters
        )
        
        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一位专业的小说大纲架构师，擅长构建完整的故事大纲体系。",
                temperature=0.7,
                max_tokens=8192,
            )
            
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="outline_refiner",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            
            outline_data = self._parse_outline_response(response["content"])
            
            logger.info(f"大纲细化完成，生成{len(outline_data.get('volumes', []))}卷内容")
            
            return outline_data
            
        except Exception as e:
            logger.error(f"大纲细化失败：{e}")
            raise
    
    async def generate_main_plot_detailed(
        self,
        world_setting_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成详细主线剧情
        
        基于世界观设定，生成包含起承转合的详细主线
        
        Args:
            world_setting_data: 世界观设定数据
        
        Returns:
            主线剧情数据
        """
        logger.info("开始生成详细主线剧情")
        
        prompt = self._build_main_plot_prompt(world_setting_data)
        
        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一位擅长构建主线剧情的小说架构师。",
                temperature=0.7,
                max_tokens=4096,
            )
            
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="outline_refiner_main_plot",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            
            main_plot = self._parse_main_plot_response(response["content"])
            
            logger.info("主线剧情生成完成")
            
            return main_plot
            
        except Exception as e:
            logger.error(f"主线剧情生成失败：{e}")
            raise
    
    async def generate_volumes_with_tension_cycles(
        self,
        genre: str,
        total_chapters: int,
        main_plot: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """生成带张力循环的卷大纲
        
        根据小说类型和长度，生成包含欲扬先抑循环的卷大纲
        
        Args:
            genre: 小说类型
            total_chapters: 总章节数
            main_plot: 主线剧情（可选）
        
        Returns:
            卷大纲列表
        """
        logger.info("开始生成带张力循环的卷大纲")
        
        prompt = self._build_volumes_prompt(
            genre=genre,
            total_chapters=total_chapters,
            main_plot=main_plot
        )
        
        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一位擅长设计故事节奏和张力循环的小说架构师。",
                temperature=0.7,
                max_tokens=8192,
            )
            
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="outline_refiner_volumes",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            
            volumes = self._parse_volumes_response(response["content"])
            
            logger.info(f"卷大纲生成完成，共{len(volumes)}卷")
            
            return volumes
            
        except Exception as e:
            logger.error(f"卷大纲生成失败：{e}")
            raise
    
    async def ensure_ending_coherence(
        self,
        main_plot: Dict[str, Any],
        volumes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """确保结局连贯性
        
        检查主线剧情和卷大纲的结局部分，确保逻辑连贯
        
        Args:
            main_plot: 主线剧情
            volumes: 卷大纲列表
        
        Returns:
            包含连贯性检查和修正建议的报告
        """
        logger.info("开始检查结局连贯性")
        
        prompt = self._build_coherence_prompt(main_plot, volumes)
        
        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一位擅长检查故事逻辑连贯性的资深编辑。",
                temperature=0.5,
                max_tokens=4096,
            )
            
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="outline_refiner_coherence",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            
            coherence_report = self._parse_coherence_response(response["content"])
            
            logger.info(f"结局连贯性检查完成，评分：{coherence_report.get('coherence_score', 0)}")
            
            return coherence_report
            
        except Exception as e:
            logger.error(f"结局连贯性检查失败：{e}")
            raise
    
    def _build_refine_outline_prompt(
        self,
        world_setting_data: Dict[str, Any],
        genre: str,
        tags: List[str],
        total_chapters: int
    ) -> str:
        """构建大纲细化提示词"""
        world_name = world_setting_data.get("world_name", "未命名世界")
        world_type = world_setting_data.get("world_type", "未知类型")
        power_system = world_setting_data.get("power_system", {})
        factions = world_setting_data.get("factions", [])
        
        prompt = f"""
# 任务：生成完整的小说大纲

## 小说基本信息
- **类型**: {genre}
- **标签**: {", ".join(tags)}
- **总章节数**: {total_chapters}

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
根据总章节数，设计 3-5 卷内容，每卷包含：
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

注意：
1. 确保张力循环符合"欲扬先抑"原则
2. 关键事件应分布在张力循环的释放期
3. 各卷之间应有清晰的递进关系
4. 支线剧情应与主线交织
"""
        return prompt
    
    def _build_main_plot_prompt(self, world_setting_data: Dict[str, Any]) -> str:
        """构建主线剧情提示词"""
        world_name = world_setting_data.get("world_name", "未命名世界")
        world_type = world_setting_data.get("world_type", "未知类型")
        power_system = world_setting_data.get("power_system", {})
        
        prompt = f"""
# 任务：生成详细主线剧情

## 世界观设定
- **世界名称**: {world_name}
- **世界类型**: {world_type}
- **力量体系**: {json.dumps(power_system, ensure_ascii=False)}

## 要求

请生成一个详细的主线剧情，包含以下四个部分：

### 1. 开端（Setup，约占总篇幅 10%）
- 主角的初始状态（身份、能力、处境）
- 触发事件（打破平衡的事件）
- 主角的目标和动机

### 2. 发展（Conflict，约占总篇幅 50%）
- 主要冲突的来源
- 冲突的逐步升级过程
- 主角遇到的主要阻碍和挫折
- 盟友和敌人的出现

### 3. 高潮（Climax，约占总篇幅 30%）
- 最大冲突的爆发点
- 关键转折点
- 主角的终极考验
- 决定性事件

### 4. 结局（Resolution，约占总篇幅 10%）
- 冲突的解决方式
- 主角的归宿
- 世界的变化
- 主题升华

## 输出格式

请严格按照以下 JSON 格式输出：

{{
  "structure_type": "三幕式/英雄之旅",
  "setup": {{
    "initial_state": "...",
    "inciting_incident": "...",
    "goal_and_motivation": "..."
  }},
  "conflict": {{
    "source": "...",
    "escalation": ["阶段 1", "阶段 2", "阶段 3"],
    "obstacles": ["阻碍 1", "阻碍 2"],
    "allies_and_enemies": {{
      "allies": ["盟友 1", "盟友 2"],
      "enemies": ["敌人 1", "敌人 2"]
    }}
  }},
  "climax": {{
    "explosion_point": "...",
    "turning_point": "...",
    "ultimate_test": "...",
    "decisive_event": "..."
  }},
  "resolution": {{
    "conflict_resolution": "...",
    "protagonist_fate": "...",
    "world_change": "...",
    "theme_sublimation": "..."
  }}
}}
"""
        return prompt
    
    def _build_volumes_prompt(
        self,
        genre: str,
        total_chapters: int,
        main_plot: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建卷大纲提示词"""
        main_plot_str = json.dumps(main_plot, ensure_ascii=False) if main_plot else "暂无主线剧情"
        
        num_volumes = max(3, min(5, total_chapters // 20))
        
        prompt = f"""
# 任务：生成带张力循环的卷大纲

## 小说信息
- **类型**: {genre}
- **总章节数**: {total_chapters}
- **计划卷数**: {num_volumes}卷

## 主线剧情参考
{main_plot_str}

## 要求

请设计{num_volumes}卷内容，每卷应包含：

### 卷结构
- **卷号**: 第 X 卷
- **卷名**: 2-4 字标题，体现本卷主题
- **章节范围**: [起始章，结束章]，确保各卷章节数合理分配
- **卷概述**: 200-300 字，描述本卷主要内容

### 核心冲突
- 本卷的主要矛盾
- 与主线的关系

### 张力循环（重点）
每卷设计 2-3 个"欲扬先抑"循环，每个循环包含：
- **chapters**: [起始章，结束章]
- **suppress_events**: 压制期事件列表（2-3 个），描述主角遭遇的挫折、压制
- **release_event**: 释放期事件（1 个），描述主角的反击、胜利

张力循环原则：
1. 压制期占循环的 70% 左右，释放期占 30%
2. 压制事件逐步升级
3. 释放事件应带来爽感和成就感
4. 循环之间应有递进关系

### 关键事件
- 3-5 个重大事件
- 每个事件包含：chapter（章节号）、event（描述）、impact（影响）
- 关键事件应分布在张力循环的释放期

## 输出格式

请严格按照以下 JSON 格式输出：

[
  {{
    "number": 1,
    "title": "卷名",
    "chapters": [1, 20],
    "summary": "...",
    "core_conflict": "...",
    "relation_to_main_plot": "...",
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
]

注意：
1. 各卷之间应有清晰的递进关系
2. 张力循环应符合"先抑后扬"原则
3. 关键事件应推动剧情发展
"""
        return prompt
    
    def _build_coherence_prompt(
        self,
        main_plot: Dict[str, Any],
        volumes: List[Dict[str, Any]]
    ) -> str:
        """构建连贯性检查提示词"""
        main_plot_str = json.dumps(main_plot, ensure_ascii=False)
        volumes_str = json.dumps(volumes, ensure_ascii=False)
        
        prompt = f"""
# 任务：检查结局连贯性

## 主线剧情
{main_plot_str}

## 卷大纲
{volumes_str}

## 检查要点

请检查以下内容：

### 1. 主线与卷大纲的一致性
- 主线的结局是否在最后一卷得到体现
- 各卷的核心冲突是否服务于主线
- 支线剧情是否有完整的收尾

### 2. 逻辑连贯性
- 关键转折点是否合理分布
- 高潮章节是否在高潮位置
- 结局是否解决了所有主要冲突

### 3. 角色弧光完整性
- 主角的成长轨迹是否清晰
- 重要配角是否有完整的故事线
- 反派是否有合理的结局

### 4. 张力循环合理性
- 各卷的张力循环是否有递进
- 最后一卷的张力循环是否导向高潮
- 结局部分是否有适当的释放

## 输出格式

请严格按照以下 JSON 格式输出：

{{
  "coherence_score": 8.5,
  "consistency_check": {{
    "main_plot_alignment": true,
    "volume_progression": true,
    "sub_plot_resolution": true
  }},
  "logic_issues": [
    {{
      "issue": "问题描述",
      "severity": "high/medium/low",
      "suggestion": "改进建议"
    }}
  ],
  "character_arc_check": {{
    "protagonist_growth": "清晰/模糊/缺失",
    "supporting_characters": "完整/不完整",
    "antagonist_fate": "合理/不合理"
  }},
  "tension_cycle_check": {{
    "progression": "合理/不合理",
    "climax_buildup": "充分/不足",
    "resolution": "恰当/不恰当"
  }},
  "improvement_suggestions": [
    "建议 1",
    "建议 2"
  ],
  "ending_analysis": {{
    "conflict_resolution": "完整/部分/缺失",
    "emotional_impact": "强/中/弱",
    "theme_consistency": "一致/不一致"
  }}
}}
"""
        return prompt
    
    def _parse_outline_response(self, content: str) -> Dict[str, Any]:
        """解析大纲响应"""
        try:
            content = content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            outline_data = json.loads(content)
            
            required_fields = ["structure_type", "main_plot", "volumes"]
            for field in required_fields:
                if field not in outline_data:
                    logger.warning(f"Missing required field: {field}")
                    outline_data[field] = {} if field in ["main_plot"] else []
            
            return outline_data
            
        except json.JSONDecodeError as e:
            logger.error(f"解析大纲响应失败：{e}")
            return {
                "structure_type": "三幕式",
                "main_plot": {},
                "sub_plots": [],
                "volumes": [],
                "key_turning_points": [],
                "climax_chapter": None,
            }
    
    def _parse_main_plot_response(self, content: str) -> Dict[str, Any]:
        """解析主线剧情响应"""
        try:
            content = content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"解析主线剧情响应失败：{e}")
            return {
                "structure_type": "三幕式",
                "setup": {},
                "conflict": {},
                "climax": {},
                "resolution": {},
            }
    
    def _parse_volumes_response(self, content: str) -> List[Dict[str, Any]]:
        """解析卷大纲响应"""
        try:
            content = content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            volumes = json.loads(content)
            
            if not isinstance(volumes, list):
                logger.warning("卷大纲应为列表格式")
                return []
            
            return volumes
            
        except json.JSONDecodeError as e:
            logger.error(f"解析卷大纲响应失败：{e}")
            return []
    
    def _parse_coherence_response(self, content: str) -> Dict[str, Any]:
        """解析连贯性检查响应"""
        try:
            content = content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            report = json.loads(content)
            
            if "coherence_score" not in report:
                report["coherence_score"] = 5.0
            
            return report
            
        except json.JSONDecodeError as e:
            logger.error(f"解析连贯性检查响应失败：{e}")
            return {
                "coherence_score": 5.0,
                "consistency_check": {},
                "logic_issues": [],
                "improvement_suggestions": [],
            }
