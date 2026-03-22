# P1 问题修复计划

## #32 大纲与章节关联弱 - 未建立外键关联和同步机制

### 问题分析
1. Chapter 模型有 `outline_task`、`outline_version` 字段，但**未建立外键关联**
2. 大纲分解后，章节配置是**一次性复制**，大纲更新不会自动同步到章节
3. 动态更新机制只更新大纲表，不更新已分解的章节

### 修复方案

#### 1. 修改 Chapter 模型，添加外键关联
```python
# core/models/chapter.py
class Chapter(Base):
    # ... 现有字段
    plot_outline_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("plot_outlines.id", ondelete="SET NULL"),
        nullable=True
    )  # 关联大纲
    outline_version_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("plot_outline_versions.id", ondelete="SET NULL"),
        nullable=True
    )  # 关联大纲版本
```

#### 2. 修改大纲分解逻辑，记录关联 ID
```python
# backend/services/outline_service.py
async def decompose_outline(self, ...):
    # 获取大纲对象
    outline_result = await self.db.execute(
        select(PlotOutline).where(PlotOutline.novel_id == novel_id)
    )
    outline = outline_result.scalar_one_or_none()
    
    # 分解时记录大纲 ID
    for ch_num in range(start_ch, end_ch + 1):
        chapter_config = self._generate_chapter_config(...)
        chapter_config['plot_outline_id'] = str(outline.id)
```

#### 3. 实现大纲 - 章节同步机制
```python
# backend/services/outline_service.py
async def sync_outline_to_chapters(self, outline_id: UUID, updated_fields: List[str]):
    """
    大纲更新后，同步到受影响的章节
    
    Args:
        outline_id: 大纲 ID
        updated_fields: 更新的字段列表
    """
    # 1. 获取大纲
    outline = await self._get_outline(outline_id)
    
    # 2. 查找所有关联的章节
    chapters_result = await self.db.execute(
        select(Chapter)
        .where(Chapter.plot_outline_id == outline_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = chapters_result.scalars().all()
    
    # 3. 标记受影响的章节（添加版本标记）
    for chapter in chapters:
        chapter.outline_version = f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"
        # 可以在这里添加更复杂的同步逻辑
    
    await self.db.commit()
```

#### 4. 添加章节批量更新接口
```python
# backend/api/v1/chapters.py
@router.post("/bulk-sync-outline")
async def bulk_sync_outline(
    novel_id: UUID,
    outline_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    批量同步大纲到章节
    """
    service = OutlineService(db)
    result = await service.sync_outline_to_chapters(outline_id, ["mandatory_events"])
    return {"success": True, "affected_chapters": len(result)}
```

### 验收标准
- [ ] Chapter 模型添加外键关联
- [ ] 数据库迁移脚本
- [ ] 大纲分解时记录大纲 ID
- [ ] 实现大纲 - 章节同步接口
- [ ] 单元测试验证同步机制

---

## 其他 P1 问题修复计划

### #33 角色关系管理不完整（1 天）
- 实现双向关系同步
- 删除角色时清理引用
- 定义标准关系类型枚举

### #34 上下文管理碎片化（3 天）
- 创建 UnifiedContextManager
- 统一三层存储
- 添加内存清理策略

### #35 大纲对比功能缺失（2 天）
- 实现 compare_outline_versions 端点
- 使用 diff 算法计算差异
- 前端展示可视化对比

### #36 章节大纲验证规则简单（3 天）
- 引入语义相似度检测
- 检查事件顺序和因果关系
- 添加角色行为一致性检查

### #37 缺少大纲 - 章节一致性监控（2 天）
- 创建 OutlineDeviationMonitor 服务
- 定期扫描已写章节
- 偏差超过阈值时发送告警
