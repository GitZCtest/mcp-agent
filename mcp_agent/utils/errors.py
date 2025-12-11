"""
错误处理工具模块

提供统一的错误处理、重试机制和用户友好的错误提示。
"""

import asyncio
import functools
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union
from enum import Enum

from mcp_agent.utils.logger import get_logger

logger = get_logger(__name__)


# ==================== 自定义异常 ====================

class MCPAgentError(Exception):
    """MCP Agent 基础异常"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | 详情: {self.details}"
        return self.message

    def user_friendly_message(self) -> str:
        """返回用户友好的错误信息"""
        return self.message


class ConfigurationError(MCPAgentError):
    """配置错误"""

    def user_friendly_message(self) -> str:
        return f"配置错误: {self.message}"


class APIError(MCPAgentError):
    """API调用错误"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        provider: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.status_code = status_code
        self.provider = provider

    def user_friendly_message(self) -> str:
        if self.status_code == 401:
            return "API密钥无效或已过期，请检查配置"
        elif self.status_code == 429:
            return "API请求过于频繁，请稍后重试"
        elif self.status_code == 500:
            return "API服务暂时不可用，请稍后重试"
        elif self.status_code == 503:
            return "API服务过载，请稍后重试"
        return f"API调用失败: {self.message}"


class NetworkError(MCPAgentError):
    """网络错误"""

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.original_error = original_error

    def user_friendly_message(self) -> str:
        return "网络连接失败，请检查网络设置后重试"


class MCPServerError(MCPAgentError):
    """MCP服务器错误"""

    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.server_name = server_name

    def user_friendly_message(self) -> str:
        if self.server_name:
            return f"MCP服务器 '{self.server_name}' 连接失败: {self.message}"
        return f"MCP服务器错误: {self.message}"


class ToolExecutionError(MCPAgentError):
    """工具执行错误"""

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.tool_name = tool_name

    def user_friendly_message(self) -> str:
        if self.tool_name:
            return f"工具 '{self.tool_name}' 执行失败: {self.message}"
        return f"工具执行失败: {self.message}"


class TimeoutError(MCPAgentError):
    """超时错误"""

    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.timeout_seconds = timeout_seconds

    def user_friendly_message(self) -> str:
        if self.timeout_seconds:
            return f"操作超时（{self.timeout_seconds}秒），请稍后重试"
        return "操作超时，请稍后重试"


# ==================== 重试策略 ====================

class RetryStrategy(Enum):
    """重试策略"""
    FIXED = "fixed"  # 固定间隔
    EXPONENTIAL = "exponential"  # 指数退避
    LINEAR = "linear"  # 线性增长


class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        retryable_exceptions: Optional[List[Type[Exception]]] = None,
        retryable_status_codes: Optional[List[int]] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.strategy = strategy
        self.retryable_exceptions = retryable_exceptions or [
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
        ]
        self.retryable_status_codes = retryable_status_codes or [
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        ]

    def get_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        if self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (2 ** attempt)
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)
        else:
            delay = self.base_delay

        return min(delay, self.max_delay)

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """判断是否应该重试"""
        if attempt >= self.max_retries:
            return False

        # 检查异常类型
        for exc_type in self.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True

        # 检查API错误状态码
        if isinstance(exception, APIError) and exception.status_code:
            return exception.status_code in self.retryable_status_codes

        return False


# 默认重试配置
DEFAULT_RETRY_CONFIG = RetryConfig()


# ==================== 重试装饰器 ====================

def retry(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    同步函数重试装饰器

    Args:
        config: 重试配置
        on_retry: 重试时的回调函数
    """
    retry_config = config or DEFAULT_RETRY_CONFIG

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(retry_config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not retry_config.should_retry(e, attempt):
                        raise

                    delay = retry_config.get_delay(attempt)
                    logger.warning(
                        f"函数 {func.__name__} 执行失败 (尝试 {attempt + 1}/{retry_config.max_retries + 1}): {e}"
                        f"，{delay:.1f}秒后重试..."
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    time.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


def async_retry(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    异步函数重试装饰器

    Args:
        config: 重试配置
        on_retry: 重试时的回调函数
    """
    retry_config = config or DEFAULT_RETRY_CONFIG

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(retry_config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not retry_config.should_retry(e, attempt):
                        raise

                    delay = retry_config.get_delay(attempt)
                    logger.warning(
                        f"异步函数 {func.__name__} 执行失败 (尝试 {attempt + 1}/{retry_config.max_retries + 1}): {e}"
                        f"，{delay:.1f}秒后重试..."
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    await asyncio.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


# ==================== 错误处理工具函数 ====================

def get_user_friendly_error(exception: Exception) -> str:
    """
    获取用户友好的错误信息

    Args:
        exception: 异常对象

    Returns:
        用户友好的错误信息
    """
    # 自定义异常
    if isinstance(exception, MCPAgentError):
        return exception.user_friendly_message()

    # 标准异常映射
    error_messages = {
        ConnectionError: "网络连接失败，请检查网络设置",
        TimeoutError: "操作超时，请稍后重试",
        asyncio.TimeoutError: "操作超时，请稍后重试",
        FileNotFoundError: "文件不存在",
        PermissionError: "权限不足，无法执行操作",
        ValueError: "参数错误",
        KeyError: "配置项缺失",
    }

    for exc_type, message in error_messages.items():
        if isinstance(exception, exc_type):
            return f"{message}: {str(exception)}"

    # 默认消息
    return f"发生错误: {type(exception).__name__}: {str(exception)}"


def handle_api_error(exception: Exception, provider: str = "unknown") -> APIError:
    """
    处理API错误，转换为统一的APIError

    Args:
        exception: 原始异常
        provider: API提供商

    Returns:
        APIError实例
    """
    # 尝试提取状态码
    status_code = None
    if hasattr(exception, 'status_code'):
        status_code = exception.status_code
    elif hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
        status_code = exception.response.status_code

    return APIError(
        message=str(exception),
        status_code=status_code,
        provider=provider,
        details={"original_error": type(exception).__name__},
    )


def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    log_error: bool = True,
    **kwargs,
) -> Any:
    """
    安全执行函数，捕获异常并返回默认值

    Args:
        func: 要执行的函数
        *args: 位置参数
        default: 异常时的默认返回值
        log_error: 是否记录错误日志
        **kwargs: 关键字参数

    Returns:
        函数返回值或默认值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_error:
            logger.error(f"安全执行失败 {func.__name__}: {e}")
        return default


async def async_safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    log_error: bool = True,
    **kwargs,
) -> Any:
    """
    安全执行异步函数，捕获异常并返回默认值

    Args:
        func: 要执行的异步函数
        *args: 位置参数
        default: 异常时的默认返回值
        log_error: 是否记录错误日志
        **kwargs: 关键字参数

    Returns:
        函数返回值或默认值
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        if log_error:
            logger.error(f"异步安全执行失败 {func.__name__}: {e}")
        return default


# ==================== 错误收集器 ====================

class ErrorCollector:
    """
    错误收集器

    用于收集多个操作中的错误，最后统一处理
    """

    def __init__(self):
        self.errors: List[Dict[str, Any]] = []

    def add(
        self,
        error: Exception,
        context: str = "",
        critical: bool = False,
    ) -> None:
        """添加错误"""
        self.errors.append({
            "error": error,
            "context": context,
            "critical": critical,
            "type": type(error).__name__,
            "message": str(error),
        })

        # 记录日志
        level = "error" if critical else "warning"
        getattr(logger, level)(f"[{context}] {type(error).__name__}: {error}")

    def has_errors(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0

    def has_critical_errors(self) -> bool:
        """是否有严重错误"""
        return any(e["critical"] for e in self.errors)

    def get_summary(self) -> str:
        """获取错误摘要"""
        if not self.errors:
            return "无错误"

        lines = [f"共 {len(self.errors)} 个错误:"]
        for i, err in enumerate(self.errors, 1):
            prefix = "[严重]" if err["critical"] else ""
            lines.append(f"  {i}. {prefix}[{err['context']}] {err['type']}: {err['message']}")

        return "\n".join(lines)

    def clear(self) -> None:
        """清除所有错误"""
        self.errors.clear()

    def raise_if_critical(self) -> None:
        """如果有严重错误则抛出"""
        critical_errors = [e for e in self.errors if e["critical"]]
        if critical_errors:
            raise MCPAgentError(
                f"存在 {len(critical_errors)} 个严重错误",
                details={"errors": critical_errors},
            )
