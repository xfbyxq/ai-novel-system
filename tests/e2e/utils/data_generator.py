"""测试数据生成器."""

import random
from typing import Dict, List, Optional
from faker import Faker


class TestDataGenerator:
    """测试数据生成器类."""

    def __init__(self, locale: str = "zh_CN"):
        """
        初始化测试数据生成器

        Args:
            locale: 本地化设置，默认为中文
        """
        self.fake = Faker(locale)
        self._setup_constants()

    def _setup_constants(self):
        """设置常量数据."""
        self.GENRES = [
            "仙侠",
            "都市",
            "玄幻",
            "科幻",
            "悬疑",
            "历史",
            "军事",
            "游戏",
            "体育",
            "武侠",
        ]

        self.TAGS = [
            "热血",
            "轻松",
            "虐心",
            "搞笑",
            "升级流",
            "系统流",
            "无敌流",
            "重生",
            "穿越",
            "快节奏",
            "慢热",
            "爽文",
            "智斗",
            "感情线",
            "群像剧",
        ]

        self.CHARACTER_TYPES = ["protagonist", "supporting", "antagonist", "minor"]

        self.GENDERS = ["male", "female", "other"]

        self.LENGTH_TYPES = ["短文", "中篇", "长篇"]

        self.PLATFORMS = [
            "起点中文网",
            "晋江文学城",
            "纵横中文网",
            "创世中文网",
            "17K小说网",
            "逐浪网",
        ]

    def generate_novel_data(
        self,
        title: Optional[str] = None,
        genre: Optional[str] = None,
        tags: Optional[List[str]] = None,
        synopsis: Optional[str] = None,
        length_type: Optional[str] = None,
    ) -> Dict:
        """
        生成小说测试数据

        Args:
            title: 小说标题
            genre: 小说类型
            tags: 标签列表
            synopsis: 简介
            length_type: 篇幅类型

        Returns:
            dict: 小说数据
        """
        return {
            "title": title or self.fake.sentence(nb_words=4).rstrip("."),
            "genre": genre or random.choice(self.GENRES),
            "tags": tags or random.sample(self.TAGS, k=random.randint(1, 3)),
            "synopsis": synopsis or self.fake.paragraph(nb_sentences=3),
            "length_type": length_type or random.choice(self.LENGTH_TYPES),
            "author": self.fake.name(),
        }

    def generate_character_data(
        self,
        name: Optional[str] = None,
        role_type: Optional[str] = None,
        gender: Optional[str] = None,
        age: Optional[int] = None,
    ) -> Dict:
        """
        生成角色测试数据

        Args:
            name: 角色姓名
            role_type: 角色类型
            gender: 性别
            age: 年龄

        Returns:
            dict: 角色数据
        """
        return {
            "name": name or self.fake.name(),
            "role_type": role_type or random.choice(self.CHARACTER_TYPES),
            "gender": gender or random.choice(self.GENDERS),
            "age": age or random.randint(16, 80),
            "appearance": self.fake.paragraph(nb_sentences=2),
            "personality": self.fake.paragraph(nb_sentences=2),
            "background": self.fake.paragraph(nb_sentences=3),
            "goals": self.fake.sentence(nb_words=6),
            "abilities": self.fake.paragraph(nb_sentences=2),
        }

    def generate_outline_data(
        self,
        core_conflict: Optional[str] = None,
        protagonist_goal: Optional[str] = None,
        antagonist: Optional[str] = None,
    ) -> Dict:
        """
        生成大纲测试数据

        Args:
            core_conflict: 核心冲突
            protagonist_goal: 主角目标
            antagonist: 反派设定

        Returns:
            dict: 大纲数据
        """
        return {
            "core_conflict": core_conflict or self.fake.sentence(nb_words=8),
            "protagonist_goal": protagonist_goal or self.fake.sentence(nb_words=6),
            "antagonist": antagonist or self.fake.name(),
            "progression_path": self.fake.paragraph(nb_sentences=3),
            "emotional_arc": self.fake.paragraph(nb_sentences=2),
            "key_revelations": self.fake.paragraph(nb_sentences=2),
            "character_growth": self.fake.paragraph(nb_sentences=2),
            "ending_description": self.fake.paragraph(nb_sentences=2),
        }

    def generate_chapter_data(
        self, chapter_number: Optional[int] = None, title: Optional[str] = None
    ) -> Dict:
        """
        生成章节测试数据

        Args:
            chapter_number: 章节数
            title: 章节标题

        Returns:
            dict: 章节数据
        """
        num = chapter_number or random.randint(1, 100)
        return {
            "chapter_number": num,
            "title": title or f"第{num}章 {self.fake.sentence(nb_words=3).rstrip('.')}",
            "content": self.fake.text(max_nb_chars=2000),
            "word_count": random.randint(2000, 5000),
        }

    def generate_user_data(
        self, username: Optional[str] = None, email: Optional[str] = None
    ) -> Dict:
        """
        生成用户测试数据

        Args:
            username: 用户名
            email: 邮箱

        Returns:
            dict: 用户数据
        """
        return {
            "username": username or self.fake.user_name(),
            "email": email or self.fake.email(),
            "password": self.fake.password(length=12),
            "full_name": self.fake.name(),
        }

    def generate_platform_account_data(self, platform: Optional[str] = None) -> Dict:
        """
        生成平台账号测试数据

        Args:
            platform: 平台名称

        Returns:
            dict: 平台账号数据
        """
        return {
            "platform": platform or random.choice(self.PLATFORMS),
            "account_name": self.fake.user_name(),
            "username": self.fake.user_name(),
            "password": self.fake.password(length=12),
            "extra_credentials": self.fake.text(max_nb_chars=100),
        }

    def generate_batch_chapters_data(
        self, start_chapter: int = 1, end_chapter: int = 5
    ) -> List[Dict]:
        """
        生成批量章节测试数据

        Args:
            start_chapter: 起始章节数
            end_chapter: 结束章节数

        Returns:
            list: 章节数据列表
        """
        return [
            self.generate_chapter_data(chapter_number=i)
            for i in range(start_chapter, end_chapter + 1)
        ]


# 创建全局实例以便直接使用
_test_data_generator = TestDataGenerator()


# 导出便捷函数
def generate_novel_data(**kwargs) -> Dict:
    """生成小说测试数据的便捷函数."""
    return _test_data_generator.generate_novel_data(**kwargs)


def generate_character_data(**kwargs) -> Dict:
    """生成角色测试数据的便捷函数."""
    return _test_data_generator.generate_character_data(**kwargs)


def generate_outline_data(**kwargs) -> Dict:
    """生成大纲测试数据的便捷函数."""
    return _test_data_generator.generate_outline_data(**kwargs)


def generate_chapter_data(**kwargs) -> Dict:
    """生成章节测试数据的便捷函数."""
    return _test_data_generator.generate_chapter_data(**kwargs)


def generate_user_data(**kwargs) -> Dict:
    """生成用户测试数据的便捷函数."""
    return _test_data_generator.generate_user_data(**kwargs)


def generate_platform_account_data(**kwargs) -> Dict:
    """生成平台账号测试数据的便捷函数."""
    return _test_data_generator.generate_platform_account_data(**kwargs)


def generate_batch_chapters_data(
    start_chapter: int = 1, end_chapter: int = 5
) -> List[Dict]:
    """生成批量章节测试数据的便捷函数."""
    return _test_data_generator.generate_batch_chapters_data(start_chapter, end_chapter)
