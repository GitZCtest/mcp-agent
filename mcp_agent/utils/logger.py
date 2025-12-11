"""
日志工具模块

提供统一的日志配置和管理功能，支持：
- 多级别日志（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- 同时输出到文件和控制台
- 日志文件按日期/大小轮转
- 敏感信息脱敏
- 性能指标记录
"""

import logging
import re
import sys
import time
import functools
import traceback
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional, Dict, Any, Callable, List
from contextlib import contextmanager

try:
    import colorlog
    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False


# ==================== 敏感信息过滤器 ====================

class SensitiveDataFilter(logging.Filter):
    """
    敏感信息过滤器

    自动脱敏日志中的敏感信息，如API密钥、密码等
    """

    # 敏感字段模式
    SENSITIVE_PATTERNS = [
        # API Keys
        (r'(api[_-]?key\s*[=:]\s*)["\']?([a-zA-Z0-9_-]{20,})["\']?', r'\1***REDACTED***'),
        (r'(sk-[a-zA-Z0-9]{20,})', r'sk-***REDACTED***'),
        (r'(anthropic[_-]?api[_-]?key\s*[=:]\s*)["\']?([^\s"\']+)["\']?', r'\1***REDACTED***'),
        (r'(openai[_-]?api[_-]?key\s*[=:]\s*)["\']?([^\s"\']+)["\']?', r'\1***REDACTED***'),
        # Passwords
        (r'(password\s*[=:]\s*)["\']?([^\s"\']+)["\']?', r'\1***REDACTED***'),
        (r'(passwd\s*[=:]\s*)["\']?([^\s"\']+)["\']?', r'\1***REDACTED***'),
        (r'(secret\s*[=:]\s*)["\']?([^\s"\']+)["\']?', r'\1***REDACTED***'),
        # Tokens
        (r'(token\s*[=:]\s*)["\']?([a-zA-Z0-9_-]{20,})["\']?', r'\1***REDACTED***'),
        (r'(bearer\s+)([a-zA-Z0-9_-]{20,})', r'\1***REDACTED***'),
        # Authorization headers
        (r'(Authorization["\']?\s*:\s*["\']?)(Bearer\s+)?([^\s"\']+)', r'\1\2***REDACTED***'),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.SENSITIVE_PATTERNS
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤并脱敏日志记录"""
        if record.msg:
            record.msg = self._redact(str(record.msg))
        if record.args:
            record.args = tuple(
                self._redact(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True

    def _redact(self, text: str) -> str:
        """脱敏文本中的敏感信息"""
        for pattern, replacement in self._compiled_patterns:
            text = pattern.sub(replacement, text)
        return text


# ==================== 性能记录器 ====================

class PerformanceLogger:
    """
    性能记录器

    用于记录操作的执行时间和性能指标
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._timers: Dict[str, float] = {}

    def start_timer(self, name: str) -> None:
        """开始计时"""
        self._timers[name] = time.perf_counter()

    def stop_timer(self, name: str, log_level: int = logging.DEBUG) -> float:
        """
        停止计时并记录

        Returns:
            执行时间（秒）
        """
        if name not in self._timers:
            return 0.0

        elapsed = time.perf_counter() - self._timers[name]
        del self._timers[name]

        self.logger.log(log_level, f"[性能] {name}: {elapsed:.3f}秒")
        return elapsed

    @contextmanager
    def measure(self, name: str, log_level: int = logging.DEBUG):
        """
        上下文管理器，用于测量代码块执行时间

        Usage:
            with perf.measure("操作名称"):
                # 执行代码
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.logger.log(log_level, f"[性能] {name}: {elapsed:.3f}秒")

    def log_metrics(self, metrics: Dict[str, Any], prefix: str = "") -> None:
        """记录性能指标"""
        prefix_str = f"[{prefix}] " if prefix else ""
        for key, value in metrics.items():
            if isinstance(value, float):
                self.logger.debug(f"{prefix_str}{key}: {value:.3f}")
            else:
                self.logger.debug(f"{prefix_str}{key}: {value}")


# ==================== 增强的日志记录器 ====================

class EnhancedLogger:
    """
    增强的日志记录器

    提供：
    - 敏感信息自动脱敏
    - 性能记录
    - 结构化日志
    - 异常详细记录
    """

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self.perf = PerformanceLogger(logger)

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        self._logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        """记录异常，包含完整堆栈"""
        self._logger.exception(msg, *args, **kwargs)

    def log_exception(self, exc: Exception, context: str = "") -> None:
        """
        详细记录异常信息

        Args:
            exc: 异常对象
            context: 上下文描述
        """
        context_str = f"[{context}] " if context else ""
        self._logger.error(
            f"{context_str}异常: {type(exc).__name__}: {exc}\n"
            f"堆栈:\n{traceback.format_exc()}"
        )

    def log_api_call(
        self,
        method: str,
        endpoint: str,
        status: Optional[int] = None,
        duration: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """记录API调用"""
        parts = [f"API调用: {method} {endpoint}"]
        if status:
            parts.append(f"状态: {status}")
        if duration:
            parts.append(f"耗时: {duration:.3f}s")
        if error:
            parts.append(f"错误: {error}")

        level = logging.ERROR if error else logging.DEBUG
        self._logger.log(level, " | ".join(parts))

    def log_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Optional[str] = None,
        success: bool = True,
        duration: Optional[float] = None,
    ) -> None:
        """记录工具调用"""
        status = "成功" if success else "失败"
        parts = [f"工具调用: {tool_name}", f"状态: {status}"]

        if duration:
            parts.append(f"耗时: {duration:.3f}s")

        # 参数摘要（避免过长）
        args_str = str(arguments)
        if len(args_str) > 200:
            args_str = args_str[:200] + "..."
        parts.append(f"参数: {args_str}")

        level = logging.INFO if success else logging.ERROR
        self._logger.log(level, " | ".join(parts))

        # 结果单独记录（DEBUG级别）
        if result:
            result_preview = result[:500] + "..." if len(result) > 500 else result
            self._logger.debug(f"工具结果: {result_preview}")

    def log_mcp_event(
        self,
        event_type: str,
        server_name: str,
        details: Optional[str] = None,
        success: bool = True,
    ) -> None:
        """记录MCP事件"""
        status = "成功" if success else "失败"
        msg = f"MCP事件: {event_type} | 服务器: {server_name} | 状态: {status}"
        if details:
            msg += f" | 详情: {details}"

        level = logging.INFO if success else logging.ERROR
        self._logger.log(level, msg)


# ==================== 日志设置函数 ====================

# 全局日志记录器缓存
_loggers: Dict[str, EnhancedLogger] = {}
_initialized = False


def setup_logger(
    name: str = "mcp_agent",
    level: str = "INFO",
    log_file: Optional[str] = None,
    console: bool = True,
    max_size: int = 10,
    backup_count: int = 5,
    use_date_rotation: bool = False,
    format_style: str = "default",
    enable_sensitive_filter: bool = True,
) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径
        console: 是否输出到控制台
        max_size: 日志文件最大大小（MB），仅在use_date_rotation=False时有效
        backup_count: 保留的日志文件数量
        use_date_rotation: 是否按日期轮转（否则按大小轮转）
        format_style: 格式样式 (default/detailed/simple)
        enable_sensitive_filter: 是否启用敏感信息过滤

    Returns:
        配置好的日志记录器
    """
    global _initialized

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除现有的处理器
    logger.handlers.clear()
    logger.propagate = False

    # 选择日志格式
    if format_style == "detailed":
        log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    elif format_style == "simple":
        log_format = "%(levelname)s - %(message)s"
    else:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    date_format = "%Y-%m-%d %H:%M:%S"

    # 添加敏感信息过滤器
    if enable_sensitive_filter:
        logger.addFilter(SensitiveDataFilter())

    # 控制台处理器（带颜色）
    if console:
        if HAS_COLORLOG:
            console_handler = colorlog.StreamHandler(sys.stdout)
            color_format = f"%(log_color)s{log_format}%(reset)s"
            console_formatter = colorlog.ColoredFormatter(
                color_format,
                datefmt=date_format,
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
            )
            console_handler.setFormatter(console_formatter)
        else:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(
                logging.Formatter(log_format, datefmt=date_format)
            )

        console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if use_date_rotation:
            # 按日期轮转
            file_handler = TimedRotatingFileHandler(
                log_file,
                when="midnight",
                interval=1,
                backupCount=backup_count,
                encoding="utf-8",
            )
            # 设置日志文件名后缀格式
            file_handler.suffix = "%Y%m%d"
        else:
            # 按大小轮转
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_size * 1024 * 1024,
                backupCount=backup_count,
                encoding="utf-8",
            )

        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    _initialized = True
    return logger


def get_logger(name: str = "mcp_agent") -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        日志记录器
    """
    logger = logging.getLogger(name)

    # 如果没有处理器，设置默认配置
    if not logger.handlers and not _initialized:
        setup_logger(name, console=False)  # 默认不输出到控制台，避免干扰

    return logger


def get_enhanced_logger(name: str = "mcp_agent") -> EnhancedLogger:
    """
    获取增强的日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        增强的日志记录器
    """
    if name not in _loggers:
        logger = get_logger(name)
        _loggers[name] = EnhancedLogger(logger)
    return _loggers[name]


# ==================== 装饰器 ====================

def log_function_call(
    logger_name: str = "mcp_agent",
    log_args: bool = True,
    log_result: bool = False,
    log_time: bool = True,
):
    """
    函数调用日志装饰器

    Args:
        logger_name: 日志记录器名称
        log_args: 是否记录参数
        log_result: 是否记录返回值
        log_time: 是否记录执行时间
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            func_name = func.__qualname__

            # 记录调用
            if log_args:
                args_str = str(args)[:100] + "..." if len(str(args)) > 100 else str(args)
                kwargs_str = str(kwargs)[:100] + "..." if len(str(kwargs)) > 100 else str(kwargs)
                logger.debug(f"调用 {func_name}(args={args_str}, kwargs={kwargs_str})")
            else:
                logger.debug(f"调用 {func_name}")

            start_time = time.perf_counter() if log_time else None

            try:
                result = func(*args, **kwargs)

                if log_time:
                    elapsed = time.perf_counter() - start_time
                    logger.debug(f"{func_name} 完成，耗时: {elapsed:.3f}s")

                if log_result:
                    result_str = str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
                    logger.debug(f"{func_name} 返回: {result_str}")

                return result

            except Exception as e:
                if log_time:
                    elapsed = time.perf_counter() - start_time
                    logger.error(f"{func_name} 失败，耗时: {elapsed:.3f}s，错误: {e}")
                else:
                    logger.error(f"{func_name} 失败，错误: {e}")
                raise

        return wrapper
    return decorator


def log_async_function_call(
    logger_name: str = "mcp_agent",
    log_args: bool = True,
    log_result: bool = False,
    log_time: bool = True,
):
    """
    异步函数调用日志装饰器
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            func_name = func.__qualname__

            if log_args:
                args_str = str(args)[:100] + "..." if len(str(args)) > 100 else str(args)
                kwargs_str = str(kwargs)[:100] + "..." if len(str(kwargs)) > 100 else str(kwargs)
                logger.debug(f"调用 {func_name}(args={args_str}, kwargs={kwargs_str})")
            else:
                logger.debug(f"调用 {func_name}")

            start_time = time.perf_counter() if log_time else None

            try:
                result = await func(*args, **kwargs)

                if log_time:
                    elapsed = time.perf_counter() - start_time
                    logger.debug(f"{func_name} 完成，耗时: {elapsed:.3f}s")

                if log_result:
                    result_str = str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
                    logger.debug(f"{func_name} 返回: {result_str}")

                return result

            except Exception as e:
                if log_time:
                    elapsed = time.perf_counter() - start_time
                    logger.error(f"{func_name} 失败，耗时: {elapsed:.3f}s，错误: {e}")
                else:
                    logger.error(f"{func_name} 失败，错误: {e}")
                raise

        return wrapper
    return decorator


# ==================== 便捷函数 ====================

def log_startup(version: str = "unknown", config_info: Optional[Dict[str, Any]] = None) -> None:
    """记录程序启动"""
    logger = get_logger("mcp_agent")
    logger.info("=" * 50)
    logger.info(f"MCP Agent 启动 - 版本: {version}")
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if config_info:
        for key, value in config_info.items():
            logger.info(f"  {key}: {value}")
    logger.info("=" * 50)


def log_shutdown(reason: str = "正常退出") -> None:
    """记录程序退出"""
    logger = get_logger("mcp_agent")
    logger.info("=" * 50)
    logger.info(f"MCP Agent 退出 - 原因: {reason}")
    logger.info(f"退出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
