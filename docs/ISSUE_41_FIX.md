# Issue #41: 角色关系可视化后端支持不足 - 增强方案

## 当前状态

已有 API:
- `GET /novels/{novel_id}/characters/relationships` - 获取角色关系图数据（节点 + 边格式）

## 问题描述

当前后端支持存在以下不足：

1. **缺少关系分析**：仅提供原始数据，无关系网络分析
2. **缺少过滤功能**：无法按关系类型、角色类型过滤
3. **缺少聚合统计**：无关系密度、中心度等图论指标
4. **缺少子图提取**：无法获取特定角色的关系子图
5. **缺少路径查询**：无法查询两个角色之间的关系路径

## 增强方案

### 1. 添加关系分析指标

```python
@router.get("/relationships/analysis")
async def analyze_character_relationships(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """分析角色关系网络"""
    # 计算指标：
    # - 关系密度
    # - 角色中心度（Degree Centrality）
    # - 关键角色识别
    # - 关系群落检测
    return {
        "total_characters": 50,
        "total_relationships": 120,
        "density": 0.096,
        "most_central_characters": [...],
        "isolated_characters": [...],
        "relationship_clusters": [...],
    }
```

### 2. 添加过滤功能

```python
@router.get("/relationships/filtered")
async def get_filtered_relationships(
    novel_id: UUID,
    relationship_types: Optional[List[str]] = None,
    role_types: Optional[List[str]] = None,
    min_degree: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取过滤后的关系图"""
    # 支持过滤：
    # - relationship_types: ["师徒", "恋人", "敌人", ...]
    # - role_types: ["主角", "配角", "反派", ...]
    # - min_degree: 最小关系数（过滤孤立节点）
```

### 3. 添加角色子图查询

```python
@router.get("/characters/{character_id}/ego-network")
async def get_character_ego_network(
    novel_id: UUID,
    character_id: UUID,
    degrees: int = 1,  # 几度关系（1=直接关系，2=朋友的朋友）
    db: AsyncSession = Depends(get_db),
):
    """获取角色的关系子图（Ego Network）"""
    # 返回指定角色的直接/间接关系网络
```

### 4. 添加关系路径查询

```python
@router.get("/relationships/path")
async def find_relationship_path(
    novel_id: UUID,
    from_character: UUID,
    to_character: UUID,
    max_depth: int = 3,
    db: AsyncSession = Depends(get_db),
):
    """查找两个角色之间的关系路径"""
    # 使用 BFS/DFS 算法查找关系链
    # 例如：A 是 B 的师父，B 是 C 的朋友 => A 与 C 的关系路径
```

### 5. 添加关系统计 API

```python
@router.get("/relationships/statistics")
async def get_relationship_statistics(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取关系统计数据"""
    return {
        "by_type": {
            "师徒": 10,
            "恋人": 5,
            "朋友": 20,
            "敌人": 8,
        },
        "by_role": {
            "主角": 15,
            "配角": 30,
            "反派": 5,
        },
        "distribution": {...},
    }
```

## 实施优先级

### P0 - 核心功能
1. ✅ 基础关系图 API（已实现）
2. ⬜ 过滤功能
3. ⬜ 关系统计

### P1 - 增强功能
1. ⬜ 关系分析指标
2. ⬜ 角色子图查询

### P2 - 高级功能
1. ⬜ 关系路径查询
2. ⬜ 群落检测

## 技术实现

使用 `networkx` 库进行图论分析：

```bash
pip install networkx
```

示例实现：

```python
import networkx as nx

def build_relationship_graph(characters, relationships):
    """构建关系图"""
    G = nx.DiGraph()
    
    # 添加节点
    for char in characters:
        G.add_node(
            char.id,
            name=char.name,
            role_type=char.role_type,
            gender=char.gender,
        )
    
    # 添加边
    for char in characters:
        if char.relationships:
            for target_name, rel_type in char.relationships.items():
                G.add_edge(char.id, target_name, type=rel_type)
    
    return G

def calculate_centrality(G):
    """计算中心度"""
    return nx.degree_centrality(G)

def find_clusters(G):
    """检测群落"""
    return list(nx.community.louvain_communities(G.to_undirected()))
```

## 预期效果

- 提供完整的角色关系分析能力
- 支持前端高级可视化功能
- 帮助作者理解角色网络结构
- 发现潜在的关系不一致问题
