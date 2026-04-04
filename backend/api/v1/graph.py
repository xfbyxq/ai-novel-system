"""图数据库API端点.

提供图数据库相关的API接口，包括同步、查询、实体抽取等。
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.dependencies import get_db
from backend.services.entity_extractor_service import (
    EntityExtractorService,
    extract_chapter_entities,
)
from backend.services.graph_query_service import (
    GraphQueryService,
    get_character_network_async,
)
from backend.services.graph_sync_service import GraphSyncService, sync_novel_to_graph
from core.graph.neo4j_client import get_neo4j_client, init_neo4j_client
from core.logging_config import logger
from core.models.character import Character
from core.models.chapter import Chapter
from core.models.novel import Novel
from workers.celery_app import celery_app


# ============ 请求Schema定义 ============


class ExtractAllRequest(BaseModel):
    """全量图谱抽取请求."""

    start_chapter: Optional[int] = Field(None, description="起始章节号，默认1")
    end_chapter: Optional[int] = Field(None, description="结束章节号，null表示到最后")

router = APIRouter(prefix="/novels/{novel_id}/graph", tags=["graph"])


# ============ 健康检查与状态 ============


@router.get("/health")
async def get_graph_health() -> Dict[str, Any]:
    """检查图数据库健康状态.

    Returns:
        包含连接状态和配置信息的字典
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        return {
            "enabled": False,
            "message": "图数据库功能未启用",
        }

    client = get_neo4j_client()

    if not client or not client.is_connected:
        return {
            "enabled": True,
            "connected": False,
            "message": "图数据库未连接",
        }

    try:
        health_info = await client.health_check()
        return {
            "enabled": True,
            "connected": True,
            "message": "图数据库正常运行",
            "details": health_info,
        }
    except Exception as e:
        return {
            "enabled": True,
            "connected": False,
            "message": f"健康检查失败: {str(e)}",
        }


@router.post("/init")
async def initialize_graph_connection() -> Dict[str, Any]:
    """初始化图数据库连接.

    Returns:
        初始化结果
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(
            status_code=400,
            detail="图数据库功能未启用，请在配置中设置 ENABLE_GRAPH_DATABASE=True",
        )

    try:
        init_neo4j_client()
        client = get_neo4j_client()

        if client and client.is_connected:
            return {"success": True, "message": "图数据库连接初始化成功"}
        else:
            return {"success": False, "message": "图数据库连接初始化失败"}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"初始化失败: {str(e)}",
        )


# ============ 数据同步 ============


@router.post("/sync")
async def sync_novel_to_graph_db(
    novel_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    full_sync: bool = Query(True, description="是否全量同步"),
) -> Dict[str, Any]:
    """同步小说数据到图数据库.

    Args:
        novel_id: 小说ID
        background_tasks: 后台任务
        db: 数据库会话
        full_sync: 是否全量同步（默认True）

    Returns:
        同步任务启动信息
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(
            status_code=400,
            detail="图数据库功能未启用",
        )

    # 验证小说存在
    stmt = select(Novel).where(Novel.id == novel_id)
    result = await db.execute(stmt)
    novel = result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    # 启动后台同步任务
    async def run_sync():
        try:
            sync_result = await sync_novel_to_graph(novel_id, db)
            logger.info(f"同步完成: {sync_result.to_dict()}")
        except Exception as e:
            logger.error(f"同步失败: {e}")

    background_tasks.add_task(run_sync)

    return {
        "success": True,
        "message": f"同步任务已启动，小说: {novel.title}",
        "sync_type": "full" if full_sync else "partial",
    }


@router.get("/sync/status")
async def get_sync_status(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """获取同步状态.

    查询图数据库中该小说的节点和关系数量。

    Args:
        novel_id: 小说ID
        db: 数据库会话

    Returns:
        图数据库统计信息
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        return {"enabled": False}

    client = get_neo4j_client()
    if not client or not client.is_connected:
        return {"enabled": True, "connected": False}

    try:
        # 查询节点统计
        query = """
        MATCH (n {novel_id: $novel_id})
        RETURN labels(n)[0] as label, count(n) as count
        """
        node_stats = await client.execute_query(
            query, {"novel_id": str(novel_id)}
        )

        # 查询关系统计
        rel_query = """
        MATCH (a {novel_id: $novel_id})-[r]->(b {novel_id: $novel_id})
        RETURN type(r) as type, count(r) as count
        """
        rel_stats = await client.execute_query(
            rel_query, {"novel_id": str(novel_id)}
        )

        return {
            "enabled": True,
            "connected": True,
            "novel_id": str(novel_id),
            "nodes": {row.get("label", "unknown"): row.get("count", 0) for row in node_stats},
            "relationships": {row.get("type", "unknown"): row.get("count", 0) for row in rel_stats},
        }

    except Exception as e:
        return {"enabled": True, "connected": True, "error": str(e)}


@router.delete("/sync")
async def clear_graph_data(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """清除小说的图数据库数据.

    Args:
        novel_id: 小说ID
        db: 数据库会话

    Returns:
        删除结果
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(status_code=400, detail="图数据库功能未启用")

    client = get_neo4j_client()
    if not client or not client.is_connected:
        raise HTTPException(status_code=503, detail="图数据库未连接")

    try:
        sync_service = GraphSyncService(client, db)
        deleted_count = await sync_service.delete_novel_graph(novel_id)

        return {
            "success": True,
            "deleted_nodes": deleted_count,
            "message": f"已删除 {deleted_count} 个节点",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ============ 图查询 ============


@router.get("/network/{character_name}")
async def get_character_network(
    novel_id: UUID,
    character_name: str,
    depth: int = Query(2, ge=1, le=5, description="查询深度"),
) -> Dict[str, Any]:
    """获取角色的关系网络.

    Args:
        novel_id: 小说ID
        character_name: 角色名称
        depth: 查询深度（1-5）

    Returns:
        角色关系网络数据
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(status_code=400, detail="图数据库功能未启用")

    network = await get_character_network_async(str(novel_id), character_name, depth)

    if not network:
        raise HTTPException(
            status_code=404,
            detail=f"角色 '{character_name}' 不存在或无关系数据",
        )

    return {
        "success": True,
        "character_id": network.character_id,
        "character_name": network.character_name,
        "depth": network.depth,
        "nodes": network.nodes,
        "edges": network.edges,
        "total_relations": network.total_relations,
        "prompt_format": network.to_prompt(),
    }


@router.get("/path")
async def find_character_path(
    novel_id: UUID,
    from_character: str = Query(..., description="起始角色"),
    to_character: str = Query(..., description="目标角色"),
) -> Dict[str, Any]:
    """查找两个角色间的最短关系路径.

    Args:
        novel_id: 小说ID
        from_character: 起始角色名称
        to_character: 目标角色名称

    Returns:
        路径信息
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(status_code=400, detail="图数据库功能未启用")

    client = get_neo4j_client()
    if not client or not client.is_connected:
        raise HTTPException(status_code=503, detail="图数据库未连接")

    query_service = GraphQueryService(client)
    path = await query_service.find_shortest_path(
        str(novel_id), from_character, to_character
    )

    if not path:
        raise HTTPException(status_code=404, detail="未找到路径")

    return {
        "success": True,
        "from_character": path.from_character,
        "to_character": path.to_character,
        "length": path.length,
        "nodes": [{"id": n.id, "name": n.name, "label": n.label} for n in path.nodes],
        "edges": [
            {
                "from_id": e.from_id,
                "to_id": e.to_id,
                "relation_type": e.relation_type,
            }
            for e in path.edges
        ],
        "prompt_format": path.to_prompt(),
    }


@router.get("/relationships")
async def get_all_relationships(
    novel_id: UUID,
    relationship_type: Optional[str] = Query(None, description="关系类型过滤"),
) -> Dict[str, Any]:
    """获取小说中所有角色关系.

    Args:
        novel_id: 小说ID
        relationship_type: 可选的关系类型过滤

    Returns:
        关系列表
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(status_code=400, detail="图数据库功能未启用")

    client = get_neo4j_client()
    if not client or not client.is_connected:
        raise HTTPException(status_code=503, detail="图数据库未连接")

    query_service = GraphQueryService(client)
    relationships = await query_service.get_all_relationships(
        str(novel_id), relationship_type
    )

    return {
        "success": True,
        "total": len(relationships),
        "relationships": relationships,
    }


@router.get("/conflicts")
async def check_consistency_conflicts(
    novel_id: UUID,
) -> Dict[str, Any]:
    """检测一致性冲突.

    检测死亡角色出现、矛盾关系等问题。

    Args:
        novel_id: 小说ID

    Returns:
        冲突报告列表
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(status_code=400, detail="图数据库功能未启用")

    client = get_neo4j_client()
    if not client or not client.is_connected:
        raise HTTPException(status_code=503, detail="图数据库未连接")

    query_service = GraphQueryService(client)
    conflicts = await query_service.check_consistency_conflicts(str(novel_id))

    return {
        "success": True,
        "total_conflicts": len(conflicts),
        "conflicts": [c.to_dict() for c in conflicts],
        "severity_summary": {
            "critical": len([c for c in conflicts if c.severity == "critical"]),
            "high": len([c for c in conflicts if c.severity == "high"]),
            "medium": len([c for c in conflicts if c.severity == "medium"]),
            "low": len([c for c in conflicts if c.severity == "low"]),
        },
    }


@router.get("/influence/{character_name}")
async def get_character_influence(
    novel_id: UUID,
    character_name: str,
) -> Dict[str, Any]:
    """获取角色影响力分析.

    Args:
        novel_id: 小说ID
        character_name: 角色名称

    Returns:
        影响力报告
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(status_code=400, detail="图数据库功能未启用")

    client = get_neo4j_client()
    if not client or not client.is_connected:
        raise HTTPException(status_code=503, detail="图数据库未连接")

    query_service = GraphQueryService(client)
    influence = await query_service.find_character_influence(
        str(novel_id), character_name
    )

    if not influence:
        raise HTTPException(
            status_code=404,
            detail=f"角色 '{character_name}' 不存在",
        )

    return {"success": True, "influence": influence.to_dict()}


@router.get("/timeline")
async def get_event_timeline(
    novel_id: UUID,
    character_name: Optional[str] = Query(None, description="角色名过滤"),
) -> Dict[str, Any]:
    """获取事件时间线.

    Args:
        novel_id: 小说ID
        character_name: 可选的角色名过滤

    Returns:
        事件列表（按章节排序）
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(status_code=400, detail="图数据库功能未启用")

    client = get_neo4j_client()
    if not client or not client.is_connected:
        raise HTTPException(status_code=503, detail="图数据库未连接")

    query_service = GraphQueryService(client)
    timeline = await query_service.get_event_timeline(
        str(novel_id), character_name
    )

    return {
        "success": True,
        "total_events": len(timeline),
        "timeline": timeline,
    }


@router.get("/foreshadowings/pending")
async def get_pending_foreshadowings(
    novel_id: UUID,
    current_chapter: int = Query(..., description="当前章节号"),
) -> Dict[str, Any]:
    """获取待回收的伏笔.

    Args:
        novel_id: 小说ID
        current_chapter: 当前章节号

    Returns:
        待回收伏笔列表
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(status_code=400, detail="图数据库功能未启用")

    client = get_neo4j_client()
    if not client or not client.is_connected:
        raise HTTPException(status_code=503, detail="图数据库未连接")

    query_service = GraphQueryService(client)
    foreshadowings = await query_service.find_pending_foreshadowings(
        str(novel_id), current_chapter
    )

    return {
        "success": True,
        "total": len(foreshadowings),
        "foreshadowings": foreshadowings,
        "current_chapter": current_chapter,
    }


# ============ 实体抽取 ============


@router.post("/extract")
async def extract_entities_from_chapter(
    novel_id: UUID,
    chapter_number: int,
    chapter_content: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """从章节内容中抽取实体.

    Args:
        novel_id: 小说ID
        chapter_number: 章节号
        chapter_content: 章节内容
        db: 数据库会话

    Returns:
        抽取结果
    """
    if not settings.ENABLE_ENTITY_EXTRACTION:
        raise HTTPException(status_code=400, detail="实体抽取功能未启用")

    # 获取已有角色列表
    stmt = select(Character).where(Character.novel_id == novel_id)
    result = await db.execute(stmt)
    characters = result.scalars().all()
    known_characters = [c.name for c in characters]

    # 执行抽取
    extraction_result = await extract_chapter_entities(
        chapter_number, chapter_content, known_characters
    )

    return {
        "success": True,
        "result": extraction_result.to_dict(),
    }


@router.post("/extract/batch")
async def extract_entities_batch(
    novel_id: UUID,
    chapters: List[Dict[str, Any]],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """批量抽取多章节实体.

    Args:
        novel_id: 小说ID
        chapters: 章节列表，每项包含 chapter_number 和 content
        db: 数据库会话

    Returns:
        所有章节的抽取结果
    """
    if not settings.ENABLE_ENTITY_EXTRACTION:
        raise HTTPException(status_code=400, detail="实体抽取功能未启用")

    # 获取已有角色列表
    stmt = select(Character).where(Character.novel_id == novel_id)
    result = await db.execute(stmt)
    characters = result.scalars().all()
    known_characters = [c.name for c in characters]

    # 执行批量抽取
    service = EntityExtractorService()
    results = await service.extract_entities_batch(chapters, known_characters)

    return {
        "success": True,
        "total_chapters": len(results),
        "results": [r.to_dict() for r in results],
    }


# ============ 全量图谱抽取 ============


@router.post("/extract-all")
async def extract_all_chapters_graph(
    novel_id: UUID,
    request: ExtractAllRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """全量章节图谱抽取.

    从数据库读取所有章节内容，调用LLM进行实体抽取，同步到Neo4j图数据库。
    使用Celery异步执行，支持进度查询。

    Args:
        novel_id: 小说ID
        request: 抽取请求参数
        db: 数据库会话

    Returns:
        任务启动信息，包含task_id用于查询进度
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(
            status_code=400,
            detail="图数据库功能未启用，请在配置中设置 ENABLE_GRAPH_DATABASE=True",
        )

    if not settings.ENABLE_ENTITY_EXTRACTION:
        raise HTTPException(
            status_code=400,
            detail="实体抽取功能未启用，请在配置中设置 ENABLE_ENTITY_EXTRACTION=True",
        )

    # 验证小说存在
    stmt = select(Novel).where(Novel.id == novel_id)
    result = await db.execute(stmt)
    novel = result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    # 获取小说的最大章节号
    max_stmt = select(func.max(Chapter.chapter_number)).where(
        Chapter.novel_id == novel_id,
        Chapter.content.isnot(None),
    )
    max_result = await db.execute(max_stmt)
    max_chapter = max_result.scalar_one_or_none() or 0

    if max_chapter == 0:
        return {
            "success": False,
            "message": "小说暂无已生成的章节内容",
            "task_id": None,
        }

    # 确定抽取范围
    start = request.start_chapter or 1
    end = request.end_chapter or max_chapter

    # 校验范围
    if start < 1:
        raise HTTPException(status_code=400, detail="起始章节号不能小于1")
    if end > max_chapter:
        end = max_chapter  # 自动调整到最大章节
    if start > end:
        raise HTTPException(status_code=400, detail="起始章节号不能大于结束章节号")

    # 计算范围内章节数
    count_stmt = select(func.count(Chapter.id)).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number >= start,
        Chapter.chapter_number <= end,
        Chapter.content.isnot(None),
    )
    count_result = await db.execute(count_stmt)
    chapter_count = count_result.scalar_one_or_none() or 0

    # 启动Celery异步任务
    from workers.generation_worker import run_extract_all_chapters_task

    task = run_extract_all_chapters_task.delay(
        str(novel_id), start, end
    )

    logger.info(
        f"Started extract-all task {task.id} for novel {novel_id}, "
        f"range {start}-{end}, {chapter_count} chapters"
    )

    return {
        "success": True,
        "task_id": task.id,
        "novel_id": str(novel_id),
        "novel_title": novel.title,
        "chapter_range": f"{start}-{end}" if start != end else str(start),
        "total_chapters": chapter_count,
        "message": f"全量图谱抽取任务已启动，共{chapter_count}个章节",
    }


@router.get("/extract-all/{task_id}/status")
async def get_extract_all_task_status(
    novel_id: UUID,
    task_id: str,
) -> Dict[str, Any]:
    """查询全量图谱抽取任务状态.

    Args:
        novel_id: 小说ID
        task_id: Celery任务ID

    Returns:
        任务执行状态和进度信息
    """
    if not settings.ENABLE_GRAPH_DATABASE:
        raise HTTPException(
            status_code=400,
            detail="图数据库功能未启用",
        )

    # 获取任务结果
    task_result = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "novel_id": str(novel_id),
        "status": task_result.status,
        "ready": task_result.ready(),
    }

    # 根据任务状态返回不同信息
    if task_result.status == "PENDING":
        response["message"] = "任务等待执行"
        response["progress"] = 0

    elif task_result.status == "PROGRESS":
        # 任务进行中，获取进度信息
        info = task_result.info or {}
        response["current"] = info.get("current", 0)
        response["total"] = info.get("total", 0)
        response["progress"] = info.get("current", 0) / max(info.get("total", 1), 1) * 100
        response["message"] = info.get("status", "正在处理中...")

    elif task_result.status == "SUCCESS":
        # 任务成功完成
        result = task_result.result or {}
        response["result"] = result
        response["message"] = f"抽取完成，处理了{result.get('processed_chapters', 0)}个章节"
        response["summary"] = {
            "total_chapters": result.get("total_chapters", 0),
            "processed_chapters": result.get("processed_chapters", 0),
            "total_entities": result.get("total_entities", 0),
            "total_relations": result.get("total_relations", 0),
            "duration_seconds": result.get("duration_seconds", 0),
            "errors": result.get("errors", []),
        }

    elif task_result.status == "FAILURE":
        # 任务失败
        response["message"] = "任务执行失败"
        response["error"] = str(task_result.info) if task_result.info else "未知错误"

    else:
        response["message"] = f"任务状态: {task_result.status}"

    return response
