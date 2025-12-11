from typing import List, Optional, Dict, Any
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, ListView, ListItem, Label, Button, Static, Input, Select, ContentSwitcher
from textual.screen import Screen, ModalScreen
from textual.binding import Binding
from textual.message import Message
from rich.text import Text

from mcp_agent.config import Config
from mcp_agent.installer import MCPInstaller, PackageDiscovery
from mcp_agent.server_registry import ServerRegistry

class ServerListItem(ListItem):
    """服务器列表项"""
    def __init__(self, name: str, config: Dict[str, Any], status: str = "stopped"):
        self.server_name = name
        self.server_config = config
        self.status = status
        super().__init__()

    def compose(self) -> ComposeResult:
        status_color = "green" if self.status == "running" else "red"
        symbol = "🟢" if self.status == "running" else "🔴"
        yield Label(f"{symbol} {self.server_name}", classes="server-name")
        yield Label(self.server_config.get("command", ""), classes="server-cmd")

class DashboardScreen(Screen):
    """主仪表盘屏幕"""
    BINDINGS = [
        ("n", "new_server", "新建服务器"),
        ("d", "delete_server", "删除服务器"),
        ("enter", "view_details", "查看详情"),
        ("r", "refresh", "刷新"),
        ("i", "install_wizard", "安装向导"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Vertical(
                Label("已安装服务器", classes="section-title"),
                ListView(id="server-list"),
                classes="server-list-container"
            ),
            Vertical(
                Label("服务器信息", classes="section-title"),
                Static(id="server-info", classes="info-box"),
                classes="server-info-container"
            ),
            classes="main-layout"
        )
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_server_list()

    def refresh_server_list(self) -> None:
        server_list = self.query_one("#server-list", ListView)
        server_list.clear()
        
        config: Config = self.app.config
        servers = config.get("mcp.servers", [])
        
        # 获取当前连接状态 (需要从App获取agent引用，暂时模拟)
        # TODO: Implement generic status checking
        
        for server in servers:
            name = server.get("name")
            if name:
                server_list.append(ServerListItem(name, server))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, ServerListItem):
            info_box = self.query_one("#server-info", Static)
            config = event.item.server_config
            
            info_text = f"""[bold cyan]{event.item.server_name}[/]
            
[yellow]Command:[/]{config.get('command')}
[yellow]Args:[/]{' '.join(config.get('args', []))}
[yellow]Env:[/]{config.get('env', {})}
"""
            info_box.update(info_text)

    def action_new_server(self) -> None:
        self.app.push_screen("config_editor")

    def action_delete_server(self) -> None:
        server_list = self.query_one("#server-list", ListView)
        if server_list.index is not None:
             item = server_list.children[server_list.index]
             if isinstance(item, ServerListItem):
                 # TODO: Confirm dialog
                 if self.app.config.remove_server(item.server_name):
                     self.app.config.save()
                     self.refresh_server_list()
                     self.notify(f"服务器 {item.server_name} 已删除")

    def action_view_details(self) -> None:
        server_list = self.query_one("#server-list", ListView)
        if server_list.index is not None and isinstance(server_list.highlighted_child, ServerListItem):
            self.app.push_screen(ServerDetailScreen(server_list.highlighted_child.server_config))

    def action_install_wizard(self) -> None:
        self.app.push_screen("install_wizard")


class ServerDetailScreen(Screen):
    """服务器详情屏幕"""
    BINDINGS = [("escape", "back", "返回")]

    def __init__(self, server_config: Dict[str, Any]):
        self.server_config = server_config
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Label(f"Server: {self.server_config.get('name')}", classes="title"),
            Static(str(self.server_config)),
            Button("返回", variant="primary", id="btn-back")
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.dismiss()
            
    def action_back(self) -> None:
        self.dismiss()


class ConfigEditorScreen(Screen):
    """配置编辑器屏幕"""
    BINDINGS = [("escape", "cancel", "取消")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Label("新建/编辑服务器", classes="title"),
            Input(placeholder="服务器名称", id="input-name"),
            Input(placeholder="命令 (如 npx, python)", id="input-cmd"),
            Input(placeholder="参数 (空格分隔)", id="input-args"),
            Horizontal(
                Button("保存", variant="success", id="btn-save"),
                Button("取消", variant="error", id="btn-cancel"),
                classes="button-row"
            )
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-save":
            self._save_config()

    def _save_config(self) -> None:
        name = self.query_one("#input-name", Input).value
        cmd = self.query_one("#input-cmd", Input).value
        args_str = self.query_one("#input-args", Input).value
        
        if not name or not cmd:
            self.notify("名称和命令不能为空", severity="error")
            return
            
        args = args_str.split() if args_str else []
        
        new_config = {
            "name": name,
            "command": cmd,
            "args": args
        }
        
        try:
            self.app.config.add_server(new_config)
            self.app.config.save()
            self.dismiss(result=True)
            self.notify(f"服务器 {name} 已保存")
        except Exception as e:
            self.notify(f"保存失败: {str(e)}", severity="error")

    def action_cancel(self) -> None:
        self.dismiss()

class InstallWizardScreen(Screen):
    """安装向导屏幕"""
    BINDINGS = [
        ("escape", "cancel", "取消/返回"),
        ("enter", "next", "下一步/确认"),
    ]
    
    CSS = """
    .wizard-step {
        padding: 1;
        align: center middle;
    }
    .wizard-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #search-results {
        height: 1fr;
        border: solid $secondary;
        margin: 1 0;
    }
    .install-log {
        height: 1fr;
        border: solid $secondary;
        background: $surface;
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield Label("MCP服务器安装向导", classes="title")
            with ContentSwitcher(initial="step-search", id="wizard-switcher"):
                # Step 1: Search
                yield Vertical(
                    Label("步骤 1/3: 搜索包", classes="wizard-title"),
                    Input(placeholder="输入包名或关键词 (如 @modelcontextprotocol/server-filesystem)", id="input-search"),
                    Button("搜索", variant="primary", id="btn-search"),
                    Label("或输入 'npm'/'github' 浏览推荐列表", classes="hint"),
                    id="step-search", classes="wizard-step"
                )
                
                # Step 2: Select
                yield Vertical(
                    Label("步骤 2/3: 选择要安装的包", classes="wizard-title"),
                    ListView(id="search-results"),
                    Label("按 Enter 选择，Esc 返回", classes="hint"),
                    id="step-select", classes="wizard-step"
                )
                
                # Step 3: Install
                yield Vertical(
                    Label("步骤 3/3: 正在安装...", classes="wizard-title"),
                    Static("正在通过 npm 安装包，请稍候...", id="install-status"),
                    Static(id="install-log", classes="install-log"),
                    Button("完成", variant="success", id="btn-finish", disabled=True),
                    id="step-install", classes="wizard-step"
                )
            yield Button("取消", id="btn-cancel-wizard")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-wizard":
            self.dismiss()
        elif event.button.id == "btn-search":
            self._do_search()
        elif event.button.id == "btn-finish":
            # Refresh main list and close
            self.app.query_one("DashboardScreen").refresh_server_list()
            self.dismiss()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "input-search":
            self._do_search()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "search-results":
             if isinstance(event.item, Label): # Should be custom item
                 package_name = str(event.item.renderable) # Simple for now
                 self._start_install(package_name)

    async def _do_search(self) -> None:
        query = self.query_one("#input-search", Input).value
        if not query:
            return
            
        switcher = self.query_one("#wizard-switcher", ContentSwitcher)
        switcher.current = "step-select"
        
        results_list = self.query_one("#search-results", ListView)
        results_list.clear()
        results_list.append(Label("正在搜索..."))
        
        # Async search
        if self.app.package_discovery:
            # Determine source based on query or generic search
            # For now, simplistic heuristic or just use npm search as default
            try:
                # Use discover_npm_packages which allows custom query
                packages = await self.app.package_discovery.discover_npm_packages(query=query, limit=20)
                
                results_list.clear()
                if not packages:
                    results_list.append(Label("[yellow]未找到匹配的包[/]"))
                else:
                    for pkg in packages:
                        # Create a descriptive label
                        # Storing package name in renderable might be fragile, but works for simple Label
                        # Better to have a custom ListItem but Label is okay for now
                        label = Label(f"{pkg.name}")
                        results_list.append(label)
                        
            except Exception as e:
                results_list.clear()
                results_list.append(Label(f"[red]搜索失败: {str(e)}[/]"))
        else:
             results_list.clear()
             results_list.append(Label("[red]无法执行搜索: PackageDiscovery 未初始化[/]"))

    async def _start_install(self, package_name: str) -> None:
        switcher = self.query_one("#wizard-switcher", ContentSwitcher)
        switcher.current = "step-install"
        
        log_view = self.query_one("#install-log", Static)
        status = self.query_one("#install-status", Static)
        
        status.update(f"正在安装 {package_name}...")
        log_view.update(f"[cyan]运行 npm install -g {package_name}...\n")
        
        # Integration with real installer
        try:
            # Real installation logic
            if self.app.installer:
                 # install_package is async
                 result = await self.app.installer.install_package(package_name)
            
            # This is a placeholder for actual async installation logic
            # In real implementation we would call the installer here
            if self.app.installer:
                 result = await self.app.installer.install_package(package_name)
                 if result.success:
                     log_view.update(log_view.renderable + f"\n[green]安装成功![/]\n")
                     status.update("安装完成")
                     
                     # Auto-configure suggestion
                     self.app.config.add_server({
                         "name": package_name.split("/")[-1].replace("server-", ""),
                         "command": "npx",
                         "args": ["-y", package_name]
                     })
                     self.app.config.save()
                     log_view.update(log_view.renderable + f"\n[green]已自动配置服务器![/]\n")
                 else:
                     log_view.update(log_view.renderable + f"\n[red]安装失败: {result.error}[/]\n")
                     status.update("安装失败")
            else:
                # Mock path if installer not available (testing)
                await asyncio.sleep(2) 
                log_view.update(log_view.renderable + f"\n[green](模拟) 安装成功![/]\n")
                status.update("安装完成")

            self.query_one("#btn-finish", Button).disabled = False
            
        except Exception as e:
            log_view.update(log_view.renderable + f"\n[red]发生错误: {str(e)}[/]\n")
            status.update("错误")
            self.query_one("#btn-finish", Button).disabled = False

    def action_cancel(self) -> None:
        # Go back steps or close
        switcher = self.query_one("#wizard-switcher", ContentSwitcher)
        if switcher.current == "step-search":
            self.dismiss()
        elif switcher.current == "step-select":
            switcher.current = "step-search"
        elif switcher.current == "step-install":
            self.dismiss() # Can't really stop install mid-way easily yet


class ServerManagerApp(App):
    """MCP 服务器管理器 TUI 应用"""
    CSS = """
    .section-title {
        background: $primary;
        color: $text;
        padding: 1;
        text-align: center;
    }
    
    .server-list-container {
        width: 1fr;
        height: 1fr;
        border: solid $secondary;
    }
    
    .server-info-container {
        width: 1fr;
        height: 1fr;
        border: solid $secondary;
        margin-left: 1;
    }
    
    .main-layout {
        layout: horizontal;
        height: 1fr;
    }
    
    .info-box {
        padding: 1;
    }
    
    .title {
        text-align: center;
        text-style: bold;
        padding: 1;
    }
    
    .button-row {
        align: center middle;
        margin-top: 1;
    }
    
    Button {
        margin: 1;
    }
    """
    
    SCREENS = {
        "dashboard": DashboardScreen,
        "config_editor": ConfigEditorScreen,
        "install_wizard": InstallWizardScreen
    }

    def __init__(self, config: Config, registry: ServerRegistry, installer: MCPInstaller, package_discovery: Optional[PackageDiscovery] = None):
        self.config = config
        self.registry = registry
        self.installer = installer
        self.package_discovery = package_discovery
        super().__init__()

    def on_mount(self) -> None:
        self.push_screen("dashboard")

if __name__ == "__main__":
    # For testing independently
    from mcp_agent.config import Config
    from mcp_agent.server_registry import ServerRegistry
    from mcp_agent.installer import MCPInstaller
    
    cfg = Config()
    app = ServerManagerApp(cfg, None, None, None) # Mocks for now
    app.run()
