"""市场分析服务 - 负责整合和分析市场数据"""
import logging
from datetime import date, timedelta
from typing import List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.crawl_result import CrawlResult
from core.models.reader_preference import ReaderPreference

logger = logging.getLogger(__name__)


class MarketAnalysisService:
    """市场分析服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_market_data(
        self,
        platform: str = "all",
        data_type: str = "all",
        days: int = 7,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取市场数据
        
        Args:
            platform: 平台 (all, qidian, douyin)
            data_type: 数据类型 (all, ranking, hot, search_trend, tag)
            days: 天数
            limit: 限制数量
            
        Returns:
            市场数据列表
        """
        cutoff_date = date.today() - timedelta(days=days)
        
        query = select(CrawlResult).where(
            CrawlResult.created_at >= cutoff_date
        )
        
        # 平台过滤
        if platform != "all":
            query = query.where(CrawlResult.platform == platform)
        
        # 数据类型过滤
        if data_type != "all":
            query = query.where(CrawlResult.data_type == data_type)
        
        # 按创建时间倒序，限制数量
        query = query.order_by(CrawlResult.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return [item.processed_data for item in result.scalars().all()]
    
    async def get_reader_preferences(
        self,
        platform: str = "all",
        genre: str = "all",
        days: int = 30,
    ) -> Dict[str, Any]:
        """获取读者偏好数据
        
        Args:
            platform: 平台
            genre: 分类
            days: 天数
            
        Returns:
            读者偏好分析
        """
        cutoff_date = date.today() - timedelta(days=days)
        
        query = select(ReaderPreference).where(
            ReaderPreference.data_date >= cutoff_date
        )
        
        # 平台过滤
        if platform != "all":
            query = query.where(ReaderPreference.source == platform)
        
        # 分类过滤
        if genre != "all":
            query = query.where(ReaderPreference.genre == genre)
        
        result = await self.db.execute(query)
        preferences = result.scalars().all()
        
        # 分析数据
        analysis = {
            "total_records": len(preferences),
            "platform_distribution": {},
            "genre_distribution": {},
            "trending_tags": {},
            "average_trend_score": 0,
        }
        
        if not preferences:
            return analysis
        
        # 计算分布
        for pref in preferences:
            # 平台分布
            platform_key = pref.source
            analysis["platform_distribution"][platform_key] = (
                analysis["platform_distribution"].get(platform_key, 0) + 1
            )
            
            # 分类分布
            genre_key = pref.genre or "未知"
            analysis["genre_distribution"][genre_key] = (
                analysis["genre_distribution"].get(genre_key, 0) + 1
            )
            
            # 标签趋势
            for tag in pref.tags or []:
                analysis["trending_tags"][tag] = (
                    analysis["trending_tags"].get(tag, 0) + 1
                )
            
            # 趋势分数
            if pref.trend_score:
                analysis["average_trend_score"] += pref.trend_score
        
        # 计算平均趋势分数
        analysis["average_trend_score"] /= len(preferences)
        
        # 排序标签
        analysis["trending_tags"] = dict(
            sorted(
                analysis["trending_tags"].items(),
                key=lambda x: x[1],
                reverse=True
            )
        )
        
        return analysis
    
    async def get_trending_topics(
        self,
        platform: str = "all",
        limit: int = 20,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """获取热门话题
        
        Args:
            platform: 平台
            limit: 限制数量
            days: 天数
            
        Returns:
            热门话题列表
        """
        # 获取市场数据
        market_data = await self.get_market_data(
            platform=platform,
            data_type="hot",
            days=days,
            limit=200,
        )
        
        # 提取话题
        topics = []
        for item in market_data:
            if platform == "douyin" or platform == "all":
                if item.get("title"):
                    topics.append({
                        "title": item["title"],
                        "heat": item.get("heat", ""),
                        "platform": "douyin",
                        "tags": item.get("tags", []),
                    })
            if platform == "qidian" or platform == "all":
                if item.get("book_title"):
                    topics.append({
                        "title": item["book_title"],
                        "heat": f"{item.get('word_count', 0)}字",
                        "platform": "qidian",
                        "tags": item.get("tags", []),
                        "genre": item.get("genre", ""),
                    })
            if platform == "fanqie" or platform == "all":
                if item.get("book_title"):
                    topics.append({
                        "title": item["book_title"],
                        "heat": f"{item.get('word_count', 0)}字",
                        "platform": "fanqie",
                        "tags": item.get("tags", []),
                        "genre": item.get("genre", ""),
                    })
            if platform == "zongheng" or platform == "all":
                if item.get("book_title"):
                    topics.append({
                        "title": item["book_title"],
                        "heat": f"{item.get('word_count', 0)}字",
                        "platform": "zongheng",
                        "tags": item.get("tags", []),
                        "genre": item.get("genre", ""),
                    })
        
        # 按热度排序并限制
        return topics[:limit]
    
    async def get_recommended_genres(
        self,
        platform: str = "all",
        days: int = 30,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """获取推荐分类
        
        Args:
            platform: 平台
            days: 天数
            limit: 限制数量
            
        Returns:
            推荐分类列表
        """
        preferences = await self.get_reader_preferences(
            platform=platform,
            days=days,
        )
        
        # 提取分类分布
        genre_dist = preferences.get("genre_distribution", {})
        
        # 转换为列表并排序
        recommended = [
            {
                "genre": genre,
                "count": count,
                "score": count / preferences.get("total_records", 1),
            }
            for genre, count in genre_dist.items()
        ]
        
        # 按数量排序
        recommended.sort(key=lambda x: x["count"], reverse=True)
        
        return recommended[:limit]
    
    async def get_trending_tags(
        self,
        platform: str = "all",
        days: int = 14,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """获取热门标签
        
        Args:
            platform: 平台
            days: 天数
            limit: 限制数量
            
        Returns:
            热门标签列表
        """
        preferences = await self.get_reader_preferences(
            platform=platform,
            days=days,
        )
        
        # 提取标签趋势
        tag_dist = preferences.get("trending_tags", {})
        
        # 转换为列表并排序
        trending = [
            {
                "tag": tag,
                "count": count,
                "score": count / preferences.get("total_records", 1),
            }
            for tag, count in tag_dist.items()
        ]
        
        # 按数量排序
        trending.sort(key=lambda x: x["count"], reverse=True)
        
        return trending[:limit]
    
    async def generate_market_report(
        self,
        days: int = 7,
        include_platforms: List[str] = None,
    ) -> Dict[str, Any]:
        """生成市场报告
        
        Args:
            days: 天数
            include_platforms: 包含的平台
            
        Returns:
            市场报告
        """
        if include_platforms is None:
            include_platforms = ["qidian", "douyin", "fanqie", "zongheng"]
        
        report = {
            "generated_at": date.today().isoformat(),
            "days_analyzed": days,
            "platforms": {},
            "overall_insights": {},
        }
        
        # 分析每个平台
        for platform in include_platforms:
            platform_data = {
                "trending_topics": await self.get_trending_topics(
                    platform=platform,
                    days=days,
                    limit=10,
                ),
                "recommended_genres": await self.get_recommended_genres(
                    platform=platform,
                    days=days,
                    limit=5,
                ),
                "trending_tags": await self.get_trending_tags(
                    platform=platform,
                    days=days,
                    limit=15,
                ),
                "reader_preferences": await self.get_reader_preferences(
                    platform=platform,
                    days=days,
                ),
            }
            report["platforms"][platform] = platform_data
        
        # 整体洞察
        overall_preferences = await self.get_reader_preferences(
            platform="all",
            days=days,
        )
        
        report["overall_insights"] = {
            "total_records": overall_preferences.get("total_records", 0),
            "platform_distribution": overall_preferences.get("platform_distribution", {}),
            "top_genres": dict(
                sorted(
                    overall_preferences.get("genre_distribution", {}).items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            ),
            "top_tags": dict(
                sorted(
                    overall_preferences.get("trending_tags", {}).items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:20]
            ),
            "average_trend_score": overall_preferences.get("average_trend_score", 0),
        }
        
        return report
