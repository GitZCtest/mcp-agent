"""
Rich 命令行界面辅助模块。

本模块封装了命令行的所有视觉呈现，包括欢迎提示、用户/助手消息、
工具调用及错误信息。通过集中管理样式，CLI 层可以专注业务流程。

示例::

    >>> ui = ConsoleUI()
    >>> ui.display_welcome()
    >>> ui.display_user_message("你好")
    >>> with ui.display_thinking():
    ...     pass  # 执行耗时操作
    >>> ui.display_assistant_message("**欢迎使用 MCP Agent!**")
    >>> ui.display_tool_call("search_docs", {"query": "rich"}, "docs")
    >>> ui.display_tool_result("找到 10 条结果", success=True)
    >>> ui.display_error("示例错误")
    >>> ui.display_success("操作成功")
    >>> ui.display_warning("注意事项")
    >>> ui.display_system_message("系统通知")
    >>> ui.display_json({"key": "value"})
    >>> ui.display_step(1, 5, "初始化配置")
"""

from __future__ import annotations

import json
from typing import Any, ContextManager, Dict, Iterable, Optional, Tuple

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.json import JSON
from rich.markdown import Markdown
from rich.panel import Panel
from rich.pretty import Pretty
from rich.status import Status
from rich.table import Table
from rich.text import Text

__all__ = ["ConsoleUI"]


class ConsoleUI:
    """封装 Rich 组件的命令行 UI 工具。"""

    def __init__(self, prompt: str = "MCP Agent> ") -> None:
        """
        创建 UI 辅助对象。

        Args:
            prompt: 用户输入提示符，默认 "MCP Agent> "
        """
        # 在 Windows 上强制使用 UTF-8 编码
        import sys
        import io
        if sys.platform == 'win32':
            # 尝试设置控制台编码为 UTF-8
            try:
                import os
                os.system('chcp 65001 >nul 2>&1')
            except:
                pass

            # 重新配置 stdout 和 stderr 使用 UTF-8
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            if hasattr(sys.stderr, 'buffer'):
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

        # 创建 Console，强制使用 UTF-8
        self.console = Console(force_terminal=True, legacy_windows=False)
        self.prompt_text = prompt
        self.max_result_preview = 800
        self._commands: Iterable[Tuple[str, str]] = (
            ("/help", "显示帮助信息"),
            ("/tools", "列出可用工具"),
            ("/servers", "显示MCP服务器状态"),
            ("/reconnect <name>", "重新连接服务器"),
            ("/clear", "清除对话历史"),
            ("/history", "查看对话历史"),
            ("/save <filename>", "保存对话到文件"),
            ("/load <filename>", "加载对话历史"),
            ("/stats", "显示统计信息"),
            ("/system <prompt>", "设置系统提示词"),
            ("/exit, /quit", "退出程序"),
        )

    def set_prompt(self, prompt: str) -> None:
        """更新交互提示符。"""
        self.prompt_text = prompt

    def display_welcome(self) -> None:
        """以面板样式展示欢迎信息和命令说明。"""
        title = Text("MCP Agent", style="bold cyan")
        subtitle = Text("智能命令行助手", style="bold magenta")
        description = Text(
            "连接多种 LLM 与 MCP 服务，提供流畅的终端体验。",
            style="white",
        )

        # 构建命令说明表，方便新用户快速上手。
        commands_table = Table(
            "命令",
            "说明",
            box=box.SIMPLE_HEAVY,
            show_edge=False,
            header_style="bold bright_white",
            row_styles=["white", "bright_black"],
            padding=(0, 1),
        )
        for command, desc in self._commands:
            commands_table.add_row(command, desc)

        # 使用 Panel 包裹核心标题和介绍。
        panel = Panel(
            Group(
                Align.center(title),
                Align.center(subtitle),
                Align.center(Text("─" * 32, style="bright_black")),
                Align.center(description),
            ),
            title="欢迎",
            subtitle="输入 /help 查看命令",
            border_style="bright_blue",
            padding=(1, 2),
        )

        self.console.print(panel)
        self.console.print(Align.center(commands_table))
        self.console.print()

    def display_user_message(self, message: str) -> None:
        """使用蓝色前缀展示用户输入。"""
        text = Text("You: ", style="bold blue")
        text.append(message or "", style="white")
        self.console.print(text)

    def display_assistant_message(self, message: str) -> None:
        """
        以绿色面板展示助手回复，支持 Markdown 与代码高亮。

        Args:
            message: 助手的回复内容
        """
        # Markdown 渲染可自动处理标题、列表以及代码块。
        renderable = Markdown(message or "", code_theme="monokai", justify="left")
        panel = Panel(
            renderable,
            title="[bold green]Assistant[/]",
            border_style="green",
            padding=(1, 2),
        )
        self.console.print(panel)

    def display_tool_call(self, tool_name: str, args: dict, server: Optional[str]) -> None:
        """
        展示来自 LLM 的工具调用请求。

        Args:
            tool_name: 工具名称
            args: 调用参数
            server: 工具所属服务器
        """
        # Pretty 在终端中友好地打印嵌套参数。
        body = Group(
            Text(f"工具: {tool_name}", style="bold cyan"),
            Text(f"服务器: {server or '未知'}", style="cyan"),
            Text("参数:", style="cyan"),
            Pretty(args or {}, expand_all=True),
        )
        panel = Panel(
            body,
            title="工具调用",
            border_style="bright_cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        self.console.print(panel)

    def display_tool_result(self, result: str, success: bool) -> None:
        """
        展示工具执行结果，必要时进行截断。

        Args:
            result: 工具返回内容
            success: 是否执行成功
        """
        color = "green" if success else "red"
        # 截断冗长输出，避免刷屏。
        content = self._truncate_text(result or "")
        panel = Panel(
            content,
            title="工具执行结果",
            border_style=color,
            padding=(1, 2),
        )
        self.console.print(panel)

    def display_thinking(self) -> ContextManager[Status]:
        """返回一个带有 Spinner 的上下文管理器，用于等待耗时操作。"""
        return self.console.status(
            "[bold yellow]思考中...[/]",
            spinner="dots",  # 使用轻量级动画提示等待
            spinner_style="yellow",
        )

    def display_error(self, error: str) -> None:
        """
        醒目地展示错误信息。

        Args:
            error: 错误信息内容
        """
        panel = Panel(
            Text(error, style="bold white"),
            title="[ERROR] 错误",
            border_style="bright_red",
            padding=(1, 2),
        )
        self.console.print(panel)

    def display_success(self, message: str) -> None:
        """
        展示成功消息。

        Args:
            message: 成功消息内容
        """
        panel = Panel(
            Text(message, style="bold white"),
            title="[OK] 成功",
            border_style="bright_green",
            padding=(1, 2),
        )
        self.console.print(panel)

    def display_warning(self, warning: str) -> None:
        """
        展示警告信息。

        Args:
            warning: 警告信息内容
        """
        panel = Panel(
            Text(warning, style="bold black"),
            title="[WARN] 警告",
            border_style="bright_yellow",
            padding=(1, 2),
        )
        self.console.print(panel)

    def display_system_message(self, message: str, title: str = "系统消息") -> None:
        """
        展示系统消息。

        Args:
            message: 系统消息内容
            title: 面板标题，默认为"系统消息"
        """
        panel = Panel(
            Text(message, style="cyan"),
            title=f"[INFO] {title}",
            border_style="bright_cyan",
            padding=(1, 2),
        )
        self.console.print(panel)

    def display_json(self, data: Any, title: str = "JSON 数据") -> None:
        """
        以格式化方式展示 JSON 数据，支持语法高亮。

        Args:
            data: 要展示的数据（dict、list 或任何可 JSON 序列化的对象）
            title: 面板标题，默认为"JSON 数据"
        """
        try:
            # 如果是字符串，先尝试解析为 JSON
            if isinstance(data, str):
                data = json.loads(data)

            # 使用 Rich 的 JSON 组件进行渲染
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            renderable = JSON(json_str, indent=2, highlight=True)

            panel = Panel(
                renderable,
                title=f"[JSON] {title}",
                border_style="bright_magenta",
                padding=(1, 2),
            )
            self.console.print(panel)
        except (json.JSONDecodeError, TypeError) as e:
            # 如果无法序列化，使用 Pretty 打印
            panel = Panel(
                Pretty(data, expand_all=True),
                title=f"[DATA] {title}",
                border_style="bright_magenta",
                padding=(1, 2),
            )
            self.console.print(panel)

    def display_step(
        self,
        current: int,
        total: int,
        description: str,
        status: str = "进行中"
    ) -> None:
        """
        展示步骤进度信息。

        Args:
            current: 当前步骤编号（从1开始）
            total: 总步骤数
            description: 步骤描述
            status: 步骤状态，默认为"进行中"
        """
        # 计算进度百分比
        percentage = (current / total * 100) if total > 0 else 0

        # 创建进度条
        bar_length = 20
        filled_length = int(bar_length * current // total) if total > 0 else 0
        bar = "=" * filled_length + "-" * (bar_length - filled_length)

        # 状态颜色映射
        status_colors = {
            "进行中": "yellow",
            "完成": "green",
            "失败": "red",
            "等待": "blue",
        }
        status_color = status_colors.get(status, "white")

        # 构建显示内容
        content = Group(
            Text(f"步骤 {current}/{total}", style="bold bright_white"),
            Text(f"进度: [{bar}] {percentage:.0f}%", style="bright_cyan"),
            Text(f"描述: {description}", style="white"),
            Text(f"状态: {status}", style=f"bold {status_color}"),
        )

        panel = Panel(
            content,
            title="[STEP] 执行步骤",
            border_style="bright_blue",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        self.console.print(panel)

    def display_title(self, title: str, subtitle: Optional[str] = None) -> None:
        """
        展示大标题和副标题。

        Args:
            title: 主标题文本
            subtitle: 副标题文本（可选）
        """
        title_text = Text(title, style="bold bright_cyan")

        if subtitle:
            content = Group(
                Align.center(title_text),
                Align.center(Text("─" * 40, style="bright_black")),
                Align.center(Text(subtitle, style="bright_white")),
            )
        else:
            content = Align.center(title_text)

        panel = Panel(
            content,
            border_style="bright_cyan",
            padding=(1, 2),
        )
        self.console.print(panel)
        self.console.print()

    def display_divider(self, text: Optional[str] = None) -> None:
        """
        展示分隔线，可选带文字。

        Args:
            text: 分隔线中间的文字（可选）
        """
        if text:
            divider = Text(f"── {text} ", style="bright_black")
            divider.append("─" * (self.console.width - len(text) - 4), style="bright_black")
        else:
            divider = Text("─" * self.console.width, style="bright_black")

        self.console.print(divider)

    def get_user_input(self) -> str:
        """
        获取用户输入。

        支持在行尾添加反斜杠 `\\` 进行多行输入。
        """
        lines = []
        continuation_prompt = "... "

        while True:
            prompt = self.prompt_text if not lines else continuation_prompt
            line = self.console.input(f"[bold blue]{prompt}[/]")

            if not lines and not line.strip():
                return ""

            # 末尾的反斜杠表示“继续输入下一行”。
            if line.endswith("\\"):
                lines.append(line[:-1])
                continue

            lines.append(line)
            break

        return "\n".join(lines)

    def _truncate_text(self, text: str) -> str:
        """截断冗长文本并添加提示。"""
        if len(text) <= self.max_result_preview:
            return text
        return f"{text[:self.max_result_preview]}...（已截断）"


if __name__ == "__main__":
    # 提供一个全面的演示，方便开发调试 UI。
    ui = ConsoleUI()

    # 1. 欢迎页面
    ui.display_welcome()

    # 2. 标题展示
    ui.display_title("增强的 UI 功能演示", "ConsoleUI 完整功能展示")

    # 3. 用户消息
    ui.display_user_message("你好，Agent！")

    # 4. 思考状态
    with ui.display_thinking():
        import time
        time.sleep(0.5)

    # 5. 助手消息
    ui.display_assistant_message(
        "**欢迎使用 MCP Agent！**\n\n这是一个增强的 UI 系统。\n\n```python\nprint('代码高亮演示')\n```"
    )

    # 6. 系统消息
    ui.display_system_message("系统已初始化完成")

    # 7. 分隔线
    ui.display_divider("工具调用演示")

    # 8. 工具调用
    ui.display_tool_call(
        "search_docs",
        {"query": "rich", "limit": 10},
        "docs"
    )

    # 9. 工具结果
    ui.display_tool_result("找到 3 条结果", success=True)

    # 10. 成功消息
    ui.display_success("工具执行成功！")

    # 11. 警告消息
    ui.display_warning("这是一条警告消息，请注意检查配置")

    # 12. JSON 展示
    ui.display_divider("JSON 数据展示")
    ui.display_json({
        "status": "success",
        "data": {
            "name": "MCP Agent",
            "version": "1.0.0",
            "features": ["streaming", "tool_calling", "multi_provider"]
        },
        "count": 42
    }, title="配置信息")

    # 13. 步骤展示
    ui.display_divider("步骤进度演示")
    ui.display_step(1, 5, "初始化配置", "完成")
    ui.display_step(3, 5, "连接 MCP 服务器", "进行中")
    ui.display_step(5, 5, "启动 Agent", "等待")

    # 14. 错误消息
    ui.display_error("演示错误消息")

    ui.console.print("\n[bold green]>>> UI 功能演示完成！[/]\n")

