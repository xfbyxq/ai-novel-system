"""
ForeshadowingAutoDetector - 伏笔自动检测系统.

使用 LLM 从章节文本中自动识别潜在伏笔，并验证伏笔回收的匹配度。
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agents.base.json_extractor import JsonExtractor
from core.logging_config import logger


@dataclass
class DetectedForeshadowing:
    """自动检测到的伏笔候选项."""

    content: str = ""  # 伏笔内容描述
    chapter_number: int = 0  # 所在章节
    ftype: str = "plot"  # 伏笔类型：plot, character, item, mystery, hint, other
    importance: int = 5  # 重要性 1-10
    confidence: float = 0.0  # 检测置信度 0-1
    context_snippet: str = ""  # 触发伏笔判断的上下文片段
    potential_resolution: str = ""  # 可能的回收方向
    detection_reason: str = ""  # 为什么认为这是伏笔

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式."""
        return {
            "content": self.content,
            "chapter_number": self.chapter_number,
            "ftype": self.ftype,
            "importance": self.importance,
            "confidence": self.confidence,
            "context_snippet": self.context_snippet,
            "potential_resolution": self.potential_resolution,
            "detection_reason": self.detection_reason,
        }


@dataclass
class ForeshadowingMatchResult:
    """伏笔埋设与回收的匹配结果."""

    planted_id: str = ""  # 被匹配的伏笔ID
    planted_content: str = ""  # 伏笔原始内容
    resolution_text: str = ""  # 回收文本
    match_score: float = 0.0  # 0-1 语义匹配度
    match_analysis: str = ""  # 匹配分析说明
    is_valid_resolution: bool = False  # 是否为有效回收

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式."""
        return {
            "planted_id": self.planted_id,
            "planted_content": self.planted_content,
            "resolution_text": self.resolution_text,
            "match_score": self.match_score,
            "match_analysis": self.match_analysis,
            "is_valid_resolution": self.is_valid_resolution,
        }


class ForeshadowingAutoDetector:
    """
    伏笔自动检测器.

    使用 LLM 从章节文本中自动识别伏笔并验证回收匹配度。

    核心功能：
    1. detect_foreshadowings: 分析章节文本，识别潜在伏笔
    2. validate_resolution_match: 验证文本是否构成有效回收
    3. detect_and_match_resolutions: 检测章节中是否有待回收伏笔的回收
    4. merge_with_tracker: 将检测结果合并到追踪器
    """

    # 伏笔检测提示词模板
    DETECTION_PROMPT = """你是一位专业的小说文学分析师，擅长识别文本中的伏笔。

## 任务
分析以下章节内容，识别其中可能的伏笔。

## 伏笔定义
伏笔是作者在故事前期埋下的线索，暗示未来将要发生的情节、揭示的人物真相或重要信息。

## 识别标准
请根据以下标准识别伏笔：
1. **看似随意但强调了某个细节的描述**：如特别提及某物品的位置、某人的习惯等
2. **暗示未来事件的对话或内心独白**：角色的预言性言论、不祥的预感等
3. **未解释的神秘物品、人物或现象**：突然出现但未说明来历或用途的事物
4. **预言、梦境、谶语等常见伏笔载体**：明确的预示性内容
5. **角色做出的关键但未解释原因的决定**：为后续剧情埋下悬念

## 已有伏笔列表（避免重复检测）
{existing_foreshadowings}

## 章节内容
{chapter_content}

## 输出要求
请以 JSON 数组格式输出检测到的伏笔，每个伏笔包含以下字段：
- content: 伏笔内容描述（简洁明了）
- ftype: 伏笔类型：plot/character/item/mystery/hint/other
- importance: 重要性评分 1-10（10最重要）
- confidence: 检测置信度 0-1（你对该判断的确定程度）
- context_snippet: 触发伏笔判断的原文片段（不超过100字）
- potential_resolution: 可能的回收方向预测
- detection_reason: 判断为伏笔的理由

**注意**：
- 不要过度解读，只识别有明确伏笔特征的内容
- 如果没有检测到明显伏笔，返回空数组 []
- 普通的叙事铺垫不属于伏笔
- 确保输出为合法的 JSON 格式

请直接输出 JSON 数组，不要有其他说明文字：
```json
[
  ...
]
```"""

    # 回收匹配验证提示词模板
    MATCH_VALIDATION_PROMPT = """你是一位专业的小说文学分析师，
    需要判断一段文本是否构成对某个伏笔的有效回收。

## 伏笔信息
- 埋设章节：第 {planted_chapter} 章
- 伏笔内容：{planted_content}

## 待验证的回收文本
- 所在章节：第 {resolution_chapter} 章
- 文本内容：{resolution_text}

## 评估标准
请根据以下标准判断是否为有效回收：
1. **语义关联度**：回收内容是否直接关联伏笔所暗示的内容
2. **逻辑合理性**：回收方式是否在伏笔暗示的合理范围内
3. **完整性**：是否完全回收还是仅部分回收
4. **意外性**：回收是否有出人意料的效果（好的伏笔回收通常有此特点）

## 输出要求
请以 JSON 格式输出评估结果：
- match_score: 匹配度评分 0-1（1表示完全匹配）
- match_analysis: 匹配分析说明（详细解释为什么给出这个分数）
- is_valid_resolution: 是否为有效回收（布尔值，match_score >= 0.5 为有效）

请直接输出 JSON 对象：
```json
{
  "match_score": 0.0-1.0,
  "match_analysis": "分析说明...",
  "is_valid_resolution": true/false
}
```"""

    # 批量回收检测提示词
    RESOLUTION_DETECTION_PROMPT = """你是一位专业的小说文学分析师，
    需要检测章节中是否有待回收伏笔的回收内容。

## 待回收的伏笔列表
{pending_foreshadowings}

## 当前章节内容（第 {chapter_number} 章）
{chapter_content}

## 任务
检查当前章节是否包含对上述任何伏笔的回收内容。

## 输出要求
请以 JSON 数组格式输出检测结果，每个结果包含：
- planted_id: 对应的伏笔ID
- planted_content: 伏笔原始内容（从上面的列表复制）
- resolution_text: 章节中的回收文本片段
- match_score: 匹配度 0-1
- match_analysis: 匹配分析说明
- is_valid_resolution: 是否为有效回收（布尔值）

如果没有检测到任何回收，返回空数组 []。

请直接输出 JSON 数组：
```json
[
  ...
]
```"""

    def __init__(self, qwen_client: Optional[Any] = None) -> None:
        """
        初始化伏笔自动检测器.

        Args:
            qwen_client: QwenClient 实例，用于调用 LLM。如果为 None，
                         异步方法将返回空列表并记录警告日志。
        """
        self.qwen_client = qwen_client
        if qwen_client is None:
            logger.warning(
                "ForeshadowingAutoDetector 初始化时未提供 qwen_client，" "所有检测方法将返回空结果"
            )

    async def detect_foreshadowings(
        self,
        chapter_content: str,
        chapter_number: int,
        existing_foreshadowings: Optional[List[Dict[str, Any]]] = None,
    ) -> List[DetectedForeshadowing]:
        """
        使用 LLM 分析章节文本，自动识别潜在伏笔.

        识别标准：
        1. 看似随意但强调了某个细节的描述
        2. 暗示未来事件的对话或内心独白
        3. 未解释的神秘物品、人物或现象
        4. 预言、梦境、谶语等常见伏笔载体
        5. 角色做出的关键但未解释原因的决定

        Args:
            chapter_content: 章节内容
            chapter_number: 当前章节号
            existing_foreshadowings: 已有的伏笔列表（避免重复检测）

        Returns:
            检测到的伏笔候选列表
        """
        if self.qwen_client is None:
            logger.warning("detect_foreshadowings: qwen_client 未初始化，返回空列表")
            return []

        # 格式化已有伏笔列表
        existing_str = "（无）"
        if existing_foreshadowings:
            existing_items = []
            for f in existing_foreshadowings[:20]:  # 最多显示20个，避免提示词过长
                content = f.get("content", "")[:50]
                chapter = f.get("planted_chapter", "?")
                existing_items.append(f"- 第{chapter}章：{content}")
            existing_str = "\n".join(existing_items)

        # 构建提示词
        prompt = self.DETECTION_PROMPT.format(
            chapter_content=chapter_content[:8000],  # 限制长度避免超出上下文
            existing_foreshadowings=existing_str,
        )

        try:
            # 调用 LLM
            response = await self.qwen_client.chat(
                prompt=prompt,
                system="你是一位专业的小说文学分析师，擅长识别和分析伏笔。",
                temperature=0.3,  # 低温度保证分析稳定性
            )

            content = response.get("content", "")
            logger.info(f"[伏笔检测] 第{chapter_number}章，LLM响应长度: {len(content)}")

            # 解析 JSON
            result_list = JsonExtractor.extract_array(content, default=[])

            # 转换为 DetectedForeshadowing 对象
            detected_list = []
            for item in result_list:
                if not isinstance(item, dict):
                    continue

                detected = DetectedForeshadowing(
                    content=item.get("content", ""),
                    chapter_number=chapter_number,
                    ftype=item.get("ftype", "plot"),
                    importance=min(10, max(1, item.get("importance", 5))),
                    confidence=min(1.0, max(0.0, item.get("confidence", 0.0))),
                    context_snippet=item.get("context_snippet", ""),
                    potential_resolution=item.get("potential_resolution", ""),
                    detection_reason=item.get("detection_reason", ""),
                )

                # 过滤低置信度结果
                if detected.confidence >= 0.5 and detected.content:
                    detected_list.append(detected)
                else:
                    logger.debug(
                        f"过滤低置信度伏笔: {detected.content[:30]}... "
                        f"(置信度: {detected.confidence})"
                    )

            logger.info(f"[伏笔检测] 第{chapter_number}章检测到 {len(detected_list)} 个有效伏笔")
            return detected_list

        except Exception as e:
            logger.error(f"[伏笔检测] 第{chapter_number}章检测失败: {e}")
            return []

    async def validate_resolution_match(
        self,
        planted_content: str,
        planted_chapter: int,
        resolution_text: str,
        resolution_chapter: int,
    ) -> ForeshadowingMatchResult:
        """
        验证一段文本是否构成对某个伏笔的有效回收.

        评估标准：
        1. 语义关联度：回收内容是否直接关联伏笔
        2. 逻辑合理性：回收方式是否在伏笔暗示的范围内
        3. 完整性：是否完全回收还是部分回收
        4. 意外性：回收是否有出人意料的效果（好的伏笔回收应有）

        Args:
            planted_content: 伏笔内容
            planted_chapter: 伏笔埋设章节
            resolution_text: 待验证的回收文本
            resolution_chapter: 回收所在章节

        Returns:
            ForeshadowingMatchResult 匹配结果
        """
        if self.qwen_client is None:
            logger.warning("validate_resolution_match: qwen_client 未初始化")
            return ForeshadowingMatchResult(
                planted_content=planted_content,
                resolution_text=resolution_text,
                match_analysis="LLM 客户端未初始化，无法验证",
            )

        # 构建提示词
        prompt = self.MATCH_VALIDATION_PROMPT.format(
            planted_chapter=planted_chapter,
            planted_content=planted_content,
            resolution_text=resolution_text[:2000],  # 限制长度
            resolution_chapter=resolution_chapter,
        )

        try:
            # 调用 LLM
            response = await self.qwen_client.chat(
                prompt=prompt,
                system="你是一位专业的小说文学分析师，擅长分析伏笔与回收的匹配关系。",
                temperature=0.2,
            )

            content = response.get("content", "")

            # 解析 JSON
            result = JsonExtractor.extract_object(
                content,
                default={
                    "match_score": 0.0,
                    "match_analysis": "解析失败",
                    "is_valid_resolution": False,
                },
            )

            return ForeshadowingMatchResult(
                planted_content=planted_content,
                resolution_text=resolution_text,
                match_score=min(1.0, max(0.0, result.get("match_score", 0.0))),
                match_analysis=result.get("match_analysis", ""),
                is_valid_resolution=result.get("is_valid_resolution", False),
            )

        except Exception as e:
            logger.error(f"[回收验证] 验证失败: {e}")
            return ForeshadowingMatchResult(
                planted_content=planted_content,
                resolution_text=resolution_text,
                match_analysis=f"验证过程出错: {e}",
            )

    async def detect_and_match_resolutions(
        self,
        chapter_content: str,
        chapter_number: int,
        pending_foreshadowings: List[Dict[str, Any]],
    ) -> List[ForeshadowingMatchResult]:
        """
        在章节中检测是否有待回收伏笔的回收内容.

        对每个 pending 伏笔，检查当前章节是否包含回收内容。

        Args:
            chapter_content: 章节内容
            chapter_number: 当前章节号
            pending_foreshadowings: 待回收的伏笔列表，每个元素应包含
                                    id, content, planted_chapter 等字段

        Returns:
            匹配结果列表
        """
        if self.qwen_client is None:
            logger.warning("detect_and_match_resolutions: qwen_client 未初始化，返回空列表")
            return []

        if not pending_foreshadowings:
            logger.info(f"[回收检测] 第{chapter_number}章无待回收伏笔")
            return []

        # 格式化待回收伏笔列表
        pending_items = []
        for f in pending_foreshadowings[:15]:  # 限制数量避免提示词过长
            pending_items.append(
                f"- ID: {f.get('id', 'unknown')}\n"
                f"  内容: {f.get('content', '')[:100]}\n"
                f"  埋设章节: {f.get('planted_chapter', '?')}"
            )
        pending_str = "\n".join(pending_items)

        # 构建提示词
        prompt = self.RESOLUTION_DETECTION_PROMPT.format(
            pending_foreshadowings=pending_str,
            chapter_number=chapter_number,
            chapter_content=chapter_content[:8000],
        )

        try:
            # 调用 LLM
            response = await self.qwen_client.chat(
                prompt=prompt,
                system="你是一位专业的小说文学分析师，擅长识别伏笔的回收。",
                temperature=0.3,
            )

            content = response.get("content", "")
            logger.info(f"[回收检测] 第{chapter_number}章，LLM响应长度: {len(content)}")

            # 解析 JSON
            result_list = JsonExtractor.extract_array(content, default=[])

            # 转换为 ForeshadowingMatchResult 对象
            match_results = []
            for item in result_list:
                if not isinstance(item, dict):
                    continue

                match = ForeshadowingMatchResult(
                    planted_id=item.get("planted_id", ""),
                    planted_content=item.get("planted_content", ""),
                    resolution_text=item.get("resolution_text", ""),
                    match_score=min(1.0, max(0.0, item.get("match_score", 0.0))),
                    match_analysis=item.get("match_analysis", ""),
                    is_valid_resolution=item.get("is_valid_resolution", False),
                )

                # 只保留有效匹配
                if match.match_score >= 0.5:
                    match_results.append(match)

            logger.info(f"[回收检测] 第{chapter_number}章检测到 {len(match_results)} 个有效回收")
            return match_results

        except Exception as e:
            logger.error(f"[回收检测] 第{chapter_number}章检测失败: {e}")
            return []

    def merge_with_tracker(
        self,
        detected: List[DetectedForeshadowing],
        tracker: Any,
        confidence_threshold: float = 0.7,
    ) -> List[str]:
        """
        将自动检测到的伏笔合并到现有追踪器.

        只有置信度 >= threshold 的伏笔才会注册。
        返回新注册的伏笔 ID 列表。

        调用 tracker.plant() 来注册新伏笔。

        Args:
            detected: 检测到的伏笔列表
            tracker: ForeshadowingTracker 实例（使用 duck typing）
            confidence_threshold: 置信度阈值，默认 0.7

        Returns:
            新注册的伏笔 ID 列表
        """
        registered_ids: List[str] = []

        for item in detected:
            # 检查置信度
            if item.confidence < confidence_threshold:
                logger.debug(
                    f"跳过低置信度伏笔: {item.content[:30]}... "
                    f"(置信度: {item.confidence} < {confidence_threshold})"
                )
                continue

            # 检查内容有效性
            if not item.content or not item.content.strip():
                logger.debug("跳过空内容的伏笔")
                continue

            try:
                # 使用 duck typing 调用 tracker.plant()
                # 从 ftype 字符串转换为 ForeshadowingType 枚举
                from agents.foreshadowing_tracker import ForeshadowingType

                ftype_map = {
                    "plot": ForeshadowingType.PLOT,
                    "character": ForeshadowingType.CHARACTER,
                    "item": ForeshadowingType.ITEM,
                    "mystery": ForeshadowingType.MYSTERY,
                    "hint": ForeshadowingType.HINT,
                    "other": ForeshadowingType.OTHER,
                }
                ftype = ftype_map.get(item.ftype.lower(), ForeshadowingType.PLOT)

                # 调用 tracker.plant() 注册伏笔
                fid = tracker.plant(
                    content=item.content,
                    chapter_number=item.chapter_number,
                    ftype=ftype,
                    importance=item.importance,
                    notes=f"[自动检测] 置信度: {item.confidence:.2f}。"
                    f"原因: {item.detection_reason}",
                )

                registered_ids.append(fid)
                logger.info(
                    f"[伏笔注册] 成功注册伏笔: {item.content[:30]}... "
                    f"(ID: {fid}, 置信度: {item.confidence:.2f})"
                )

            except AttributeError as e:
                logger.error(f"tracker 缺少 plant 方法: {e}")
                break
            except Exception as e:
                logger.error(f"注册伏笔失败: {item.content[:30]}... 错误: {e}")
                continue

        logger.info(f"[伏笔合并] 共注册 {len(registered_ids)}/{len(detected)} 个检测到的伏笔")
        return registered_ids


# 便捷函数
async def detect_chapter_foreshadowings(
    chapter_content: str,
    chapter_number: int,
    qwen_client: Optional[Any] = None,
    existing_foreshadowings: Optional[List[Dict[str, Any]]] = None,
) -> List[DetectedForeshadowing]:
    """
    便捷函数：检测章节中的伏笔.

    Args:
        chapter_content: 章节内容
        chapter_number: 章节号
        qwen_client: LLM 客户端实例
        existing_foreshadowings: 已有伏笔列表

    Returns:
        检测到的伏笔列表
    """
    detector = ForeshadowingAutoDetector(qwen_client=qwen_client)
    return await detector.detect_foreshadowings(
        chapter_content=chapter_content,
        chapter_number=chapter_number,
        existing_foreshadowings=existing_foreshadowings,
    )
