"""测试 NovelCrewManager 功能"""

import json
import logging

from agents.crew_manager import NovelCrewManager
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def test_planning_phase():
    """测试企划阶段"""
    logger.info("=" * 80)
    logger.info("开始测试企划阶段")
    logger.info("=" * 80)

    # 初始化客户端
    client = QwenClient()
    tracker = CostTracker(model="qwen-plus")
    crew_manager = NovelCrewManager(client, tracker)

    # 执行企划阶段
    result = crew_manager.run_planning_phase(
        genre="玄幻",
        tags=["修炼", "系统", "逆袭"],
        context="希望创作一部关于废材逆袭的玄幻小说",
    )

    # 输出结果
    logger.info("\n" + "=" * 80)
    logger.info("企划阶段结果：")
    logger.info("=" * 80)
    
    logger.info("\n【主题分析】")
    logger.info(json.dumps(result["topic_analysis"], ensure_ascii=False, indent=2))
    
    logger.info("\n【世界观设定】")
    logger.info(json.dumps(result["world_setting"], ensure_ascii=False, indent=2))
    
    logger.info("\n【角色设计】")
    logger.info(json.dumps(result["characters"], ensure_ascii=False, indent=2))
    
    logger.info("\n【情节大纲】")
    logger.info(json.dumps(result["plot_outline"], ensure_ascii=False, indent=2))

    # 输出成本统计
    logger.info("\n" + "=" * 80)
    logger.info("成本统计：")
    logger.info("=" * 80)
    summary = tracker.get_summary()
    logger.info(json.dumps(summary, ensure_ascii=False, indent=2))

    return result


def test_writing_phase(novel_data: dict):
    """测试写作阶段"""
    logger.info("\n" + "=" * 80)
    logger.info("开始测试写作阶段")
    logger.info("=" * 80)

    # 初始化客户端
    client = QwenClient()
    tracker = CostTracker(model="qwen-plus")
    crew_manager = NovelCrewManager(client, tracker)

    # 准备小说数据
    novel_info = {
        "title": novel_data["topic_analysis"].get("core_concept", "未命名小说"),
        "genre": novel_data["topic_analysis"].get("recommended_genre", "玄幻"),
        "world_setting": novel_data["world_setting"],
        "characters": novel_data["characters"],
        "plot_outline": novel_data["plot_outline"],
    }

    # 写第一章
    chapter_result = crew_manager.run_writing_phase(
        novel_data=novel_info,
        chapter_number=1,
        volume_number=1,
    )

    # 输出结果
    logger.info("\n" + "=" * 80)
    logger.info("写作阶段结果：")
    logger.info("=" * 80)

    logger.info("\n【章节计划】")
    logger.info(json.dumps(chapter_result["chapter_plan"], ensure_ascii=False, indent=2))

    logger.info("\n【初稿】")
    logger.info(chapter_result["draft"])

    logger.info("\n【编辑后内容】")
    logger.info(chapter_result["edited_content"])

    logger.info("\n【连续性检查报告】")
    logger.info(json.dumps(chapter_result["continuity_report"], ensure_ascii=False, indent=2))

    # 输出成本统计
    logger.info("\n" + "=" * 80)
    logger.info("成本统计：")
    logger.info("=" * 80)
    summary = tracker.get_summary()
    logger.info(json.dumps(summary, ensure_ascii=False, indent=2))

    return chapter_result


def main():
    """主测试流程"""
    try:
        # 测试企划阶段
        planning_result = test_planning_phase()

        # 保存企划结果
        with open("planning_result.json", "w", encoding="utf-8") as f:
            json.dump(planning_result, f, ensure_ascii=False, indent=2)
        logger.info("\n✅ 企划结果已保存到 planning_result.json")

        # 测试写作阶段
        writing_result = test_writing_phase(planning_result)

        # 保存章节内容
        with open("chapter_1.txt", "w", encoding="utf-8") as f:
            f.write(writing_result["final_content"])
        logger.info("\n✅ 第一章内容已保存到 chapter_1.txt")

        logger.info("\n" + "=" * 80)
        logger.info("🎉 所有测试完成！")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"\n❌ 测试失败：{e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
