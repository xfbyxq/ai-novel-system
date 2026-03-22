# #34 上下文管理碎片化 - 重构计划

**Issue**: [P1] 上下文管理碎片化 - 三层存储数据同步风险  
**状态**: 第一阶段完成，第二阶段进行中  
**预计完成**: 2026-03-23

---

## 📋 重构目标

### 当前问题
1. **三层存储碎片化**
   - GenerationService._team_contexts (内存字典)
   - MemoryService (内存缓存)
   - PersistentMemory (SQLite 持久化)

2. **数据同步依赖手动调用**
   - 容易遗漏导致数据不一致

3. **内存泄漏风险**
   - _team_contexts 无清理机制

4. **上下文构建逻辑重复**
   - _build_previous_context
   - _build_previous_context_enhanced

### 目标架构
```
┌─────────────────────────────────────┐
│     GenerationService               │
│  (使用 UnifiedContextManager)       │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│   UnifiedContextManager             │
│  ┌─────────────────────────────┐    │
│  │ LRUCache (内存缓存)          │    │
│  │ - max_size: 100             │    │
│  │ - TTL: 30 分钟               │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ MemoryService (兼容层)       │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ PersistentMemory (SQLite)    │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

---

## ✅ 第一阶段（已完成）

### 完成内容
1. ✅ 创建 UnifiedContextManager 类
2. ✅ 实现 LRUCache 带 TTL 过期
3. ✅ 自动同步机制
4. ✅ 在 GenerationService 中集成
5. ✅ 替换 `_build_previous_context_enhanced` 调用

### 代码变更
- `backend/services/context_manager.py`: 新建 (400+ 行)
- `backend/services/generation_service.py`: +20 行

---

## ⏳ 第二阶段（进行中）

### 待完成任务

#### 1. 替换所有 `_build_previous_context` 调用
**位置**: 
- `backend/services/generation_service.py:1242`
- `backend/services/generation_service.py:1775`

**修改方案**:
```python
# 旧代码
previous_summary = self._build_previous_context(novel_id, novel, chapter_number)

# 新代码
context_manager = self._get_context_manager(novel_id)
previous_summary = await context_manager.build_previous_context(chapter_number, count=3)
```

**预计工时**: 30 分钟

---

#### 2. 移除 `_team_contexts` 字典
**位置**: `GenerationService.__init__`

**修改方案**:
```python
# 删除这行
self._team_contexts: dict[str, NovelTeamContext] = {}

# 替换为
self._context_managers: dict[str, UnifiedContextManager] = {}
```

**预计工时**: 15 分钟

---

#### 3. 删除 `_get_or_create_team_context` 方法
**位置**: `backend/services/generation_service.py:1716`

**修改方案**:
- 直接删除整个方法
- 所有调用处替换为 `_get_context_manager`

**预计工时**: 30 分钟

---

#### 4. 删除 `_build_previous_context` 和 `_build_previous_context_enhanced` 方法
**位置**: 
- `backend/services/generation_service.py:1521`
- `backend/services/generation_service.py:1775`

**修改方案**:
- 直接删除（已被 UnifiedContextManager.build_previous_context 替代）

**预计工时**: 15 分钟

---

#### 5. 添加定期清理机制
**位置**: `GenerationService`

**修改方案**:
```python
async def cleanup_expired_contexts(self) -> Dict[str, int]:
    """清理过期的上下文缓存."""
    stats = {"total_cleaned": 0}
    
    # 清理每个小说的上下文管理器
    for novel_id, manager in self._context_managers.items():
        cleaned = await manager.cleanup()
        stats[f"novel_{novel_id}"] = cleaned
        stats["total_cleaned"] += cleaned.get("memory_cache_expired", 0)
    
    # 清理长期未使用的上下文管理器
    now = datetime.now(timezone.utc)
    inactive_threshold = timedelta(hours=2)
    
    inactive_novels = [
        novel_id for novel_id, last_active in self._last_active_time.items()
        if now - last_active > inactive_threshold
    ]
    
    for novel_id in inactive_novels:
        del self._context_managers[novel_id]
        del self._last_active_time[novel_id]
        logger.info(f"Cleaned up inactive context manager for novel {novel_id}")
    
    return stats
```

**预计工时**: 45 分钟

---

#### 6. 添加单元测试
**文件**: `tests/services/test_context_manager.py`

**测试用例**:
1. test_lru_cache_basic - 基本缓存功能
2. test_lru_cache_ttl - TTL 过期
3. test_lru_cache_max_size - LRU 淘汰
4. test_context_manager_sync - 三层同步
5. test_context_manager_build_previous - 构建前文

**预计工时**: 1 小时

---

## 📅 第三阶段（计划）

### 验证和文档
1. ✅ 运行现有测试确保无回归
2. ✅ 添加新测试覆盖新功能
3. ✅ 更新文档说明新架构
4. ✅ 性能基准测试

**预计工时**: 1 小时

---

## 📊 总体进度

| 阶段 | 任务数 | 已完成 | 进行中 | 未开始 | 进度 |
|------|--------|--------|--------|--------|------|
| 第一阶段 | 5 | 5 | 0 | 0 | 100% |
| 第二阶段 | 6 | 0 | 1 | 5 | 15% |
| 第三阶段 | 4 | 0 | 0 | 4 | 0% |
| **总计** | **15** | **5** | **1** | **9** | **40%** |

---

## 🎯 今日目标

- [x] 创建 UnifiedContextManager
- [x] 替换 `_build_previous_context_enhanced`
- [ ] 替换 `_build_previous_context`
- [ ] 移除 `_team_contexts`
- [ ] 删除旧方法
- [ ] 添加清理机制
- [ ] 添加单元测试

**预计完成时间**: 2026-03-22 18:00

---

**更新时间**: 2026-03-22 15:20  
**负责人**: 小 C
