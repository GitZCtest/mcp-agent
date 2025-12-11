# 日志系统使用指南

## 概述

MCP Agent 提供了一个完善的日志系统，包括：

- **基础日志功能**：彩色控制台输出、文件日志轮转
- **日志配置管理**：灵活的配置选项
- **日志过滤器**：多种过滤策略
- **日志分析工具**：日志文件分析和统计

## 基础使用

### 1. 简单日志记录

```python
from mcp_agent.utils import setup_logger, get_logger

# 设置日志记录器
logger = setup_logger(
    name="my_app",
    level="INFO",
    log_file="logs/app.log",
    console=True
)

# 使用日志
logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")
```

### 2. 获取已存在的日志记录器

```python
from mcp_agent.utils import get_logger

# 获取日志记录器
logger = get_logger("my_app")
logger.info("使用已存在的日志记录器")
```

## 高级配置

### 1. 使用 LogConfig 类

```python
from mcp_agent.utils import LogConfig

# 创建日志配置
config = LogConfig({
    "level": "DEBUG",
    "file": "logs/app.log",
    "console": True,
    "max_size": 10,  # MB
    "backup_count": 5,
})

# 设置日志记录器
logger = config.setup_logger(
    name="my_app",
    format_style="detailed"  # default/detailed/simple
)
```

### 2. 全局日志配置

```python
from mcp_agent.utils import init_logging, get_log_config

# 初始化全局配置
init_logging({
    "level": "INFO",
    "file": "logs/app.log",
    "console": True,
})

# 在任何地方获取配置
config = get_log_config()
logger = config.get_logger("my_module")
```

### 3. 不同格式样式

```python
# 默认格式
logger = config.setup_logger("app", format_style="default")
# 输出: 2024-12-10 10:00:00 - app - INFO - 消息内容

# 详细格式（包含文件名和行号）
logger = config.setup_logger("app", format_style="detailed")
# 输出: 2024-12-10 10:00:00 - app - INFO - [main.py:42] - 消息内容

# 简单格式
logger = config.setup_logger("app", format_style="simple")
# 输出: INFO - 消息内容
```

## 日志过滤器

### 1. 级别过滤器

只允许特定级别的日志通过：

```python
from mcp_agent.utils import LevelFilter
import logging

# 只允许 ERROR 和 CRITICAL
filter = LevelFilter([logging.ERROR, logging.CRITICAL])
logger.addFilter(filter)
```

### 2. 模块过滤器

只记录特定模块的日志：

```python
from mcp_agent.utils import ModuleFilter

# 只记录 mcp_agent.agent 模块的日志
filter = ModuleFilter(["mcp_agent.agent"])
logger.addFilter(filter)

# 排除特定模块
filter = ModuleFilter(["mcp_agent.tests"], exclude=True)
logger.addFilter(filter)
```

### 3. 模式过滤器

根据正则表达式过滤：

```python
from mcp_agent.utils import PatternFilter

# 只记录包含 "error" 或 "failed" 的日志
filter = PatternFilter(["error", "failed"], case_sensitive=False)
logger.addFilter(filter)

# 排除包含特定模式的日志
filter = PatternFilter(["debug", "trace"], exclude=True)
logger.addFilter(filter)
```

### 4. 速率限制过滤器

限制日志频率：

```python
from mcp_agent.utils import RateLimitFilter

# 每分钟最多60条相同消息
filter = RateLimitFilter(max_per_minute=60)
logger.addFilter(filter)
```

### 5. 敏感数据过滤器

自动屏蔽敏感信息：

```python
from mcp_agent.utils import SensitiveDataFilter

# 自动屏蔽 API 密钥、密码等
filter = SensitiveDataFilter(mask="***REDACTED***")
logger.addFilter(filter)

# 示例
logger.info("API Key: sk-1234567890")
# 输出: API Key: ***REDACTED***
```

### 6. 上下文过滤器

为日志添加上下文信息：

```python
from mcp_agent.utils import ContextFilter

# 添加用户ID和会话ID
filter = ContextFilter({
    "user_id": "user123",
    "session_id": "sess456"
})
logger.addFilter(filter)
```

### 7. 重复消息过滤器

过滤连续重复的日志：

```python
from mcp_agent.utils import DuplicateFilter

# 最多允许3次重复
filter = DuplicateFilter(max_duplicates=3)
logger.addFilter(filter)
```

### 8. 使用过滤器工厂

```python
from mcp_agent.utils import create_filter

# 创建级别过滤器
filter = create_filter("level", levels=[logging.ERROR])

# 创建模式过滤器
filter = create_filter("pattern", patterns=["error"], exclude=False)

# 创建敏感数据过滤器
filter = create_filter("sensitive", mask="***")
```

## 日志分析

### 1. 分析日志文件

```python
from mcp_agent.utils import LogAnalyzer

# 创建分析器
analyzer = LogAnalyzer("logs/app.log")

# 分析日志
stats = analyzer.analyze()

print(f"总行数: {stats['total_lines']}")
print(f"级别统计: {stats['level_counts']}")
print(f"时间范围: {stats['time_range']}")
print(f"错误数量: {len(stats['error_messages'])}")
```

### 2. 打印日志摘要

```python
from mcp_agent.utils import print_log_summary

# 打印摘要
print_log_summary("logs/app.log")
```

输出示例：
```
==================================================
日志分析摘要
==================================================
日志文件: logs/app.log
总行数: 1234

级别统计:
  DEBUG: 234 (19.0%)
  INFO: 890 (72.1%)
  WARNING: 89 (7.2%)
  ERROR: 18 (1.5%)
  CRITICAL: 3 (0.2%)

时间范围: 2024-12-10 08:00:00 至 2024-12-10 10:00:00

错误/严重错误数: 21
最近的错误:
  2024-12-10 09:55:23 - app - ERROR - 连接失败...
  2024-12-10 09:58:12 - app - ERROR - 超时错误...

活跃模块 (Top 5):
  mcp_agent.agent: 456
  mcp_agent.cli: 234
  mcp_agent.config: 123
==================================================
```

### 3. 搜索日志

```python
analyzer = LogAnalyzer("logs/app.log")

# 搜索包含 "error" 的日志
errors = analyzer.search("error", case_sensitive=False)

# 按级别过滤
warnings = analyzer.filter_by_level("WARNING")

# 按时间范围过滤
logs = analyzer.filter_by_time_range(
    "2024-12-10 08:00:00",
    "2024-12-10 10:00:00"
)
```

### 4. 导出错误日志

```python
analyzer = LogAnalyzer("logs/app.log")
analyzer.analyze()
analyzer.export_errors("logs/errors_only.log")
```

## 配置文件示例

在 `config/config.yaml` 中配置日志：

```yaml
logging:
  # 日志级别
  level: "INFO"
  
  # 日志文件路径
  file: "logs/mcp-agent.log"
  
  # 是否输出到控制台
  console: true
  
  # 日志格式
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
  # 日志文件最大大小（MB）
  max_size: 10
  
  # 保留的日志文件数量
  backup_count: 5
```

## 最佳实践

### 1. 使用合适的日志级别

```python
# DEBUG: 详细的调试信息
logger.debug(f"变量值: {variable}")

# INFO: 一般信息
logger.info("应用启动成功")

# WARNING: 警告信息
logger.warning("配置项缺失，使用默认值")

# ERROR: 错误信息
logger.error("操作失败", exc_info=True)

# CRITICAL: 严重错误
logger.critical("系统崩溃")
```

### 2. 记录异常信息

```python
try:
    # 可能出错的代码
    result = risky_operation()
except Exception as e:
    # 记录完整的异常堆栈
    logger.error("操作失败", exc_info=True)
    # 或
    logger.exception("操作失败")
```

### 3. 使用结构化日志

```python
# 不好的做法
logger.info(f"用户 {user_id} 执行了 {action}")

# 好的做法（便于解析）
logger.info(
    "用户操作",
    extra={
        "user_id": user_id,
        "action": action,
        "timestamp": datetime.now()
    }
)
```

### 4. 避免敏感信息泄露

```python
# 使用敏感数据过滤器
from mcp_agent.utils import SensitiveDataFilter

filter = SensitiveDataFilter()
logger.addFilter(filter)

# 或手动处理
logger.info(f"API Key: {api_key[:4]}...{api_key[-4:]}")
```

### 5. 性能考虑

```python
# 避免在循环中频繁记录
for item in large_list:
    # 不好
    logger.debug(f"处理项目: {item}")

# 使用速率限制
from mcp_agent.utils import RateLimitFilter
logger.addFilter(RateLimitFilter(max_per_minute=10))

# 或批量记录
if len(large_list) > 0:
    logger.info(f"处理了 {len(large_list)} 个项目")
```

## 故障排查

### 1. 日志文件未创建

检查：
- 日志目录是否存在
- 是否有写入权限
- 配置文件路径是否正确

### 2. 日志级别不生效

确保：
- 日志记录器和处理器的级别都正确设置
- 没有被过滤器拦截

### 3. 日志文件过大

使用日志轮转：
```python
# 基于大小的轮转
config.setup_logger(
    "app",
    max_bytes=10*1024*1024,  # 10MB
    backup_count=5
)

# 基于时间的轮转
config.setup_logger(
    "app",
    max_bytes=0,  # 禁用大小轮转
    when="midnight",  # 每天午夜轮转
    backup_count=7
)
```

## 命令行工具

### 分析日志文件

```bash
# 使用 Python 脚本
python -c "from mcp_agent.utils import print_log_summary; print_log_summary('logs/app.log')"
```

## 总结

MCP Agent 的日志系统提供了：

✅ 灵活的配置选项  
✅ 多种日志过滤策略  
✅ 自动敏感数据屏蔽  
✅ 日志分析和统计工具  
✅ 彩色控制台输出  
✅ 文件日志轮转  
✅ 性能优化选项  

合理使用日志系统可以帮助你更好地监控和调试应用程序！