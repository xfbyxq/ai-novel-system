"""市场分析服务 - 负责整合和分析市场数据"""
import logging
from datetime import date, timedelta, datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.crawl_result import CrawlResult
from core.models.reader_preference import ReaderPreference
from llm.qwen_client import qwen_client

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
        genre: Optional[str] = None,
        min_word_count: Optional[int] = None,
        max_word_count: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """获取市场数据
        
        Args:
            platform: 平台 (all, qidian, douyin, fanqie, zongheng)
            data_type: 数据类型 (all, ranking, hot, search_trend, tag)
            days: 天数
            limit: 限制数量
            genre: 分类
            min_word_count: 最小字数
            max_word_count: 最大字数
            page: 页码
            page_size: 每页大小
            
        Returns:
            市场数据列表
        """
        cutoff_date = date.today() - timedelta(days=days)
        
        # 基础查询
        base_query = select(CrawlResult).where(
            CrawlResult.created_at >= cutoff_date
        )
        
        # 平台过滤
        if platform != "all":
            base_query = base_query.where(CrawlResult.platform == platform)
        
        # 数据类型过滤
        if data_type != "all":
            base_query = base_query.where(CrawlResult.data_type == data_type)
        
        # 计算总数
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 分页
        offset = (page - 1) * page_size
        query = base_query.order_by(CrawlResult.created_at.desc()).offset(offset).limit(page_size)
        
        result = await self.db.execute(query)
        items = result.scalars().all()
        
        # 处理数据
        processed_items = []
        for item in items:
            data = item.processed_data
            # 添加平台信息
            data['platform'] = item.platform
            data['data_date'] = item.created_at.date().isoformat()
            processed_items.append(data)
        
        return {
            "items": processed_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    
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
            "average_rating": 0,
            "average_word_count": 0,
            "temporal_trends": {},
            "genre_heat_map": {},
        }
        
        if not preferences:
            return analysis
        
        # 计算分布
        rating_count = 0
        word_count_sum = 0
        
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
            
            # 评分
            if pref.rating:
                analysis["average_rating"] += pref.rating
                rating_count += 1
            
            # 字数
            if pref.word_count:
                word_count_sum += pref.word_count
            
            # 时间趋势
            date_key = pref.data_date.isoformat() if pref.data_date else "未知"
            if date_key not in analysis["temporal_trends"]:
                analysis["temporal_trends"][date_key] = {
                    "count": 0,
                    "genres": {},
                    "average_trend": 0
                }
            analysis["temporal_trends"][date_key]["count"] += 1
            if genre_key not in analysis["temporal_trends"][date_key]["genres"]:
                analysis["temporal_trends"][date_key]["genres"][genre_key] = 0
            analysis["temporal_trends"][date_key]["genres"][genre_key] += 1
            if pref.trend_score:
                analysis["temporal_trends"][date_key]["average_trend"] += pref.trend_score
            
            # 分类热度图
            if genre_key not in analysis["genre_heat_map"]:
                analysis["genre_heat_map"][genre_key] = {
                    "total_count": 0,
                    "total_trend_score": 0,
                    "total_rating": 0,
                    "rating_count": 0
                }
            analysis["genre_heat_map"][genre_key]["total_count"] += 1
            if pref.trend_score:
                analysis["genre_heat_map"][genre_key]["total_trend_score"] += pref.trend_score
            if pref.rating:
                analysis["genre_heat_map"][genre_key]["total_rating"] += pref.rating
                analysis["genre_heat_map"][genre_key]["rating_count"] += 1
        
        # 计算平均值
        analysis["average_trend_score"] = analysis["average_trend_score"] / len(preferences) if preferences else 0
        analysis["average_rating"] = analysis["average_rating"] / rating_count if rating_count > 0 else 0
        analysis["average_word_count"] = word_count_sum / len(preferences) if preferences else 0
        
        # 计算时间趋势的平均趋势分
        for date_key, data in analysis["temporal_trends"].items():
            data["average_trend"] = data["average_trend"] / data["count"] if data["count"] > 0 else 0
        
        # 计算分类热度图的平均值
        for genre_key, data in analysis["genre_heat_map"].items():
            data["average_trend_score"] = data["total_trend_score"] / data["total_count"] if data["total_count"] > 0 else 0
            data["average_rating"] = data["total_rating"] / data["rating_count"] if data["rating_count"] > 0 else 0
            data["heat_score"] = (data["average_trend_score"] * 0.6) + (data["average_rating"] * 0.4) if data["rating_count"] > 0 else data["average_trend_score"]
        
        # 排序标签
        analysis["trending_tags"] = dict(
            sorted(
                analysis["trending_tags"].items(),
                key=lambda x: x[1],
                reverse=True
            )
        )
        
        # 排序时间趋势
        analysis["temporal_trends"] = dict(
            sorted(
                analysis["temporal_trends"].items(),
                key=lambda x: x[0]
            )
        )
        
        # 排序分类热度图
        analysis["genre_heat_map"] = dict(
            sorted(
                analysis["genre_heat_map"].items(),
                key=lambda x: x[1]["heat_score"],
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
        for item in market_data.get("items", []):
            if platform == "douyin" or platform == "all":
                if item.get("title"):
                    topics.append({
                        "title": item["title"],
                        "heat": item.get("heat", ""),
                        "platform": "douyin",
                        "tags": item.get("tags", []),
                        "data_date": item.get("data_date", ""),
                    })
            if platform == "qidian" or platform == "all":
                if item.get("book_title"):
                    topics.append({
                        "title": item["book_title"],
                        "heat": f"{item.get('word_count', 0)}字",
                        "platform": "qidian",
                        "tags": item.get("tags", []),
                        "genre": item.get("genre", ""),
                        "word_count": item.get("word_count", 0),
                        "rating": item.get("rating", 0),
                        "data_date": item.get("data_date", ""),
                    })
            if platform == "fanqie" or platform == "all":
                if item.get("book_title"):
                    topics.append({
                        "title": item["book_title"],
                        "heat": f"{item.get('word_count', 0)}字",
                        "platform": "fanqie",
                        "tags": item.get("tags", []),
                        "genre": item.get("genre", ""),
                        "word_count": item.get("word_count", 0),
                        "rating": item.get("rating", 0),
                        "data_date": item.get("data_date", ""),
                    })
            if platform == "zongheng" or platform == "all":
                if item.get("book_title"):
                    topics.append({
                        "title": item["book_title"],
                        "heat": f"{item.get('word_count', 0)}字",
                        "platform": "zongheng",
                        "tags": item.get("tags", []),
                        "genre": item.get("genre", ""),
                        "word_count": item.get("word_count", 0),
                        "rating": item.get("rating", 0),
                        "data_date": item.get("data_date", ""),
                    })
        
        # 按热度排序并限制
        topics.sort(key=lambda x: x.get("word_count", 0) or 0, reverse=True)
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
        genre_heat_map = preferences.get("genre_heat_map", {})
        
        # 转换为列表并排序
        recommended = []
        for genre, count in genre_dist.items():
            heat_data = genre_heat_map.get(genre, {})
            recommended.append({
                "genre": genre,
                "count": count,
                "score": count / preferences.get("total_records", 1),
                "heat_score": heat_data.get("heat_score", 0),
                "average_rating": heat_data.get("average_rating", 0),
                "average_trend_score": heat_data.get("average_trend_score", 0),
            })
        
        # 按热度分数排序
        recommended.sort(key=lambda x: x["heat_score"], reverse=True)
        
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
            "cross_platform_analysis": {},
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
            "average_rating": overall_preferences.get("average_rating", 0),
            "average_word_count": overall_preferences.get("average_word_count", 0),
        }
        
        # 跨平台分析
        cross_platform_data = {
            "genre_comparison": {},
            "tag_comparison": {},
            "platform_specific_trends": {},
        }
        
        # 收集各平台的分类数据
        for platform, data in report["platforms"].items():
            genres = data["recommended_genres"]
            for genre_data in genres:
                genre = genre_data["genre"]
                if genre not in cross_platform_data["genre_comparison"]:
                    cross_platform_data["genre_comparison"][genre] = {}
                cross_platform_data["genre_comparison"][genre][platform] = genre_data["heat_score"]
            
            # 收集各平台的标签数据
            tags = data["trending_tags"]
            for tag_data in tags[:10]:  # 只取前10个标签
                tag = tag_data["tag"]
                if tag not in cross_platform_data["tag_comparison"]:
                    cross_platform_data["tag_comparison"][tag] = {}
                cross_platform_data["tag_comparison"][tag][platform] = tag_data["score"]
        
        report["cross_platform_analysis"] = cross_platform_data
        
        return report
    
    async def get_genre_analysis(
        self,
        genre: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """获取特定分类的详细分析
        
        Args:
            genre: 分类名称
            days: 天数
            
        Returns:
            分类详细分析
        """
        preferences = await self.get_reader_preferences(
            genre=genre,
            days=days,
        )
        
        # 获取该分类在各平台的表现
        platform_performance = {}
        for platform in ["qidian", "douyin", "fanqie", "zongheng"]:
            platform_data = await self.get_reader_preferences(
                platform=platform,
                genre=genre,
                days=days,
            )
            if platform_data.get("total_records", 0) > 0:
                platform_performance[platform] = {
                    "total_records": platform_data["total_records"],
                    "average_trend_score": platform_data["average_trend_score"],
                    "average_rating": platform_data["average_rating"],
                    "top_tags": list(platform_data.get("trending_tags", {}).items())[:10],
                }
        
        # 获取时间趋势
        temporal_trends = preferences.get("temporal_trends", {})
        
        analysis = {
            "genre": genre,
            "total_records": preferences.get("total_records", 0),
            "average_trend_score": preferences.get("average_trend_score", 0),
            "average_rating": preferences.get("average_rating", 0),
            "average_word_count": preferences.get("average_word_count", 0),
            "platform_performance": platform_performance,
            "temporal_trends": temporal_trends,
            "top_tags": list(preferences.get("trending_tags", {}).items())[:20],
        }
        
        return analysis
    
    async def get_platform_comparison(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """获取平台对比分析
        
        Args:
            days: 天数
            
        Returns:
            平台对比分析
        """
        platforms = ["qidian", "douyin", "fanqie", "zongheng"]
        comparison_data = {}
        
        for platform in platforms:
            preferences = await self.get_reader_preferences(
                platform=platform,
                days=days,
            )
            
            comparison_data[platform] = {
                "total_records": preferences.get("total_records", 0),
                "average_trend_score": preferences.get("average_trend_score", 0),
                "average_rating": preferences.get("average_rating", 0),
                "average_word_count": preferences.get("average_word_count", 0),
                "top_genres": await self.get_recommended_genres(
                    platform=platform,
                    days=days,
                    limit=5,
                ),
                "top_tags": await self.get_trending_tags(
                    platform=platform,
                    days=days,
                    limit=10,
                ),
            }
        
        return comparison_data
    
    def _prepare_time_series_data(
        self,
        temporal_trends: Dict[str, Dict[str, Any]],
        metric: str = "count"
    ) -> Tuple[pd.DataFrame, Optional[LinearRegression]]:
        """准备时间序列数据
        
        Args:
            temporal_trends: 时间趋势数据
            metric: 要分析的指标
            
        Returns:
            处理后的DataFrame和训练好的模型
        """
        if not temporal_trends:
            return pd.DataFrame(), None
        
        # 转换为DataFrame
        data = []
        for date_str, trend_data in temporal_trends.items():
            if date_str == "未知":
                continue
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                value = trend_data.get(metric, 0)
                if metric == "average_trend":
                    value = trend_data.get(metric, 0)
                data.append({
                    "date": date_obj,
                    "value": value
                })
            except ValueError:
                continue
        
        if not data:
            return pd.DataFrame(), None
        
        # 排序并处理
        df = pd.DataFrame(data).sort_values("date")
        df["date_ordinal"] = df["date"].apply(lambda x: x.toordinal())
        
        # 训练模型
        X = df["date_ordinal"].values.reshape(-1, 1)
        y = df["value"].values
        
        if len(X) < 2:
            return df, None
        
        model = LinearRegression()
        model.fit(X, y)
        
        return df, model
    
    def _predict_trend(
        self,
        model: LinearRegression,
        df: pd.DataFrame,
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """预测趋势
        
        Args:
            model: 训练好的模型
            df: 历史数据
            days: 预测天数
            
        Returns:
            预测结果
        """
        if model is None or df.empty:
            return []
        
        predictions = []
        last_date = df["date"].max()
        
        for i in range(1, days + 1):
            pred_date = last_date + timedelta(days=i)
            pred_ordinal = pred_date.toordinal()
            pred_value = model.predict([[pred_ordinal]])[0]
            
            predictions.append({
                "date": pred_date.isoformat(),
                "value": float(pred_value),
                "is_prediction": True
            })
        
        return predictions
    
    def _detect_trend_changes(
        self,
        df: pd.DataFrame,
        threshold: float = 0.1
    ) -> List[Dict[str, Any]]:
        """检测趋势变化
        
        Args:
            df: 时间序列数据
            threshold: 变化阈值
            
        Returns:
            趋势变化点
        """
        if df.empty or len(df) < 3:
            return []
        
        changes = []
        values = df["value"].values
        dates = df["date"].values
        
        for i in range(1, len(values)):
            prev_value = values[i-1]
            curr_value = values[i]
            
            if prev_value > 0:
                change_ratio = (curr_value - prev_value) / prev_value
                if abs(change_ratio) > threshold:
                    changes.append({
                        "date": dates[i].isoformat(),
                        "previous_value": float(prev_value),
                        "current_value": float(curr_value),
                        "change_ratio": float(change_ratio),
                        "change_type": "increase" if change_ratio > 0 else "decrease"
                    })
        
        return changes
    
    async def get_trend_analysis(
        self,
        platform: str = "all",
        genre: str = "all",
        metric: str = "count",
        days: int = 90,
        forecast_days: int = 90,
    ) -> Dict[str, Any]:
        """获取趋势分析
        
        Args:
            platform: 平台
            genre: 分类
            metric: 指标
            days: 历史天数
            forecast_days: 预测天数
            
        Returns:
            趋势分析结果
        """
        # 获取读者偏好数据
        preferences = await self.get_reader_preferences(
            platform=platform,
            genre=genre,
            days=days,
        )
        
        temporal_trends = preferences.get("temporal_trends", {})
        
        # 准备数据并训练模型
        df, model = self._prepare_time_series_data(temporal_trends, metric)
        
        # 生成预测
        predictions = []
        if model is not None:
            predictions = self._predict_trend(model, df, forecast_days)
        
        # 检测趋势变化
        trend_changes = self._detect_trend_changes(df)
        
        # 计算统计信息
        stats = {
            "total_days": len(df),
            "average_value": float(df["value"].mean()) if not df.empty else 0,
            "max_value": float(df["value"].max()) if not df.empty else 0,
            "min_value": float(df["value"].min()) if not df.empty else 0,
            "trend_direction": "stable"
        }
        
        # 分析趋势方向
        if model is not None and not df.empty:
            slope = model.coef_[0]
            if slope > 0.001:
                stats["trend_direction"] = "increasing"
            elif slope < -0.001:
                stats["trend_direction"] = "decreasing"
            stats["slope"] = float(slope)
        
        # 构建历史数据
        historical_data = []
        for _, row in df.iterrows():
            historical_data.append({
                "date": row["date"].isoformat(),
                "value": float(row["value"]),
                "is_prediction": False
            })
        
        return {
            "platform": platform,
            "genre": genre,
            "metric": metric,
            "historical_data": historical_data,
            "predictions": predictions,
            "trend_changes": trend_changes,
            "statistics": stats,
            "model_accuracy": {
                "r2_score": float(r2_score(df["value"], model.predict(df["date_ordinal"].values.reshape(-1, 1))))
                if model is not None and len(df) > 2 else 0
            }
        }
    
    async def get_genre_trend_comparison(
        self,
        genres: List[str],
        days: int = 90,
    ) -> Dict[str, Any]:
        """获取分类趋势对比
        
        Args:
            genres: 分类列表
            days: 天数
            
        Returns:
            分类趋势对比
        """
        comparison_data = {}
        
        for genre in genres:
            analysis = await self.get_trend_analysis(
                genre=genre,
                days=days,
                forecast_days=30
            )
            comparison_data[genre] = analysis
        
        return {
            "genres": genres,
            "comparison": comparison_data,
            "days_analyzed": days
        }
    
    async def generate_trend_report(
        self,
        platform: str = "all",
        days: int = 90,
        forecast_days: int = 90,
    ) -> Dict[str, Any]:
        """生成趋势报告
        
        Args:
            platform: 平台
            days: 历史天数
            forecast_days: 预测天数
            
        Returns:
            趋势报告
        """
        # 获取推荐分类
        recommended_genres = await self.get_recommended_genres(
            platform=platform,
            days=days,
            limit=5
        )
        
        genre_names = [g["genre"] for g in recommended_genres]
        
        # 分析每个分类的趋势
        genre_analyses = {}
        for genre in genre_names:
            analysis = await self.get_trend_analysis(
                platform=platform,
                genre=genre,
                days=days,
                forecast_days=forecast_days
            )
            genre_analyses[genre] = analysis
        
        # 分析整体趋势
        overall_analysis = await self.get_trend_analysis(
            platform=platform,
            days=days,
            forecast_days=forecast_days
        )
        
        # 识别热门趋势
        hot_trends = []
        for genre, analysis in genre_analyses.items():
            direction = analysis["statistics"].get("trend_direction")
            slope = analysis["statistics"].get("slope", 0)
            if direction == "increasing" and abs(slope) > 0.01:
                hot_trends.append({
                    "genre": genre,
                    "slope": slope,
                    "direction": direction,
                    "average_value": analysis["statistics"]["average_value"]
                })
        
        # 排序热门趋势
        hot_trends.sort(key=lambda x: x["slope"], reverse=True)
        
        return {
            "generated_at": date.today().isoformat(),
            "platform": platform,
            "days_analyzed": days,
            "forecast_days": forecast_days,
            "overall_trend": overall_analysis,
            "top_genre_trends": genre_analyses,
            "hot_trends": hot_trends[:3],
            "recommendations": self._generate_trend_recommendations(hot_trends, overall_analysis)
        }
    
    def _generate_trend_recommendations(
        self,
        hot_trends: List[Dict[str, Any]],
        overall_analysis: Dict[str, Any]
    ) -> List[str]:
        """生成趋势建议
        
        Args:
            hot_trends: 热门趋势
            overall_analysis: 整体分析
            
        Returns:
            建议列表
        """
        recommendations = []
        
        if hot_trends:
            top_genre = hot_trends[0]["genre"]
            recommendations.append(f"重点关注{top_genre}分类，呈现强劲增长趋势")
        
        direction = overall_analysis["statistics"]["trend_direction"]
        if direction == "increasing":
            recommendations.append("整体市场呈现增长趋势，建议扩大投入")
        elif direction == "decreasing":
            recommendations.append("整体市场呈现下降趋势，建议调整策略")
        
        if len(hot_trends) >= 2:
            recommendations.append(f"多元化布局{hot_trends[0]["genre"]}和{hot_trends[1]["genre"]}分类")
        
        return recommendations
    
    async def analyze_sentiment(
        self,
        text: str
    ) -> Dict[str, Any]:
        """分析文本情感
        
        Args:
            text: 要分析的文本
            
        Returns:
            情感分析结果
        """
        try:
            prompt = f"""请分析以下文本的情感倾向，返回JSON格式的结果：

文本：{text}

要求：
1. sentiment: 情感倾向，可选值：positive, negative, neutral
2. score: 情感强度，范围0-1
3. confidence: 分析置信度，范围0-1
4. explanation: 简短解释

JSON格式示例：
{{
  "sentiment": "positive",
  "score": 0.85,
  "confidence": 0.92,
  "explanation": "文本表达了积极的态度..."
}}
"""
            
            response = qwen_client.chat(prompt)
            content = response.get("content", "")
            
            # 提取JSON部分
            import json
            import re
            
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                json_str = json_match.group(0)
                sentiment_result = json.loads(json_str)
                return sentiment_result
            else:
                # 如果没有返回JSON，返回默认值
                return {
                    "sentiment": "neutral",
                    "score": 0.5,
                    "confidence": 0.7,
                    "explanation": "无法解析情感分析结果"
                }
        except Exception as e:
            logger.error(f"情感分析失败: {e}")
            return {
                "sentiment": "neutral",
                "score": 0.5,
                "confidence": 0.5,
                "explanation": f"分析失败: {str(e)}"
            }
    
    async def analyze_comments_sentiment(
        self,
        comments: List[str]
    ) -> Dict[str, Any]:
        """分析评论情感
        
        Args:
            comments: 评论列表
            
        Returns:
            情感分析结果
        """
        if not comments:
            return {
                "total_comments": 0,
                "sentiment_distribution": {},
                "average_score": 0,
                "detailed_analysis": []
            }
        
        sentiment_results = []
        sentiment_distribution = {
            "positive": 0,
            "negative": 0,
            "neutral": 0
        }
        
        total_score = 0
        
        for comment in comments[:10]:  # 限制分析数量
            result = await self.analyze_sentiment(comment)
            sentiment_results.append({
                "comment": comment,
                "sentiment": result.get("sentiment", "neutral"),
                "score": result.get("score", 0.5),
                "confidence": result.get("confidence", 0.5)
            })
            
            sentiment = result.get("sentiment", "neutral")
            sentiment_distribution[sentiment] += 1
            total_score += result.get("score", 0.5)
        
        average_score = total_score / len(sentiment_results) if sentiment_results else 0
        
        return {
            "total_comments": len(comments),
            "analyzed_comments": len(sentiment_results),
            "sentiment_distribution": sentiment_distribution,
            "average_score": average_score,
            "detailed_analysis": sentiment_results
        }
    
    async def generate_ai_insights(
        self,
        market_data: Dict[str, Any],
        trend_analysis: Dict[str, Any],
        platform: str = "all"
    ) -> Dict[str, Any]:
        """生成AI市场洞察
        
        Args:
            market_data: 市场数据
            trend_analysis: 趋势分析数据
            platform: 平台
            
        Returns:
            AI洞察结果
        """
        try:
            # 构建提示词
            prompt = f"""基于以下市场数据和趋势分析，生成详细的市场洞察报告：

平台：{platform}

市场数据摘要：
- 总记录数: {market_data.get('total_records', 0)}
- 平台分布: {market_data.get('platform_distribution', {})}
- 热门分类: {list(market_data.get('top_genres', {}).keys())[:5]}
- 热门标签: {list(market_data.get('top_tags', {}).keys())[:10]}

趋势分析摘要：
- 趋势方向: {trend_analysis.get('statistics', {}).get('trend_direction', 'stable')}
- 平均趋势值: {trend_analysis.get('statistics', {}).get('average_value', 0)}
- 预测趋势: {len(trend_analysis.get('predictions', [])) > 0}

要求：
1. 市场现状分析：当前市场的整体状况
2. 趋势预测：基于数据的未来趋势预测
3. 机会识别：潜在的市场机会
4. 风险分析：可能的风险因素
5. 战略建议：具体的行动建议
6. 数据驱动：所有分析都要基于提供的数据
7. 格式清晰：使用Markdown格式，结构清晰

请生成详细的分析报告，至少5个关键洞察点。
"""
            
            response = qwen_client.chat(prompt)
            content = response.get("content", "")
            
            # 提取关键洞察
            import re
            insights = []
            
            # 简单提取段落作为洞察
            paragraphs = re.split(r'\n\s*\n', content)
            for i, para in enumerate(paragraphs[:5]):  # 取前5个段落作为关键洞察
                if para.strip():
                    insights.append({
                        "id": i + 1,
                        "content": para.strip(),
                        "importance": 5 - i  # 优先级递减
                    })
            
            return {
                "success": True,
                "insights": insights,
                "full_report": content,
                "generated_at": date.today().isoformat()
            }
        except Exception as e:
            logger.error(f"生成AI洞察失败: {e}")
            return {
                "success": False,
                "insights": [],
                "full_report": f"生成洞察失败: {str(e)}",
                "generated_at": date.today().isoformat()
            }
    
    async def analyze_market_text(
        self,
        text: str,
        analysis_type: str = "market"
    ) -> Dict[str, Any]:
        """分析市场相关文本
        
        Args:
            text: 要分析的文本
            analysis_type: 分析类型: market, genre, trend
            
        Returns:
            文本分析结果
        """
        try:
            analysis_prompts = {
                "market": "分析以下市场相关文本，识别关键趋势、机会和风险",
                "genre": "分析以下文本，识别小说类型、风格特点和目标受众",
                "trend": "分析以下文本，识别市场趋势变化和预测"
            }
            
            prompt = f"""{analysis_prompts.get(analysis_type, analysis_prompts['market'])}：

文本：{text}

要求：
1. 关键发现：提取3-5个关键发现
2. 分析深度：提供详细的分析
3. 数据支持：基于文本内容进行分析
4. 格式清晰：使用Markdown格式

请生成详细的分析结果。
"""
            
            response = qwen_client.chat(prompt)
            content = response.get("content", "")
            
            return {
                "success": True,
                "analysis_type": analysis_type,
                "result": content,
                "generated_at": date.today().isoformat()
            }
        except Exception as e:
            logger.error(f"文本分析失败: {e}")
            return {
                "success": False,
                "analysis_type": analysis_type,
                "result": f"分析失败: {str(e)}",
                "generated_at": date.today().isoformat()
            }
    
    async def generate_ai_market_report(
        self,
        days: int = 30,
        platform: str = "all"
    ) -> Dict[str, Any]:
        """生成AI市场报告
        
        Args:
            days: 分析天数
            platform: 平台
            
        Returns:
            AI市场报告
        """
        # 获取市场数据
        market_data = await self.get_reader_preferences(
            platform=platform,
            days=days
        )
        
        # 获取趋势分析
        trend_analysis = await self.get_trend_analysis(
            platform=platform,
            days=days,
            forecast_days=30
        )
        
        # 生成AI洞察
        ai_insights = await self.generate_ai_insights(
            market_data=market_data,
            trend_analysis=trend_analysis,
            platform=platform
        )
        
        return {
            "generated_at": date.today().isoformat(),
            "days_analyzed": days,
            "platform": platform,
            "market_data_summary": {
                "total_records": market_data.get("total_records", 0),
                "top_genres": list(market_data.get("genre_distribution", {}).keys())[:5],
                "top_tags": list(market_data.get("trending_tags", {}).keys())[:10]
            },
            "trend_summary": {
                "direction": trend_analysis.get("statistics", {}).get("trend_direction", "stable"),
                "has_predictions": len(trend_analysis.get("predictions", [])) > 0
            },
            "ai_insights": ai_insights,
            "recommendations": ai_insights.get("insights", [])
        }
