"""
异常模块 - 定义系统的异常层次结构

本模块提供细化的异常类，便于定位和处理不同类型的错误。
异常层次结构：
- NovelException (基类)
  - NovelSystemError (系统级错误)
    - DatabaseError (数据库错误)
    - CacheError (缓存错误)
    - LLMError (LLM API 错误)
    - ConfigError (配置错误)
  - NovelBusinessError (业务级错误)
    - NovelError (小说相关错误)
    - ChapterError (章节相关错误)
    - CharacterError (角色相关错误)
    - WorldSettingError (世界观相关错误)
    - OutlineError (大纲相关错误)
    - GenerationError (生成相关错误)
    - PublishError (发布相关错误)
  - ValidationError (验证错误)
    - InvalidParameterError (参数验证错误)
    - MissingRequiredFieldError (必填字段缺失)
    - DataFormatError (数据格式错误)
  - ExternalServiceError (外部服务错误)
    - CrawlerError (爬虫错误)
    - PlatformAPIError (平台 API 错误)
"""

from typing import Any, Dict, Optional


class NovelException(Exception):
    """
    小说系统异常基类.
    
    所有自定义异常都应继承此类，便于统一捕获和处理。
    
    Attributes:
        message: 错误消息
        code: 错误代码（可选）
        details: 额外详细信息（可选）
    """

    def __init__(
        self,
        message: str = "系统发生错误",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化异常.
        
        Args:
            message: 错误消息
            code: 错误代码，用于前端展示或日志分类
            details: 额外详细信息，如堆栈、上下文等
        """
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """
        将异常转换为字典格式，便于 API 响应.
        
        Returns:
            包含异常信息的字典
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "details": self.details,
        }


# ============================================================================
# 系统级异常
# ============================================================================


class NovelSystemError(NovelException):
    """
    系统级错误基类.
    
    表示系统层面的错误，如数据库连接失败、配置错误等。
    """

    def __init__(
        self,
        message: str = "系统错误",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code or "SYSTEM_ERROR", details)


class DatabaseError(NovelSystemError):
    """
    数据库操作错误.
    
    包括连接失败、查询错误、事务失败等。
    """

    def __init__(
        self,
        message: str = "数据库操作失败",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if operation:
            detail_info["operation"] = operation
        super().__init__(message, "DATABASE_ERROR", detail_info)


class CacheError(NovelSystemError):
    """
    缓存操作错误.
    
    包括 Redis 连接失败、缓存读写错误等。
    """

    def __init__(
        self,
        message: str = "缓存操作失败",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if operation:
            detail_info["operation"] = operation
        super().__init__(message, "CACHE_ERROR", detail_info)


class LLMError(NovelSystemError):
    """
    LLM API 调用错误.
    
    包括 API 密钥无效、请求超时、响应解析失败等。
    """

    def __init__(
        self,
        message: str = "LLM API 调用失败",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if provider:
            detail_info["provider"] = provider
        if model:
            detail_info["model"] = model
        super().__init__(message, "LLM_ERROR", detail_info)


class ConfigError(NovelSystemError):
    """
    配置错误.
    
    包括配置项缺失、配置值无效、配置依赖关系错误等。
    """

    def __init__(
        self,
        message: str = "配置错误",
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if config_key:
            detail_info["config_key"] = config_key
        super().__init__(message, "CONFIG_ERROR", detail_info)


# ============================================================================
# 业务级异常
# ============================================================================


class NovelBusinessError(NovelException):
    """
    业务级错误基类.
    
    表示业务逻辑层面的错误，如资源不存在、操作不允许等。
    """

    def __init__(
        self,
        message: str = "业务错误",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code or "BUSINESS_ERROR", details)


class NovelError(NovelBusinessError):
    """
    小说相关错误.
    
    包括小说不存在、小说创建失败、小说更新冲突等。
    """

    def __init__(
        self,
        message: str = "小说操作失败",
        novel_id: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if novel_id:
            detail_info["novel_id"] = novel_id
        if operation:
            detail_info["operation"] = operation
        super().__init__(message, "NOVEL_ERROR", detail_info)


class ChapterError(NovelBusinessError):
    """
    章节相关错误.
    
    包括章节不存在、章节生成失败、章节发布失败等。
    """

    def __init__(
        self,
        message: str = "章节操作失败",
        novel_id: Optional[str] = None,
        chapter_number: Optional[int] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if novel_id:
            detail_info["novel_id"] = novel_id
        if chapter_number is not None:
            detail_info["chapter_number"] = chapter_number
        if operation:
            detail_info["operation"] = operation
        super().__init__(message, "CHAPTER_ERROR", detail_info)


class CharacterError(NovelBusinessError):
    """
    角色相关错误.
    
    包括角色不存在、角色同步失败、角色创建冲突等。
    """

    def __init__(
        self,
        message: str = "角色操作失败",
        novel_id: Optional[str] = None,
        character_id: Optional[str] = None,
        character_name: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if novel_id:
            detail_info["novel_id"] = novel_id
        if character_id:
            detail_info["character_id"] = character_id
        if character_name:
            detail_info["character_name"] = character_name
        if operation:
            detail_info["operation"] = operation
        super().__init__(message, "CHARACTER_ERROR", detail_info)


class WorldSettingError(NovelBusinessError):
    """
    世界观相关错误.
    
    包括世界观不存在、世界观更新失败等。
    """

    def __init__(
        self,
        message: str = "世界观操作失败",
        novel_id: Optional[str] = None,
        setting_type: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if novel_id:
            detail_info["novel_id"] = novel_id
        if setting_type:
            detail_info["setting_type"] = setting_type
        if operation:
            detail_info["operation"] = operation
        super().__init__(message, "WORLD_SETTING_ERROR", detail_info)


class OutlineError(NovelBusinessError):
    """
    大纲相关错误.
    
    包括大纲不存在、大纲生成失败、大纲版本冲突等。
    """

    def __init__(
        self,
        message: str = "大纲操作失败",
        novel_id: Optional[str] = None,
        outline_id: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if novel_id:
            detail_info["novel_id"] = novel_id
        if outline_id:
            detail_info["outline_id"] = outline_id
        if operation:
            detail_info["operation"] = operation
        super().__init__(message, "OUTLINE_ERROR", detail_info)


class GenerationError(NovelBusinessError):
    """
    生成相关错误.
    
    包括生成任务失败、生成超时、生成质量不达标等。
    """

    def __init__(
        self,
        message: str = "生成任务失败",
        task_id: Optional[str] = None,
        novel_id: Optional[str] = None,
        chapter_number: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if task_id:
            detail_info["task_id"] = task_id
        if novel_id:
            detail_info["novel_id"] = novel_id
        if chapter_number is not None:
            detail_info["chapter_number"] = chapter_number
        super().__init__(message, "GENERATION_ERROR", detail_info)


class PublishError(NovelBusinessError):
    """
    发布相关错误.
    
    包括发布任务失败、平台 API 错误、发布状态同步失败等。
    """

    def __init__(
        self,
        message: str = "发布任务失败",
        task_id: Optional[str] = None,
        novel_id: Optional[str] = None,
        chapter_number: Optional[int] = None,
        platform: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if task_id:
            detail_info["task_id"] = task_id
        if novel_id:
            detail_info["novel_id"] = novel_id
        if chapter_number is not None:
            detail_info["chapter_number"] = chapter_number
        if platform:
            detail_info["platform"] = platform
        super().__init__(message, "PUBLISH_ERROR", detail_info)


# ============================================================================
# 验证异常
# ============================================================================


class ValidationError(NovelException):
    """
    验证错误基类.
    
    表示数据验证失败，包括参数验证、格式验证、业务规则验证等。
    """

    def __init__(
        self,
        message: str = "验证失败",
        field: Optional[str] = None,
        value: Any = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if field:
            detail_info["field"] = field
        if value is not None:
            detail_info["value"] = str(value)
        super().__init__(message, "VALIDATION_ERROR", detail_info)


class InvalidParameterError(ValidationError):
    """
    参数验证错误.
    
    表示 API 参数或函数参数无效。
    """

    def __init__(
        self,
        message: str = "参数无效",
        parameter: Optional[str] = None,
        expected_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if parameter:
            detail_info["parameter"] = parameter
        if expected_type:
            detail_info["expected_type"] = expected_type
        super().__init__(message, "INVALID_PARAMETER", detail_info)


class MissingRequiredFieldError(ValidationError):
    """
    必填字段缺失错误.
    
    表示创建或更新操作时缺少必填字段。
    """

    def __init__(
        self,
        message: str = "必填字段缺失",
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if field:
            detail_info["field"] = field
        super().__init__(message, "MISSING_REQUIRED_FIELD", detail_info)


class DataFormatError(ValidationError):
    """
    数据格式错误.
    
    表示数据格式不符合预期，如 JSON 解析失败、日期格式错误等。
    """

    def __init__(
        self,
        message: str = "数据格式错误",
        field: Optional[str] = None,
        expected_format: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if field:
            detail_info["field"] = field
        if expected_format:
            detail_info["expected_format"] = expected_format
        super().__init__(message, "DATA_FORMAT_ERROR", detail_info)


# ============================================================================
# 外部服务异常
# ============================================================================


class ExternalServiceError(NovelSystemError):
    """
    外部服务错误基类.
    
    表示调用外部服务（如爬虫、平台 API）时发生的错误。
    """

    def __init__(
        self,
        message: str = "外部服务调用失败",
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if service_name:
            detail_info["service_name"] = service_name
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", detail_info)


class CrawlerError(ExternalServiceError):
    """
    爬虫错误.
    
    包括网页抓取失败、反爬虫拦截、解析失败等。
    """

    def __init__(
        self,
        message: str = "爬虫操作失败",
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if url:
            detail_info["url"] = url
        if status_code:
            detail_info["status_code"] = status_code
        super().__init__(message, "CRAWLER_ERROR", detail_info)


class PlatformAPIError(ExternalServiceError):
    """
    平台 API 错误.
    
    包括小说平台 API 调用失败、认证失败、频率限制等。
    """

    def __init__(
        self,
        message: str = "平台 API 调用失败",
        platform: Optional[str] = None,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if platform:
            detail_info["platform"] = platform
        if endpoint:
            detail_info["endpoint"] = endpoint
        if status_code:
            detail_info["status_code"] = status_code
        super().__init__(message, "PLATFORM_API_ERROR", detail_info)


# ============================================================================
# 便捷异常类（用于常见场景）
# ============================================================================


class NotFoundError(NovelBusinessError):
    """
    资源未找到错误.
    
    用于统一处理资源不存在的情况。
    """

    def __init__(
        self,
        resource_type: str = "资源",
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"{resource_type}不存在"
        if resource_id:
            message += f": {resource_id}"
        detail_info = details or {}
        if resource_id:
            detail_info["resource_id"] = resource_id
        detail_info["resource_type"] = resource_type
        super().__init__(message, "NOT_FOUND", detail_info)


class ConflictError(NovelBusinessError):
    """
    资源冲突错误.
    
    用于处理唯一性约束冲突、版本冲突等。
    """

    def __init__(
        self,
        message: str = "资源冲突",
        resource_type: Optional[str] = None,
        conflict_field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if resource_type:
            detail_info["resource_type"] = resource_type
        if conflict_field:
            detail_info["conflict_field"] = conflict_field
        super().__init__(message, "CONFLICT_ERROR", detail_info)


class PermissionError(NovelBusinessError):
    """
    权限错误.
    
    表示用户没有执行某操作的权限。
    """

    def __init__(
        self,
        message: str = "权限不足",
        required_permission: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if required_permission:
            detail_info["required_permission"] = required_permission
        super().__init__(message, "PERMISSION_ERROR", detail_info)


class RateLimitError(NovelSystemError):
    """
    频率限制错误.
    
    表示 API 调用频率超过限制。
    """

    def __init__(
        self,
        message: str = "请求频率超限",
        service: Optional[str] = None,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        detail_info = details or {}
        if service:
            detail_info["service"] = service
        if retry_after:
            detail_info["retry_after_seconds"] = retry_after
        super().__init__(message, "RATE_LIMIT_ERROR", detail_info)
