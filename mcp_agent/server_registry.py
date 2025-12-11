"""
MCP服务器注册表模块

提供MCP服务器配置模板、交互式配置向导和配置验证功能。
"""

import asyncio
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich import box


class ServerCategory(Enum):
    """服务器分类"""
    FILE_OPERATIONS = "文件操作"
    DATABASE = "数据库"
    WEB_SEARCH = "网络搜索"
    HTTP = "HTTP请求"
    MEMORY = "记忆存储"
    VERSION_CONTROL = "版本控制"
    BROWSER = "浏览器自动化"
    COMMUNICATION = "通讯协作"
    UTILITIES = "实用工具"
    CUSTOM = "自定义"


@dataclass
class ServerParam:
    """服务器参数定义"""
    name: str
    description: str
    required: bool = True
    default: Optional[str] = None
    env_var: Optional[str] = None  # 可从环境变量读取
    validation_pattern: Optional[str] = None  # 正则验证
    validation_message: Optional[str] = None


@dataclass
class ServerTemplate:
    """MCP服务器模板"""
    name: str
    display_name: str
    description: str
    package: str
    command: str = "npx"
    category: ServerCategory = ServerCategory.UTILITIES
    params: List[ServerParam] = field(default_factory=list)
    env_vars: Dict[str, str] = field(default_factory=dict)
    example_usage: str = ""
    install_command: Optional[str] = None
    test_command: Optional[str] = None
    
    def get_args(self, param_values: Dict[str, str]) -> List[str]:
        """根据参数值生成命令行参数"""
        args = ["-y", self.package]
        for param in self.params:
            value = param_values.get(param.name)
            if value:
                args.append(value)
        return args
    
    def get_env(self, param_values: Dict[str, str]) -> Dict[str, str]:
        """根据参数值生成环境变量"""
        env = {}
        for key, template in self.env_vars.items():
            # 替换模板中的 ${param_name}
            value = template
            for pname, pvalue in param_values.items():
                value = value.replace(f"${{{pname}}}", pvalue or "")
            if value and value != template:  # 有实际值
                env[key] = value
        return env
    
    def validate_param(self, param_name: str, value: str) -> Tuple[bool, str]:
        """验证参数值"""
        param = next((p for p in self.params if p.name == param_name), None)
        if not param:
            return True, ""
        
        if param.required and not value:
            return False, f"参数 {param_name} 是必需的"
        
        if value and param.validation_pattern:
            if not re.match(param.validation_pattern, value):
                return False, param.validation_message or f"参数 {param_name} 格式无效"
        
        return True, ""


# ============================================================
# 内置服务器模板 (10+)
# ============================================================

BUILTIN_SERVERS: Dict[str, ServerTemplate] = {
    # 1. 文件系统
    "filesystem": ServerTemplate(
        name="filesystem",
        display_name="文件系统",
        description="读写本地文件系统，支持文件创建、读取、编辑、搜索等操作",
        package="@modelcontextprotocol/server-filesystem",
        category=ServerCategory.FILE_OPERATIONS,
        params=[
            ServerParam(
                name="directory",
                description="允许访问的目录路径",
                required=True,
                default="./workspace",
            ),
        ],
        example_usage="适合需要操作本地文件的场景，如代码编辑、文档处理等。",
    ),
    
    # 2. PostgreSQL
    "postgres": ServerTemplate(
        name="postgres",
        display_name="PostgreSQL",
        description="连接PostgreSQL数据库，执行SQL查询和数据操作",
        package="@modelcontextprotocol/server-postgres",
        category=ServerCategory.DATABASE,
        params=[
            ServerParam(
                name="connection_string",
                description="数据库连接字符串",
                required=True,
                default="postgresql://localhost/mydb",
                validation_pattern=r"^postgresql://.*",
                validation_message="连接字符串必须以 postgresql:// 开头",
            ),
        ],
        env_vars={
            "PGPASSWORD": "${password}",
        },
        example_usage="适合需要与PostgreSQL数据库交互的场景。",
    ),
    
    # 3. SQLite
    "sqlite": ServerTemplate(
        name="sqlite",
        display_name="SQLite",
        description="连接SQLite数据库，执行SQL查询和数据操作",
        package="@modelcontextprotocol/server-sqlite",
        category=ServerCategory.DATABASE,
        params=[
            ServerParam(
                name="database_path",
                description="SQLite数据库文件路径",
                required=True,
                default="./data.db",
            ),
        ],
        example_usage="适合轻量级数据存储和查询场景。",
    ),
    
    # 4. Brave搜索
    "brave-search": ServerTemplate(
        name="brave-search",
        display_name="Brave搜索",
        description="使用Brave搜索引擎进行网络搜索",
        package="@modelcontextprotocol/server-brave-search",
        category=ServerCategory.WEB_SEARCH,
        params=[
            ServerParam(
                name="api_key",
                description="Brave Search API密钥",
                required=True,
                env_var="BRAVE_API_KEY",
            ),
        ],
        env_vars={
            "BRAVE_API_KEY": "${api_key}",
        },
        example_usage="适合需要搜索最新网络信息的场景。从 https://brave.com/search/api/ 获取API密钥。",
    ),
    
    # 5. Fetch (HTTP请求)
    "fetch": ServerTemplate(
        name="fetch",
        display_name="HTTP请求",
        description="发送HTTP请求获取网页内容和API数据",
        package="@modelcontextprotocol/server-fetch",
        category=ServerCategory.HTTP,
        params=[],
        example_usage="适合需要获取网页内容或调用外部API的场景。",
    ),
    
    # 6. Memory
    "memory": ServerTemplate(
        name="memory",
        display_name="记忆存储",
        description="基于知识图谱的持久化记忆存储",
        package="@modelcontextprotocol/server-memory",
        category=ServerCategory.MEMORY,
        params=[],
        example_usage="适合需要跨会话保存信息的场景。",
    ),
    
    # 7. GitHub
    "github": ServerTemplate(
        name="github",
        display_name="GitHub",
        description="与GitHub交互，管理仓库、Issue、PR等",
        package="@modelcontextprotocol/server-github",
        category=ServerCategory.VERSION_CONTROL,
        params=[
            ServerParam(
                name="token",
                description="GitHub Personal Access Token",
                required=True,
                env_var="GITHUB_TOKEN",
            ),
        ],
        env_vars={
            "GITHUB_PERSONAL_ACCESS_TOKEN": "${token}",
        },
        example_usage="适合需要与GitHub仓库交互的场景。从 https://github.com/settings/tokens 创建Token。",
    ),
    
    # 8. Puppeteer
    "puppeteer": ServerTemplate(
        name="puppeteer",
        display_name="Puppeteer浏览器",
        description="控制无头浏览器进行网页自动化操作",
        package="@modelcontextprotocol/server-puppeteer",
        category=ServerCategory.BROWSER,
        params=[],
        example_usage="适合需要浏览器自动化、截图、网页测试的场景。",
    ),
    
    # 9. Slack
    "slack": ServerTemplate(
        name="slack",
        display_name="Slack",
        description="与Slack工作区交互，发送消息和管理频道",
        package="@modelcontextprotocol/server-slack",
        category=ServerCategory.COMMUNICATION,
        params=[
            ServerParam(
                name="bot_token",
                description="Slack Bot Token (xoxb-...开头)",
                required=True,
                env_var="SLACK_BOT_TOKEN",
                validation_pattern=r"^xoxb-.*",
                validation_message="Token必须以 xoxb- 开头",
            ),
            ServerParam(
                name="team_id",
                description="Slack Team ID",
                required=True,
                env_var="SLACK_TEAM_ID",
            ),
        ],
        env_vars={
            "SLACK_BOT_TOKEN": "${bot_token}",
            "SLACK_TEAM_ID": "${team_id}",
        },
        example_usage="适合需要与Slack集成的场景。",
    ),
    
    # 10. 时间工具
    "time": ServerTemplate(
        name="time",
        display_name="时间工具",
        description="获取当前时间和时区转换功能",
        package="@modelcontextprotocol/server-time",
        category=ServerCategory.UTILITIES,
        params=[],
        example_usage="适合需要时间相关功能的场景。",
    ),
    
    # 11. Sequential Thinking
    "sequential-thinking": ServerTemplate(
        name="sequential-thinking",
        display_name="序列思考",
        description="提供动态和反思性问题解决的思考框架",
        package="@modelcontextprotocol/server-sequential-thinking",
        category=ServerCategory.UTILITIES,
        params=[],
        example_usage="适合需要复杂推理和分步思考的场景。",
    ),
    
    # 12. Everything Search (Windows)
    "everything": ServerTemplate(
        name="everything",
        display_name="Everything搜索",
        description="使用Everything进行快速文件搜索（Windows）",
        package="@modelcontextprotocol/server-everything",
        category=ServerCategory.FILE_OPERATIONS,
        params=[],
        example_usage="适合Windows系统的快速文件搜索。需要安装Everything软件。",
    ),
}


class ServerRegistry:
    """MCP服务器注册表"""
    
    def __init__(self, custom_servers: Optional[Dict[str, ServerTemplate]] = None):
        """
        初始化服务器注册表
        
        Args:
            custom_servers: 自定义服务器模板
        """
        self._servers = BUILTIN_SERVERS.copy()
        if custom_servers:
            self._servers.update(custom_servers)
        self._console = Console()
    
    def list_available(self, category: Optional[ServerCategory] = None) -> List[ServerTemplate]:
        """
        列出所有可用服务器
        
        Args:
            category: 可选，按类别筛选
            
        Returns:
            服务器模板列表
        """
        servers = list(self._servers.values())
        if category:
            servers = [s for s in servers if s.category == category]
        return sorted(servers, key=lambda s: (s.category.value, s.name))
    
    def get_server(self, name: str) -> Optional[ServerTemplate]:
        """
        获取服务器模板
        
        Args:
            name: 服务器名称
            
        Returns:
            服务器模板，不存在则返回None
        """
        return self._servers.get(name)
    
    def search_servers(self, query: str) -> List[ServerTemplate]:
        """
        搜索服务器
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的服务器列表
        """
        query = query.lower()
        results = []
        for server in self._servers.values():
            if (query in server.name.lower() or 
                query in server.display_name.lower() or
                query in server.description.lower()):
                results.append(server)
        return results
    
    def get_categories(self) -> List[Tuple[ServerCategory, int]]:
        """
        获取所有分类及其服务器数量
        
        Returns:
            (分类, 数量) 列表
        """
        category_counts: Dict[ServerCategory, int] = {}
        for server in self._servers.values():
            category_counts[server.category] = category_counts.get(server.category, 0) + 1
        return [(cat, count) for cat, count in sorted(category_counts.items(), key=lambda x: x[0].value)]
    
    def register_server(self, template: ServerTemplate) -> None:
        """
        注册新的服务器模板
        
        Args:
            template: 服务器模板
        """
        self._servers[template.name] = template
    
    def validate_server_config(self, config: Dict[str, Any]) -> List[str]:
        """
        验证服务器配置
        
        Args:
            config: 服务器配置字典
            
        Returns:
            错误列表，空表示验证通过
        """
        errors = []
        
        # 检查必需字段
        if not config.get("name"):
            errors.append("缺少服务器名称")
        if not config.get("command"):
            errors.append("缺少启动命令")
        
        # 检查命令是否可执行
        command = config.get("command", "")
        if command and command not in ["npx", "node", "python", "uvx"]:
            if not shutil.which(command):
                errors.append(f"命令 '{command}' 不在系统PATH中")
        
        return errors
    
    def check_npm_installed(self) -> bool:
        """检查npm是否已安装"""
        return shutil.which("npm") is not None
    
    def check_npx_installed(self) -> bool:
        """检查npx是否已安装"""
        return shutil.which("npx") is not None
    
    async def test_server_connection(
        self, 
        config: Dict[str, Any],
        timeout: float = 10.0
    ) -> Tuple[bool, str]:
        """
        测试服务器连接
        
        Args:
            config: 服务器配置
            timeout: 超时时间（秒）
            
        Returns:
            (成功, 消息)
        """
        command = config.get("command", "npx")
        args = config.get("args", [])
        env = {**os.environ, **config.get("env", {})}
        
        try:
            # 尝试启动服务器进程
            process = await asyncio.create_subprocess_exec(
                command,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            
            # 等待一小段时间看是否能正常启动
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
                # 如果进程立即退出，检查返回码
                if process.returncode != 0:
                    stderr = await process.stderr.read()
                    return False, f"服务器启动失败: {stderr.decode()[:200]}"
            except asyncio.TimeoutError:
                # 进程仍在运行，说明启动成功
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    process.kill()
                return True, "服务器可以正常启动"
            
            return True, "服务器启动验证通过"
            
        except FileNotFoundError:
            return False, f"命令 '{command}' 未找到"
        except Exception as e:
            return False, f"测试连接失败: {str(e)}"
    
    def generate_config(
        self, 
        template: ServerTemplate, 
        param_values: Dict[str, str],
        enabled: bool = True
    ) -> Dict[str, Any]:
        """
        根据模板生成服务器配置
        
        Args:
            template: 服务器模板
            param_values: 参数值
            enabled: 是否启用
            
        Returns:
            服务器配置字典
        """
        return {
            "name": template.name,
            "command": template.command,
            "args": template.get_args(param_values),
            "env": template.get_env(param_values),
            "description": template.description,
            "enabled": enabled,
        }


class InteractiveConfigWizard:
    """交互式配置向导"""
    
    def __init__(self, registry: ServerRegistry, console: Optional[Console] = None):
        """
        初始化向导
        
        Args:
            registry: 服务器注册表
            console: Rich控制台
        """
        self.registry = registry
        self.console = console or Console()
    
    def display_available_servers(self) -> None:
        """显示所有可用服务器"""
        categories = self.registry.get_categories()
        
        for category, count in categories:
            servers = self.registry.list_available(category)
            
            table = Table(
                title=f"[bold cyan]{category.value}[/] ({count})",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("名称", style="green", width=18)
            table.add_column("显示名", width=15)
            table.add_column("描述", width=45)
            
            for server in servers:
                table.add_row(
                    server.name,
                    server.display_name,
                    server.description[:45] + "..." if len(server.description) > 45 else server.description,
                )
            
            self.console.print(table)
            self.console.print()
    
    def select_server(self) -> Optional[ServerTemplate]:
        """
        交互式选择服务器
        
        Returns:
            选择的服务器模板
        """
        self.display_available_servers()
        
        server_name = Prompt.ask(
            "[bold cyan]请输入要添加的服务器名称[/]",
            default="",
        )
        
        if not server_name:
            return None
        
        template = self.registry.get_server(server_name)
        if not template:
            # 尝试搜索
            matches = self.registry.search_servers(server_name)
            if matches:
                self.console.print(f"\n[yellow]未找到 '{server_name}'，您是否想要：[/]")
                for m in matches[:5]:
                    self.console.print(f"  • {m.name} - {m.display_name}")
                return None
            else:
                self.console.print(f"[red]未找到服务器: {server_name}[/]")
                return None
        
        return template
    
    def configure_params(self, template: ServerTemplate) -> Optional[Dict[str, str]]:
        """
        交互式配置参数
        
        Args:
            template: 服务器模板
            
        Returns:
            参数值字典，取消则返回None
        """
        self.console.print(f"\n[bold green]配置 {template.display_name}[/]")
        self.console.print(f"[dim]{template.description}[/]\n")
        
        if template.example_usage:
            self.console.print(Panel(
                template.example_usage,
                title="使用说明",
                border_style="blue",
            ))
        
        param_values: Dict[str, str] = {}
        
        for param in template.params:
            # 尝试从环境变量获取默认值
            default = param.default or ""
            if param.env_var:
                env_value = os.getenv(param.env_var)
                if env_value:
                    default = env_value
                    self.console.print(f"[dim]从环境变量 {param.env_var} 读取[/]")
            
            # 提示输入
            required_mark = "[red]*[/]" if param.required else ""
            prompt_text = f"{required_mark}[cyan]{param.description}[/]"
            
            while True:
                value = Prompt.ask(
                    prompt_text,
                    default=default,
                )
                
                # 验证
                is_valid, error = template.validate_param(param.name, value)
                if is_valid:
                    param_values[param.name] = value
                    break
                else:
                    self.console.print(f"[red]{error}[/]")
        
        return param_values
    
    def preview_config(self, config: Dict[str, Any]) -> bool:
        """
        预览配置并确认
        
        Args:
            config: 服务器配置
            
        Returns:
            用户是否确认
        """
        self.console.print("\n[bold cyan]配置预览:[/]")
        
        table = Table(box=box.SIMPLE)
        table.add_column("配置项", style="cyan")
        table.add_column("值")
        
        table.add_row("名称", config["name"])
        table.add_row("命令", config["command"])
        table.add_row("参数", " ".join(config["args"]))
        
        if config.get("env"):
            env_display = ", ".join(f"{k}=***" for k in config["env"].keys())
            table.add_row("环境变量", env_display)
        
        table.add_row("描述", config.get("description", "-"))
        table.add_row("启用", "是" if config.get("enabled", True) else "否")
        
        self.console.print(table)
        
        return Confirm.ask("\n[bold]确认添加此服务器?[/]", default=True)
    
    def run_wizard(self, server_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        运行配置向导
        
        Args:
            server_name: 可选，直接指定服务器名称
            
        Returns:
            生成的服务器配置，取消则返回None
        """
        # 检查npm
        if not self.registry.check_npx_installed():
            self.console.print("[red]错误: 未检测到npx，请先安装Node.js[/]")
            self.console.print("[dim]下载地址: https://nodejs.org/[/]")
            return None
        
        # 选择服务器
        if server_name:
            template = self.registry.get_server(server_name)
            if not template:
                self.console.print(f"[red]未找到服务器模板: {server_name}[/]")
                self.console.print("[dim]使用 /list-available 查看可用服务器[/]")
                return None
        else:
            template = self.select_server()
            if not template:
                return None
        
        # 配置参数
        param_values = self.configure_params(template)
        if param_values is None:
            return None
        
        # 生成配置
        config = self.registry.generate_config(template, param_values)
        
        # 预览确认
        if not self.preview_config(config):
            self.console.print("[yellow]已取消[/]")
            return None
        
        return config


# 全局注册表实例
_registry: Optional[ServerRegistry] = None


def get_registry() -> ServerRegistry:
    """获取全局服务器注册表实例"""
    global _registry
    if _registry is None:
        _registry = ServerRegistry()
    return _registry
