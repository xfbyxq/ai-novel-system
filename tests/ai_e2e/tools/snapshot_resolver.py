"""a11y 快照解析器 — 将 ElementRef 语义描述解析为当前快照中的 UID.

chrome-devtools MCP 的 take_snapshot 返回格式如：
    uid=1_18 button "plus 创建小说"
    uid=2_4  textbox "* 标题" required

本模块负责解析这种文本格式，并根据 ElementRef 的 role/name 匹配到 UID。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from tests.ai_e2e.schemas.test_case_schema import ElementRef


@dataclass
class SnapshotElement:
    """解析后的快照元素."""

    uid: str
    role: str
    name: str
    attributes: list[str] = field(default_factory=list)
    depth: int = 0


# 匹配快照行的正则: "uid=1_18 button "plus 创建小说" disabled focused"
# 捕获组: uid, role, name(引号内), 剩余属性
_SNAPSHOT_LINE_RE = re.compile(
    r"^(\s*)"  # 缩进（用于计算深度）
    r"uid=(\S+)"  # UID
    r"\s+(\w+)"  # role
    r'(?:\s+"([^"]*)")?'  # 可选的 name（引号内）
    r"(.*)$"  # 剩余属性
)


class SnapshotResolver:
    """从 a11y 快照文本中，根据 ElementRef 语义描述找到匹配的 UID.

    匹配策略（按优先级）：
    1. role + name 精确匹配
    2. name 模糊匹配（包含关系）
    3. fallback_name 匹配
    4. 均失败 → 返回 None（交给 SelfHealer）
    """

    def resolve(self, snapshot: str, element: ElementRef) -> str | None:
        """解析快照，返回匹配 ElementRef 的 UID.

        Args:
            snapshot: take_snapshot 返回的原始文本
            element: 语义元素引用

        Returns:
            匹配的 UID 字符串，或 None（未找到）
        """
        elements = self.parse_snapshot(snapshot)
        if not elements:
            return None

        # 策略 1: role + name 精确匹配
        if element.role:
            uid = self._match_role_and_name(elements, element.role, element.name)
            if uid:
                return uid

        # 策略 2: name 模糊匹配（不限定 role）
        uid = self._match_name_fuzzy(elements, element.name)
        if uid:
            return uid

        # 策略 3: fallback_name 匹配
        if element.fallback_name:
            if element.role:
                uid = self._match_role_and_name(elements, element.role, element.fallback_name)
                if uid:
                    return uid
            uid = self._match_name_fuzzy(elements, element.fallback_name)
            if uid:
                return uid

        return None

    def parse_snapshot(self, snapshot: str) -> list[SnapshotElement]:
        """解析快照文本为结构化元素列表.

        Args:
            snapshot: take_snapshot 返回的原始文本

        Returns:
            解析后的元素列表
        """
        elements: list[SnapshotElement] = []
        for line in snapshot.splitlines():
            match = _SNAPSHOT_LINE_RE.match(line)
            if not match:
                continue

            indent, uid, role, name, rest = match.groups()
            depth = len(indent) // 2  # 每级缩进 2 空格

            # 解析剩余属性（如 disabled, focused, required 等）
            attrs = rest.strip().split() if rest and rest.strip() else []

            elements.append(
                SnapshotElement(
                    uid=uid,
                    role=role,
                    name=name or "",
                    attributes=attrs,
                    depth=depth,
                )
            )
        return elements

    def find_elements_by_text(self, snapshot: str, text: str) -> list[SnapshotElement]:
        """在快照中查找包含指定文本的所有元素.

        Args:
            snapshot: 快照文本
            text: 要查找的文本

        Returns:
            匹配的元素列表
        """
        elements = self.parse_snapshot(snapshot)
        return [e for e in elements if text in e.name]

    def _match_role_and_name(
        self, elements: list[SnapshotElement], role: str, name: str
    ) -> str | None:
        """role + name 匹配：先精确再模糊."""
        # 精确匹配: role 完全一致，name 包含目标文本
        for elem in elements:
            if elem.role == role and name in elem.name:
                return elem.uid

        # role 匹配但 name 需要更宽松的比较（去除前缀符号如 * 号）
        normalized_name = name.strip("* ").strip()
        if normalized_name != name:
            for elem in elements:
                if elem.role == role and normalized_name in elem.name:
                    return elem.uid

        return None

    def _match_name_fuzzy(self, elements: list[SnapshotElement], name: str) -> str | None:
        """不限定 role 的模糊 name 匹配.

        优先匹配可交互元素（button / textbox / combobox / menuitem），
        避免误匹配到 StaticText 等装饰性元素。
        """
        # 可交互角色优先级
        interactive_roles = {
            "button",
            "textbox",
            "combobox",
            "menuitem",
            "link",
            "checkbox",
            "radio",
            "switch",
            "slider",
        }

        # 先在可交互元素中查找
        for elem in elements:
            if elem.role in interactive_roles and name in elem.name:
                return elem.uid

        # 退而求其次：在所有元素中查找
        for elem in elements:
            if name in elem.name and elem.role != "StaticText":
                return elem.uid

        # 最后：包括 StaticText
        for elem in elements:
            if name in elem.name:
                return elem.uid

        return None
