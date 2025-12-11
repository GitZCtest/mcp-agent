"""
MCP Agent 主入口文件

启动命令行智能体应用，并注入全局 ConsoleUI。
"""

import sys
import io
import atexit
import signal

# 在 Windows 上设置 UTF-8 编码
if sys.platform == 'win32':
    # 设置控制台代码页为 UTF-8
    try:
        import os
        os.system('chcp 65001 >nul 2>&1')
    except:
        pass

    # 重新配置标准输入输出流
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    if hasattr(sys.stdin, 'buffer'):
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')

from mcp_agent.cli import main as cli_main
from mcp_agent.ui import ConsoleUI
from mcp_agent.utils.logger import setup_logger, log_startup, log_shutdown, get_logger

# 版本号
__version__ = "0.1.0"


def _on_exit():
    """程序退出时的清理函数"""
    log_shutdown("正常退出")


def _signal_handler(signum, frame):
    """信号处理函数"""
    sig_name = signal.Signals(signum).name
    log_shutdown(f"收到信号 {sig_name}")
    sys.exit(0)


def main() -> None:
    """程序入口：创建 UI 并交给 CLI 子系统。"""
    # 初始化日志系统
    logger = setup_logger(
        name="mcp_agent",
        level="INFO",
        log_file="logs/mcp-agent.log",
        console=False,  # CLI有自己的输出，日志不输出到控制台
        max_size=10,
        backup_count=5,
        use_date_rotation=True,
        enable_sensitive_filter=True,
    )

    # 注册退出处理
    atexit.register(_on_exit)

    # 注册信号处理（仅在非Windows或支持的信号）
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
    except (AttributeError, ValueError):
        pass  # Windows可能不支持某些信号

    # 记录启动
    log_startup(
        version=__version__,
        config_info={
            "Python版本": sys.version.split()[0],
            "平台": sys.platform,
        }
    )

    try:
        cli_main.main(standalone_mode=False, obj={"ui": ConsoleUI()})
    except KeyboardInterrupt:
        log_shutdown("用户中断 (Ctrl+C)")
    except SystemExit as e:
        if e.code != 0:
            log_shutdown(f"异常退出，代码: {e.code}")
        raise
    except Exception as e:
        logger.exception(f"程序异常退出: {e}")
        log_shutdown(f"异常: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
