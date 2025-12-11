"""
命令行接口模块

提供交互式命令行界面，支持多MCP服务器管理。
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import List, Optional, Dict, Any

import aiohttp
import click
from rich import box
from rich.table import Table
from rich.prompt import Prompt, Confirm

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
except ImportError:  # pragma: no cover - optional dependency
    PromptSession = None
    Completer = object  # type: ignore
    Completion = None  # type: ignore
    CommandCompleter = None  # type: ignore
else:
    class CommandCompleter(Completer):
        """Prompt Toolkit 补全器，仅在命令模式下触发。"""

        def __init__(self, commands: List[str]) -> None:
            self.commands = sorted(set(commands))

        def get_completions(self, document, complete_event):
            line = document.current_line_before_cursor
            stripped = line.lstrip()
            if not stripped.startswith("/"):
                return
            if " " in stripped:
                return  # 只匹配命令本身
            for cmd in self.commands:
                if cmd.startswith(stripped):
                    yield Completion(cmd, start_position=-len(stripped))

from mcp_agent.agent import MCPAgent
from mcp_agent.config import Config
from mcp_agent.installer import (
    DependencyChecker,
    MCPInstaller,
    PackageDiscovery,
    VersionManager,
)
from mcp_agent.server_registry import (
    get_registry,
    InteractiveConfigWizard,
    ServerRegistry,
)
from mcp_agent.ui import ConsoleUI
from mcp_agent.utils.logger import setup_logger


class CLI:
    """命令行接口类"""

    def __init__(self, config: Config, ui: Optional[ConsoleUI] = None):
        """
        初始化CLI

        Args:
            config: 配置对象
            ui: 可选的UI对象
        """
        self.config = config
        self.agent: Optional[MCPAgent] = None
        self.running = False
        self.ui = ui or ConsoleUI()
        self.prompt_text = self.config.get("cli.prompt", "MCP Agent> ")
        self.ui.set_prompt(self.prompt_text)
        self.command_keywords: List[str] = [
            "/help",
            "/clear",
            "/history",
            "/tools",
            "/stats",
            "/system",
            "/save",
            "/load",
            "/servers",
            "/reconnect",
            "/sessions",      # 新增
            "/search",        # 新增
            "/export",        # 新增
            "/session-stats", # 新增
            "/model",         # 切换模型
            "/config",        # 查看/修改配置
            "/models",        # 列出可用模型
            "/add-server",    # 添加MCP服务器
            "/list-available",# 列出可用服务器模板
            "/test-server",   # 测试服务器连接
            "/remove-server", # 移除服务器
            "/check-deps",    # 检查系统依赖
            "/discover",      # 发现可用包
            "/install",       # 安装包
            "/update",        # 更新包
            "/exit",
            "/quit",
        ]
        
        # 初始化服务器注册表
        self._server_registry = get_registry()
        
        # 初始化安装器组件
        self._dependency_checker = DependencyChecker(self.ui.console)
        self._package_discovery = PackageDiscovery(self.ui.console)
        self._installer = MCPInstaller(self.ui.console)
        self._version_manager = VersionManager(self.ui.console)

        # 设置日志
        log_config = config.logging
        self.logger = setup_logger(
            level=log_config.get("level", "INFO"),
            log_file=log_config.get("file"),
            console=log_config.get("console", True),
            max_size=log_config.get("max_size", 10),
            backup_count=log_config.get("backup_count", 5),
        )
        self._session: Optional[PromptSession] = self._create_prompt_session()

    def _create_prompt_session(self) -> Optional[PromptSession]:
        """创建带命令补全功能的 PromptSession。"""
        if not PromptSession or not CommandCompleter:
            return None
        try:
            completer = CommandCompleter(self.command_keywords)
            return PromptSession(
                completer=completer,
                complete_while_typing=True,
                reserve_space_for_menu=4,
            )
        except Exception as exc:  # pragma: no cover - 容错
            self.logger.debug(f"命令补全初始化失败: {exc}")
            return None

    async def start(self) -> None:
        """启动CLI"""
        try:
            self._show_welcome()
            self.ui.console.print("\n[bold cyan]正在初始化...[/]")
            self.agent = MCPAgent(self.config, ui=self.ui)
            await self.agent.initialize()
            self.ui.console.print("[bold green]初始化完成[/]\n")

            # 显示统计信息
            self._show_init_stats()

            self.running = True
            await self._interaction_loop()
        except KeyboardInterrupt:
            self.ui.console.print("\n[bold yellow]用户中断[/]")
        except Exception as e:
            self.ui.display_error(f"启动失败: {e}")
            self.logger.exception("CLI启动失败")
        finally:
            await self.cleanup()

    def _show_init_stats(self) -> None:
        """显示初始化统计信息"""
        stats = self.agent.get_stats()
        stats_table = Table(box=box.SIMPLE_HEAVY, show_header=False)
        stats_table.add_row("提供商", stats["provider"])
        stats_table.add_row("模型", stats["model"])
        stats_table.add_row("对话历史", f"{stats['history_length']}/{stats['max_history']}")
        stats_table.add_row("最大迭代", str(stats.get("max_iterations", 10)))
        stats_table.add_row("MCP 启用", "是" if stats["mcp_enabled"] else "否")

        if stats["mcp_servers"]:
            connected = stats.get("mcp_connected_count", 0)
            total = len(stats["mcp_servers"])
            stats_table.add_row("MCP 服务器", f"{connected}/{total} 已连接")
            stats_table.add_row("总工具数", str(stats.get("mcp_total_tools", 0)))

        self.ui.console.print(stats_table)
        self.ui.console.print()

    def _show_welcome(self) -> None:
        """显示欢迎信息"""
        self.ui.display_welcome()

    def _prompt_input(self) -> str:
        """根据环境选择带补全或普通输入。"""
        if self._session:
            return self._session.prompt(self.prompt_text)
        return self.ui.get_user_input()

    async def _interaction_loop(self) -> None:
        """交互循环"""
        while self.running:
            try:
                # 获取用户输入
                user_input = await asyncio.to_thread(self._prompt_input)

                if not user_input or not user_input.strip():
                    continue

                # 处理命令
                if user_input.startswith("/"):
                    await self._handle_command(user_input)
                else:
                    self.ui.display_user_message(user_input)
                    await self._handle_message(user_input)

            except KeyboardInterrupt:
                self.ui.display_error("使用 /exit 或 /quit 退出")
            except EOFError:
                break
            except Exception as e:
                self.ui.display_error(f"错误: {e}")
                self.logger.exception("处理用户输入失败")

    async def _handle_message(self, message: str) -> None:
        """处理用户消息"""
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return
        try:
            with self.ui.display_thinking():
                response = await self.agent.chat(message, stream=False)
            self.ui.display_assistant_message(response)
        except Exception as e:
            self.ui.display_error(f"对话失败: {e}")
            self.logger.exception("处理消息失败")

    async def _handle_command(self, command: str) -> None:
        """
        处理命令

        Args:
            command: 命令字符串
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ["/exit", "/quit"]:
            self.ui.console.print("[yellow]正在退出...[/]")
            self.running = False

        elif cmd == "/help":
            self._show_help()

        elif cmd == "/clear":
            if self.agent:
                self.agent.clear_history()
            self.ui.console.print("[green]对话历史已清除[/]")

        elif cmd == "/history":
            self._show_history()

        elif cmd == "/stats":
            self._show_stats()

        elif cmd == "/tools":
            await self._show_tools()

        elif cmd == "/system":
            if args:
                if self.agent:
                    self.agent.set_system_prompt(args)
                self.ui.console.print("[green]系统提示词已更新[/]")
            else:
                self.ui.display_error("请提供系统提示词")

        elif cmd == "/save":
            await self._save_history(args)

        elif cmd == "/load":
            await self._load_history(args)

        elif cmd == "/servers":
            self._show_servers()

        elif cmd == "/reconnect":
            await self._reconnect_server(args)
        
        elif cmd == "/sessions":
            self._show_sessions()

        elif cmd == "/search":
            self._search_sessions(args)

        elif cmd == "/export":
            self._export_session(args)

        elif cmd == "/session-stats":
            self._show_session_stats()

        elif cmd == "/model":
            await self._switch_model(args)

        elif cmd == "/config":
            await self._handle_config(args)

        elif cmd == "/models":
            self._show_available_models()

        elif cmd == "/add-server":
            await self._add_server(args)

        elif cmd == "/list-available":
            self._list_available_servers(args)

        elif cmd == "/test-server":
            await self._test_server(args)

        elif cmd == "/remove-server":
            self._remove_server(args)
        
        elif cmd == "/check-deps":
            self._check_dependencies()
        
        elif cmd == "/discover":
            await self._discover_packages(args)
        
        elif cmd == "/install":
            await self._install_package(args)
        
        elif cmd == "/update":
            await self._update_packages(args)

        else:
            self.ui.display_error(f"未知命令: {cmd}")
            self.ui.console.print("输入 /help 查看可用命令")

    def _show_help(self) -> None:
        """显示帮助信息"""
        table = Table("命令", "说明", box=box.SIMPLE_HEAVY)
        table.add_row("/help", "显示此帮助信息")
        table.add_row("", "")
        table.add_row("[bold cyan]基础操作[/]", "")
        table.add_row("/clear", "清除对话历史")
        table.add_row("/history", "查看对话历史")
        table.add_row("/save <filename>", "保存对话到文件")
        table.add_row("/load <filename>", "加载对话历史")
        table.add_row("/stats", "显示统计信息")
        table.add_row("", "")
        table.add_row("[bold cyan]模型配置[/]", "")
        table.add_row("/model <name>", "切换模型")
        table.add_row("/models", "列出可用模型")
        table.add_row("/config", "查看当前配置")
        table.add_row("/config <key> <value>", "修改配置参数")
        table.add_row("/system <prompt>", "设置系统提示词")
        table.add_row("", "")
        table.add_row("[bold cyan]工具与服务器[/]", "")
        table.add_row("/tools", "列出可用工具")
        table.add_row("/servers", "显示MCP服务器状态")
        table.add_row("/reconnect <name>", "重新连接指定服务器")
        table.add_row("/add-server [name]", "添加MCP服务器")
        table.add_row("/list-available [query]", "列出可用服务器模板")
        table.add_row("/test-server <name>", "测试服务器连接")
        table.add_row("/remove-server <name>", "移除服务器")
        table.add_row("", "")
        table.add_row("[bold cyan]包管理[/]", "")
        table.add_row("/check-deps", "检查系统依赖")
        table.add_row("/discover [npm|github]", "发现可用MCP包")
        table.add_row("/install <package>", "安装MCP包")
        table.add_row("/update [package]", "更新包到最新版本")
        table.add_row("", "")
        table.add_row("[bold cyan]会话管理[/]", "")
        table.add_row("/sessions", "列出所有保存的会话")
        table.add_row("/search <keyword>", "搜索会话内容")
        table.add_row("/export [id] [format]", "导出会话 (markdown/html)")
        table.add_row("/session-stats", "显示当前会话统计")
        table.add_row("", "")
        table.add_row("/exit, /quit", "退出程序")
        self.ui.console.print("\n[bold cyan]可用命令:[/]")
        self.ui.console.print(table)
        self.ui.console.print()

    def _show_history(self) -> None:
        """显示对话历史"""
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return
        history = self.agent.get_history()
        if not history:
            self.ui.console.print("[yellow]暂无对话历史[/]")
            return

        table = Table("序号", "角色", "内容", box=box.SIMPLE_HEAVY)
        for i, msg in enumerate(history, 1):
            role = msg["role"]
            content = msg.get("content", "")
            if content:
                preview = content[:80] + "..." if len(content) > 80 else content
            else:
                preview = "[工具调用]" if "tool_calls" in msg else ""
            table.add_row(str(i), role, preview)
        self.ui.console.print(table)
        self.ui.console.print()

    def _show_sessions(self) -> None:
          """显示所有会话列表"""
          if not self.agent:
              self.ui.display_error("智能体尚未初始化")
              return

          sessions = self.agent.list_sessions(limit=20)

          if not sessions:
              self.ui.console.print("[yellow]暂无保存的会话[/]")
              return

          table = Table(
              "会话ID", "创建时间", "消息数", "模型", "预览",
              box=box.SIMPLE_HEAVY,
              show_lines=True
          )

          for session in sessions:
              # 格式化时间
              created = session.get('created_at', '')
              if created:
                  try:
                      dt = datetime.fromisoformat(created)
                      created = dt.strftime("%m-%d %H:%M")
                  except:
                      created = created[:16]

              table.add_row(
                  session.get('session_id', '')[-15:],  # 只显示后15个字符
                  created,
                  str(session.get('message_count', 0)),
                  session.get('model', '')[:20],
                  session.get('preview', '')[:30],
              )

          self.ui.console.print("\n[bold cyan]保存的会话:[/]")
          self.ui.console.print(table)
          self.ui.console.print(f"\n[dim]共 {len(sessions)} 个会话。使用 /export<session_id> 导出会话[/]")
          self.ui.console.print()

    def _search_sessions(self, keyword: str) -> None:
          """搜索会话内容"""
          if not self.agent:
              self.ui.display_error("智能体尚未初始化")
              return

          keyword = keyword.strip()
          if not keyword:
              self.ui.display_error("请提供搜索关键词，例如: /search python")
              return

          self.ui.console.print(f"[cyan]正在搜索: {keyword}...[/]")

          results = self.agent.search_sessions(keyword, limit=10)

          if not results:
              self.ui.console.print(f"[yellow]未找到包含 '{keyword}' 的会话[/]")
              return

          table = Table(
              "会话ID", "创建时间", "匹配数", "匹配内容",
              box=box.SIMPLE_HEAVY,
              show_lines=True
          )

          for result in results:
              created = result.get('created_at', '')
              if created:
                  try:
                      dt = datetime.fromisoformat(created)
                      created = dt.strftime("%m-%d %H:%M")
                  except:
                      created = created[:16]

              # 显示第一个匹配
              matches = result.get('matches', [])
              preview = ""
              if matches:
                  first_match = matches[0]
                  role_icon = "👤" if first_match.get('role') == 'user' else "🤖"
                  preview = f"{role_icon} {first_match.get('context', '')[:40]}"

              table.add_row(
                  result.get('session_id', '')[-15:],
                  created,
                  str(result.get('match_count', 0)),
                  preview,
              )

          self.ui.console.print(f"\n[bold cyan]搜索结果 ({len(results)} 个会话):[/]")
          self.ui.console.print(table)
          self.ui.console.print()

    def _export_session(self, args: str) -> None:
          """导出会话"""
          if not self.agent:
              self.ui.display_error("智能体尚未初始化")
              return

          parts = args.strip().split()
          if not parts:
              # 导出当前会话
              session_id = self.agent.get_current_session_id()
              if not session_id:
                  self.ui.display_error("没有活动会话。请指定会话ID，例如: /export session_20241201_120000")
                  return
              format_type = "markdown"
          else:
              session_id = parts[0]
              format_type = parts[1] if len(parts) > 1 else "markdown"

          # 验证格式
          if format_type.lower() not in ["markdown", "md", "html"]:
              self.ui.display_error(f"不支持的格式: {format_type}。支持: markdown, html")
              return

          if format_type.lower() in ["markdown", "md"]:
              format_type = "markdown"

          try:
              filepath = self.agent.export_session(session_id, format=format_type)
              self.ui.display_success(f"会话已导出: {filepath}")
          except FileNotFoundError:
              self.ui.display_error(f"会话不存在: {session_id}")
              self.ui.console.print("[dim]使用 /sessions 查看可用会话[/]")
          except Exception as e:
              self.ui.display_error(f"导出失败: {e}")
              self.logger.exception("导出会话失败")

    def _show_session_stats(self) -> None:
          """显示当前会话统计"""
          if not self.agent:
              self.ui.display_error("智能体尚未初始化")
              return

          stats = self.agent.get_session_stats()

          if not stats:
              self.ui.console.print("[yellow]暂无会话统计信息[/]")
              return

          table = Table("统计项", "值", box=box.SIMPLE_HEAVY)

          table.add_row("对话轮数", str(stats.get('total_turns', 0)))
          table.add_row("用户消息", str(stats.get('user_messages', 0)))
          table.add_row("助手消息", str(stats.get('assistant_messages', 0)))
          table.add_row("工具调用", f"{stats.get('tool_calls', 0)} 次")
          table.add_row("输入Token", str(stats.get('input_tokens', 0)))
          table.add_row("输出Token", str(stats.get('output_tokens', 0)))
          table.add_row("总Token", str(stats.get('total_tokens', 0)))

          # 格式化持续时间
          duration = stats.get('duration_seconds', 0)
          if duration > 3600:
              duration_str = f"{duration/3600:.1f} 小时"
          elif duration > 60:
              duration_str = f"{duration/60:.1f} 分钟"
          else:
              duration_str = f"{duration:.0f} 秒"
          table.add_row("会话时长", duration_str)

          # 显示开始时间
          start_time = stats.get('start_time', '')
          if start_time:
              try:
                  dt = datetime.fromisoformat(start_time)
                  start_time = dt.strftime("%Y-%m-%d %H:%M:%S")
              except:
                  pass
          table.add_row("开始时间", start_time or "-")

          self.ui.console.print("\n[bold cyan]当前会话统计:[/]")
          self.ui.console.print(table)
          self.ui.console.print()
    
    def _show_stats(self) -> None:
        """显示统计信息"""
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return
        stats = self.agent.get_stats()
        table = Table("项目", "值", box=box.SIMPLE_HEAVY)
        table.add_row("提供商", stats["provider"])
        table.add_row("模型", stats["model"])
        table.add_row("对话历史", f"{stats['history_length']}/{stats['max_history']}")
        table.add_row("最大迭代", str(stats.get("max_iterations", 10)))
        table.add_row("MCP 启用", "是" if stats["mcp_enabled"] else "否")

        if stats["mcp_servers"]:
            connected = stats.get("mcp_connected_count", 0)
            total = len(stats["mcp_servers"])
            table.add_row("MCP 服务器", f"{connected}/{total} 已连接")
            table.add_row("总工具数", str(stats.get("mcp_total_tools", 0)))

            for server in stats["mcp_servers"]:
                status = "[green]已连接[/]" if server["connected"] else "[red]未连接[/]"
                error = f" ({server.get('error', '')})" if server.get("error") else ""
                table.add_row(
                    f"  → {server['name']}",
                    f"{status} | {server['tools']} 工具{error}",
                )
        self.ui.console.print(table)
        self.ui.console.print()

    def _show_servers(self) -> None:
        """显示MCP服务器状态"""
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return

        servers = self.agent.get_server_info()
        if not servers:
            self.ui.console.print("[yellow]没有配置MCP服务器[/]")
            return

        table = Table("服务器", "状态", "工具", "资源", "描述", box=box.SIMPLE_HEAVY)

        for server in servers:
            name = server["name"]
            status = server.get("status", "unknown")

            # 状态颜色
            if status == "connected":
                status_display = "[green]已连接[/]"
            elif status == "connecting":
                status_display = "[yellow]连接中[/]"
            elif status == "error":
                error_msg = server.get("error", "")
                status_display = f"[red]错误[/]"
                if error_msg:
                    status_display += f"\n[dim]{error_msg[:30]}...[/dim]" if len(error_msg) > 30 else f"\n[dim]{error_msg}[/dim]"
            else:
                status_display = "[gray]未连接[/]"

            tools = str(server.get("tools", 0))
            resources = str(server.get("resources", 0))
            description = server.get("description", "-") or "-"

            table.add_row(name, status_display, tools, resources, description)

        self.ui.console.print("\n[bold cyan]MCP 服务器状态:[/]")
        self.ui.console.print(table)
        self.ui.console.print()

    async def _reconnect_server(self, server_name: str) -> None:
        """
        重新连接指定服务器

        Args:
            server_name: 服务器名称
        """
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return

        server_name = server_name.strip()
        if not server_name:
            self.ui.display_error("请指定服务器名称，例如: /reconnect filesystem")
            self.ui.console.print("\n可用服务器:")
            for server in self.agent.get_server_info():
                self.ui.console.print(f"  • {server['name']}")
            return

        # 检查服务器是否存在
        server_status = self.agent.get_server_status(server_name)
        if not server_status:
            self.ui.display_error(f"服务器不存在: {server_name}")
            self.ui.console.print("\n可用服务器:")
            for server in self.agent.get_server_info():
                self.ui.console.print(f"  • {server['name']}")
            return

        self.ui.console.print(f"[yellow]正在重新连接服务器: {server_name}...[/]")

        try:
            success = await self.agent.reconnect_server(server_name)
            if success:
                server_status = self.agent.get_server_status(server_name)
                tools = server_status.get("tools", 0) if server_status else 0
                self.ui.display_success(f"服务器 {server_name} 已重新连接 ({tools} 个工具)")
            else:
                self.ui.display_error(f"重新连接服务器 {server_name} 失败")
        except Exception as e:
            self.ui.display_error(f"重新连接失败: {e}")
            self.logger.exception(f"重新连接服务器 {server_name} 失败")

    async def _show_tools(self) -> None:
        """列出可用工具"""
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return
        try:
            tools = await self.agent.list_tools()
            if not tools:
                self.ui.console.print("[yellow]暂无可用工具[/]")
                return
            table = Table("工具名称", "所属服务器", "描述", box=box.SIMPLE_HEAVY)
            for tool in tools:
                name = tool.get("name", "unknown")
                desc = tool.get("description", "").strip()
                # 截断过长描述
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                desc = desc or "-"
                server = tool.get("server", "unknown")
                table.add_row(name, server, desc)
            self.ui.console.print(f"\n[bold cyan]可用工具 ({len(tools)}):[/]")
            self.ui.console.print(table)
            self.ui.console.print()
        except Exception as e:
            self.ui.display_error(f"列出工具失败: {e}")

    async def _save_history(self, filename: str) -> None:
        """保存对话历史到文件"""
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return

        if not filename.strip():
            self.ui.display_error("请提供文件名，例如: /save chat_history")
            return

        try:
            filepath = self.agent.save_history(filename.strip())
            self.ui.display_success(f"对话历史已保存到: {filepath}")
        except Exception as e:
            self.ui.display_error(f"保存失败: {e}")
            self.logger.exception("保存对话历史失败")

    async def _load_history(self, filename: str) -> None:
        """从文件加载对话历史"""
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return

        if not filename.strip():
            self.ui.display_error("请提供文件名，例如: /load chat_history")
            return

        try:
            info = self.agent.load_history(filename.strip())
            table = Table("项目", "值", box=box.SIMPLE_HEAVY)
            table.add_row("保存时间", info["saved_at"])
            table.add_row("原提供商", info["provider"])
            table.add_row("原模型", info["model"])
            table.add_row("消息数量", str(info["message_count"]))
            self.ui.display_success("对话历史加载成功!")
            self.ui.console.print(table)
            self.ui.console.print()
        except FileNotFoundError as e:
            self.ui.display_error(str(e))
        except Exception as e:
            self.ui.display_error(f"加载失败: {e}")
            self.logger.exception("加载对话历史失败")

    async def _switch_model(self, model_name: str) -> None:
        """
        切换模型

        Args:
            model_name: 模型名称
        """
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return

        model_name = model_name.strip()
        if not model_name:
            self.ui.display_error("请指定模型名称，例如: /model gpt-4o")
            self.ui.console.print("\n使用 /models 查看可用模型")
            return

        try:
            # 更新模型配置
            self.agent.update_model_config(model=model_name)
            # 保存到配置文件
            self.config.set("agent.model", model_name)
            self.config.save()
            
            self.ui.display_success(f"模型已切换为: {model_name} (并已保存)")

            # 显示更新后的配置
            config = self.agent.get_model_config()
            table = Table("配置项", "值", box=box.SIMPLE_HEAVY)
            table.add_row("提供商", config["provider"])
            table.add_row("模型", config["model"])
            table.add_row("温度", str(config["temperature"]))
            table.add_row("最大Token", str(config["max_tokens"]))
            self.ui.console.print(table)
            self.ui.console.print()

        except Exception as e:
            self.ui.display_error(f"切换模型失败: {e}")
            self.logger.exception("切换模型失败")

    def _handle_config(self, args: str) -> None:
        """
        处理配置命令

        Args:
            args: 命令参数
        """
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return

        args = args.strip()

        # 如果没有参数，显示当前配置
        if not args:
            self._show_current_config()
            return

        # 解析参数：/config <key> <value>
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            self.ui.display_error("用法: /config <key> <value>")
            self.ui.console.print("\n支持的配置项:")
            self.ui.console.print("  • temperature <0-2>    - 温度参数")
            self.ui.console.print("  • max_tokens <number>  - 最大token数")
            self.ui.console.print("  • max_iterations <number> - 最大迭代次数")
            return

        key = parts[0].lower()
        value_str = parts[1]

        try:
            # 根据key转换value类型
            if key == "temperature":
                value = float(value_str)
                self.agent.update_model_config(temperature=value)
                self.ui.display_success(f"温度参数已更新为: {value}")

            elif key == "max_tokens":
                value = int(value_str)
                self.agent.update_model_config(max_tokens=value)
                self.ui.display_success(f"最大token数已更新为: {value}")

            elif key == "max_iterations":
                value = int(value_str)
                self.agent.update_model_config(max_iterations=value)
                self.ui.display_success(f"最大迭代次数已更新为: {value}")

            else:
                self.ui.display_error(f"不支持的配置项: {key}")
                self.ui.console.print("\n支持的配置项: temperature, max_tokens, max_iterations")
                return

            # 显示更新后的配置
            self._show_current_config()

        except ValueError as e:
            self.ui.display_error(f"配置值无效: {e}")
        except Exception as e:
            self.ui.display_error(f"更新配置失败: {e}")
            self.logger.exception("更新配置失败")

    def _show_current_config(self) -> None:
        """显示当前模型配置"""
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return

        config = self.agent.get_model_config()

        table = Table("配置项", "当前值", "说明", box=box.SIMPLE_HEAVY)
        table.add_row("provider", config["provider"], "LLM提供商")
        table.add_row("model", config["model"], "模型名称")
        table.add_row("temperature", str(config["temperature"]), "温度参数 (0-2)")
        table.add_row("max_tokens", str(config["max_tokens"]), "最大输出token数")
        table.add_row("max_iterations", str(config["max_iterations"]), "最大工具调用轮数")
        table.add_row("max_history", str(config["max_history"]), "最大历史消息数")

        self.ui.console.print("\n[bold cyan]当前模型配置:[/]")
        self.ui.console.print(table)
        self.ui.console.print("\n[dim]使用 /config <key> <value> 修改配置[/]")
        self.ui.console.print()

    async def _fetch_remote_models(self) -> List[str]:
        """从API获取远程模型列表"""
        provider = self.config.get("agent.provider", "openai")
        base_url = self.config.get(f"api.{provider}.base_url")
        api_key = self.config.get(f"api.{provider}.api_key")
        
        # 处理环境变量
        if not api_key:
            env_key = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
            api_key = os.getenv(env_key)
            
        if not api_key:
            self.ui.display_error(f"未找到 {provider} 的API Key，无法获取模型列表")
            return []

        # 构造请求 URL (OpenAI兼容格式)
        # 注意：Anthropic原生API没有列出模型的标准公开Endpoint，但如果有Proxy通常遵循OpenAI格式
        # 如果是直接使用Anthropic，我们暂时只能列出已知模型，或者通过 /v1/models (如果BaseURL支持)
        
        if not base_url:
            if provider == "openai":
                base_url = "https://api.openai.com/v1"
            elif provider == "anthropic":
                base_url = "https://api.anthropic.com/v1"
        
        # 移除末尾斜杠
        base_url = base_url.rstrip("/")
        url = f"{base_url}/models"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        if provider == "anthropic":
             headers["x-api-key"] = api_key
             headers["anthropic-version"] = "2023-06-01"
             # Anthropic API使用x-api-key而不是Bearer
             if "Authorization" in headers:
                 del headers["Authorization"]

        self.ui.console.print(f"[dim]正在从 {url} 获取模型列表...[/]")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        self.ui.display_error(f"获取模型失败 ({resp.status}): {text}")
                        return []
                    
                    data = await resp.json()
                    # 尝试解析标准格式 { data: [ { id: ... } ] }
                    model_list = []
                    
                    if "data" in data and isinstance(data["data"], list):
                        for item in data["data"]:
                            if "id" in item:
                                model_list.append(item["id"])
                    
                    # 排序
                    model_list.sort()
                    return model_list
                    
        except Exception as e:
             self.ui.display_error(f"请求API失败: {e}")
             return []

    async def _show_available_models(self) -> None:
        """显示并管理可用模型"""
        if not self.agent:
            self.ui.display_error("智能体尚未初始化")
            return

        # 1. 获取已配置的可用模型 (Config中的白名单)
        configured_models = self.config.get("agent.available_models", [])
        
        # 2. 如果Config里没有，显示默认的一些模型
        if not configured_models:
             configured_models = ["gpt-4o", "gpt-4-turbo", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"]
        
        current_model = self.agent.model
        
        self.ui.console.print("\n[bold cyan]当前已配置的模型:[/]")
        for i, model in enumerate(configured_models):
            prefix = "  [green]*[/] " if model == current_model else "    "
            self.ui.console.print(f"{prefix}[{i+1}] {model}")
            
        self.ui.console.print()
        self.ui.console.print("[dim]提示: 输入序号切换模型，或输入 'fetch' 从API获取更多模型[/]")
        
        # 交互式选择
        choice = Prompt.ask("请选择操作", default="cancel")
        
        if choice.lower() == "cancel":
            return
            
        if choice.lower() == "fetch":
            # 从API获取
            remote_models = await self._fetch_remote_models()
            if not remote_models:
                return
                
            self.ui.console.print(f"\n[bold cyan]API返回的模型 ({len(remote_models)}):[/]")
            # 分页显示或过滤？直接列出可能太多，这里列出前50个?
            for i, model in enumerate(remote_models):
                self.ui.console.print(f"  [{i+1}] {model}")
                
            self.ui.console.print("\n[yellow]请输入要添加的模型的序号（多个用逗号隔开，例如 1,3,5）:[/]")
            selection = Prompt.ask("选择模型")
            
            if not selection:
                return
                
            try:
                indices = [int(idx.strip()) for idx in selection.split(",")]
                added_count = 0
                for idx in indices:
                    if 1 <= idx <= len(remote_models):
                        model_to_add = remote_models[idx-1]
                        if model_to_add not in configured_models:
                            configured_models.append(model_to_add)
                            added_count += 1
                
                if added_count > 0:
                    # 保存到配置
                    self.config.set("agent.available_models", configured_models)
                    self.config.save()
                    self.ui.display_success(f"已添加 {added_count} 个模型到配置")
                    
                    # 重新显示列表 (递归调用? 还是直接结束)
                    # 简单起见，提示用户现在可以切换
                    self.ui.console.print("[dim]现在使用 /models 可以看到新添加的模型[/]")
                else:
                    self.ui.console.print("[yellow]没有添加任何新模型（可能已存在）[/]")
                    
            except ValueError:
                self.ui.display_error("输入格式错误，请输入数字序号")
                
        else:
            # 尝试切换模型 (序号)
            try:
                idx = int(choice)
                if 1 <= idx <= len(configured_models):
                    new_model = configured_models[idx-1]
                    await self._switch_model(new_model)
                else:
                    self.ui.display_error("序号无效")
            except ValueError:
                # 也许用户直接输入了模型名
                 if choice in configured_models:
                      await self._switch_model(choice)
                 else:
                     # 尝试模糊匹配或忽略
                     pass

    async def _add_server(self, args: str) -> None:
        """
        添加MCP服务器（交互式向导）

        Args:
            args: 可选的服务器名称
        """
        server_name = args.strip() if args else None

        # 创建向导
        wizard = InteractiveConfigWizard(self._server_registry, self.ui.console)

        try:
            config = wizard.run_wizard(server_name)
            if config:
                # 添加到配置
                self.config.add_server(config)
                self.config.save()  # 保存到磁盘
                self.ui.display_success(f"服务器 '{config['name']}' 已添加到配置")
                self.ui.console.print("[dim]配置已保存，重启后生效。或使用 /reconnect 连接新服务器[/]")

                # 询问是否立即连接
                from rich.prompt import Confirm
                if self.agent and Confirm.ask("是否立即连接此服务器?", default=True):
                    # 尝试连接，如果失败则自动安装
                    await self._reconnect_or_install_server(config['name'], config)
        except ValueError as e:
            self.ui.display_error(str(e))
        except Exception as e:
            self.ui.display_error(f"添加服务器失败: {e}")
            self.logger.exception("添加服务器失败")

    def _list_available_servers(self, args: str) -> None:
        """
        列出可用的MCP服务器模板

        Args:
            args: 可选的搜索关键词
        """
        search_query = args.strip() if args else None

        if search_query:
            servers = self._server_registry.search_servers(search_query)
            if not servers:
                self.ui.console.print(f"[yellow]未找到匹配 '{search_query}' 的服务器[/]")
                return
            self.ui.console.print(f"\n[bold cyan]搜索结果 ({len(servers)}):[/]\n")
        else:
            servers = self._server_registry.list_available()
            self.ui.console.print("\n[bold cyan]可用的MCP服务器模板:[/]\n")

        # 按分类分组显示
        from mcp_agent.server_registry import ServerCategory
        categories: dict = {}
        for server in servers:
            cat = server.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(server)

        for category, server_list in categories.items():
            table = Table(
                title=f"[bold]{category.value}[/]",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("名称", style="green", width=18)
            table.add_column("显示名", width=12)
            table.add_column("描述", width=40)

            for server in server_list:
                desc = server.description[:40] + "..." if len(server.description) > 40 else server.description
                table.add_row(server.name, server.display_name, desc)

            self.ui.console.print(table)
            self.ui.console.print()

        self.ui.console.print("[dim]使用 /add-server <name> 添加服务器[/]")

    async def _test_server(self, args: str) -> None:
        """
        测试服务器连接

        Args:
            args: 服务器名称
        """
        server_name = args.strip()
        if not server_name:
            self.ui.display_error("请指定服务器名称，例如: /test-server filesystem")
            self.ui.console.print("\n已配置的服务器:")
            for name in self.config.get_server_names():
                self.ui.console.print(f"  • {name}")
            return

        # 获取服务器配置
        server_config = self.config.get_server_by_name(server_name)
        if not server_config:
            self.ui.display_error(f"服务器不存在: {server_name}")
            self.ui.console.print("\n已配置的服务器:")
            for name in self.config.get_server_names():
                self.ui.console.print(f"  • {name}")
            return

        self.ui.console.print(f"[cyan]正在测试服务器连接: {server_name}...[/]")

        # 验证配置
        errors = self.config.validate_server_config(server_config)
        if errors:
            self.ui.display_error("配置验证失败:")
            for error in errors:
                self.ui.console.print(f"  • {error}")
            return

        # 测试连接
        success, message = await self._server_registry.test_server_connection(server_config)
        if success:
            self.ui.display_success(f"服务器 '{server_name}' 连接测试通过")
            self.ui.console.print(f"[dim]{message}[/]")
        else:
            self.ui.display_error(f"连接测试失败: {message}")

    def _remove_server(self, args: str) -> None:
        """
        移除MCP服务器

        Args:
            args: 服务器名称
        """
        server_name = args.strip()
        if not server_name:
            self.ui.display_error("请指定服务器名称，例如: /remove-server filesystem")
            self.ui.console.print("\n已配置的服务器:")
            for name in self.config.get_server_names():
                self.ui.console.print(f"  • {name}")
            return

        # 确认删除
        from rich.prompt import Confirm
        if not Confirm.ask(f"确定要移除服务器 '{server_name}'?", default=False):
            self.ui.console.print("[yellow]已取消[/]")
            return

        if self.config.remove_server(server_name):
            self.config.save()  # 保存到磁盘
            self.ui.display_success(f"服务器 '{server_name}' 已移除")
            self.ui.console.print("[dim]配置已更新，重启后生效[/]")
        else:
            self.ui.display_error(f"服务器不存在: {server_name}")
    
    async def _handle_config(self, args: str) -> None:
        """处理配置命令"""
        if not args:
            # 无参数，打开TUI
            await self._open_config_tui()
            return
            
        # 有参数，尝试设置配置 (简单实现)
        try:
            key, value = args.split(" ", 1)
            self.config.set(key, value)
            self.config.save()
            self.ui.display_success(f"已更新配置: {key} = {value}")
        except ValueError:
            self.ui.display_error("格式错误。使用: /config <key> <value>")

    async def _open_config_tui(self) -> None:
        """打开TUI配置界面"""
        try:
            from mcp_agent.tui import ServerManagerApp
            
            self.ui.console.print("正在启动配置界面...", style="dim")
            
            # 初始化TUI应用
            app = ServerManagerApp(
                config=self.config,
                registry=self._server_registry,
                installer=self._installer,
                package_discovery=self._package_discovery
            )
            
            # 运行应用
            await app.run_async()
            
            # TUI关闭后刷新控制台
            self.ui.console.clear()
            self.ui.display_success("配置已更新")
            pass
            
        except ImportError:
            self.ui.display_error("未安装 textual 库，无法启动 TUI。请根据 requirements.txt 安装依赖。")
        except Exception as e:
            self.ui.display_error(f"启动 TUI 失败: {e}")
            self.logger.exception("启动 TUI 失败")

    def _check_dependencies(self) -> None:
        """检查系统依赖"""
        self.ui.console.print("\n[bold cyan]正在检查系统依赖...[/]\n")
        dependencies = self._dependency_checker.check_all()
        self._dependency_checker.display_status(dependencies)
    
    async def _discover_packages(self, args: str) -> None:
        """
        发现可用的MCP包
        
        Args:
            args: 搜索来源 (npm/github) 或为空
        """
        source = args.strip().lower() if args else "npm"
        
        if source not in ["npm", "github"]:
            self.ui.display_error("请指定来源: npm 或 github")
            self.ui.console.print("示例: /discover npm")
            return
        
        self.ui.console.print(f"\n[cyan]正在从 {source.upper()} 发现MCP包...[/]\n")
        
        try:
            if source == "npm":
                packages = await self._package_discovery.discover_npm_packages()
            else:
                packages = await self._package_discovery.discover_github_repos()
            
            self._package_discovery.display_packages(packages)
            
            if packages:
                self.ui.console.print(f"\n[dim]使用 /install <package> 安装包[/]")
        
        except Exception as e:
            self.ui.display_error(f"发现包失败: {e}")
            self.logger.exception("发现包失败")
    
    async def _install_package(self, args: str) -> None:
        """
        安装MCP包
        
        Args:
            args: 包名或包名列表（空格分隔）
        """
        if not args.strip():
            self.ui.display_error("请指定要安装的包名")
            self.ui.console.print("示例: /install @modelcontextprotocol/server-time")
            return
        
        # 检查前置条件
        if not self._installer.check_prerequisites():
            return
        
        packages = args.strip().split()
        
        try:
            if len(packages) == 1:
                # 单个包安装
                result = await self._installer.install_package(packages[0])
                
                if result.success:
                    self.ui.display_success(
                        f"✓ {result.package} 安装成功 (版本: {result.version or '未知'})"
                    )
                    self.ui.console.print(f"[dim]耗时: {result.duration:.1f}秒[/]")
                    
                    # 询问是否添加到配置
                    from rich.prompt import Confirm
                    if Confirm.ask("是否将此包添加到MCP配置?", default=True):
                        # 尝试从注册表获取模板
                        template = self._server_registry.get_server(packages[0].split('/')[-1])
                        if template:
                            wizard = InteractiveConfigWizard(self._server_registry, self.ui.console)
                            config = wizard.run_wizard(template.name)
                            if config:
                                self.config.add_server(config)
                                self.ui.display_success("已添加到配置")
                        else:
                            self.ui.console.print("[yellow]未找到配置模板，请手动配置[/]")
                else:
                    self.ui.display_error(f"✗ 安装失败: {result.error}")
            else:
                # 批量安装
                results = await self._installer.batch_install(packages)
                
                # 显示成功的包
                success_packages = [r.package for r in results if r.success]
                if success_packages:
                    self.ui.console.print("\n[green]成功安装的包:[/]")
                    for pkg in success_packages:
                        self.ui.console.print(f"  • {pkg}")
        
        except Exception as e:
            self.ui.display_error(f"安装失败: {e}")
            self.logger.exception("安装包失败")
    
    async def _update_packages(self, args: str) -> None:
        """
        更新MCP包
        
        Args:
            args: 包名，为空则检查所有已安装的包
        """
        package_name = args.strip() if args else None
        
        try:
            if package_name:
                # 更新单个包
                self.ui.console.print(f"\n[cyan]正在检查 {package_name} 的更新...[/]\n")
                
                update_info = await self._version_manager.check_updates(package_name)
                if update_info:
                    current, latest = update_info
                    if current == latest:
                        self.ui.console.print(f"[green]{package_name} 已是最新版本 ({current})[/]")
                    else:
                        self.ui.console.print(f"[yellow]发现新版本:[/]")
                        self.ui.console.print(f"  当前: {current}")
                        self.ui.console.print(f"  最新: {latest}")
                        
                        from rich.prompt import Confirm
                        if Confirm.ask("是否更新?", default=True):
                            await self._version_manager.update_package(package_name)
                else:
                    self.ui.display_error(f"无法检查 {package_name} 的更新")
            else:
                # 检查所有已配置服务器的更新
                server_names = self.config.get_server_names()
                if not server_names:
                    self.ui.console.print("[yellow]没有已配置的服务器[/]")
                    return
                
                self.ui.console.print(f"\n[cyan]正在检查 {len(server_names)} 个包的更新...[/]\n")
                
                # 提取包名（去掉@前缀和版本号）
                packages = []
                for name in server_names:
                    server = self.config.get_server_by_name(name)
                    if server and server.get("args"):
                        # 从args中提取包名
                        for arg in server["args"]:
                            if arg.startswith("@") or "/" in arg:
                                packages.append(arg.split("@")[0])
                                break
                
                if not packages:
                    self.ui.console.print("[yellow]未找到可更新的npm包[/]")
                    return
                
                updates = await self._version_manager.check_all_updates(packages)
                self._version_manager.display_updates(updates)
                
                if updates:
                    from rich.prompt import Confirm
                    if Confirm.ask(f"是否更新所有 {len(updates)} 个包?", default=False):
                        await self._version_manager.update_all(list(updates.keys()))
        
        except Exception as e:
            self.ui.display_error(f"更新失败: {e}")
            self.logger.exception("更新包失败")


    async def _reconnect_or_install_server(
        self, 
        server_name: str,
        server_config: dict
    ) -> None:
        """
        尝试连接服务器，如果失败则自动安装并重试
        
        Args:
            server_name: 服务器名称
            server_config: 服务器配置
        """
        # 首先尝试连接
        self.ui.console.print(f"[yellow]正在连接服务器: {server_name}...[/]")
        
        try:
            # 检查服务器是否存在于agent中
            if not self.agent:
                self.ui.display_error("智能体尚未初始化")
                return
            
            # 尝试重新连接
            success = await self.agent.reconnect_server(server_name)
            
            if success:
                server_status = self.agent.get_server_status(server_name)
                tools = server_status.get("tools", 0) if server_status else 0
                self.ui.display_success(f"服务器 {server_name} 已连接 ({tools} 个工具)")
                return
            
            # 连接失败，尝试自动安装
            self.ui.console.print(f"[yellow]服务器连接失败，可能是npm包未安装[/]")
            
            # 从配置中提取包名
            package_name = self._extract_package_name(server_config)
            
            if not package_name:
                self.ui.display_error("无法从配置中提取包名，请手动安装")
                return
            
            # 询问是否自动安装
            from rich.prompt import Confirm
            if Confirm.ask(f"是否自动安装 {package_name}?", default=True):
                # 检查前置条件
                if not self._installer.check_prerequisites():
                    return
                
                # 安装包
                self.ui.console.print(f"\n[cyan]正在安装 {package_name}...[/]")
                result = await self._installer.install_package(package_name)
                
                if result.success:
                    self.ui.display_success(
                        f"✓ {package_name} 安装成功 (版本: {result.version or '未知'})"
                    )
                    self.ui.console.print(f"[dim]耗时: {result.duration:.1f}秒[/]")
                    
                    # 重新尝试连接
                    self.ui.console.print(f"\n[cyan]正在重新连接服务器...[/]")
                    success = await self.agent.reconnect_server(server_name)
                    
                    if success:
                        server_status = self.agent.get_server_status(server_name)
                        tools = server_status.get("tools", 0) if server_status else 0
                        self.ui.display_success(f"服务器 {server_name} 已成功连接 ({tools} 个工具)")
                    else:
                        self.ui.display_error("安装成功但连接仍然失败，请检查配置")
                else:
                    self.ui.display_error(f"✗ 安装失败: {result.error}")
                    self.ui.console.print("[dim]请手动安装或检查网络连接[/]")
        
        except Exception as e:
            self.ui.display_error(f"操作失败: {e}")
            self.logger.exception("连接或安装服务器失败")
    
    def _extract_package_name(self, server_config: dict) -> str:
        """
        从服务器配置中提取npm包名
        
        Args:
            server_config: 服务器配置
            
        Returns:
            包名或None
        """
        args = server_config.get("args", [])
        
        # 查找以@开头或包含/的参数（npm包名格式）
        for arg in args:
            if isinstance(arg, str):
                # 跳过-y等选项
                if arg.startswith("-"):
                    continue
                # npm包通常是 @scope/package 或 package 格式
                if arg.startswith("@") or "/" in arg:
                    # 去掉可能的版本号
                    return arg.split("@")[0] if "@" in arg[1:] else arg
        
        return None


    async def cleanup(self) -> None:
        """清理资源"""
        if self.agent:
            self.ui.console.print("[cyan]正在关闭智能体...[/]")
            await self.agent.close()

        self.ui.console.print("\n[bold cyan]再见！[/]")


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="配置文件路径",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="详细输出模式",
)
@click.pass_context
def main(
    ctx: click.Context,
    config: Optional[str],
    verbose: bool,
) -> None:
    """
    MCP Agent - 命令行智能体

    一个基于MCP协议的智能对话助手，支持多个LLM提供商和自动工具调用。
    """
    try:
        # 加载配置
        cfg = Config(config)

        # 设置日志级别
        if verbose:
            cfg.set("logging.level", "DEBUG")

        # 验证配置
        errors = cfg.validate()
        if errors:
            ui = ctx.obj.get("ui") if ctx and ctx.obj else ConsoleUI()
            ui.display_error("配置验证失败:")
            for error in errors:
                ui.console.print(f"  • {error}")
            sys.exit(1)

        # 启动CLI
        shared_ui = ctx.obj.get("ui") if ctx and ctx.obj else None
        ui = shared_ui or ConsoleUI()
        cli = CLI(cfg, ui=ui)
        asyncio.run(cli.start())

    except Exception as e:
        ui = ctx.obj.get("ui") if ctx and ctx.obj else ConsoleUI()
        ui.display_error(f"启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
