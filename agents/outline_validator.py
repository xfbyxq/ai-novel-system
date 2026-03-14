"""大纲一致性验证 Agent

功能：
1. 验证章节与大纲一致性
2. 检查角色一致性
3. 检查剧情连贯性
4. 检查世界观一致性
5. 生成改进建议
"""
import json
from typing import Any, Dict, List, Optional

from llm.qwen_client import QwenClient
from llm.cost_tracker import CostTracker

from core.logging_config import logger


class OutlineValidator:
    """大纲验证 Agent"""
    
    def __init__(self, client: Optional[QwenClient] = None, cost_tracker: Optional[CostTracker] = None):
        """初始化大纲验证 Agent
        
        Args:
            client: LLM 客户端
            cost_tracker: 成本跟踪器
        """
        self.client = client or QwenClient()
        self.cost_tracker = cost_tracker or CostTracker()
    
    async def validate_chapter_against_outline(
        self,
        chapter_plan: Dict[str, Any],
        outline_task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """验证章节与大纲一致性
        
        检查章节计划是否符合大纲要求
        
        Args:
            chapter_plan: 章节计划
            outline_task: 大纲任务（包含强制性事件等）
        
        Returns:
            验证报告
        """
        logger.info(f"开始验证章节 {chapter_plan.get('chapter_number', '未知')} 与大纲的一致性")
        
        prompt = self._build_chapter_validation_prompt(chapter_plan, outline_task)
        
        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一位严格的小说编辑，负责检查章节内容是否符合大纲要求。",
                temperature=0.5,
                max_tokens=4096,
            )
            
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="outline_validator_chapter",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            
            validation_report = self._parse_validation_response(response["content"])
            
            passed = validation_report.get("passed", False)
            logger.info(f"章节验证完成：{'通过' if passed else '未通过'}")
            
            return validation_report
            
        except Exception as e:
            logger.error(f"章节验证失败：{e}")
            raise
    
    async def check_character_consistency(
        self,
        chapter_plan: Dict[str, Any],
        character_states: Dict[str, Any]
    ) -> Dict[str, Any]:
        """检查角色一致性
        
        检查章节中的角色行为、性格、能力是否与设定一致
        
        Args:
            chapter_plan: 章节计划
            character_states: 角色状态（包含角色设定和当前状态）
        
        Returns:
            角色一致性检查报告
        """
        logger.info(f"开始检查章节 {chapter_plan.get('chapter_number', '未知')} 的角色一致性")
        
        prompt = self._build_character_consistency_prompt(chapter_plan, character_states)
        
        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一位精通角色塑造的资深编辑，擅长发现角色行为的不一致之处。",
                temperature=0.5,
                max_tokens=4096,
            )
            
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="outline_validator_character",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            
            consistency_report = self._parse_character_consistency_response(response["content"])
            
            score = consistency_report.get("consistency_score", 0)
            logger.info(f"角色一致性检查完成，评分：{score}")
            
            return consistency_report
            
        except Exception as e:
            logger.error(f"角色一致性检查失败：{e}")
            raise
    
    async def check_plot_continuity(
        self,
        chapter_plan: Dict[str, Any],
        previous_chapters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """检查剧情连贯性
        
        检查章节与之前章节的剧情是否连贯
        
        Args:
            chapter_plan: 章节计划
            previous_chapters: 之前章节的摘要或计划
        
        Returns:
            剧情连贯性检查报告
        """
        logger.info(f"开始检查章节 {chapter_plan.get('chapter_number', '未知')} 的剧情连贯性")
        
        prompt = self._build_plot_continuity_prompt(chapter_plan, previous_chapters)
        
        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一位擅长剧情连贯性检查的编辑，确保故事逻辑严密。",
                temperature=0.5,
                max_tokens=4096,
            )
            
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="outline_validator_plot",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            
            continuity_report = self._parse_plot_continuity_response(response["content"])
            
            score = continuity_report.get("continuity_score", 0)
            logger.info(f"剧情连贯性检查完成，评分：{score}")
            
            return continuity_report
            
        except Exception as e:
            logger.error(f"剧情连贯性检查失败：{e}")
            raise
    
    async def check_world_setting_consistency(
        self,
        chapter_plan: Dict[str, Any],
        world_setting: Dict[str, Any]
    ) -> Dict[str, Any]:
        """检查世界观一致性
        
        检查章节内容是否符合世界观设定
        
        Args:
            chapter_plan: 章节计划
            world_setting: 世界观设定数据
        
        Returns:
            世界观一致性检查报告
        """
        logger.info(f"开始检查章节 {chapter_plan.get('chapter_number', '未知')} 的世界观一致性")
        
        prompt = self._build_world_setting_consistency_prompt(chapter_plan, world_setting)
        
        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一位世界观架构师，负责检查内容是否符合设定的世界观体系。",
                temperature=0.5,
                max_tokens=4096,
            )
            
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="outline_validator_world",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            
            consistency_report = self._parse_world_setting_consistency_response(response["content"])
            
            score = consistency_report.get("consistency_score", 0)
            logger.info(f"世界观一致性检查完成，评分：{score}")
            
            return consistency_report
            
        except Exception as e:
            logger.error(f"世界观一致性检查失败：{e}")
            raise
    
    async def generate_improvement_suggestions(
        self,
        validation_issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """生成改进建议
        
        基于验证发现的问题，生成具体的改进建议
        
        Args:
            validation_issues: 验证发现的问题列表
        
        Returns:
            改进建议列表
        """
        logger.info(f"开始为{len(validation_issues)}个问题生成改进建议")
        
        prompt = self._build_improvement_suggestions_prompt(validation_issues)
        
        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一位经验丰富的小说编辑，擅长提供具体可行的改进建议。",
                temperature=0.6,
                max_tokens=4096,
            )
            
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="outline_validator_suggestions",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            
            suggestions = self._parse_suggestions_response(response["content"])
            
            logger.info(f"生成了{len(suggestions)}条改进建议")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"生成改进建议失败：{e}")
            raise
    
    def _build_chapter_validation_prompt(
        self,
        chapter_plan: Dict[str, Any],
        outline_task: Dict[str, Any]
    ) -> str:
        """构建章节验证提示词"""
        chapter_plan_str = json.dumps(chapter_plan, ensure_ascii=False)
        outline_task_str = json.dumps(outline_task, ensure_ascii=False)
        
        prompt = f"""
# 任务：验证章节与大纲的一致性

## 章节计划
{chapter_plan_str}

## 大纲任务要求
{outline_task_str}

## 检查要点

请检查以下内容：

### 1. 强制性事件完成度
- 大纲要求的强制性事件是否在章节计划中得到体现
- 事件的呈现方式是否合理
- 是否有遗漏的重要事件

### 2. 张力循环位置
- 章节在张力循环中的位置是否正确
- 如果是压制期，是否有相应的挫折情节
- 如果是释放期，是否有相应的爽感情节

### 3. 章节节奏
- 章节的节奏是否符合大纲要求
- 是否有适当的冲突和高潮
- 结尾是否有吸引力

### 4. 伏笔和铺垫
- 是否为后续剧情埋下伏笔
- 是否呼应了前面的铺垫
- 伏笔是否自然不突兀

## 输出格式

请严格按照以下 JSON 格式输出：

{{
  "passed": true,
  "completion_rate": 0.85,
  "mandatory_events_check": {{
    "completed": ["事件 1", "事件 2"],
    "missing": ["事件 3"],
    "partially_completed": [
      {{
        "event": "事件 4",
        "completion": 0.5,
        "note": "部分完成的原因"
      }}
    ]
  }},
  "tension_cycle_check": {{
    "expected_position": "suppress",
    "actual_position": "suppress",
    "matches": true,
    "note": "评价"
  }},
  "pacing_check": {{
    "appropriate": true,
    "conflict_level": "medium",
    "climax_present": false,
    "ending_hook": true
  }},
  "foreshadowing_check": {{
    "new_foreshadowing": ["伏笔 1"],
    "callback_to_previous": ["呼应 1"],
    "natural_integration": true
  }},
  "quality_score": 8.5,
  "issues": [
    {{
      "type": "missing_event/tension_mismatch/pacing_issue/foreshadowing_issue",
      "severity": "high/medium/low",
      "description": "问题描述"
    }}
  ],
  "suggestions": ["建议 1", "建议 2"]
}}
"""
        return prompt
    
    def _build_character_consistency_prompt(
        self,
        chapter_plan: Dict[str, Any],
        character_states: Dict[str, Any]
    ) -> str:
        """构建角色一致性检查提示词"""
        chapter_plan_str = json.dumps(chapter_plan, ensure_ascii=False)
        character_states_str = json.dumps(character_states, ensure_ascii=False)
        
        prompt = f"""
# 任务：检查角色一致性

## 章节计划
{chapter_plan_str}

## 角色状态
{character_states_str}

## 检查要点

请检查以下内容：

### 1. 性格一致性
- 角色的言行是否符合其性格设定
- 情绪反应是否合理
- 决策是否符合角色特点

### 2. 能力一致性
- 角色展现的能力是否符合设定
- 是否有突然变强或变弱的情况
- 能力使用是否合理

### 3. 关系一致性
- 角色间的互动是否符合关系设定
- 态度变化是否有合理的原因
- 对话风格是否符合角色身份

### 4. 成长弧光
- 角色的成长是否循序渐进
- 是否有突兀的性格转变
- 是否符合角色发展轨迹

## 输出格式

请严格按照以下 JSON 格式输出：

{{
  "consistency_score": 9.0,
  "character_checks": [
    {{
      "character_name": "角色名",
      "personality_consistent": true,
      "ability_consistent": true,
      "relationship_consistent": true,
      "growth_arc_consistent": true,
      "issues": [
        {{
          "type": "personality/ability/relationship/growth",
          "severity": "high/medium/low",
          "description": "问题描述",
          "context": "出现问题的具体情境"
        }}
      ]
    }}
  ],
  "major_inconsistencies": [
    {{
      "character": "角色名",
      "issue": "问题描述",
      "severity": "high/medium/low",
      "suggestion": "改进建议"
    }}
  ],
  "positive_aspects": ["角色塑造好的方面 1", "方面 2"]
}}
"""
        return prompt
    
    def _build_plot_continuity_prompt(
        self,
        chapter_plan: Dict[str, Any],
        previous_chapters: List[Dict[str, Any]]
    ) -> str:
        """构建剧情连贯性检查提示词"""
        chapter_plan_str = json.dumps(chapter_plan, ensure_ascii=False)
        previous_chapters_str = json.dumps(previous_chapters[:5], ensure_ascii=False)  # 只取最近 5 章
        
        prompt = f"""
# 任务：检查剧情连贯性

## 当前章节计划
{chapter_plan_str}

## 之前章节摘要（最近 5 章）
{previous_chapters_str}

## 检查要点

请检查以下内容：

### 1. 时间线连贯性
- 时间推进是否合理
- 是否有时间跳跃或倒流
- 事件顺序是否符合逻辑

### 2. 空间连贯性
- 场景转换是否合理
- 角色位置是否连续
- 地理关系是否正确

### 3. 事件连贯性
- 当前章节是否承接上一章的结尾
- 事件因果是否合理
- 是否有突兀的情节转折

### 4. 状态连贯性
- 角色状态（伤势、情绪、物品）是否连续
- 环境状态是否连续
- 剧情状态（任务进度、关系发展）是否连续

### 5. 信息连贯性
- 角色知道的信息是否符合其经历
- 是否有信息泄露或遗忘
- 伏笔回收是否合理

## 输出格式

请严格按照以下 JSON 格式输出：

{{
  "continuity_score": 8.5,
  "timeline_check": {{
    "consistent": true,
    "time_gap": "合理/不合理",
    "sequence_issues": []
  }},
  "spatial_check": {{
    "consistent": true,
    "scene_transitions": "流畅/生硬",
    "location_issues": []
  }},
  "event_check": {{
    "consistent": true,
    "causality": "合理/不合理",
    "transition_quality": "smooth/abrupt",
    "issues": []
  }},
  "state_check": {{
    "consistent": true,
    "character_states": "连续/不连续",
    "environment_states": "连续/不连续",
    "issues": []
  }},
  "information_check": {{
    "consistent": true,
    "knowledge_distribution": "合理/不合理",
    "foreshadowing_payoff": "合理/不合理",
    "issues": []
  }},
  "major_issues": [
    {{
      "type": "timeline/spatial/event/state/information",
      "severity": "high/medium/low",
      "description": "问题描述",
      "context": "具体情境"
    }}
  ],
  "suggestions": ["建议 1", "建议 2"]
}}
"""
        return prompt
    
    def _build_world_setting_consistency_prompt(
        self,
        chapter_plan: Dict[str, Any],
        world_setting: Dict[str, Any]
    ) -> str:
        """构建世界观一致性检查提示词"""
        chapter_plan_str = json.dumps(chapter_plan, ensure_ascii=False)
        world_setting_str = json.dumps(world_setting, ensure_ascii=False)
        
        prompt = f"""
# 任务：检查世界观一致性

## 章节计划
{chapter_plan_str}

## 世界观设定
{world_setting_str}

## 检查要点

请检查以下内容：

### 1. 力量体系一致性
- 角色使用的能力是否符合力量体系设定
- 能力等级是否合理
- 能力限制是否被遵守

### 2. 地理环境一致性
- 场景描述是否符合世界地理设定
- 地名是否正确
- 环境特征是否符合设定

### 3. 势力组织一致性
- 出场的势力是否符合设定
- 势力关系是否正确
- 组织结构和职位是否正确

### 4. 社会文化一致性
- 社会制度是否符合设定
- 文化习俗是否正确
- 语言风格是否符合世界观

### 5. 历史背景一致性
- 提及的历史事件是否符合设定
- 时间线是否正确
- 历史人物和事件引用是否准确

### 6. 物理规则一致性
- 世界的物理规则是否被遵守
- 特殊规则（如魔法、科技）是否一致
- 是否有违反设定的情况

## 输出格式

请严格按照以下 JSON 格式输出：

{{
  "consistency_score": 9.0,
  "power_system_check": {{
    "consistent": true,
    "ability_usage": "合理/不合理",
    "level_consistent": true,
    "limitations_respected": true,
    "issues": []
  }},
  "geography_check": {{
    "consistent": true,
    "location_names": "正确/错误",
    "environment_description": "符合/不符合",
    "issues": []
  }},
  "faction_check": {{
    "consistent": true,
    "faction_relations": "正确/错误",
    "organization_structure": "正确/错误",
    "issues": []
  }},
  "culture_check": {{
    "consistent": true,
    "social_system": "符合/不符合",
    "customs": "正确/错误",
    "language_style": "符合/不符合",
    "issues": []
  }},
  "history_check": {{
    "consistent": true,
    "historical_events": "准确/不准确",
    "timeline": "正确/错误",
    "issues": []
  }},
  "physics_check": {{
    "consistent": true,
    "world_rules": "遵守/违反",
    "special_rules": "一致/不一致",
    "issues": []
  }},
  "major_violations": [
    {{
      "category": "power/geography/faction/culture/history/physics",
      "severity": "high/medium/low",
      "description": "违规描述",
      "correct_setting": "正确设定",
      "suggestion": "改进建议"
    }}
  ]
}}
"""
        return prompt
    
    def _build_improvement_suggestions_prompt(
        self,
        validation_issues: List[Dict[str, Any]]
    ) -> str:
        """构建改进建议提示词"""
        issues_str = json.dumps(validation_issues, ensure_ascii=False)
        
        prompt = f"""
# 任务：生成改进建议

## 验证发现的问题
{issues_str}

## 要求

请针对每个问题，提供具体、可行的改进建议。

### 建议原则
1. **具体性**: 建议应具体明确，可操作
2. **可行性**: 建议应在作者能力范围内可实现
3. **优先级**: 区分问题的轻重缓急
4. **建设性**: 以建设性的方式提出建议

### 建议分类
- **高优先级**: 必须修改的严重问题
- **中优先级**: 建议修改的重要问题
- **低优先级**: 可选的优化建议

## 输出格式

请严格按照以下 JSON 格式输出：

[
  {{
    "issue_id": 1,
    "issue_type": "character/plot/world/pacing/foreshadowing",
    "severity": "high/medium/low",
    "original_issue": "原问题描述",
    "suggestions": [
      {{
        "suggestion_id": 1,
        "title": "建议标题",
        "description": "详细描述",
        "example": "示例（可选）",
        "effort": "low/medium/high",
        "impact": "low/medium/high"
      }}
    ],
    "recommended_action": "最推荐的行动方案",
    "alternative_approaches": ["替代方案 1", "替代方案 2"]
  }}
]

注意：
1. 每个问题至少提供 2 个建议
2. 建议应针对问题根源，而非表面现象
3. 提供具体的修改示例
4. 考虑修改的影响范围
"""
        return prompt
    
    def _parse_validation_response(self, content: str) -> Dict[str, Any]:
        """解析章节验证响应"""
        try:
            content = content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            report = json.loads(content)
            
            if "passed" not in report:
                report["passed"] = False
            if "completion_rate" not in report:
                report["completion_rate"] = 0.0
            if "quality_score" not in report:
                report["quality_score"] = 5.0
            
            return report
            
        except json.JSONDecodeError as e:
            logger.error(f"解析章节验证响应失败：{e}")
            return {
                "passed": False,
                "completion_rate": 0.0,
                "quality_score": 5.0,
                "issues": [],
                "suggestions": [],
            }
    
    def _parse_character_consistency_response(self, content: str) -> Dict[str, Any]:
        """解析角色一致性响应"""
        try:
            content = content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            report = json.loads(content)
            
            if "consistency_score" not in report:
                report["consistency_score"] = 5.0
            
            return report
            
        except json.JSONDecodeError as e:
            logger.error(f"解析角色一致性响应失败：{e}")
            return {
                "consistency_score": 5.0,
                "character_checks": [],
                "major_inconsistencies": [],
            }
    
    def _parse_plot_continuity_response(self, content: str) -> Dict[str, Any]:
        """解析剧情连贯性响应"""
        try:
            content = content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            report = json.loads(content)
            
            if "continuity_score" not in report:
                report["continuity_score"] = 5.0
            
            return report
            
        except json.JSONDecodeError as e:
            logger.error(f"解析剧情连贯性响应失败：{e}")
            return {
                "continuity_score": 5.0,
                "timeline_check": {},
                "spatial_check": {},
                "event_check": {},
                "state_check": {},
                "information_check": {},
                "major_issues": [],
            }
    
    def _parse_world_setting_consistency_response(self, content: str) -> Dict[str, Any]:
        """解析世界观一致性响应"""
        try:
            content = content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            report = json.loads(content)
            
            if "consistency_score" not in report:
                report["consistency_score"] = 5.0
            
            return report
            
        except json.JSONDecodeError as e:
            logger.error(f"解析世界观一致性响应失败：{e}")
            return {
                "consistency_score": 5.0,
                "power_system_check": {},
                "geography_check": {},
                "faction_check": {},
                "culture_check": {},
                "history_check": {},
                "physics_check": {},
                "major_violations": [],
            }
    
    def _parse_suggestions_response(self, content: str) -> List[Dict[str, Any]]:
        """解析改进建议响应"""
        try:
            content = content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            suggestions = json.loads(content)
            
            if not isinstance(suggestions, list):
                logger.warning("改进建议应为列表格式")
                return []
            
            return suggestions
            
        except json.JSONDecodeError as e:
            logger.error(f"解析改进建议响应失败：{e}")
            return []
