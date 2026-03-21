"""
缓存服务单元测试

测试 backend.services.cache_service 模块的 Redis 单例和连接管理
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json


class TestCacheServiceSingleton:
    """CacheService 单例模式测试"""
    
    def test_singleton_instance(self):
        """测试单例模式确保只有一个实例"""
        from backend.services.cache_service import CacheService
        
        # 清除之前的实例
        CacheService._instance = None
        CacheService._client = None
        
        instance1 = CacheService()
        instance2 = CacheService()
        
        # 应该是同一个实例
        assert instance1 is instance2
    
    def test_singleton_with_multiple_imports(self):
        """测试多次导入仍保持单例"""
        from backend.services.cache_service import CacheService
        
        # 清除之前的实例
        CacheService._instance = None
        CacheService._client = None
        
        # 模拟多次导入
        instances = [CacheService() for _ in range(5)]
        
        # 所有实例都应该是同一个
        for instance in instances[1:]:
            assert instance is instances[0]


class TestCacheServiceConnection:
    """CacheService 连接管理测试"""
    
    @patch('backend.services.cache_service.redis')
    def test_redis_client_initialization(self, mock_redis):
        """测试 Redis 客户端初始化"""
        from backend.services.cache_service import CacheService
        from backend.config import settings
        
        # 清除之前的实例
        CacheService._instance = None
        CacheService._client = None
        
        # Mock Redis client
        mock_client = Mock()
        mock_redis.from_url.return_value = mock_client
        
        service = CacheService()
        
        # 验证 Redis 客户端被正确初始化
        mock_redis.from_url.assert_called_once_with(
            settings.REDIS_URL,
            decode_responses=True
        )
        assert service._client is mock_client
    
    @patch('backend.services.cache_service.redis')
    def test_redis_client_property(self, mock_redis):
        """测试 client 属性返回正确的客户端"""
        from backend.services.cache_service import CacheService
        
        # 清除之前的实例
        CacheService._instance = None
        CacheService._client = None
        
        mock_client = Mock()
        mock_redis.from_url.return_value = mock_client
        
        service = CacheService()
        
        assert service.client is mock_client
    
    @patch('backend.services.cache_service.redis')
    def test_close_connection(self, mock_redis):
        """测试关闭 Redis 连接"""
        from backend.services.cache_service import CacheService
        
        # 清除之前的实例
        CacheService._instance = None
        CacheService._client = None
        
        mock_client = Mock()
        mock_redis.from_url.return_value = mock_client
        
        service = CacheService()
        service.close()
        
        # 验证连接被关闭
        mock_client.close.assert_called_once()
        assert service._initialized is False


class TestCacheServiceOperations:
    """CacheService 基本操作测试"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """创建 Mock 缓存服务"""
        from backend.services.cache_service import CacheService
        
        # 清除之前的实例
        CacheService._instance = None
        CacheService._client = None
        
        with patch('backend.services.cache_service.redis') as mock_redis:
            mock_client = Mock()
            mock_redis.from_url.return_value = mock_client
            
            service = CacheService()
            yield service, mock_client
    
    @pytest.mark.asyncio
    async def test_get_success(self, mock_cache_service):
        """测试成功获取缓存"""
        service, mock_client = mock_cache_service
        
        mock_client.get.return_value = b'test_value'
        
        result = await service.get('test_key')
        
        # 由于设置了 decode_responses=True，不需要 decode
        mock_client.get.assert_called_once_with('test_key')
        assert result == b'test_value'  # 直接返回 bytes
    
    @pytest.mark.asyncio
    async def test_get_not_found(self, mock_cache_service):
        """测试获取不存在的缓存"""
        service, mock_client = mock_cache_service
        
        mock_client.get.return_value = None
        
        result = await service.get('nonexistent_key')
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_exception_handling(self, mock_cache_service):
        """测试获取缓存时的异常处理"""
        service, mock_client = mock_cache_service
        
        mock_client.get.side_effect = Exception('Redis error')
        
        result = await service.get('test_key')
        
        # 异常应该被捕获，返回 None
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_success(self, mock_cache_service):
        """测试成功设置缓存"""
        service, mock_client = mock_cache_service
        
        result = await service.set('test_key', 'test_value', ttl=3600)
        
        mock_client.setex.assert_called_once_with('test_key', 3600, 'test_value')
        assert result is True
    
    @pytest.mark.asyncio
    async def test_set_exception_handling(self, mock_cache_service):
        """测试设置缓存时的异常处理"""
        service, mock_client = mock_cache_service
        
        mock_client.setex.side_effect = Exception('Redis error')
        
        result = await service.set('test_key', 'test_value')
        
        # 异常应该被捕获，返回 False
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_success(self, mock_cache_service):
        """测试成功删除缓存"""
        service, mock_client = mock_cache_service
        
        result = await service.delete('test_key')
        
        mock_client.delete.assert_called_once_with('test_key')
        assert result is True
    
    @pytest.mark.asyncio
    async def test_exists_true(self, mock_cache_service):
        """测试缓存存在"""
        service, mock_client = mock_cache_service
        
        mock_client.exists.return_value = 1
        
        result = await service.exists('test_key')
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_exists_false(self, mock_cache_service):
        """测试缓存不存在"""
        service, mock_client = mock_cache_service
        
        mock_client.exists.return_value = 0
        
        result = await service.exists('nonexistent_key')
        
        assert result is False


class TestCacheServiceGenerationResult:
    """生成结果缓存测试"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """创建 Mock 缓存服务"""
        from backend.services.cache_service import CacheService
        
        # 清除之前的实例
        CacheService._instance = None
        CacheService._client = None
        
        with patch('backend.services.cache_service.redis') as mock_redis:
            mock_client = Mock()
            mock_redis.from_url.return_value = mock_client
            
            service = CacheService()
            yield service, mock_client
    
    @pytest.mark.asyncio
    async def test_get_generation_result(self, mock_cache_service):
        """测试获取生成结果"""
        service, mock_client = mock_cache_service
        
        test_data = {'result': 'test', 'status': 'completed'}
        mock_client.get.return_value = json.dumps(test_data).encode('utf-8')
        
        result = await service.get_generation_result('task_123')
        
        mock_client.get.assert_called_once_with('generation:task_123')
        assert result == test_data
    
    @pytest.mark.asyncio
    async def test_set_generation_result(self, mock_cache_service):
        """测试设置生成结果"""
        service, mock_client = mock_cache_service
        
        test_data = {'result': 'test', 'status': 'completed'}
        
        await service.set_generation_result('task_123', test_data, ttl=300)
        
        expected_value = json.dumps(test_data)
        mock_client.setex.assert_called_once_with('generation:task_123', 300, expected_value)
    
    @pytest.mark.asyncio
    async def test_delete_generation_result(self, mock_cache_service):
        """测试删除生成结果"""
        service, mock_client = mock_cache_service
        
        await service.delete_generation_result('task_123')
        
        mock_client.delete.assert_called_once_with('generation:task_123')


class TestCacheServiceAgentOutput:
    """Agent 输出缓存测试"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """创建 Mock 缓存服务"""
        from backend.services.cache_service import CacheService
        
        # 清除之前的实例
        CacheService._instance = None
        CacheService._client = None
        
        with patch('backend.services.cache_service.redis') as mock_redis:
            mock_client = Mock()
            mock_redis.from_url.return_value = mock_client
            
            service = CacheService()
            yield service, mock_client
    
    @pytest.mark.asyncio
    async def test_get_agent_output(self, mock_cache_service):
        """测试获取 Agent 输出"""
        service, mock_client = mock_cache_service
        
        test_data = {'output': 'test content'}
        mock_client.get.return_value = json.dumps(test_data).encode('utf-8')
        
        result = await service.get_agent_output('writer', 1, version=1)
        
        expected_key = 'agent:writer:novel:1:v1'
        mock_client.get.assert_called_once_with(expected_key)
        assert result == test_data
    
    @pytest.mark.asyncio
    async def test_set_agent_output(self, mock_cache_service):
        """测试设置 Agent 输出"""
        service, mock_client = mock_cache_service
        
        test_data = {'output': 'test content'}
        
        await service.set_agent_output('writer', 1, version=1, output=test_data)
        
        expected_key = 'agent:writer:novel:1:v1'
        expected_value = json.dumps(test_data)
        mock_client.setex.assert_called_once_with(expected_key, 3600, expected_value)


class TestCacheServiceChapterContent:
    """章节内容缓存测试"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """创建 Mock 缓存服务"""
        from backend.services.cache_service import CacheService
        
        # 清除之前的实例
        CacheService._instance = None
        CacheService._client = None
        
        with patch('backend.services.cache_service.redis') as mock_redis:
            mock_client = Mock()
            mock_redis.from_url.return_value = mock_client
            
            service = CacheService()
            yield service, mock_client
    
    @pytest.mark.asyncio
    async def test_get_chapter_content(self, mock_cache_service):
        """测试获取章节内容"""
        service, mock_client = mock_cache_service
        
        mock_client.get.return_value = b'Chapter content here'
        
        result = await service.get_chapter_content(1, 5)
        
        expected_key = 'chapter:1:5:content'
        mock_client.get.assert_called_once_with(expected_key)
        assert result == b'Chapter content here'
    
    @pytest.mark.asyncio
    async def test_set_chapter_content(self, mock_cache_service):
        """测试设置章节内容"""
        service, mock_client = mock_cache_service
        
        content = 'This is chapter content'
        
        await service.set_chapter_content(1, 5, content, ttl=7200)
        
        expected_key = 'chapter:1:5:content'
        mock_client.setex.assert_called_once_with(expected_key, 7200, content)


class TestCacheServiceDashboardStats:
    """仪表盘统计缓存测试"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """创建 Mock 缓存服务"""
        from backend.services.cache_service import CacheService
        
        # 清除之前的实例
        CacheService._instance = None
        CacheService._client = None
        
        with patch('backend.services.cache_service.redis') as mock_redis:
            mock_client = Mock()
            mock_redis.from_url.return_value = mock_client
            
            service = CacheService()
            yield service, mock_client
    
    @pytest.mark.asyncio
    async def test_get_dashboard_stats(self, mock_cache_service):
        """测试获取仪表盘统计"""
        service, mock_client = mock_cache_service
        
        test_stats = {'total_novels': 10, 'total_words': 50000}
        mock_client.get.return_value = json.dumps(test_stats).encode('utf-8')
        
        result = await service.get_dashboard_stats(123)
        
        expected_key = 'dashboard:123:stats'
        mock_client.get.assert_called_once_with(expected_key)
        assert result == test_stats
    
    @pytest.mark.asyncio
    async def test_set_dashboard_stats(self, mock_cache_service):
        """测试设置仪表盘统计"""
        service, mock_client = mock_cache_service
        
        test_stats = {'total_novels': 10, 'total_words': 50000}
        
        await service.set_dashboard_stats(123, test_stats, ttl=300)
        
        expected_key = 'dashboard:123:stats'
        expected_value = json.dumps(test_stats)
        mock_client.setex.assert_called_once_with(expected_key, 300, expected_value)
