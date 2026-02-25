#!/usr/bin/env python3
"""
创建测试用的小说数据，包含世界观信息
"""

import asyncio
import json
from core.database import async_session_factory
from core.models.novel import Novel, NovelStatus, NovelLengthType
from core.models.world_setting import WorldSetting
from core.models.character import Character
from core.models.plot_outline import PlotOutline
from core.models.chapter import Chapter

async def create_test_novel():
    """创建测试用的小说数据"""
    async with async_session_factory() as db:
        try:
            # 创建小说基础信息（不指定ID，使用默认的uuid4）
            novel = Novel(
                title="测试小说：苍穹大陆",
                author="测试作者",
                genre="玄幻",
                tags=["修炼", "冒险", "热血"],
                status=NovelStatus.writing,
                length_type=NovelLengthType.long,
                word_count=100000,
                chapter_count=10,
                cover_url="https://example.com/cover.jpg",
                synopsis="这是一部关于修炼者在苍穹大陆上冒险的故事。",
                target_platform="起点中文网"
            )
            db.add(novel)
            await db.flush()
            
            # 创建世界观设定
            world_content = json.dumps({
                "world_name": "苍穹大陆",
                "world_type": "玄幻世界",
                "power_system": {
                    "name": "灵力修炼",
                    "levels": [
                        {"name": "练气期", "description": "初步感应天地灵气，纳入体内"},
                        {"name": "筑基期", "description": "将灵气凝聚成基，奠定修炼基础"},
                        {"name": "金丹期", "description": "灵气凝聚成丹，实力大幅提升"},
                        {"name": "元婴期", "description": "修炼出元婴，可御空飞行"},
                        {"name": "化神期", "description": "精神力化神，掌握规则之力"}
                    ]
                },
                "geography": "苍穹大陆分为东域、西域、南域、北域和中域五大区域，每个区域都有独特的地理环境和势力分布。中域是修炼资源最丰富的地方，也是各大势力的聚集地。",
                "factions": "主要势力包括：青云门（正道领袖）、魔教（邪道势力）、天机阁（情报组织）、佣兵公会（雇佣组织）和各大帝国（世俗势力）。"
            }, ensure_ascii=False)
            
            world_setting = WorldSetting(
                novel_id=novel.id,
                world_type="玄幻",
                raw_content=world_content
            )
            db.add(world_setting)
            
            # 创建角色
            from core.models.character import RoleType, Gender
            characters = [
                Character(
                    novel_id=novel.id,
                    name="李云霄",
                    role_type=RoleType.protagonist,
                    gender=Gender.male,
                    appearance="剑眉星目，身材修长，气质不凡",
                    personality="坚韧不拔，重情重义，机智过人",
                    background="出身平凡，偶然获得神秘传承"
                ),
                Character(
                    novel_id=novel.id,
                    name="苏玉儿",
                    role_type=RoleType.supporting,
                    gender=Gender.female,
                    appearance="倾国倾城，气质出尘",
                    personality="温柔善良，聪明伶俐",
                    background="青云门掌门之女"
                )
            ]
            db.add_all(characters)
            
            # 创建剧情大纲
            plot_outline = PlotOutline(
                novel_id=novel.id,
                raw_content="主角李云霄从平凡少年成长为一代强者的故事。他在修炼路上遇到各种挑战，结交好友，击败敌人，最终成为苍穹大陆的顶尖强者。"
            )
            db.add(plot_outline)
            
            # 创建章节
            chapters = [
                Chapter(
                    novel_id=novel.id,
                    chapter_number=1,
                    title="第一章 平凡少年",
                    content="李云霄是一个平凡的山村少年，每天过着平静的生活。直到有一天，他在山中采药时遇到了一位重伤的老人..."
                ),
                Chapter(
                    novel_id=novel.id,
                    chapter_number=2,
                    title="第二章 神秘传承",
                    content="老人是一位强大的修炼者，他看出李云霄的天赋，将自己的传承传授给了他..."
                )
            ]
            db.add_all(chapters)
            
            await db.commit()
            
            print(f"测试小说创建成功！")
            print(f"小说ID: {novel.id}")
            print(f"小说标题: {novel.title}")
            print(f"世界观设定已添加")
            print(f"角色数量: {len(characters)}")
            print(f"章节数量: {len(chapters)}")
            
        except Exception as e:
            await db.rollback()
            print(f"创建测试小说失败: {e}")

if __name__ == "__main__":
    asyncio.run(create_test_novel())
