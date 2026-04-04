"""关系类型映射器.

处理PostgreSQL中存储的关系类型与Neo4j图关系的映射。
基于现有的 RelationshipType 枚举。
"""

from typing import Dict, List, Tuple

from core.models.character import RELATIONSHIP_REVERSE_MAP, RelationshipType


class RelationshipMapper:
    """关系类型映射器.

    负责在PostgreSQL的关系字典格式和Neo4j的图关系格式之间转换。
    """

    # 角色关系子类型映射（用于CHARACTER_RELATION关系的type属性）
    RELATIONSHIP_SUBTYPES = {
        # 情感关系
        "lover": {"label": "恋人", "symmetric": True},
        "spouse": {"label": "配偶", "symmetric": True},
        "crush": {"label": "暗恋", "symmetric": False},  # 单向
        "ex_lover": {"label": "前任", "symmetric": True},
        # 家庭关系
        "parent": {"label": "父母", "symmetric": False, "reverse": "child"},
        "child": {"label": "子女", "symmetric": False, "reverse": "parent"},
        "sibling": {"label": "兄弟姐妹", "symmetric": True},
        "grandparent": {"label": "祖父母", "symmetric": False, "reverse": "grandchild"},
        "grandchild": {"label": "孙子女", "symmetric": False, "reverse": "grandparent"},
        # 社会关系
        "friend": {"label": "朋友", "symmetric": True},
        "best_friend": {"label": "挚友", "symmetric": True},
        "enemy": {"label": "敌人", "symmetric": True},
        "rival": {"label": "对手", "symmetric": True},
        "master": {"label": "师父", "symmetric": False, "reverse": "apprentice"},
        "apprentice": {"label": "徒弟", "symmetric": False, "reverse": "master"},
        "colleague": {"label": "同事", "symmetric": True},
        "classmate": {"label": "同学", "symmetric": True},
        # 组织关系
        "leader": {"label": "上级/首领", "symmetric": False, "reverse": "subordinate"},
        "subordinate": {"label": "下属", "symmetric": False, "reverse": "leader"},
        "member": {"label": "组织成员", "symmetric": True},
        # 其他
        "ally": {"label": "盟友", "symmetric": True},
        "neutral": {"label": "中立", "symmetric": True},
        "unknown": {"label": "未知", "symmetric": True},
    }

    @classmethod
    def get_reverse_relation(cls, relation_type: str) -> str:
        """获取关系的反向类型.

        Args:
            relation_type: 原关系类型

        Returns:
            反向关系类型，如果是对称关系则返回原类型
        """
        # 先检查自定义映射
        if relation_type in cls.RELATIONSHIP_SUBTYPES:
            subtype_info = cls.RELATIONSHIP_SUBTYPES[relation_type]
            if subtype_info.get("symmetric", False):
                return relation_type
            if "reverse" in subtype_info:
                return subtype_info["reverse"]

        # 使用模型中定义的反向映射
        try:
            rel_enum = RelationshipType(relation_type)
            reverse_enum = RELATIONSHIP_REVERSE_MAP.get(rel_enum)
            return reverse_enum.value if reverse_enum else "unknown"
        except ValueError:
            return "unknown"

    @classmethod
    def is_symmetric_relation(cls, relation_type: str) -> bool:
        """判断关系是否为对称关系.

        对称关系：A对B的关系等同于B对A的关系（如朋友、敌人）。
        非对称关系：A对B的关系不同于B对A的关系（如师父-徒弟）。

        Args:
            relation_type: 关系类型

        Returns:
            是否为对称关系
        """
        if relation_type in cls.RELATIONSHIP_SUBTYPES:
            return cls.RELATIONSHIP_SUBTYPES[relation_type].get("symmetric", False)

        # 默认假设为对称
        return True

    @classmethod
    def get_relation_label(cls, relation_type: str) -> str:
        """获取关系的中文标签.

        Args:
            relation_type: 关系类型

        Returns:
            关系的中文标签
        """
        if relation_type in cls.RELATIONSHIP_SUBTYPES:
            return cls.RELATIONSHIP_SUBTYPES[relation_type].get("label", relation_type)
        return relation_type

    @classmethod
    def relationships_to_edges(
        cls,
        character_id: str,
        relationships: Dict[str, str],
        name_to_id_map: Dict[str, str],
    ) -> List[Tuple[str, str, str, Dict]]:
        """将角色的关系字典转换为图边列表.

        Args:
            character_id: 角色ID
            relationships: 关系字典 {角色名: 关系类型}
            name_to_id_map: 角色名到ID的映射

        Returns:
            边列表 [(from_id, to_id, relation_subtype, properties), ...]
        """
        edges = []

        for target_name, relation_type in relationships.items():
            target_id = name_to_id_map.get(target_name.strip())
            if not target_id:
                continue

            # 跳过自引用
            if target_id == character_id:
                continue

            # 构建关系属性
            properties = {
                "type": relation_type,
                "strength": 5,  # 默认强度
            }

            edges.append((character_id, target_id, relation_type, properties))

        return edges

    @classmethod
    def edges_to_relationships_dict(
        cls,
        edges: List[Tuple[str, str, str, Dict]],
        id_to_name_map: Dict[str, str],
    ) -> Dict[str, str]:
        """将图边列表转换为关系字典格式.

        Args:
            edges: 边列表
            id_to_name_map: ID到角色名的映射

        Returns:
            关系字典 {角色名: 关系类型}
        """
        relationships = {}

        for from_id, to_id, relation_subtype, properties in edges:
            target_name = id_to_name_map.get(to_id, "")
            if target_name:
                relationships[target_name] = relation_subtype

        return relationships

    @classmethod
    def validate_relation_type(cls, relation_type: str) -> bool:
        """验证关系类型是否有效.

        Args:
            relation_type: 关系类型

        Returns:
            是否为有效的关系类型
        """
        return relation_type in cls.RELATIONSHIP_SUBTYPES

    @classmethod
    def get_all_relation_types(cls) -> List[str]:
        """获取所有有效的关系类型.

        Returns:
            关系类型列表
        """
        return list(cls.RELATIONSHIP_SUBTYPES.keys())

    @classmethod
    def categorize_relation(cls, relation_type: str) -> str:
        """对关系类型进行分类.

        Args:
            relation_type: 关系类型

        Returns:
            关系类别：emotion/family/social/organization/other
        """
        emotion_relations = {"lover", "spouse", "crush", "ex_lover"}
        family_relations = {"parent", "child", "sibling", "grandparent", "grandchild"}
        social_relations = {
            "friend",
            "best_friend",
            "enemy",
            "rival",
            "master",
            "apprentice",
            "colleague",
            "classmate",
        }
        org_relations = {"leader", "subordinate", "member", "ally"}

        if relation_type in emotion_relations:
            return "emotion"
        elif relation_type in family_relations:
            return "family"
        elif relation_type in social_relations:
            return "social"
        elif relation_type in org_relations:
            return "organization"
        else:
            return "other"
