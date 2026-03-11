"""
CharacterConsistencyTracker - 角色一致性追踪器

追踪内容：
1. 核心动机（Core Motivation）：角色行为的根本驱动力
2. 行为准则（Personal Code）：角色不会违背的原则
3. 性格特质（Personality Traits）：影响决策的性格因素
4. 历史决策（Decision History）：过去的关键选择

解决根本原因 3：角色行为约束不足
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from core.logging_config import logger


@dataclass
class CharacterProfile:
    """
    角色档案
    
    包含角色的核心设定，用于一致性验证
    """
    name: str
    core_motivation: str  # 核心动机，如"为家族复仇"
    personal_code: str  # 行为准则，如"不伤害无辜"
    personality_traits: List[str]  # 性格特质，如 ["谨慎", "重情义", "倔强"]
    
    # 可选字段
    background: str = ""  # 背景故事
    goals: List[str] = field(default_factory=list)  # 目标列表
    fears: List[str] = field(default_factory=list)  # 恐惧/弱点
    relationships: Dict[str, str] = field(default_factory=dict)  # 关键关系 {角色名：关系描述}
    skills: List[str] = field(default_factory=list)  # 技能/能力
    
    # 元数据
    first_appearance_chapter: int = 1
    importance_level: int = 5  # 1-10，主角=10
    
    def to_prompt(self) -> str:
        """转换为提示词格式"""
        parts = [
            f"## 角色档案：{self.name}",
            f"**核心动机**: {self.core_motivation}",
            f"**行为准则**: {self.personal_code}",
            f"**性格特质**: {', '.join(self.personality_traits)}"
        ]
        
        if self.background:
            parts.append(f"**背景**: {self.background[:100]}")
        
        if self.goals:
            parts.append(f"**目标**: {', '.join(self.goals[:3])}")
        
        if self.relationships:
            parts.append("**关键关系**:")
            for char, relation in list(self.relationships.items())[:3]:
                parts.append(f"- {char}: {relation}")
        
        return "\n".join(parts)
    
    @classmethod
    def from_character_data(cls, character_data: Dict[str, Any]) -> "CharacterProfile":
        """从角色数据创建档案"""
        # 从现有角色数据中提取信息
        name = character_data.get("name", "")
        
        # 尝试从不同字段提取核心动机
        core_motivation = (
            character_data.get("core_motivation", "") or
            character_data.get("motivation", "") or
            character_data.get("goal", "") or
            "未定义"
        )
        
        # 尝试提取行为准则
        personal_code = (
            character_data.get("personal_code", "") or
            character_data.get("principle", "") or
            character_data.get("code", "") or
            "无明显准则"
        )
        
        # 提取性格特质
        personality_traits = (
            character_data.get("personality_traits", []) or
            character_data.get("traits", []) or
            character_data.get("personality", "").split(",") or
            ["未定义"]
        )
        
        # 提取背景
        background = character_data.get("background", "")
        
        # 提取目标
        goals = character_data.get("goals", [])
        
        # 提取关系
        relationships = character_data.get("relationships", {})
        
        return cls(
            name=name,
            core_motivation=core_motivation,
            personal_code=personal_code,
            personality_traits=personality_traits,
            background=background,
            goals=goals,
            relationships=relationships
        )


@dataclass
class DecisionRecord:
    """决策记录"""
    chapter_number: int
    decision: str  # 决策内容
    reason: str  # 决策原因
    alternatives_considered: List[str] = field(default_factory=list)  # 考虑过的其他选项
    consequences: List[str] = field(default_factory=list)  # 后果
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "chapter": self.chapter_number,
            "decision": self.decision,
            "reason": self.reason,
            "alternatives": self.alternatives_considered,
            "consequences": self.consequences
        }


@dataclass
class BehavioralPattern:
    """行为模式"""
    pattern_type: str  # "conflict_response", "social_interaction", "decision_making"
    description: str
    examples: List[str] = field(default_factory=list)
    consistency_score: float = 1.0  # 一致性评分 (0-1)
    
    def to_prompt(self) -> str:
        """转换为提示词"""
        return f"{self.pattern_type}: {self.description}"


@dataclass
class ConsistencyValidation:
    """一致性验证结果"""
    passed: bool = True
    issues: List[Dict[str, Any]] = field(default_factory=list)
    
    # 各维度评分
    motivation_alignment: float = 1.0  # 动机一致性
    code_adherence: float = 1.0  # 准则遵守度
    personality_consistency: float = 1.0  # 性格一致性
    historical_consistency: float = 1.0  # 历史一致性
    
    # 详细分析
    analysis: str = ""
    suggestions: List[str] = field(default_factory=list)
    
    @property
    def overall_score(self) -> float:
        """计算综合评分"""
        return (
            self.motivation_alignment * 0.35 +
            self.code_adherence * 0.30 +
            self.personality_consistency * 0.20 +
            self.historical_consistency * 0.15
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "passed": self.passed,
            "overall_score": round(self.overall_score, 2),
            "dimension_scores": {
                "motivation_alignment": round(self.motivation_alignment, 2),
                "code_adherence": round(self.code_adherence, 2),
                "personality_consistency": round(self.personality_consistency, 2),
                "historical_consistency": round(self.historical_consistency, 2)
            },
            "issues": self.issues,
            "suggestions": self.suggestions,
            "analysis": self.analysis
        }


class CharacterConsistencyTracker:
    """
    角色一致性追踪器
    
    核心功能：
    1. 维护角色档案（动机、准则、性格）
    2. 记录历史决策
    3. 验证新行为的一致性
    4. 识别行为模式
    """
    
    # 验证提示词模板
    VALIDATION_PROMPT = """请作为专业编辑，验证以下角色行为是否与其人设一致。

## 角色档案
{character_profile}

## 历史重要决策
{decision_history}

## 待验证的行为

章节：第{chapter_number}章
行为描述：{proposed_action}
情境：{context}

## 验证任务

请从以下维度验证：

1. **动机一致性**：此行为是否符合角色的核心动机「{core_motivation}」？
2. **准则遵守**：此行为是否违背了角色的行为准则「{personal_code}」？
3. **性格一致性**：此行为是否符合角色的性格特质 {personality_traits}？
4. **历史一致性**：此行为是否与角色历史决策一致？

## 输出格式

请以 JSON 格式输出验证结果：
{{
    "passed": true/false,
    "dimension_scores": {{
        "motivation_alignment": 0-1,
        "code_adherence": 0-1,
        "personality_consistency": 0-1,
        "historical_consistency": 0-1
    }},
    "issues": [
        {{
            "type": "motivation_mismatch/code_violation/personality_inconsistency/historical_conflict",
            "description": "问题描述",
            "severity": "critical/high/medium/low"
        }}
    ],
    "analysis": "详细分析",
    "suggestions": ["改进建议 1", "改进建议 2"]
}}
"""
    
    def __init__(self, character_profile: CharacterProfile):
        """
        初始化角色一致性追踪器
        
        Args:
            character_profile: 角色档案
        """
        self.profile = character_profile
        self.decision_history: List[DecisionRecord] = []
        self.behavioral_patterns: Dict[str, BehavioralPattern] = {}
        self.validation_history: List[ConsistencyValidation] = []
        
        logger.info(f"CharacterConsistencyTracker initialized for {character_profile.name}")
        logger.info(f"Core motivation: {character_profile.core_motivation}")
    
    def record_decision(
        self,
        chapter_number: int,
        decision: str,
        reason: str,
        alternatives: Optional[List[str]] = None,
        consequences: Optional[List[str]] = None
    ):
        """
        记录角色的重要决策
        
        Args:
            chapter_number: 章节号
            decision: 决策内容
            reason: 决策原因
            alternatives: 考虑过的其他选项
            consequences: 后果
        """
        record = DecisionRecord(
            chapter_number=chapter_number,
            decision=decision,
            reason=reason,
            alternatives_considered=alternatives or [],
            consequences=consequences or []
        )
        
        self.decision_history.append(record)
        
        # 更新行为模式
        self._update_behavioral_patterns(record)
        
        logger.info(
            f"Recorded decision for {self.profile.name} in chapter {chapter_number}: {decision}"
        )
    
    def _update_behavioral_patterns(self, decision: DecisionRecord):
        """根据新决策更新行为模式"""
        # 简化实现：识别决策类型并更新模式
        decision_lower = decision.decision.lower()
        
        # 冲突应对模式
        if any(word in decision_lower for word in ["战斗", "逃避", "谈判", "妥协"]):
            if "conflict_response" not in self.behavioral_patterns:
                self.behavioral_patterns["conflict_response"] = BehavioralPattern(
                    pattern_type="conflict_response",
                    description=""
                )
            
            pattern = self.behavioral_patterns["conflict_response"]
            pattern.examples.append(decision.decision)
            
            # 更新描述
            if len(pattern.examples) > 0:
                pattern.description = f"倾向于{decision.decision.split()[-1]}的方式解决冲突"
        
        # 决策模式
        if any(word in decision_lower for word in ["决定", "选择", "放弃", "坚持"]):
            if "decision_making" not in self.behavioral_patterns:
                self.behavioral_patterns["decision_making"] = BehavioralPattern(
                    pattern_type="decision_making",
                    description=""
                )
            
            pattern = self.behavioral_patterns["decision_making"]
            pattern.examples.append(decision.decision)
    
    def validate_action(
        self,
        proposed_action: str,
        context: str,
        chapter_number: int
    ) -> ConsistencyValidation:
        """
        验证角色行为是否一致
        
        Args:
            proposed_action: 待验证的行为
            context: 行为发生的情境
            chapter_number: 章节号
        
        Returns:
            ConsistencyValidation
        """
        logger.info(f"Validating action for {self.profile.name}: {proposed_action[:50]}...")
        
        validation = ConsistencyValidation()
        
        # 维度 1：动机一致性
        motivation_result = self._check_motivation_alignment(
            proposed_action, context
        )
        validation.motivation_alignment = motivation_result["score"]
        if not motivation_result["aligned"]:
            validation.issues.append({
                "type": "motivation_mismatch",
                "description": motivation_result["reason"],
                "severity": "high"
            })
        
        # 维度 2：准则遵守
        code_result = self._check_code_adherence(proposed_action)
        validation.code_adherence = code_result["score"]
        if not code_result["adherent"]:
            validation.issues.append({
                "type": "code_violation",
                "description": code_result["reason"],
                "severity": "critical"
            })
        
        # 维度 3：性格一致性
        personality_result = self._check_personality_consistency(
            proposed_action, context
        )
        validation.personality_consistency = personality_result["score"]
        if not personality_result["consistent"]:
            validation.issues.append({
                "type": "personality_inconsistency",
                "description": personality_result["reason"],
                "severity": "medium"
            })
        
        # 维度 4：历史一致性
        historical_result = self._check_historical_consistency(
            proposed_action, chapter_number
        )
        validation.historical_consistency = historical_result["score"]
        if historical_result["conflicts"]:
            for conflict in historical_result["conflicts"]:
                validation.issues.append({
                    "type": "historical_conflict",
                    "description": conflict,
                    "severity": "high"
                })
        
        # 综合判断
        validation.passed = (
            validation.overall_score >= 0.7 and
            not any(issue["severity"] == "critical" for issue in validation.issues)
        )
        
        # 生成分析和建议
        validation.analysis = self._generate_analysis(validation)
        if not validation.passed:
            validation.suggestions = self._generate_suggestions(validation)
        
        # 记录历史
        self.validation_history.append(validation)
        
        logger.info(
            f"Validation completed: score={validation.overall_score:.2f}, "
            f"passed={validation.passed}"
        )
        
        return validation
    
    def _check_motivation_alignment(
        self,
        action: str,
        context: str
    ) -> Dict[str, Any]:
        """检查行为与核心动机的一致性"""
        action_lower = action.lower()
        motivation_lower = self.profile.core_motivation.lower()
        
        # 简化检查：关键词匹配
        # 实际应该用 LLM 进行语义分析
        
        score = 0.5  # 基础分
        
        # 检查是否包含动机相关词汇
        motivation_keywords = motivation_lower.split()
        matches = sum(1 for kw in motivation_keywords if kw in action_lower or kw in context.lower())
        
        if matches > 0:
            score += 0.3 * (matches / len(motivation_keywords))
        
        # 检查是否服务于角色目标
        for goal in self.profile.goals:
            if goal.lower() in action_lower or goal.lower() in context.lower():
                score += 0.2
                break
        
        return {
            "aligned": score >= 0.6,
            "score": min(1.0, score),
            "reason": (
                "行为与核心动机一致" if score >= 0.6
                else "行为与核心动机关联不明确"
            )
        }
    
    def _check_code_adherence(self, action: str) -> Dict[str, Any]:
        """检查行为是否遵守个人准则"""
        action_lower = action.lower()
        code_lower = self.profile.personal_code.lower()
        
        # 检查是否明显违背准则
        violating_keywords = [
            "伤害无辜", "背叛", "欺骗", "偷窃", "逃跑"
        ]
        
        for keyword in violating_keywords:
            if keyword in action_lower:
                # 检查是否与准则冲突
                if "不" in code_lower or "拒绝" in code_lower:
                    return {
                        "adherent": False,
                        "score": 0.2,
                        "reason": f"行为可能违背准则「{self.profile.personal_code}」"
                    }
        
        return {
            "adherent": True,
            "score": 1.0,
            "reason": "行为未违背已知准则"
        }
    
    def _check_personality_consistency(
        self,
        action: str,
        context: str
    ) -> Dict[str, Any]:
        """检查行为与性格特质的一致性"""
        score = 0.8  # 基础分
        
        # 根据性格特质检查行为
        for trait in self.profile.personality_traits:
            trait_lower = trait.lower()
            
            # 简化：检查行为是否符合性格
            if "谨慎" in trait_lower:
                if any(word in action.lower() for word in ["冲动", "冒险", "鲁莽"]):
                    score -= 0.2
            elif "勇敢" in trait_lower:
                if any(word in action.lower() for word in ["逃跑", "退缩", "害怕"]):
                    score -= 0.2
            elif "重情义" in trait_lower:
                if any(word in action.lower() for word in ["背叛", "抛弃", "出卖"]):
                    score -= 0.3
        
        return {
            "consistent": score >= 0.6,
            "score": max(0.0, score),
            "reason": (
                "行为与性格一致" if score >= 0.6
                else "行为与某些性格特质不符"
            )
        }
    
    def _check_historical_consistency(
        self,
        action: str,
        chapter_number: int
    ) -> Dict[str, Any]:
        """检查行为与历史决策的一致性"""
        conflicts = []
        score = 1.0
        
        action_lower = action.lower()
        
        # 检查与历史决策的冲突
        for record in self.decision_history:
            if record.chapter_number >= chapter_number:
                continue
            
            # 简化检查：寻找相反的决策
            if "放弃" in action_lower and "坚持" in record.decision.lower():
                conflicts.append(
                    f"与第{record.chapter_number}章的决策「{record.decision}」矛盾"
                )
                score -= 0.3
            
            if "接受" in action_lower and "拒绝" in record.decision.lower():
                conflicts.append(
                    f"与第{record.chapter_number}章的决策「{record.decision}」矛盾"
                )
                score -= 0.3
        
        return {
            "consistent": len(conflicts) == 0,
            "score": max(0.0, score),
            "conflicts": conflicts
        }
    
    def _generate_analysis(self, validation: ConsistencyValidation) -> str:
        """生成详细分析"""
        parts = []
        
        # 动机分析
        if validation.motivation_alignment >= 0.8:
            parts.append("行为与核心动机高度一致。")
        elif validation.motivation_alignment >= 0.6:
            parts.append("行为与核心动机基本一致。")
        else:
            parts.append("行为与核心动机关联不明确。")
        
        # 准则分析
        if validation.code_adherence >= 0.9:
            parts.append("行为严格遵守个人准则。")
        else:
            parts.append("行为可能违背个人准则。")
        
        # 性格分析
        if validation.personality_consistency >= 0.8:
            parts.append("行为符合性格特质。")
        else:
            parts.append("行为与某些性格特质不符。")
        
        # 历史分析
        if validation.historical_consistency >= 0.9:
            parts.append("行为与历史决策一致。")
        else:
            parts.append("行为与历史决策存在冲突。")
        
        return " ".join(parts)
    
    def _generate_suggestions(self, validation: ConsistencyValidation) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        if validation.motivation_alignment < 0.6:
            suggestions.append(
                f"建议明确说明此行为如何服务于「{self.profile.core_motivation}」"
            )
        
        if validation.code_adherence < 0.8:
            suggestions.append(
                f"建议重新考虑此行为是否违背「{self.profile.personal_code}」"
            )
        
        if validation.personality_consistency < 0.6:
            traits_str = ", ".join(self.profile.personality_traits[:2])
            suggestions.append(
                f"建议调整行为方式以体现{traits_str}的特点"
            )
        
        if validation.historical_consistency < 0.8:
            suggestions.append(
                "建议说明角色为何改变之前的决定"
            )
        
        return suggestions
    
    def build_character_prompt(self) -> str:
        """
        构建角色一致性提示词
        
        用于在生成前提醒作家
        """
        return f"""
{self.profile.to_prompt()}

## 历史重要决策
{self._format_decision_history()}

## 行为模式
{self._format_behavioral_patterns()}

## 创作约束

当{self.profile.name}面临选择时：
1. **必须优先考虑**：{self.profile.core_motivation}
2. **绝不能违背**：{self.profile.personal_code}
3. **决策风格应体现**：{', '.join(self.profile.personality_traits[:2])}

## 警告

避免以下问题：
- 行为与核心动机不符
- 违背个人准则
- 性格前后不一致
- 与历史决策矛盾
"""
    
    def _format_decision_history(self) -> str:
        """格式化决策历史"""
        if not self.decision_history:
            return "（无历史决策记录）"
        
        parts = []
        for record in self.decision_history[-5:]:  # 最近 5 个决策
            parts.append(
                f"- 第{record.chapter_number}章：{record.decision} "
                f"（原因：{record.reason}）"
            )
        
        return "\n".join(parts)
    
    def _format_behavioral_patterns(self) -> str:
        """格式化行为模式"""
        if not self.behavioral_patterns:
            return "（无明显行为模式）"
        
        parts = []
        for pattern in self.behavioral_patterns.values():
            parts.append(f"- {pattern.to_prompt()}")
        
        return "\n".join(parts)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.validation_history:
            return {
                "total_validations": 0,
                "pass_rate": 0,
                "average_score": 0
            }
        
        total = len(self.validation_history)
        passed = sum(1 for v in self.validation_history if v.passed)
        avg_score = sum(v.overall_score for v in self.validation_history) / total
        
        return {
            "total_validations": total,
            "pass_rate": round(passed / total, 2),
            "average_score": round(avg_score, 2)
        }


# 便捷函数
def create_character_tracker(
    name: str,
    core_motivation: str,
    personal_code: str,
    personality_traits: List[str],
    **kwargs
) -> CharacterConsistencyTracker:
    """便捷函数：创建角色追踪器"""
    profile = CharacterProfile(
        name=name,
        core_motivation=core_motivation,
        personal_code=personal_code,
        personality_traits=personality_traits,
        **kwargs
    )
    return CharacterConsistencyTracker(profile)


def validate_character_action(
    character_data: Dict[str, Any],
    proposed_action: str,
    context: str,
    chapter_number: int,
    decision_history: Optional[List[Dict[str, Any]]] = None
) -> ConsistencyValidation:
    """便捷函数：验证角色行为"""
    profile = CharacterProfile.from_character_data(character_data)
    tracker = CharacterConsistencyTracker(profile)
    
    # 添加历史决策
    if decision_history:
        for record in decision_history:
            tracker.record_decision(
                chapter_number=record.get("chapter", 0),
                decision=record.get("decision", ""),
                reason=record.get("reason", "")
            )
    
    return tracker.validate_action(proposed_action, context, chapter_number)
