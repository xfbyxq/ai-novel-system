"""
连贯性验证引擎

使用 LLM 验证新章节是否满足合理期待。
区分"连贯性问题"和"艺术性打破期待"。
"""

import json
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.qwen_client import QwenClient

from agents.continuity_models import (
    ContinuityConstraint,
    ConstraintList,
    ValidationReport,
)


class ValidationEngine:
    """
    连贯性验证引擎

    核心方法：
    1. 将约束和生成内容一起交给 LLM
    2. 让 LLM 判断是否满足约束
    3. 如果不满足，让 LLM 描述具体违反情况
    4. 区分"问题"和"艺术性打破期待"
    """

    # 验证提示词模板
    VALIDATION_PROMPT = """请作为专业编辑，评估以下章节开头是否满足了读者的合理期待。

## 上一章结尾
{previous_ending}

## 推断的读者期待
{constraints_description}

## 本章开头
{new_chapter_beginning}

## 评估任务
请评估本章开头是否合理地回应了上一章结尾引发的读者期待。

**重要说明**：
1. "回应期待"不等于"满足所有期待"，有时打破期待也是有效的文学手法
2. 关键是评估这种处理是否有艺术合理性，而非机械检查
3. 如果打破期待，是否有足够的叙事支撑？
4. 考虑小说的整体类型和风格

## 输出格式
请以 JSON 格式输出评估结果：
{{
    "overall_assessment": "通过/需改进/严重问题",
    "satisfied_constraints": [
        {{
            "constraint": "约束描述",
            "how_satisfied": "如何满足的（引用原文）"
        }}
    ],
    "unsatisfied_constraints": [
        {{
            "constraint": "约束描述",
            "why_unsatisfied": "为什么未满足",
            "severity": "critical/high/medium/low",
            "suggestion": "如何改进（如果确实需要改进）"
        }}
    ],
    "artistic_breaking": [
        {{
            "constraint": "约束描述",
            "why_breaking_is_valid": "为什么这种打破是艺术上合理的"
        }}
    ],
    "quality_score": 0-100
}}
"""

    def __init__(self, qwen_client: Optional[QwenClient] = None):
        """
        初始化验证引擎

        Args:
            qwen_client: 通义千问客户端
        """
        self.client = qwen_client or QwenClient()
        logger.info("ValidationEngine initialized")

    async def validate(
        self,
        previous_ending: str,
        new_chapter_beginning: str,
        constraints: ConstraintList,
    ) -> ValidationReport:
        """
        验证新章节是否满足连贯性约束

        Args:
            previous_ending: 上一章结尾（500-800 字）
            new_chapter_beginning: 新章节开头（500-800 字）
            constraints: 推断的约束列表

        Returns:
            验证报告
        """
        logger.info(
            f"开始验证连贯性，约束数：{len(constraints)}, "
            f"新章节长度：{len(new_chapter_beginning)} 字"
        )

        try:
            # 构建约束描述
            constraints_description = self._format_constraints(constraints)

            # 调用 LLM 验证
            response = await self.client.chat(
                prompt=self.VALIDATION_PROMPT.format(
                    previous_ending=previous_ending,
                    constraints_description=constraints_description,
                    new_chapter_beginning=new_chapter_beginning,
                ),
                system="你是一位专业的文学编辑，擅长评估章节过渡的连贯性和艺术性。",
                temperature=0.3,
                max_tokens=2048,
            )

            # 解析结果
            content = response.get("content", "")
            report_data = self._parse_llm_response(content)

            # 创建验证报告
            report = self._create_validation_report(report_data, constraints)

            logger.info(
                f"验证完成：{report.overall_assessment}, "
                f"质量评分：{report.quality_score:.1f}"
            )

            return report

        except Exception as e:
            logger.error(f"验证失败：{e}", exc_info=True)
            # 返回一个保守的验证报告
            return ValidationReport(
                overall_assessment="需改进",
                quality_score=50.0,
                suggestions=["自动验证失败，建议人工审核"],
            )

    def _format_constraints(self, constraints: ConstraintList) -> str:
        """
        格式化约束描述

        Args:
            constraints: 约束列表

        Returns:
            格式化的约束描述文本
        """
        if not constraints:
            return "（无特殊期待）"

        lines = []
        for i, c in enumerate(constraints, 1):
            line = f"{i}. [{c.constraint_type}] {c.description}"
            if c.priority >= 8:
                line += " (高优先级)"
            lines.append(line)

        return "\n".join(lines)

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """
        解析 LLM 响应

        使用多种策略解析 JSON：
        1. 直接解析
        2. 提取代码块中的 JSON
        3. 提取花括号内的 JSON

        Args:
            content: LLM 响应的原始内容

        Returns:
            解析后的字典
        """
        import re

        # 策略 1: 直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 策略 2: 提取代码块中的 JSON
        json_block_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL
        )
        if json_block_match:
            try:
                return json.loads(json_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # 策略 3: 提取花括号内的 JSON
        brace_match = re.search(r"(\{.*?\})", content, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError:
                pass

        logger.warning("无法解析 LLM 响应，返回默认结构")
        return {
            "overall_assessment": "需改进",
            "quality_score": 50.0,
            "satisfied_constraints": [],
            "unsatisfied_constraints": [],
            "artistic_breaking": [],
        }

    def _create_validation_report(
        self, report_data: Dict[str, Any], constraints: ConstraintList
    ) -> ValidationReport:
        """
        创建验证报告

        Args:
            report_data: LLM 解析后的数据
            constraints: 原始约束列表

        Returns:
            ValidationReport 对象
        """
        # 提取各个字段
        overall = report_data.get("overall_assessment", "需改进")
        quality_score = float(report_data.get("quality_score", 50.0))

        satisfied = report_data.get("satisfied_constraints", [])
        unsatisfied = report_data.get("unsatisfied_constraints", [])
        artistic_breaking = report_data.get("artistic_breaking", [])

        # 提取建议和问题
        suggestions = []
        critical_issues = []

        for item in unsatisfied:
            severity = item.get("severity", "medium")
            suggestion = item.get("suggestion", "")

            if suggestion:
                suggestions.append(suggestion)

            if severity in ["critical", "high"]:
                issue_desc = (
                    f"[{severity}] {item.get('constraint', '未知约束')}: "
                    f"{item.get('why_unsatisfied', '')}"
                )
                critical_issues.append(issue_desc)

        # 创建报告
        report = ValidationReport(
            overall_assessment=overall,
            satisfied_constraints=satisfied,
            unsatisfied_constraints=unsatisfied,
            artistic_breaking=artistic_breaking,
            suggestions=suggestions,
            critical_issues=critical_issues,
            quality_score=quality_score,
        )

        return report

    async def validate_with_retry(
        self,
        previous_ending: str,
        new_chapter_beginning: str,
        constraints: ConstraintList,
        max_retries: int = 2,
    ) -> ValidationReport:
        """
        带重试的验证

        如果第一次验证失败，可以尝试重新生成评估。

        Args:
            previous_ending: 上一章结尾
            new_chapter_beginning: 新章节开头
            constraints: 约束列表
            max_retries: 最大重试次数

        Returns:
            验证报告
        """
        last_report = None

        for attempt in range(max_retries + 1):
            report = await self.validate(
                previous_ending=previous_ending,
                new_chapter_beginning=new_chapter_beginning,
                constraints=constraints,
            )

            # 如果验证通过或不是解析错误，直接返回
            if report.overall_assessment != "需改进" or attempt >= max_retries:
                return report

            # 否则记录日志并重试
            logger.warning(f"验证结果不理想，重试 {attempt + 1}/{max_retries}")
            last_report = report

        return last_report

    def calculate_transition_quality(self, report: ValidationReport) -> str:
        """
        根据验证报告计算过渡质量等级

        Args:
            report: 验证报告

        Returns:
            质量等级 "优秀"|"良好"|"合格"|"需改进"|"差"
        """
        score = report.quality_score

        if score >= 90:
            return "优秀"
        elif score >= 80:
            return "良好"
        elif score >= 70:
            return "合格"
        elif score >= 60:
            return "需改进"
        else:
            return "差"


# 便捷函数
async def validate_chapter_transition(
    previous_ending: str,
    new_chapter_beginning: str,
    constraints: ConstraintList,
    qwen_client: Optional[QwenClient] = None,
) -> ValidationReport:
    """
    便捷函数：验证章节过渡

    Args:
        previous_ending: 上一章结尾
        new_chapter_beginning: 新章节开头
        constraints: 约束列表
        qwen_client: 通义千问客户端

    Returns:
        验证报告
    """
    engine = ValidationEngine(qwen_client)
    return await engine.validate(previous_ending, new_chapter_beginning, constraints)
