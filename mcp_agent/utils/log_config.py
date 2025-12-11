"""
日志配置模块

提供更完善的日志配置和管理功能。
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime

import colorlog


class LogConfig:
    """日志配置类"""
    
    # 日志级别映射
    LEVEL_MAP = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    # 默认日志格式
    DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DETAILED_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    SIMPLE_FORMAT = "%(levelname)s - %(message)s"
    
    # 日期格式
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    # 颜色配置
    COLOR_CONFIG = {
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white",
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化日志配置
        
        Args:
            config: 日志配置字典
        """
        self.config = config or {}
        self._loggers: Dict[str, logging.Logger] = {}
    
    def setup_logger(
        self,
        name: str = "mcp_agent",
        level: Optional[str] = None,
        log_file: Optional[str] = None,
        console: Optional[bool] = None,
        format_style: str = "default",
        max_bytes: Optional[int] = None,
        backup_count: Optional[int] = None,
        when: str = "midnight",
        use_color: bool = True,
    ) -> logging.Logger:
        """
        设置日志记录器
        
        Args:
            name: 日志记录器名称
            level: 日志级别
            log_file: 日志文件路径
            console: 是否输出到控制台
            format_style: 格式样式（default/detailed/simple）
            max_bytes: 日志文件最大字节数（用于RotatingFileHandler）
            backup_count: 保留的备份文件数量
            when: 时间轮转间隔（用于TimedRotatingFileHandler）
            use_color: 是否使用彩色输出
        
        Returns:
            配置好的日志记录器
        """
        # 如果已存在，直接返回
        if name in self._loggers:
            return self._loggers[name]
        
        # 获取配置值
        level = level or self.config.get("level", "INFO")
        log_file = log_file or self.config.get("file")
        console = console if console is not None else self.config.get("console", True)
        max_bytes = max_bytes or self.config.get("max_size", 10) * 1024 * 1024
        backup_count = backup_count or self.config.get("backup_count", 5)
        
        # 创建日志记录器
        logger = logging.getLogger(name)
        logger.setLevel(self.LEVEL_MAP.get(level.upper(), logging.INFO))
        logger.handlers.clear()
        logger.propagate = False
        
        # 选择格式
        if format_style == "detailed":
            log_format = self.DETAILED_FORMAT
        elif format_style == "simple":
            log_format = self.SIMPLE_FORMAT
        else:
            log_format = self.config.get("format", self.DEFAULT_FORMAT)
        
        # 添加控制台处理器
        if console:
            console_handler = self._create_console_handler(
                level, log_format, use_color
            )
            logger.addHandler(console_handler)
        
        # 添加文件处理器
        if log_file:
            file_handler = self._create_file_handler(
                log_file, level, log_format, max_bytes, backup_count, when
            )
            logger.addHandler(file_handler)
        
        # 缓存日志记录器
        self._loggers[name] = logger
        
        return logger
    
    def _create_console_handler(
        self,
        level: str,
        log_format: str,
        use_color: bool = True,
    ) -> logging.Handler:
        """
        创建控制台处理器
        
        Args:
            level: 日志级别
            log_format: 日志格式
            use_color: 是否使用彩色输出
        
        Returns:
            控制台处理器
        """
        handler = colorlog.StreamHandler(sys.stdout)
        handler.setLevel(self.LEVEL_MAP.get(level.upper(), logging.INFO))
        
        if use_color:
            color_format = f"%(log_color)s{log_format}%(reset)s"
            formatter = colorlog.ColoredFormatter(
                color_format,
                datefmt=self.DATE_FORMAT,
                log_colors=self.COLOR_CONFIG,
                secondary_log_colors={},
                style="%",
            )
        else:
            formatter = logging.Formatter(log_format, datefmt=self.DATE_FORMAT)
        
        handler.setFormatter(formatter)
        return handler
    
    def _create_file_handler(
        self,
        log_file: str,
        level: str,
        log_format: str,
        max_bytes: int,
        backup_count: int,
        when: str,
    ) -> logging.Handler:
        """
        创建文件处理器
        
        Args:
            log_file: 日志文件路径
            level: 日志级别
            log_format: 日志格式
            max_bytes: 最大字节数
            backup_count: 备份数量
            when: 时间轮转间隔
        
        Returns:
            文件处理器
        """
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 根据配置选择处理器类型
        if max_bytes > 0:
            # 基于大小的轮转
            handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
        else:
            # 基于时间的轮转
            handler = TimedRotatingFileHandler(
                log_file,
                when=when,
                interval=1,
                backupCount=backup_count,
                encoding="utf-8",
            )
        
        handler.setLevel(self.LEVEL_MAP.get(level.upper(), logging.INFO))
        formatter = logging.Formatter(log_format, datefmt=self.DATE_FORMAT)
        handler.setFormatter(formatter)
        
        return handler
    
    def get_logger(self, name: str = "mcp_agent") -> logging.Logger:
        """
        获取日志记录器
        
        Args:
            name: 日志记录器名称
        
        Returns:
            日志记录器
        """
        if name in self._loggers:
            return self._loggers[name]
        
        # 如果不存在，创建一个新的
        return self.setup_logger(name)
    
    def set_level(self, name: str, level: str) -> None:
        """
        设置日志级别
        
        Args:
            name: 日志记录器名称
            level: 日志级别
        """
        if name in self._loggers:
            logger = self._loggers[name]
            logger.setLevel(self.LEVEL_MAP.get(level.upper(), logging.INFO))
            
            # 同时更新所有处理器的级别
            for handler in logger.handlers:
                handler.setLevel(self.LEVEL_MAP.get(level.upper(), logging.INFO))
    
    def add_handler(
        self,
        name: str,
        handler: logging.Handler,
    ) -> None:
        """
        添加处理器
        
        Args:
            name: 日志记录器名称
            handler: 处理器
        """
        if name in self._loggers:
            self._loggers[name].addHandler(handler)
    
    def remove_handler(
        self,
        name: str,
        handler: logging.Handler,
    ) -> None:
        """
        移除处理器
        
        Args:
            name: 日志记录器名称
            handler: 处理器
        """
        if name in self._loggers:
            self._loggers[name].removeHandler(handler)
    
    def close_all(self) -> None:
        """关闭所有日志记录器"""
        for logger in self._loggers.values():
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
        self._loggers.clear()
    
    @staticmethod
    def create_log_filename(
        base_name: str = "mcp-agent",
        extension: str = "log",
        include_date: bool = False,
    ) -> str:
        """
        创建日志文件名
        
        Args:
            base_name: 基础名称
            extension: 文件扩展名
            include_date: 是否包含日期
        
        Returns:
            日志文件名
        """
        if include_date:
            date_str = datetime.now().strftime("%Y%m%d")
            return f"{base_name}_{date_str}.{extension}"
        return f"{base_name}.{extension}"


# 全局日志配置实例
_log_config: Optional[LogConfig] = None


def init_logging(config: Optional[Dict[str, Any]] = None) -> LogConfig:
    """
    初始化全局日志配置
    
    Args:
        config: 日志配置字典
    
    Returns:
        日志配置实例
    """
    global _log_config
    _log_config = LogConfig(config)
    return _log_config


def get_log_config() -> LogConfig:
    """
    获取全局日志配置
    
    Returns:
        日志配置实例
    """
    global _log_config
    if _log_config is None:
        _log_config = LogConfig()
    return _log_config


def setup_logger(
    name: str = "mcp_agent",
    **kwargs,
) -> logging.Logger:
    """
    设置日志记录器（便捷函数）
    
    Args:
        name: 日志记录器名称
        **kwargs: 其他参数
    
    Returns:
        日志记录器
    """
    config = get_log_config()
    return config.setup_logger(name, **kwargs)


def get_logger(name: str = "mcp_agent") -> logging.Logger:
    """
    获取日志记录器（便捷函数）
    
    Args:
        name: 日志记录器名称
    
    Returns:
        日志记录器
    """
    config = get_log_config()
    return config.get_logger(name)