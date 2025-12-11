"""
日志过滤器模块

提供各种日志过滤功能。
"""

import logging
import re
from typing import List, Pattern, Optional


class LevelFilter(logging.Filter):
    """
    日志级别过滤器
    
    只允许特定级别的日志通过。
    """
    
    def __init__(self, levels: List[int]):
        """
        初始化级别过滤器
        
        Args:
            levels: 允许的日志级别列表
        """
        super().__init__()
        self.levels = levels
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            是否允许通过
        """
        return record.levelno in self.levels


class ModuleFilter(logging.Filter):
    """
    模块过滤器
    
    只允许特定模块的日志通过。
    """
    
    def __init__(self, modules: List[str], exclude: bool = False):
        """
        初始化模块过滤器
        
        Args:
            modules: 模块名称列表
            exclude: 是否排除模式（True表示排除这些模块）
        """
        super().__init__()
        self.modules = modules
        self.exclude = exclude
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            是否允许通过
        """
        module_match = any(
            record.name.startswith(module) for module in self.modules
        )
        return not module_match if self.exclude else module_match


class PatternFilter(logging.Filter):
    """
    模式过滤器
    
    根据正则表达式过滤日志消息。
    """
    
    def __init__(
        self,
        patterns: List[str],
        exclude: bool = False,
        case_sensitive: bool = True,
    ):
        """
        初始化模式过滤器
        
        Args:
            patterns: 正则表达式模式列表
            exclude: 是否排除模式
            case_sensitive: 是否区分大小写
        """
        super().__init__()
        flags = 0 if case_sensitive else re.IGNORECASE
        self.patterns: List[Pattern] = [
            re.compile(pattern, flags) for pattern in patterns
        ]
        self.exclude = exclude
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            是否允许通过
        """
        message = record.getMessage()
        pattern_match = any(pattern.search(message) for pattern in self.patterns)
        return not pattern_match if self.exclude else pattern_match


class RateLimitFilter(logging.Filter):
    """
    速率限制过滤器
    
    限制相同消息的日志频率。
    """
    
    def __init__(self, max_per_minute: int = 60):
        """
        初始化速率限制过滤器
        
        Args:
            max_per_minute: 每分钟最大日志数
        """
        super().__init__()
        self.max_per_minute = max_per_minute
        self.message_counts: dict = {}
        self.last_reset = 0
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            是否允许通过
        """
        import time
        
        current_time = time.time()
        current_minute = int(current_time / 60)
        
        # 重置计数器
        if current_minute != self.last_reset:
            self.message_counts.clear()
            self.last_reset = current_minute
        
        # 检查消息计数
        message = record.getMessage()
        count = self.message_counts.get(message, 0)
        
        if count >= self.max_per_minute:
            return False
        
        self.message_counts[message] = count + 1
        return True


class SensitiveDataFilter(logging.Filter):
    """
    敏感数据过滤器
    
    自动屏蔽日志中的敏感信息。
    """
    
    # 敏感数据模式
    PATTERNS = {
        "api_key": re.compile(r"(api[_-]?key['\"]?\s*[:=]\s*['\"]?)([a-zA-Z0-9_-]+)", re.IGNORECASE),
        "password": re.compile(r"(password['\"]?\s*[:=]\s*['\"]?)([^\s'\"]+)", re.IGNORECASE),
        "token": re.compile(r"(token['\"]?\s*[:=]\s*['\"]?)([a-zA-Z0-9_-]+)", re.IGNORECASE),
        "secret": re.compile(r"(secret['\"]?\s*[:=]\s*['\"]?)([a-zA-Z0-9_-]+)", re.IGNORECASE),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    }
    
    def __init__(self, mask: str = "***REDACTED***"):
        """
        初始化敏感数据过滤器
        
        Args:
            mask: 用于替换敏感数据的掩码
        """
        super().__init__()
        self.mask = mask
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            总是返回True（不阻止日志，只修改内容）
        """
        # 获取原始消息
        if hasattr(record, "msg") and isinstance(record.msg, str):
            message = record.msg
            
            # 替换敏感数据
            for pattern_name, pattern in self.PATTERNS.items():
                if pattern_name in ["api_key", "password", "token", "secret"]:
                    # 保留键名，只替换值
                    message = pattern.sub(rf"\1{self.mask}", message)
                else:
                    # 完全替换
                    message = pattern.sub(self.mask, message)
            
            # 更新消息
            record.msg = message
        
        return True


class ContextFilter(logging.Filter):
    """
    上下文过滤器
    
    为日志记录添加上下文信息。
    """
    
    def __init__(self, context: dict):
        """
        初始化上下文过滤器
        
        Args:
            context: 上下文信息字典
        """
        super().__init__()
        self.context = context
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            总是返回True
        """
        # 添加上下文信息到记录
        for key, value in self.context.items():
            setattr(record, key, value)
        return True


class DuplicateFilter(logging.Filter):
    """
    重复消息过滤器
    
    过滤连续重复的日志消息。
    """
    
    def __init__(self, max_duplicates: int = 3):
        """
        初始化重复消息过滤器
        
        Args:
            max_duplicates: 允许的最大重复次数
        """
        super().__init__()
        self.max_duplicates = max_duplicates
        self.last_message: Optional[str] = None
        self.duplicate_count = 0
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            是否允许通过
        """
        message = record.getMessage()
        
        if message == self.last_message:
            self.duplicate_count += 1
            if self.duplicate_count > self.max_duplicates:
                return False
        else:
            # 如果有重复消息被过滤，添加一条汇总日志
            if self.duplicate_count > self.max_duplicates:
                record.msg = f"[上一条消息重复了 {self.duplicate_count - self.max_duplicates} 次]"
            
            self.last_message = message
            self.duplicate_count = 1
        
        return True


def create_filter(
    filter_type: str,
    **kwargs,
) -> Optional[logging.Filter]:
    """
    创建过滤器的工厂函数
    
    Args:
        filter_type: 过滤器类型
        **kwargs: 过滤器参数
    
    Returns:
        过滤器实例
    """
    filters = {
        "level": LevelFilter,
        "module": ModuleFilter,
        "pattern": PatternFilter,
        "rate_limit": RateLimitFilter,
        "sensitive": SensitiveDataFilter,
        "context": ContextFilter,
        "duplicate": DuplicateFilter,
    }
    
    filter_class = filters.get(filter_type)
    if filter_class:
        return filter_class(**kwargs)
    
    return None