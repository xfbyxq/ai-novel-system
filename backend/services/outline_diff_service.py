"""大纲对比服务 - 计算两个版本大纲的差异 (Issue #35).

功能：
1. 计算两个大纲版本的差异
2. 识别新增、删除、修改的内容
3. 计算受影响的章节范围
"""

import difflib
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging_config import logger
from core.models.plot_outline import PlotOutline
from core.models.plot_outline_version import PlotOutlineVersion


class OutlineDiffService:
    """大纲对比服务."""

    def __init__(self, db: AsyncSession):
        """初始化方法."""
        self.db = db

    async def compare_versions(
        self,
        novel_id: UUID,
        version_1: str,
        version_2: str,
    ) -> Dict[str, Any]:
        """
        对比两个大纲版本的差异.
        
        Args:
            novel_id: 小说 ID
            version_1: 第一个版本号 (如 "v1.0.0")
            version_2: 第二个版本号 (如 "v1.1.0")
        
        Returns:
            差异字典：
            {
                "added": {...},  # 新增内容
                "removed": {...},  # 删除内容
                "modified": {...},  # 修改内容
                "affected_chapters": [1, 2, 3],  # 受影响的章节号
                "summary": "对比摘要"
            }
        """
        logger.info(f"Comparing outline versions {version_1} and {version_2} for novel {novel_id}")
        
        # 1. 获取两个版本的数据
        v1_data = await self._get_version_data(novel_id, version_1)
        v2_data = await self._get_version_data(novel_id, version_2)
        
        if not v1_data or not v2_data:
            raise ValueError(f"版本 {version_1} 或 {version_2} 不存在")
        
        # 2. 计算差异
        diff = {
            "added": self._calculate_added(v1_data, v2_data),
            "removed": self._calculate_removed(v1_data, v2_data),
            "modified": self._calculate_modified(v1_data, v2_data),
        }
        
        # 3. 计算受影响的章节
        affected_chapters = await self._calculate_affected_chapters(novel_id, diff)
        
        # 4. 生成摘要
        summary = self._generate_summary(diff)
        
        result = {
            "version_1": version_1,
            "version_2": version_2,
            "added": diff["added"],
            "removed": diff["removed"],
            "modified": diff["modified"],
            "affected_chapters": affected_chapters,
            "summary": summary,
        }
        
        logger.info(f"Outline comparison completed: {summary}")
        return result

    async def _get_version_data(
        self,
        novel_id: UUID,
        version: str,
    ) -> Optional[Dict[str, Any]]:
        """获取指定版本的大纲数据."""
        # 如果是 "current" 或 "latest"，获取当前大纲
        if version.lower() in ["current", "latest"]:
            result = await self.db.execute(
                select(PlotOutline).where(PlotOutline.novel_id == novel_id)
            )
            outline = result.scalar_one_or_none()
            if outline:
                return {
                    "structure_type": outline.structure_type,
                    "volumes": outline.volumes,
                    "main_plot": outline.main_plot,
                    "sub_plots": outline.sub_plots,
                    "key_turning_points": outline.key_turning_points,
                }
            return None
        
        # 否则从版本历史中获取
        result = await self.db.execute(
            select(PlotOutlineVersion)
            .join(PlotOutline)
            .where(
                PlotOutline.novel_id == novel_id,
                PlotOutlineVersion.version_number == int(version.replace("v", "")),
            )
        )
        version_obj = result.scalar_one_or_none()
        
        if version_obj:
            return version_obj.version_data
        return None

    def _calculate_added(
        self,
        v1_data: Dict[str, Any],
        v2_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """计算新增内容."""
        added = {}
        
        # 对比卷信息
        v1_volumes = {v.get("number"): v for v in v1_data.get("volumes", [])}
        v2_volumes = {v.get("number"): v for v in v2_data.get("volumes", [])}
        
        new_volumes = []
        for num, volume in v2_volumes.items():
            if num not in v1_volumes:
                new_volumes.append(volume)
        
        if new_volumes:
            added["volumes"] = new_volumes
        
        # 对比主线剧情
        if v2_data.get("main_plot") and not v1_data.get("main_plot"):
            added["main_plot"] = v2_data["main_plot"]
        
        # 对比支线剧情
        v1_subplots = set(str(p) for p in v1_data.get("sub_plots", []))
        v2_subplots = set(str(p) for p in v2_data.get("sub_plots", []))
        new_subplots = v2_subplots - v1_subplots
        if new_subplots:
            added["sub_plots"] = list(new_subplots)
        
        return added

    def _calculate_removed(
        self,
        v1_data: Dict[str, Any],
        v2_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """计算删除内容."""
        removed = {}
        
        # 对比卷信息
        v1_volumes = {v.get("number"): v for v in v1_data.get("volumes", [])}
        v2_volumes = {v.get("number"): v for v in v2_data.get("volumes", [])}
        
        removed_volumes = []
        for num, volume in v1_volumes.items():
            if num not in v2_volumes:
                removed_volumes.append(volume)
        
        if removed_volumes:
            removed["volumes"] = removed_volumes
        
        # 对比主线剧情
        if v1_data.get("main_plot") and not v2_data.get("main_plot"):
            removed["main_plot"] = v1_data["main_plot"]
        
        # 对比支线剧情
        v1_subplots = set(str(p) for p in v1_data.get("sub_plots", []))
        v2_subplots = set(str(p) for p in v2_data.get("sub_plots", []))
        removed_subplots = v1_subplots - v2_subplots
        if removed_subplots:
            removed["sub_plots"] = list(removed_subplots)
        
        return removed

    def _calculate_modified(
        self,
        v1_data: Dict[str, Any],
        v2_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """计算修改内容."""
        modified = {}
        
        # 对比卷信息的变化
        v1_volumes = {v.get("number"): v for v in v1_data.get("volumes", [])}
        v2_volumes = {v.get("number"): v for v in v2_data.get("volumes", [])}
        
        modified_volumes = []
        for num in v1_volumes:
            if num in v2_volumes:
                v1_vol = v1_volumes[num]
                v2_vol = v2_volumes[num]
                
                # 使用 difflib 计算文本差异
                diff = self._compare_volume_changes(v1_vol, v2_vol)
                if diff:
                    modified_volumes.append({
                        "volume_number": num,
                        "changes": diff,
                    })
        
        if modified_volumes:
            modified["volumes"] = modified_volumes
        
        # 对比主线剧情的变化
        if v1_data.get("main_plot") and v2_data.get("main_plot"):
            main_plot_diff = self._compare_text_changes(
                str(v1_data["main_plot"]),
                str(v2_data["main_plot"]),
            )
            if main_plot_diff:
                modified["main_plot"] = main_plot_diff
        
        return modified

    def _compare_volume_changes(
        self,
        v1_volume: Dict[str, Any],
        v2_volume: Dict[str, Any],
    ) -> Dict[str, Any]:
        """对比单个卷的变化."""
        changes = {}
        
        # 对比标题
        if v1_volume.get("title") != v2_volume.get("title"):
            changes["title"] = {
                "old": v1_volume.get("title"),
                "new": v2_volume.get("title"),
            }
        
        # 对比摘要
        if v1_volume.get("summary") != v2_volume.get("summary"):
            changes["summary"] = self._compare_text_changes(
                v1_volume.get("summary", ""),
                v2_volume.get("summary", ""),
            )
        
        # 对比核心冲突
        if v1_volume.get("core_conflict") != v2_volume.get("core_conflict"):
            changes["core_conflict"] = {
                "old": v1_volume.get("core_conflict"),
                "new": v2_volume.get("core_conflict"),
            }
        
        return changes if changes else None

    def _compare_text_changes(
        self,
        text1: str,
        text2: str,
    ) -> Dict[str, Any]:
        """使用 difflib 对比文本变化."""
        if text1 == text2:
            return None
        
        # 计算相似度
        similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
        
        # 生成差异
        diff_lines = list(difflib.unified_diff(
            text1.splitlines(keepends=True),
            text2.splitlines(keepends=True),
            fromfile="old",
            tofile="new",
            n=3,
        ))
        
        return {
            "similarity": round(similarity, 2),
            "change_ratio": round(1 - similarity, 2),
            "diff": "".join(diff_lines[:20]),  # 限制差异行数
        }

    async def _calculate_affected_chapters(
        self,
        novel_id: UUID,
        diff: Dict[str, Any],
    ) -> List[int]:
        """计算受影响的章节范围."""
        affected = set()
        
        # 如果卷信息有变化，影响对应卷的所有章节
        for change_type in ["added", "removed", "modified"]:
            volumes = diff.get(change_type, {}).get("volumes", [])
            for volume in volumes:
                if isinstance(volume, dict):
                    # 从卷信息中提取章节范围
                    chapters_range = volume.get("chapters", [])
                    if len(chapters_range) == 2:
                        start, end = chapters_range
                        affected.update(range(start, end + 1))
                elif change_type == "modified" and "volume_number" in volume:
                    # 修改的卷信息
                    vol_num = volume["volume_number"]
                    # 这里需要从大纲中获取章节范围
                    # 简化处理：假设每卷 20 章
                    start = (vol_num - 1) * 20 + 1
                    end = vol_num * 20
                    affected.update(range(start, end + 1))
        
        # 如果主线剧情有重大修改，影响所有章节
        if diff.get("modified", {}).get("main_plot"):
            # 获取小说总章节数
            result = await self.db.execute(
                select(PlotOutline).where(PlotOutline.novel_id == novel_id)
            )
            outline = result.scalar_one_or_none()
            if outline and outline.volumes:
                total_chapters = sum(
                    v.get("chapters", [0, 0])[1] - v.get("chapters", [0, 0])[0] + 1
                    for v in outline.volumes
                )
                affected.update(range(1, total_chapters + 1))
        
        return sorted(list(affected))

    def _generate_summary(self, diff: Dict[str, Any]) -> str:
        """生成对比摘要."""
        parts = []
        
        # 统计变化
        added_volumes = len(diff.get("added", {}).get("volumes", []))
        removed_volumes = len(diff.get("removed", {}).get("volumes", []))
        modified_volumes = len(diff.get("modified", {}).get("volumes", []))
        
        if added_volumes > 0:
            parts.append(f"新增{added_volumes}卷")
        
        if removed_volumes > 0:
            parts.append(f"删除{removed_volumes}卷")
        
        if modified_volumes > 0:
            parts.append(f"修改{modified_volumes}卷")
        
        if diff.get("added", {}).get("sub_plots"):
            parts.append(f"新增{len(diff['added']['sub_plots'])}条支线")
        
        if diff.get("removed", {}).get("sub_plots"):
            parts.append(f"删除{len(diff['removed']['sub_plots'])}条支线")
        
        if diff.get("modified", {}).get("main_plot"):
            parts.append("主线剧情有修改")
        
        return "；".join(parts) if parts else "无重大变化"
