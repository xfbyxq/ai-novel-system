"""修订执行服务 - 执行用户确认的修改."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Character, Chapter, WorldSetting, PlotOutline, RevisionPlan
from core.models.revision_plan import RevisionPlanStatus


class ExecutionResult(BaseModel):
    """执行结果."""

    success: bool
    message: str
    changes: list[dict] = []
    affected_chapters: list[int] = []


class ChangeResult(BaseModel):
    """单个修改的结果."""

    success: bool
    target_type: str
    target_name: str
    field: str
    message: str


class RevisionExecutionService:
    """修订执行服务 - 执行用户确认的修改."""

    def __init__(self, db: AsyncSession):
        """初始化服务.

        Args:
            db: 数据库会话
        """
        self.db = db

    async def execute_plan(
        self,
        plan_id: str,
        confirmed: bool = True,
        modifications: Optional[dict] = None,
    ) -> ExecutionResult:
        """执行修订计划.

        Args:
            plan_id: 修订计划ID
            confirmed: 用户是否确认
            modifications: 用户对修改方案的调整

        Returns:
            ExecutionResult: 执行结果
        """
        # 获取修订计划
        plan = await self._get_plan(plan_id)
        if not plan:
            return ExecutionResult(
                success=False,
                message=f"修订计划不存在: {plan_id}",
            )

        # 用户拒绝
        if not confirmed:
            plan.status = RevisionPlanStatus.rejected.value
            await self.db.commit()
            return ExecutionResult(
                success=True,
                message="已取消修订",
            )

        # 合并用户调整
        final_changes = self._merge_modifications(
            plan.proposed_changes or [], modifications
        )

        # 执行修改
        change_results = []
        for change in final_changes:
            result = await self._execute_single_change(change)
            change_results.append(result)

        # 获取影响的章节
        affected = self._extract_affected_chapters(plan, change_results)

        # 更新计划状态
        plan.status = RevisionPlanStatus.executed.value
        plan.executed_at = datetime.utcnow()
        plan.user_modifications = modifications

        await self.db.commit()

        # 生成结果消息
        success_count = sum(1 for r in change_results if r.success)
        message = f"已完成 {success_count}/{len(change_results)} 项修改"

        if affected:
            message += f"，标记章节 {min(affected)}-{max(affected)} 需复查"

        return ExecutionResult(
            success=all(r.success for r in change_results),
            message=message,
            changes=[r.model_dump() for r in change_results],
            affected_chapters=affected,
        )

    async def preview_plan(
        self,
        plan_id: str,
    ) -> dict:
        """预览修订计划的影响.

        Args:
            plan_id: 修订计划ID

        Returns:
            dict: 影响预览
        """
        plan = await self._get_plan(plan_id)
        if not plan:
            return {"error": "修订计划不存在"}

        return {
            "plan_id": str(plan.id),
            "understood_intent": plan.understood_intent,
            "targets": plan.targets,
            "proposed_changes": plan.proposed_changes,
            "impact_assessment": plan.impact_assessment,
            "status": plan.status,
        }

    async def _get_plan(self, plan_id: str) -> Optional[RevisionPlan]:
        """获取修订计划.

        Args:
            plan_id: 修订计划ID

        Returns:
            Optional[RevisionPlan]: 修订计划
        """
        try:
            stmt = select(RevisionPlan).where(RevisionPlan.id == UUID(plan_id))
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except ValueError:
            return None

    def _merge_modifications(
        self,
        proposed_changes: list[dict],
        modifications: Optional[dict],
    ) -> list[dict]:
        """合并用户调整.

        Args:
            proposed_changes: 提议的修改
            modifications: 用户调整

        Returns:
            list[dict]: 合并后的修改
        """
        if not modifications:
            return proposed_changes

        # 应用用户调整
        merged = []
        for change in proposed_changes:
            merged_change = change.copy()

            # 检查是否有对应调整
            field = change.get("field")
            if field and modifications.get(field):
                merged_change["new_value"] = modifications[field]

            merged.append(merged_change)

        return merged

    async def _execute_single_change(self, change: dict) -> ChangeResult:
        """执行单个修改.

        Args:
            change: 修改信息

        Returns:
            ChangeResult: 修改结果
        """
        target_type = change.get("target_type")
        target_id = change.get("target_id")
        field = change.get("field")
        new_value = change.get("new_value")

        try:
            if target_type == "character":
                return await self._update_character(target_id, field, new_value)
            elif target_type == "chapter":
                return await self._update_chapter(target_id, field, new_value)
            elif target_type == "world_setting":
                return await self._update_world_setting(
                    change.get("novel_id"), field, new_value
                )
            elif target_type == "outline":
                return await self._update_outline(
                    change.get("novel_id"), field, new_value
                )
            else:
                return ChangeResult(
                    success=False,
                    target_type=target_type or "unknown",
                    target_name=change.get("target_name", "未知"),
                    field=field or "unknown",
                    message=f"不支持的修改类型: {target_type}",
                )
        except Exception as e:
            return ChangeResult(
                success=False,
                target_type=target_type or "unknown",
                target_name=change.get("target_name", "未知"),
                field=field or "unknown",
                message=f"修改失败: {str(e)}",
            )

    async def _update_character(
        self,
        character_id: str,
        field: str,
        new_value: Any,
    ) -> ChangeResult:
        """更新角色信息.

        Args:
            character_id: 角色ID
            field: 字段名
            new_value: 新值

        Returns:
            ChangeResult: 修改结果
        """
        stmt = select(Character).where(Character.id == UUID(character_id))
        result = await self.db.execute(stmt)
        character = result.scalar_one_or_none()

        if not character:
            return ChangeResult(
                success=False,
                target_type="character",
                target_name="未知",
                field=field,
                message="角色不存在",
            )

        # 更新字段
        if hasattr(character, field):
            setattr(character, field, new_value)
            await self.db.commit()

            return ChangeResult(
                success=True,
                target_type="character",
                target_name=character.name,
                field=field,
                message=f"已更新{character.name}的{field}",
            )
        else:
            return ChangeResult(
                success=False,
                target_type="character",
                target_name=character.name,
                field=field,
                message=f"角色没有{field}字段",
            )

    async def _update_chapter(
        self,
        chapter_id: str,
        field: str,
        new_value: Any,
    ) -> ChangeResult:
        """更新章节信息.

        Args:
            chapter_id: 章节ID
            field: 字段名
            new_value: 新值

        Returns:
            ChangeResult: 修改结果
        """
        stmt = select(Chapter).where(Chapter.id == UUID(chapter_id))
        result = await self.db.execute(stmt)
        chapter = result.scalar_one_or_none()

        if not chapter:
            return ChangeResult(
                success=False,
                target_type="chapter",
                target_name="未知",
                field=field,
                message="章节不存在",
            )

        if hasattr(chapter, field):
            setattr(chapter, field, new_value)
            await self.db.commit()

            return ChangeResult(
                success=True,
                target_type="chapter",
                target_name=f"第{chapter.chapter_number}章",
                field=field,
                message=f"已更新第{chapter.chapter_number}章的{field}",
            )
        else:
            return ChangeResult(
                success=False,
                target_type="chapter",
                target_name=f"第{chapter.chapter_number}章",
                field=field,
                message=f"章节没有{field}字段",
            )

    async def _update_world_setting(
        self,
        novel_id: str,
        field: str,
        new_value: Any,
    ) -> ChangeResult:
        """更新世界观设定.

        Args:
            novel_id: 小说ID
            field: 字段名
            new_value: 新值

        Returns:
            ChangeResult: 修改结果
        """
        stmt = select(WorldSetting).where(WorldSetting.novel_id == UUID(novel_id))
        result = await self.db.execute(stmt)
        world_setting = result.scalar_one_or_none()

        if not world_setting:
            return ChangeResult(
                success=False,
                target_type="world_setting",
                target_name="世界观",
                field=field,
                message="世界观不存在",
            )

        if hasattr(world_setting, field):
            setattr(world_setting, field, new_value)
            await self.db.commit()

            return ChangeResult(
                success=True,
                target_type="world_setting",
                target_name="世界观",
                field=field,
                message=f"已更新世界观的{field}",
            )
        else:
            return ChangeResult(
                success=False,
                target_type="world_setting",
                target_name="世界观",
                field=field,
                message=f"世界观没有{field}字段",
            )

    async def _update_outline(
        self,
        novel_id: str,
        field: str,
        new_value: Any,
    ) -> ChangeResult:
        """更新大纲信息.

        Args:
            novel_id: 小说ID
            field: 字段名
            new_value: 新值

        Returns:
            ChangeResult: 修改结果
        """
        stmt = select(PlotOutline).where(PlotOutline.novel_id == UUID(novel_id))
        result = await self.db.execute(stmt)
        outline = result.scalar_one_or_none()

        if not outline:
            return ChangeResult(
                success=False,
                target_type="outline",
                target_name="大纲",
                field=field,
                message="大纲不存在",
            )

        if hasattr(outline, field):
            setattr(outline, field, new_value)
            await self.db.commit()

            return ChangeResult(
                success=True,
                target_type="outline",
                target_name="大纲",
                field=field,
                message=f"已更新大纲的{field}",
            )
        else:
            return ChangeResult(
                success=False,
                target_type="outline",
                target_name="大纲",
                field=field,
                message=f"大纲没有{field}字段",
            )

    def _extract_affected_chapters(
        self,
        plan: RevisionPlan,
        change_results: list[ChangeResult],
    ) -> list[int]:
        """提取受影响的章节.

        Args:
            plan: 修订计划
            change_results: 修改结果

        Returns:
            list[int]: 受影响的章节列表
        """
        affected = set()

        # 从impact_assessment获取
        if plan.impact_assessment:
            affected.update(plan.impact_assessment.get("affected_chapters", []))

        # 从成功的修改中提取
        for result in change_results:
            if result.success and result.target_type == "chapter":
                # 从target_name中提取章节号
                if "第" in result.target_name:
                    try:
                        chapter_num = int(result.target_name.split("第")[1].split("章")[0])
                        affected.add(chapter_num)
                    except (IndexError, ValueError):
                        pass

        return sorted(list(affected))
