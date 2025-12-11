"""
格式化工具模块

提供消息和错误的格式化功能。
"""

from typing import Any, Dict, List, Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table


console = Console()


def format_message(
    content: str,
    role: str = "assistant",
    title: Optional[str] = None,
    markdown: bool = True,
) -> None:
    """
    格式化并打印消息
    
    Args:
        content: 消息内容
        role: 角色（user/assistant/system）
        title: 标题
        markdown: 是否使用Markdown渲染
    """
    if role == "user":
        color = "cyan"
        default_title = "👤 用户"
    elif role == "assistant":
        color = "green"
        default_title = "🤖 助手"
    else:
        color = "yellow"
        default_title = "⚙️ 系统"
    
    display_title = title or default_title
    
    if markdown:
        content_display = Markdown(content)
    else:
        content_display = content
    
    panel = Panel(
        content_display,
        title=display_title,
        border_style=color,
        padding=(1, 2),
    )
    console.print(panel)


def format_error(error: Exception, title: str = "❌ 错误") -> None:
    """
    格式化并打印错误信息
    
    Args:
        error: 异常对象
        title: 标题
    """
    error_message = f"[bold red]{type(error).__name__}[/bold red]: {str(error)}"
    panel = Panel(
        error_message,
        title=title,
        border_style="red",
        padding=(1, 2),
    )
    console.print(panel)


def format_code(code: str, language: str = "python") -> None:
    """
    格式化并打印代码
    
    Args:
        code: 代码内容
        language: 编程语言
    """
    syntax = Syntax(code, language, theme="monokai", line_numbers=True)
    console.print(syntax)


def format_table(data: List[Dict[str, Any]], title: Optional[str] = None) -> None:
    """
    格式化并打印表格
    
    Args:
        data: 表格数据
        title: 表格标题
    """
    if not data:
        console.print("[yellow]没有数据[/yellow]")
        return
    
    table = Table(title=title, show_header=True, header_style="bold magenta")
    
    # 添加列
    for key in data[0].keys():
        table.add_column(key, style="cyan")
    
    # 添加行
    for row in data:
        table.add_row(*[str(v) for v in row.values()])
    
    console.print(table)


def format_welcome() -> None:
    """
    打印欢迎信息
    """
    welcome_text = """
    # 🤖 MCP Agent
    
    欢迎使用MCP智能体！
    
    **可用命令：**
    - 直接输入消息与助手对话
    - `/help` - 显示帮助信息
    - `/clear` - 清除对话历史
    - `/save` - 保存当前会话
    - `/load` - 加载会话
    - `/exit` 或 `/quit` - 退出程序
    
    开始对话吧！
    """
    console.print(Markdown(welcome_text))


def format_token_usage(
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
) -> None:
    """
    格式化并打印Token使用统计
    
    Args:
        input_tokens: 输入Token数
        output_tokens: 输出Token数
        total_tokens: 总Token数
    """
    usage_text = (
        f"📊 Token使用: "
        f"输入={input_tokens} | "
        f"输出={output_tokens} | "
        f"总计={total_tokens}"
    )
    console.print(f"[dim]{usage_text}[/dim]")


def print_info(message: str) -> None:
    """
    打印信息消息
    
    Args:
        message: 消息内容
    """
    console.print(f"[blue]ℹ️  {message}[/blue]")


def print_success(message: str) -> None:
    """
    打印成功消息
    
    Args:
        message: 消息内容
    """
    console.print(f"[green]✅ {message}[/green]")


def print_warning(message: str) -> None:
    """
    打印警告消息
    
    Args:
        message: 消息内容
    """
    console.print(f"[yellow]⚠️  {message}[/yellow]")


def print_error(message: str) -> None:
    """
    打印错误消息
    
    Args:
        message: 消息内容
    """
    console.print(f"[red]❌ {message}[/red]")