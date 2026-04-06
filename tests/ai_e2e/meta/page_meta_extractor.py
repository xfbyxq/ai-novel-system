"""页面元数据提取器 — 从 Page Object 文件中提取 SELECTORS 和方法签名供 LLM 生成用例."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


class PageMetaExtractor:
    """从 Page Object Python 文件中提取测试相关的结构化元数据.

    提取内容：
    - SELECTORS 字典（CSS 选择器定义）
    - URL 模式
    - 公开方法签名和 docstring
    """

    def extract(self, page_file_path: str) -> dict[str, Any]:
        """解析 Page Object 文件，提取元数据.

        Args:
            page_file_path: Page Object 文件的路径

        Returns:
            结构化元数据字典：
            {"selectors": {...}, "methods": [...], "url": "...", "class_name": "..."}
        """
        source = Path(page_file_path).read_text(encoding="utf-8")
        tree = ast.parse(source)

        result: dict[str, Any] = {
            "file": page_file_path,
            "class_name": "",
            "url": "",
            "selectors": {},
            "methods": [],
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                result["class_name"] = node.name
                self._extract_class_attrs(node, result)
                self._extract_methods(node, result)
                break  # 只处理第一个类

        return result

    def extract_all(self, pages_dir: str) -> list[dict[str, Any]]:
        """提取目录下所有 Page Object 的元数据.

        Args:
            pages_dir: Page Object 文件所在目录

        Returns:
            元数据列表
        """
        pages_path = Path(pages_dir)
        results: list[dict[str, Any]] = []

        for py_file in sorted(pages_path.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                meta = self.extract(str(py_file))
                if meta["selectors"] or meta["methods"]:
                    results.append(meta)
            except Exception:
                continue

        return results

    def _extract_class_attrs(self, class_node: ast.ClassDef, result: dict) -> None:
        """提取类属性：SELECTORS 字典和 URL."""
        for item in class_node.body:
            # 提取 URL = "/novels" 类属性
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "URL":
                        if isinstance(item.value, ast.Constant):
                            result["url"] = item.value.value

            # 提取 SELECTORS = {...} 字典
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "SELECTORS":
                        result["selectors"] = self._parse_dict(item.value)

    def _extract_methods(self, class_node: ast.ClassDef, result: dict) -> None:
        """提取公开方法签名和 docstring."""
        for item in class_node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name.startswith("_"):
                continue

            method_info: dict[str, Any] = {
                "name": item.name,
                "args": [],
                "docstring": "",
                "is_async": isinstance(item, ast.AsyncFunctionDef),
            }

            # 提取参数（跳过 self）
            for arg in item.args.args:
                if arg.arg == "self":
                    continue
                annotation = ""
                if arg.annotation and isinstance(arg.annotation, ast.Name):
                    annotation = arg.annotation.id
                method_info["args"].append(
                    {
                        "name": arg.arg,
                        "type": annotation,
                    }
                )

            # 提取 docstring
            if (
                item.body
                and isinstance(item.body[0], ast.Expr)
                and isinstance(item.body[0].value, ast.Constant)
                and isinstance(item.body[0].value.value, str)
            ):
                docstring = item.body[0].value.value.strip()
                # 只取第一行
                method_info["docstring"] = docstring.split("\n")[0]

            result["methods"].append(method_info)

    def _parse_dict(self, node: ast.expr) -> dict[str, str]:
        """解析 AST 字典节点为 Python 字典."""
        if not isinstance(node, ast.Dict):
            return {}

        result: dict[str, str] = {}
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(value, ast.Constant):
                result[str(key.value)] = str(value.value)
        return result
