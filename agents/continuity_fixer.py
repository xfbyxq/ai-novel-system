"""
ContinuityFixerAgent - 连续性问题修复Agent.

负责修复连续性审查员发现的问题，在不改变核心剧情的前提下修正：
- 角色行为与设定不符
- 时间线矛盾
- 地理位置错误
- 伏笔前后矛盾
- 称呼不一致
"""

from typing import Any, Dict, List

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient


class ContinuityFixerAgent:
    """连续性问题修复Agent.

    当连续性审查员发现严重问题时，自动修复章节内容.
    采用最小修改原则，仅修复指出的问题，保留原文风格。
    """

    SYSTEM_PROMPT = """你是一位资深的小说编辑，专门负责修复章节中的连续性问题.

你的职责是：
1. 在不改变核心剧情的前提下，精确修复指出的问题
2. 保持原文的写作风格和语言特色
3. 修改幅度尽量小，只修改必要的部分
4. 确保修改后的内容与上下文自然衔接

你需要修复的问题类型包括：
- 角色行为与设定不符：确保角色言行符合其性格和背景
- 时间线矛盾：修正时间描述的冲突
- 地理位置错误：修正地点描述的错误
- 伏笔前后矛盾：确保伏笔内容前后一致
- 称呼不一致：统一人物称呼

输出要求：
- 直接输出修复后的完整章节内容
- 不要添加任何解释或说明
- 保持原文的段落格式"""

    FIX_TASK_TEMPLATE = """请修复以下章节中的连续性问题.

## 原文内容.
{original_content}

## 需要修复的问题
{issues}

## 相关背景信息
{context}

请直接输出修复后的完整章节内容，不要添加任何解释。"""

    def __init__(self, qwen_client: QwenClient, cost_tracker: CostTracker):
        """初始化修复Agent.

        Args:
            qwen_client: 通义千问客户端
            cost_tracker: 成本追踪器
        """
        self.client = qwen_client
        self.cost_tracker = cost_tracker

    async def should_fix(self, continuity_report: Dict[str, Any]) -> bool:
        """判断是否需要修复.

        Args:
            continuity_report: 连续性审查报告

        Returns:
            是否需要修复
        """
        issues = continuity_report.get("issues", [])
        if not issues:
            return False

        # 检查是否有严重问题
        critical_count = sum(
            1
            for issue in issues
            if issue.get("severity") in ["critical", "high", "严重", "高"]
        )

        # 有严重或高优先级问题时需要修复
        return critical_count > 0

    def _format_issues(self, issues: List[Dict[str, Any]]) -> str:
        """格式化问题列表.

        Args:
            issues: 问题列表

        Returns:
            格式化的问题描述
        """
        formatted = []
        for i, issue in enumerate(issues, 1):
            severity = issue.get("severity", "unknown")
            issue_type = issue.get("type", issue.get("category", "未知类型"))
            description = issue.get("description", issue.get("detail", ""))
            location = issue.get("location", "")
            suggestion = issue.get("suggestion", issue.get("fix_suggestion", ""))

            issue_text = f"{i}. [{severity}] {issue_type}"
            if location:
                issue_text += f"\n   位置：{location}"
            if description:
                issue_text += f"\n   问题：{description}"
            if suggestion:
                issue_text += f"\n   建议：{suggestion}"

            formatted.append(issue_text)

        return "\n\n".join(formatted)

    def _filter_critical_issues(
        self, issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """筛选需要修复的严重问题.

        Args:
            issues: 所有问题列表

        Returns:
            需要修复的问题列表
        """
        critical_severities = ["critical", "high", "严重", "高", "中"]
        return [
            issue for issue in issues if issue.get("severity") in critical_severities
        ]

    async def fix_issues(
        self, content: str, continuity_report: Dict[str, Any], context: str = ""
    ) -> Dict[str, Any]:
        """修复连续性问题.

        Args:
            content: 原始章节内容
            continuity_report: 连续性审查报告
            context: 相关上下文信息（角色设定、世界观等）

        Returns:
            修复结果，包含:
            - fixed_content: 修复后的内容
            - fixed_issues: 修复的问题列表
            - unchanged: 是否未做修改
        """
        issues = continuity_report.get("issues", [])

        # 筛选需要修复的问题
        critical_issues = self._filter_critical_issues(issues)

        if not critical_issues:
            logger.info("无严重问题需要修复")
            return {"fixed_content": content, "fixed_issues": [], "unchanged": True}

        logger.info(f"🔧 开始修复 {len(critical_issues)} 个连续性问题")

        # 构建修复任务提示词
        issues_text = self._format_issues(critical_issues)

        task_prompt = self.FIX_TASK_TEMPLATE.format(
            original_content=content,
            issues=issues_text,
            context=context or "（无额外上下文）",
        )

        try:
            # 调用 LLM 修复
            response = await self.client.chat(
                prompt=task_prompt,
                system=self.SYSTEM_PROMPT,
                temperature=0.5,  # 较低温度确保稳定性
                max_tokens=8192,
            )

            # 记录成本
            usage = response.get("usage", {})
            self.cost_tracker.record(
                agent_name="连续性修复Agent",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )

            fixed_content = response.get("content", "")

            # 验证修复结果
            if not fixed_content or len(fixed_content) < len(content) * 0.5:
                logger.warning("修复结果异常（内容过短），保留原文")
                return {
                    "fixed_content": content,
                    "fixed_issues": [],
                    "unchanged": True,
                    "error": "修复结果验证失败",
                }

            logger.info(f"✅ 连续性问题修复完成，修复了 {len(critical_issues)} 个问题")

            return {
                "fixed_content": fixed_content,
                "fixed_issues": critical_issues,
                "unchanged": False,
            }

        except Exception as e:
            logger.error(f"❌ 连续性修复失败: {e}")
            return {
                "fixed_content": content,
                "fixed_issues": [],
                "unchanged": True,
                "error": str(e),
            }

    async def fix_specific_issue(
        self, content: str, issue: Dict[str, Any], context: str = ""
    ) -> str:
        """修复单个特定问题.

        Args:
            content: 原始内容
            issue: 问题描述
            context: 上下文信息

        Returns:
            修复后的内容
        """
        single_issue_prompt = f"""请修复以下内容中的一个特定问题.

## 原文内容.
{content}

## 需要修复的问题
类型：{issue.get('type', '未知')}
描述：{issue.get('description', '')}
位置：{issue.get('location', '未指定')}
建议：{issue.get('suggestion', '')}

## 上下文
{context or '（无）'}

请直接输出修复后的内容，只修改问题相关的部分。"""

        try:
            response = await self.client.chat(
                prompt=single_issue_prompt,
                system=self.SYSTEM_PROMPT,
                temperature=0.4,
                max_tokens=4096,
            )

            usage = response.get("usage", {})
            self.cost_tracker.record(
                agent_name="连续性修复Agent(单问题)",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )

            return response.get("content", content)

        except Exception as e:
            logger.error(f"单问题修复失败: {e}")
            return content


class ContinuityFixerPipeline:
    """连续性修复流水线.

    集成到章节生成流程中，在连续性检查后自动修复问题.
    """

    # 重新验证提示词模板
    RECHECK_PROMPT_TEMPLATE = """请作为专业编辑，验证以下连续性问题在修复后的内容中是否已解决.

## 修复后的章节内容
{fixed_content}

## 需要验证的问题清单
{issues_list}

## 验证任务
请逐一检查每个问题在修复后的内容中是否仍然存在.
对于每个问题，判断：
1. 已解决（resolved）：问题已被修复，内容正确
2. 仍存在（remaining）：问题未被修复，或修复不彻底

## 输出格式
请以 JSON 格式输出：
{{
    "resolved": [
        {{
            "type": "问题类型",
            "description": "问题描述",
            "verification": "验证说明，为什么认为已解决"
        }}
    ],
    "remaining": [
        {{
            "type": "问题类型",
            "description": "问题描述",
            "severity": "critical/high/medium/low",
            "reason": "为什么认为仍未解决"
        }}
    ]
}}
"""

    def __init__(self, qwen_client: QwenClient, cost_tracker: CostTracker):
        """初始化方法."""
        self.fixer = ContinuityFixerAgent(qwen_client, cost_tracker)
        self.max_fix_attempts = 2  # 最大修复尝试次数

    async def process(
        self,
        content: str,
        continuity_report: Dict[str, Any],
        context: str = "",
        chapter_number: int = 0,
    ) -> Dict[str, Any]:
        """处理章节内容，必要时进行修复.

        Args:
            content: 章节内容
            continuity_report: 连续性审查报告
            context: 上下文信息
            chapter_number: 章节号

        Returns:
            处理结果
        """
        # 检查是否需要修复
        if not await self.fixer.should_fix(continuity_report):
            logger.info(f"第{chapter_number}章无需修复")
            return {
                "content": content,
                "fixed": False,
                "attempts": 0,
                "quality_score": continuity_report.get("quality_score", 0),
            }

        # 尝试修复
        current_content = content
        fix_history = []

        for attempt in range(self.max_fix_attempts):
            logger.info(
                f"第{chapter_number}章修复尝试 {attempt + 1}/{self.max_fix_attempts}"
            )

            fix_result = await self.fixer.fix_issues(
                content=current_content,
                continuity_report=continuity_report,
                context=context,
            )

            fix_history.append(
                {
                    "attempt": attempt + 1,
                    "fixed_issues": len(fix_result.get("fixed_issues", [])),
                    "unchanged": fix_result.get("unchanged", True),
                }
            )

            if fix_result.get("unchanged"):
                break

            current_content = fix_result["fixed_content"]

            # 目前简化实现，修复一次后直接返回
            break

        return {
            "content": current_content,
            "fixed": not fix_result.get("unchanged", True),
            "attempts": len(fix_history),
            "fix_history": fix_history,
            "quality_score": continuity_report.get("quality_score", 0),
        }

    async def fix_with_verification(
        self,
        content: str,
        continuity_report: Dict[str, Any],
        context: str = "",
        max_attempts: int = 3,
    ) -> Dict[str, Any]:
        """修复连贯性问题并自动验证修复结果.

        实现修复-验证闭环：修复后重新检查问题是否真正解决.

        Args:
            content: 待修复的章节内容
            continuity_report: 连贯性检查报告，包含 issues 列表
            context: 上下文信息
            max_attempts: 最大修复尝试次数

        Returns:
            包含 fixed_content, attempts, verified, fix_history 的字典
        """
        issues = continuity_report.get("issues", [])
        critical_issues = self.fixer._filter_critical_issues(issues)

        if not critical_issues:
            logger.info("无严重问题需要修复，跳过验证流程")
            return {
                "fixed_content": content,
                "attempts": 0,
                "verified": True,
                "fix_history": [],
                "all_resolved": True,
            }

        current_content = content
        fix_history: List[Dict[str, Any]] = []
        verified = False
        all_resolved = False

        for attempt in range(1, max_attempts + 1):
            logger.info(f"🔧 修复尝试 {attempt}/{max_attempts}，当前问题数: {len(critical_issues)}")

            # 调用修复方法
            fix_result = await self.fixer.fix_issues(
                content=current_content,
                continuity_report={"issues": critical_issues},
                context=context,
            )

            fixed_content = fix_result.get("fixed_content", current_content)
            unchanged = fix_result.get("unchanged", True)

            # 如果内容未变更，提前退出
            if unchanged or fixed_content == current_content:
                logger.warning("修复未产生变更，提前退出修复循环")
                fix_history.append({
                    "attempt": attempt,
                    "fixed_issues": 0,
                    "unchanged": True,
                    "verified": False,
                })
                break

            # 重新验证修复结果
            recheck_result = await self._recheck_fixes(fixed_content, {"issues": critical_issues})
            all_resolved = recheck_result.get("all_resolved", False)
            resolved_count = len(recheck_result.get("resolved_issues", []))
            remaining_count = len(recheck_result.get("remaining_issues", []))

            fix_history.append({
                "attempt": attempt,
                "fixed_issues": len(fix_result.get("fixed_issues", [])),
                "unchanged": False,
                "verified": all_resolved,
                "resolved_count": resolved_count,
                "remaining_count": remaining_count,
            })

            logger.info(
                f"✅ 验证结果: 已解决 {resolved_count} 个问题，"
                f"剩余 {remaining_count} 个问题"
            )

            if all_resolved:
                verified = True
                current_content = fixed_content
                logger.info(f"🎉 所有严重问题已在第 {attempt} 轮修复完成")
                break

            # 准备下一轮修复
            current_content = fixed_content
            remaining_report = recheck_result.get("remaining_report", {})
            critical_issues = remaining_report.get("issues", [])

            if not critical_issues:
                verified = True
                all_resolved = True
                logger.info("无剩余严重问题，修复完成")
                break

        return {
            "fixed_content": current_content,
            "attempts": len(fix_history),
            "verified": verified,
            "all_resolved": all_resolved,
            "fix_history": fix_history,
        }

    async def _recheck_fixes(
        self,
        fixed_content: str,
        original_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        """重新检查修复后的内容，验证问题是否已解决.

        使用 LLM 快速验证修复效果，不需要完整的连贯性检查.

        Args:
            fixed_content: 修复后的章节内容
            original_report: 原始问题报告

        Returns:
            {
                "all_resolved": bool,
                "resolved_issues": List[Dict],
                "remaining_issues": List[Dict],
                "remaining_report": Dict (用于下一轮修复)
            }
        """
        issues = original_report.get("issues", [])

        # 筛选严重问题
        critical_severities = ["critical", "high", "严重", "高"]
        critical_issues = [
            issue for issue in issues
            if issue.get("severity") in critical_severities
        ]

        if not critical_issues:
            return {
                "all_resolved": True,
                "resolved_issues": [],
                "remaining_issues": [],
                "remaining_report": {"issues": []},
            }

        # 构建问题清单
        issues_list = []
        for i, issue in enumerate(critical_issues, 1):
            issue_type = issue.get("type", issue.get("category", "未知类型"))
            description = issue.get("description", issue.get("detail", ""))
            severity = issue.get("severity", "unknown")
            issues_list.append(
                f"{i}. [{severity}] {issue_type}: {description}"
            )

        # 构建验证提示词
        recheck_prompt = self.RECHECK_PROMPT_TEMPLATE.format(
            fixed_content=fixed_content[:3000],  # 限制长度避免token过多
            issues_list="\n".join(issues_list),
        )

        try:
            # 调用 LLM 进行验证
            response = await self.fixer.client.chat(
                prompt=recheck_prompt,
                system="你是一位专业的编辑，擅长验证小说内容的连续性问题修复效果。",
                temperature=0.3,
                max_tokens=2048,
            )

            # 记录成本
            usage = response.get("usage", {})
            self.fixer.cost_tracker.record(
                agent_name="连续性修复验证",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )

            # 解析 JSON 响应
            import json
            content = response.get("content", "")

            # 尝试直接解析
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # 尝试提取 JSON 代码块
                import re
                json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        result = {"resolved": [], "remaining": []}
                else:
                    # 尝试提取花括号内容
                    brace_match = re.search(r"(\{.*\})", content, re.DOTALL)
                    if brace_match:
                        try:
                            result = json.loads(brace_match.group(1))
                        except json.JSONDecodeError:
                            result = {"resolved": [], "remaining": []}
                    else:
                        result = {"resolved": [], "remaining": []}

            resolved_issues = result.get("resolved", [])
            remaining_issues = result.get("remaining", [])

            all_resolved = len(remaining_issues) == 0 and len(resolved_issues) > 0

            # 构造 remaining_report 供下一轮修复使用
            remaining_report = {
                "issues": [
                    {
                        "type": issue.get("type", "未知"),
                        "description": issue.get("description", ""),
                        "severity": issue.get("severity", "high"),
                        "reason": issue.get("reason", ""),
                    }
                    for issue in remaining_issues
                ]
            }

            logger.info(
                f"重新验证完成: 已解决 {len(resolved_issues)} 个，"
                f"剩余 {len(remaining_issues)} 个"
            )

            return {
                "all_resolved": all_resolved,
                "resolved_issues": resolved_issues,
                "remaining_issues": remaining_issues,
                "remaining_report": remaining_report,
            }

        except Exception as e:
            logger.error(f"重新验证失败: {e}")
            # 验证失败时保守返回，认为问题未解决
            return {
                "all_resolved": False,
                "resolved_issues": [],
                "remaining_issues": critical_issues,
                "remaining_report": {"issues": critical_issues},
            }
