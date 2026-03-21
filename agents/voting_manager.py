"""投票共识机制 - 多 Agent 对关键决策进行投票"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient


@dataclass
class VoteCast:
    """单个 Agent 的投票"""

    voter_name: str
    voter_role: str
    chosen_option: str
    reasoning: str
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "voter_name": self.voter_name,
            "voter_role": self.voter_role,
            "chosen_option": self.chosen_option,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


@dataclass
class VoteResult:
    """投票结果"""

    topic: str = ""
    winning_option: str = ""
    vote_details: List[VoteCast] = field(default_factory=list)
    consensus_strength: float = 0.0  # 0-1, 共识强度
    option_scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "winning_option": self.winning_option,
            "consensus_strength": self.consensus_strength,
            "option_scores": self.option_scores,
            "vote_details": [v.to_dict() for v in self.vote_details],
        }


VOTING_PARTICIPANT_PROMPT = """你是{voter_role}，现在需要对以下创作决策进行投票。

决策主题：
{topic}

可选方案：
{options_text}

当前创作上下文：
{context}

请从你的专业视角（{perspective}）分析各方案的优劣，并投票。

请以JSON格式输出（不要输出其他内容）：
{{
    "chosen_option": "你选择的方案（必须是上面列出的方案之一）",
    "reasoning": "你选择此方案的详细理由（2-3句话）",
    "confidence": 0.85
}}"""


class VotingManager:
    """投票共识管理器

    支持多个 Agent 视角对关键决策进行投票，
    通过加权置信度计算获胜方案。
    """

    def __init__(self, client: QwenClient, cost_tracker: CostTracker):
        self.client = client
        self.cost_tracker = cost_tracker

    async def initiate_vote(
        self,
        topic: str,
        options: List[str],
        context: str,
        voters: List[Dict[str, str]],
    ) -> VoteResult:
        """发起一次投票

        Args:
            topic: 投票主题
            options: 可选方案列表
            context: 当前创作上下文
            voters: 投票者列表，每项包含 {name, role, perspective}
                例如: [
                    {"name": "世界观架构师", "role": "世界观专家", "perspective": "世界观一致性与扩展性"},
                    {"name": "角色设计师", "role": "角色专家", "perspective": "角色发展与关系深度"},
                ]

        Returns:
            VoteResult
        """
        logger.info(f"[VotingManager] 发起投票: {topic}, 参与者: {len(voters)}")

        options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))

        # 并行调用所有投票者
        tasks = []
        for voter in voters:
            prompt = VOTING_PARTICIPANT_PROMPT.format(
                voter_role=voter["role"],
                topic=topic,
                options_text=options_text,
                context=context[:3000],  # 截断以控制 token
                perspective=voter.get("perspective", voter["role"]),
            )
            tasks.append(self._collect_vote(voter, prompt))

        vote_casts = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤有效投票
        valid_votes: List[VoteCast] = []
        for v in vote_casts:
            if isinstance(v, VoteCast):
                valid_votes.append(v)
            else:
                logger.warning(f"[VotingManager] 投票失败: {v}")

        # 计算加权结果
        result = self._calculate_result(topic, options, valid_votes)

        logger.info(
            f"[VotingManager] 投票完成: winning={result.winning_option}, "
            f"consensus={result.consensus_strength:.2f}"
        )
        return result

    async def _collect_vote(self, voter: Dict[str, str], prompt: str) -> VoteCast:
        """收集单个投票者的投票"""
        try:
            response = await self.client.chat(
                prompt=prompt,
                system=f"你是{voter['role']}，请严格按照要求投票。",
                temperature=0.5,
                max_tokens=1024,
            )
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=f"投票-{voter['name']}",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )

            data = self._extract_json(response["content"])
            return VoteCast(
                voter_name=voter["name"],
                voter_role=voter["role"],
                chosen_option=data.get("chosen_option", ""),
                reasoning=data.get("reasoning", ""),
                confidence=min(max(float(data.get("confidence", 0.5)), 0.0), 1.0),
            )
        except Exception as e:
            logger.error(f"[VotingManager] {voter['name']} 投票失败: {e}")
            raise

    @staticmethod
    def _calculate_result(
        topic: str, options: List[str], votes: List[VoteCast]
    ) -> VoteResult:
        """按加权置信度计算获胜方案"""
        if not votes:
            return VoteResult(
                topic=topic,
                winning_option=options[0] if options else "",
                consensus_strength=0.0,
            )

        # 加权计分
        option_scores: Dict[str, float] = {opt: 0.0 for opt in options}
        for vote in votes:
            # 模糊匹配：投票结果可能不完全等于选项文本
            matched = vote.chosen_option
            for opt in options:
                if opt in vote.chosen_option or vote.chosen_option in opt:
                    matched = opt
                    break
            if matched in option_scores:
                option_scores[matched] += vote.confidence
            else:
                # 找不到匹配选项时，加到最接近的
                option_scores.setdefault(matched, 0.0)
                option_scores[matched] += vote.confidence

        # 获胜选项
        winning = max(option_scores, key=option_scores.get)
        total_weight = sum(option_scores.values())
        consensus = option_scores[winning] / total_weight if total_weight > 0 else 0

        return VoteResult(
            topic=topic,
            winning_option=winning,
            vote_details=votes,
            consensus_strength=round(consensus, 3),
            option_scores={k: round(v, 3) for k, v in option_scores.items()},
        )

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        text = text.strip()

        # 1. 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        import re

        # 2. 尝试提取代码块中的 JSON
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 3. 提取大括号内的内容
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_text = text[start : end + 1]

            # 4. 修复中文引号问题：将中文引号替换为英文引号
            json_text = json_text.replace('"', '"').replace('"', '"')

            # 5. 尝试解析修复后的 JSON
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass

            # 6. 尝试更激进的修复：处理不规范的键名引号
            try:
                # 匹配 "key": 或 ': 或 key: 模式
                fixed_text = re.sub(r'["\']?(\w+)["\']?\s*:', r'"\1":', json_text)
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                pass

            # 7. 尝试逐字段提取（最激进的方法）
            try:
                result = {}
                # 提取 chosen_option
                match = re.search(r'"chosen_option"\s*:\s*"([^"]+)"', json_text)
                if match:
                    result["chosen_option"] = match.group(1)

                # 提取 reasoning - 处理值中包含引号的情况
                match = re.search(
                    r'"reasoning"\s*:\s*"(.+?)"(?:\s*,|\s*\})', json_text, re.DOTALL
                )
                if match:
                    result["reasoning"] = match.group(1).strip()

                # 提取 confidence
                match = re.search(r'"confidence"\s*:\s*([\d.]+)', json_text)
                if match:
                    result["confidence"] = float(match.group(1))

                if result:
                    return result
            except Exception:
                pass

        # 8. 所有尝试都失败，抛出错误
        raise ValueError(f"无法提取投票 JSON: {text[:200]}...")
