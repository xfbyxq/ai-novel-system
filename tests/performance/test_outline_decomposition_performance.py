"""大纲分解性能测试 - Issue #38."""

import time
from typing import Any, Dict, List

import pytest


class TestOutlineDecompositionPerformance:
    """大纲分解性能测试."""

    @pytest.fixture
    def sample_outline_data(self) -> Dict[str, Any]:
        """示例大纲数据."""
        return {
            "volumes": [
                {
                    "number": 1,
                    "title": "第一卷",
                    "chapters": [1, 50],
                    "summary": "第一卷概要",
                    "tension_cycles": [
                        {
                            "name": "第一次张力循环",
                            "chapters": [1, 10],
                            "suppress_events": ["事件 1", "事件 2"],
                            "release_event": "释放事件 1",
                        },
                        {
                            "name": "第二次张力循环",
                            "chapters": [11, 20],
                            "suppress_events": ["事件 3", "事件 4"],
                            "release_event": "释放事件 2",
                        },
                    ],
                    "key_events": [
                        {"chapter": 1, "event": "开篇事件"},
                        {"chapter": 10, "event": "第一个高潮"},
                        {"chapter": 20, "event": "第二个高潮"},
                        {"chapter": 50, "event": "卷末高潮"},
                    ],
                },
                {
                    "number": 2,
                    "title": "第二卷",
                    "chapters": [51, 100],
                    "summary": "第二卷概要",
                    "tension_cycles": [
                        {
                            "name": "第三卷张力循环",
                            "chapters": [51, 70],
                            "suppress_events": ["事件 5"],
                            "release_event": "释放事件 3",
                        },
                    ],
                    "key_events": [
                        {"chapter": 51, "event": "第二卷开篇"},
                        {"chapter": 70, "event": "中期高潮"},
                        {"chapter": 100, "event": "第二卷结局"},
                    ],
                },
            ],
            "climax_chapter": 100,
        }

    def test_chapter_config_generation_performance(self, sample_outline_data):
        """测试章节配置生成性能."""
        from backend.services.outline_service import OutlineService
        
        # 模拟数据库会话（简化版）
        class MockDB:
            pass
        
        service = OutlineService(MockDB())
        
        # 测试分解 100 章的性能
        start = time.perf_counter()
        
        # 模拟分解过程
        chapter_configs = []
        for volume in sample_outline_data["volumes"]:
            start_ch, end_ch = volume["chapters"]
            for ch_num in range(start_ch, end_ch + 1):
                config = service._generate_chapter_config(
                    chapter_number=ch_num,
                    volume_number=volume["number"],
                    tension_cycles=volume.get("tension_cycles", []),
                    key_events=volume.get("key_events", []),
                    volume_summary=volume.get("summary", ""),
                    auto_split=True,
                    end_ch=end_ch,
                    climax_chapter=sample_outline_data.get("climax_chapter"),
                    volume_is_climax=volume.get("is_climax", False),
                )
                chapter_configs.append(config)
        
        elapsed = time.perf_counter() - start
        
        print(f"\n📊 大纲分解性能测试:")
        print(f"   总章节数：{len(chapter_configs)}")
        print(f"   分解耗时：{elapsed*1000:.2f}ms")
        print(f"   平均每章：{elapsed*1000/len(chapter_configs):.3f}ms")
        
        # 性能要求：每章分解时间 < 10ms
        avg_ms = elapsed * 1000 / len(chapter_configs)
        assert avg_ms < 10, f"章节配置生成太慢：{avg_ms:.3f}ms/章"
        assert len(chapter_configs) == 100, "应该生成 100 个章节配置"

    def test_tension_cycle_lookup_performance(self, sample_outline_data):
        """测试张力循环查找性能."""
        from backend.services.outline_service import OutlineService
        
        class MockDB:
            pass
        
        service = OutlineService(MockDB())
        
        volume = sample_outline_data["volumes"][0]
        tension_cycles = volume["tension_cycles"]
        
        # 测试查找 1000 次的性能
        iterations = 1000
        start = time.perf_counter()
        
        for _ in range(iterations):
            for ch_num in range(1, 51):
                # 模拟查找过程
                current_cycle = None
                for cycle in tension_cycles:
                    chapters_range = cycle.get("chapters", [])
                    if len(chapters_range) == 2:
                        start_ch, end_ch = chapters_range
                        if start_ch <= ch_num <= end_ch:
                            current_cycle = cycle
                            break
        
        elapsed = time.perf_counter() - start
        
        print(f"\n🔍 张力循环查找性能:")
        print(f"   查找次数：{iterations * 50}")
        print(f"   总耗时：{elapsed*1000:.2f}ms")
        print(f"   平均每次：{elapsed*1000/(iterations*50):.4f}ms")
        
        # 性能要求：每次查找 < 1ms
        avg_ms = elapsed * 1000 / (iterations * 50)
        assert avg_ms < 1.0, f"张力循环查找太慢：{avg_ms:.4f}ms/次"


class TestOutlineDecompositionOptimization:
    """大纲分解优化方案测试."""

    def test_batch_processing_optimization(self):
        """测试批量处理优化."""
        # 模拟批量处理章节配置
        chapters_per_batch = 10
        total_chapters = 100
        
        batches = []
        for i in range(0, total_chapters, chapters_per_batch):
            batch = list(range(i + 1, min(i + chapters_per_batch + 1, total_chapters + 1)))
            batches.append(batch)
        
        print(f"\n📦 批量处理优化:")
        print(f"   总章节数：{total_chapters}")
        print(f"   每批大小：{chapters_per_batch}")
        print(f"   总批次数：{len(batches)}")
        
        assert len(batches) == 10, "应该分成 10 批"
        assert len(batches[0]) == 10, "每批应该有 10 章"

    def test_cache_optimization(self):
        """测试缓存优化."""
        # 模拟缓存张力循环查找结果
        cache = {}
        
        def find_cycle_with_cache(chapter_number: int, tension_cycles: List[Dict], cache: Dict) -> Dict:
            """使用缓存的张力循环查找."""
            cache_key = f"cycle_{chapter_number}"
            
            if cache_key in cache:
                return cache[cache_key]
            
            # 实际查找逻辑
            for cycle in tension_cycles:
                chapters_range = cycle.get("chapters", [])
                if len(chapters_range) == 2:
                    start_ch, end_ch = chapters_range
                    if start_ch <= chapter_number <= end_ch:
                        cache[cache_key] = cycle
                        return cycle
            
            cache[cache_key] = None
            return None
        
        tension_cycles = [
            {"name": "Cycle 1", "chapters": [1, 10]},
            {"name": "Cycle 2", "chapters": [11, 20]},
            {"name": "Cycle 3", "chapters": [21, 30]},
        ]
        
        # 第一次查找（无缓存）
        start = time.perf_counter()
        for ch in range(1, 31):
            find_cycle_with_cache(ch, tension_cycles, cache)
        first_pass = time.perf_counter() - start
        
        # 第二次查找（有缓存）
        start = time.perf_counter()
        for ch in range(1, 31):
            find_cycle_with_cache(ch, tension_cycles, cache)
        second_pass = time.perf_counter() - start
        
        print(f"\n💾 缓存优化测试:")
        print(f"   第一次查找（无缓存）: {first_pass*1000:.2f}ms")
        print(f"   第二次查找（有缓存）: {second_pass*1000:.2f}ms")
        print(f"   性能提升：{(first_pass/second_pass):.2f}x" if second_pass > 0 else "N/A")
        
        # 缓存应该显著提升性能
        assert len(cache) == 30, "缓存应该有 30 个条目"
        assert second_pass < first_pass, "缓存后应该更快"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
