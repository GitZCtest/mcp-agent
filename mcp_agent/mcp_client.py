"""
MCP客户端模块

封装MCP协议的客户端功能，支持多服务器并行连接。
"""

import asyncio
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None

from mcp_agent.utils.logger import get_logger


logger = get_logger(__name__)


class ServerStatus(Enum):
    """服务器连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class ServerConnection:
    """服务器连接信息"""
    name: str
    config: Dict[str, Any]
    status: ServerStatus = ServerStatus.DISCONNECTED
    session: Optional[Any] = None  # ClientSession
    tools: List[Any] = field(default_factory=list)
    resources: List[Any] = field(default_factory=list)
    error_message: str = ""
    retry_count: int = 0


class MCPClient:
    """
    MCP客户端类

    支持：
    - 多服务器并行连接
    - 工具名称前缀（避免冲突）
    - 连接状态管理
    - 断线重连
    """

    def __init__(
        self,
        config: Dict[str, Any],
        use_tool_prefix: bool = True,
        progress_callback: Optional[Callable[[str, str, str], None]] = None
    ):
        """
        初始化MCP客户端

        Args:
            config: MCP配置
            use_tool_prefix: 是否给工具名添加服务器前缀
            progress_callback: 进度回调函数 (server_name, status, message)
        """
        self.config = config
        self.use_tool_prefix = use_tool_prefix
        self.progress_callback = progress_callback

        # 服务器连接管理
        self.connections: Dict[str, ServerConnection] = {}
        self._exit_stack = AsyncExitStack()
        self._initialized = False

        # 工具映射：tool_name -> (server_name, original_tool_name)
        self._tool_mapping: Dict[str, tuple] = {}

        if not MCP_AVAILABLE:
            logger.warning("MCP SDK未安装，MCP功能将不可用。请运行: pip install mcp")

    def _report_progress(self, server_name: str, status: str, message: str) -> None:
        """报告连接进度"""
        logger.info(f"[{server_name}] {status}: {message}")
        if self.progress_callback:
            try:
                self.progress_callback(server_name, status, message)
            except Exception as e:
                logger.debug(f"进度回调失败: {e}")

    async def initialize(self) -> Dict[str, bool]:
        """
        初始化MCP客户端，并行连接所有服务器

        Returns:
            各服务器连接结果 {server_name: success}
        """
        if self._initialized:
            return {name: conn.status == ServerStatus.CONNECTED
                    for name, conn in self.connections.items()}

        if not MCP_AVAILABLE:
            logger.error("MCP SDK未安装，无法初始化MCP客户端")
            return {}

        if not self.config.get("enabled", True):
            logger.info("MCP功能已禁用")
            self._initialized = True
            return {}

        servers = self.config.get("servers", [])
        if not servers:
            logger.warning("未配置MCP服务器")
            self._initialized = True
            return {}

        # 过滤启用的服务器
        enabled_servers = [s for s in servers if s.get("enabled", True)]
        if not enabled_servers:
            logger.warning("没有启用的MCP服务器")
            self._initialized = True
            return {}

        # 初始化连接对象
        for server_config in enabled_servers:
            name = server_config.get("name", "unknown")
            self.connections[name] = ServerConnection(
                name=name,
                config=server_config,
                status=ServerStatus.DISCONNECTED
            )

        # 并行连接所有服务器
        results = await self.connect_servers()

        self._initialized = True

        # 统计结果
        connected = sum(1 for r in results.values() if r)
        total = len(results)
        logger.info(f"MCP客户端初始化完成: {connected}/{total} 个服务器已连接")

        return results

    async def connect_servers(
        self,
        server_names: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        并行连接指定的服务器

        Args:
            server_names: 服务器名称列表，None表示所有未连接的服务器

        Returns:
            各服务器连接结果
        """
        if server_names is None:
            # 连接所有未连接的服务器
            targets = [
                name for name, conn in self.connections.items()
                if conn.status != ServerStatus.CONNECTED
            ]
        else:
            targets = [name for name in server_names if name in self.connections]

        if not targets:
            return {}

        # 并行连接
        tasks = [self._connect_server(name) for name in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        return_results = {}
        for name, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.error(f"连接服务器 {name} 异常: {result}")
                return_results[name] = False
            else:
                return_results[name] = result

        # 重建工具映射
        self._rebuild_tool_mapping()

        return return_results

    async def _connect_server(self, name: str) -> bool:
        """
        连接单个服务器

        Args:
            name: 服务器名称

        Returns:
            是否连接成功
        """
        conn = self.connections.get(name)
        if not conn:
            return False

        config = conn.config
        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env", {})

        if not command:
            conn.status = ServerStatus.ERROR
            conn.error_message = "缺少命令配置"
            self._report_progress(name, "ERROR", conn.error_message)
            return False

        conn.status = ServerStatus.CONNECTING
        self._report_progress(name, "CONNECTING", f"正在连接 ({command} {' '.join(args[:2])}...)")

        try:
            # 准备环境变量
            server_env = os.environ.copy()
            server_env.update(env)

            # 创建服务器参数
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=server_env
            )

            # 建立连接
            read, write = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )

            # 创建会话
            session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )

            # 初始化会话
            await session.initialize()

            conn.session = session
            conn.status = ServerStatus.CONNECTED
            conn.error_message = ""

            # 获取工具列表
            await self._fetch_tools(conn)

            # 获取资源列表
            await self._fetch_resources(conn)

            self._report_progress(
                name, "CONNECTED",
                f"已连接 ({len(conn.tools)} 工具, {len(conn.resources)} 资源)"
            )
            return True

        except Exception as e:
            conn.status = ServerStatus.ERROR
            conn.error_message = str(e)
            conn.retry_count += 1
            self._report_progress(name, "ERROR", f"连接失败: {e}")
            logger.error(f"连接服务器 {name} 失败: {e}", exc_info=True)
            return False

    async def _fetch_tools(self, conn: ServerConnection) -> None:
        """获取服务器的工具列表"""
        try:
            tools_result = await conn.session.list_tools()
            conn.tools = tools_result.tools if hasattr(tools_result, 'tools') else []
            logger.debug(f"服务器 {conn.name} 提供 {len(conn.tools)} 个工具")
        except Exception as e:
            logger.warning(f"获取服务器 {conn.name} 的工具列表失败: {e}")
            conn.tools = []

    async def _fetch_resources(self, conn: ServerConnection) -> None:
        """获取服务器的资源列表"""
        try:
            resources_result = await conn.session.list_resources()
            conn.resources = resources_result.resources if hasattr(resources_result, 'resources') else []
            logger.debug(f"服务器 {conn.name} 提供 {len(conn.resources)} 个资源")
        except Exception as e:
            logger.warning(f"获取服务器 {conn.name} 的资源列表失败: {e}")
            conn.resources = []

    def _rebuild_tool_mapping(self) -> None:
        """重建工具名称映射"""
        self._tool_mapping.clear()

        for name, conn in self.connections.items():
            if conn.status != ServerStatus.CONNECTED:
                continue

            for tool in conn.tools:
                original_name = tool.name if hasattr(tool, 'name') else str(tool)

                if self.use_tool_prefix:
                    # 带前缀的名称: filesystem_read_file
                    prefixed_name = f"{name}_{original_name}"
                    self._tool_mapping[prefixed_name] = (name, original_name)
                else:
                    # 不带前缀，可能有冲突
                    if original_name in self._tool_mapping:
                        logger.warning(
                            f"工具名称冲突: {original_name} 同时存在于 "
                            f"{self._tool_mapping[original_name][0]} 和 {name}"
                        )
                    self._tool_mapping[original_name] = (name, original_name)

    async def reconnect_server(self, name: str) -> bool:
        """
        重新连接指定服务器

        Args:
            name: 服务器名称

        Returns:
            是否连接成功
        """
        conn = self.connections.get(name)
        
        # 如果连接对象不存在，尝试从配置中创建
        if not conn:
            # 从配置中查找服务器
            servers = self.config.get("servers", [])
            server_config = None
            for s in servers:
                if s.get("name") == name:
                    server_config = s
                    break
            
            if not server_config:
                logger.error(f"服务器不存在: {name}")
                return False
            
            # 创建新的连接对象
            conn = ServerConnection(
                name=name,
                config=server_config,
                status=ServerStatus.DISCONNECTED
            )
            self.connections[name] = conn

        # 先断开现有连接
        if conn.session:
            try:
                # 注意：这里无法单独关闭一个连接，需要特殊处理
                conn.session = None
            except Exception as e:
                logger.warning(f"断开服务器 {name} 时出错: {e}")

        conn.status = ServerStatus.DISCONNECTED
        conn.tools = []
        conn.resources = []

        # 重新连接
        result = await self._connect_server(name)
        if result:
            self._rebuild_tool_mapping()
        return result

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        列出所有可用工具

        Returns:
            工具列表（包含服务器前缀的名称）
        """
        if not self._initialized:
            await self.initialize()

        all_tools = []
        for name, conn in self.connections.items():
            if conn.status != ServerStatus.CONNECTED:
                continue

            for tool in conn.tools:
                original_name = tool.name if hasattr(tool, 'name') else str(tool)

                if self.use_tool_prefix:
                    display_name = f"{name}_{original_name}"
                else:
                    display_name = original_name

                tool_dict = {
                    "server": name,
                    "name": display_name,
                    "original_name": original_name,
                    "description": tool.description if hasattr(tool, 'description') else "",
                    "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                }
                all_tools.append(tool_dict)

        return all_tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        server_name: Optional[str] = None
    ) -> Any:
        """
        调用工具

        Args:
            tool_name: 工具名称（可以是带前缀或不带前缀）
            arguments: 工具参数
            server_name: 指定服务器名称（可选）

        Returns:
            工具执行结果
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f"调用工具: {tool_name}")
        logger.debug(f"工具参数: {arguments}")

        # 解析工具名称
        target_server = None
        actual_tool_name = tool_name

        if server_name:
            # 明确指定了服务器
            target_server = server_name
            actual_tool_name = tool_name
        elif tool_name in self._tool_mapping:
            # 在映射中找到
            target_server, actual_tool_name = self._tool_mapping[tool_name]
        else:
            # 尝试解析前缀格式: server_toolname
            for name in self.connections.keys():
                prefix = f"{name}_"
                if tool_name.startswith(prefix):
                    target_server = name
                    actual_tool_name = tool_name[len(prefix):]
                    break

            # 如果还是找不到，搜索所有服务器
            if not target_server:
                for name, conn in self.connections.items():
                    if conn.status != ServerStatus.CONNECTED:
                        continue
                    for tool in conn.tools:
                        if hasattr(tool, 'name') and tool.name == tool_name:
                            target_server = name
                            actual_tool_name = tool_name
                            break
                    if target_server:
                        break

        if not target_server:
            raise ValueError(f"找不到工具: {tool_name}")

        # 检查服务器状态
        conn = self.connections.get(target_server)
        if not conn or conn.status != ServerStatus.CONNECTED:
            raise RuntimeError(f"服务器未连接: {target_server}")

        # 调用工具
        try:
            result = await conn.session.call_tool(actual_tool_name, arguments)
            logger.info(f"工具调用完成: {tool_name} (服务器: {target_server})")
            logger.debug(f"工具结果: {result}")
            return result
        except Exception as e:
            logger.error(f"工具调用失败 {tool_name}: {e}", exc_info=True)
            raise

    async def list_resources(self) -> List[Dict[str, Any]]:
        """列出所有可用资源"""
        if not self._initialized:
            await self.initialize()

        all_resources = []
        for name, conn in self.connections.items():
            if conn.status != ServerStatus.CONNECTED:
                continue

            for resource in conn.resources:
                resource_dict = {
                    "server": name,
                    "uri": resource.uri if hasattr(resource, 'uri') else str(resource),
                    "name": resource.name if hasattr(resource, 'name') else "",
                    "description": resource.description if hasattr(resource, 'description') else "",
                    "mimeType": resource.mimeType if hasattr(resource, 'mimeType') else "",
                }
                all_resources.append(resource_dict)

        return all_resources

    async def read_resource(self, uri: str, server_name: Optional[str] = None) -> Any:
        """读取资源"""
        if not self._initialized:
            await self.initialize()

        logger.info(f"读取资源: {uri}")

        # 查找资源所在的服务器
        target_server = server_name
        if not target_server:
            for name, conn in self.connections.items():
                if conn.status != ServerStatus.CONNECTED:
                    continue
                for resource in conn.resources:
                    if hasattr(resource, 'uri') and resource.uri == uri:
                        target_server = name
                        break
                if target_server:
                    break

        if not target_server:
            # 尝试第一个已连接的服务器
            for name, conn in self.connections.items():
                if conn.status == ServerStatus.CONNECTED:
                    target_server = name
                    break

        if not target_server:
            raise ValueError(f"找不到可用的服务器来读取资源: {uri}")

        conn = self.connections[target_server]
        try:
            result = await conn.session.read_resource(uri)
            logger.info(f"资源读取完成: {uri}")
            return result
        except Exception as e:
            logger.error(f"资源读取失败 {uri}: {e}", exc_info=True)
            raise

    async def close(self) -> None:
        """关闭所有连接"""
        if not self._initialized:
            return

        logger.info("正在关闭MCP客户端...")

        try:
            await self._exit_stack.aclose()
            await asyncio.sleep(0.1)

            for conn in self.connections.values():
                conn.status = ServerStatus.DISCONNECTED
                conn.session = None
                conn.tools = []
                conn.resources = []

            self._tool_mapping.clear()
            self._initialized = False

            logger.info("MCP客户端已关闭")
        except Exception as e:
            logger.error(f"关闭MCP客户端时出错: {e}", exc_info=False)

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def get_server_info(self) -> List[Dict[str, Any]]:
        """获取所有服务器信息"""
        info = []
        for name, conn in self.connections.items():
            info.append({
                "name": name,
                "status": conn.status.value,
                "connected": conn.status == ServerStatus.CONNECTED,
                "tools": len(conn.tools),
                "resources": len(conn.resources),
                "error": conn.error_message if conn.status == ServerStatus.ERROR else "",
                "description": conn.config.get("description", ""),
            })
        return info

    def get_server_status(self, name: str) -> Optional[Dict[str, Any]]:
        """获取单个服务器状态"""
        conn = self.connections.get(name)
        if not conn:
            return None
        return {
            "name": name,
            "status": conn.status.value,
            "connected": conn.status == ServerStatus.CONNECTED,
            "tools": len(conn.tools),
            "resources": len(conn.resources),
            "error": conn.error_message,
            "description": conn.config.get("description", ""),
        }

    def get_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取工具信息"""
        # 先检查映射
        if tool_name in self._tool_mapping:
            server_name, original_name = self._tool_mapping[tool_name]
            conn = self.connections.get(server_name)
            if conn and conn.status == ServerStatus.CONNECTED:
                for tool in conn.tools:
                    if hasattr(tool, 'name') and tool.name == original_name:
                        return {
                            "server": server_name,
                            "name": tool_name,
                            "original_name": original_name,
                            "description": tool.description if hasattr(tool, 'description') else "",
                            "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                        }

        # 直接搜索
        for name, conn in self.connections.items():
            if conn.status != ServerStatus.CONNECTED:
                continue
            for tool in conn.tools:
                if hasattr(tool, 'name') and tool.name == tool_name:
                    return {
                        "server": name,
                        "name": tool_name,
                        "original_name": tool_name,
                        "description": tool.description if hasattr(tool, 'description') else "",
                        "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                    }

        return None

    def get_connected_server_count(self) -> int:
        """获取已连接的服务器数量"""
        return sum(1 for conn in self.connections.values()
                   if conn.status == ServerStatus.CONNECTED)

    def get_total_tool_count(self) -> int:
        """获取总工具数量"""
        return sum(len(conn.tools) for conn in self.connections.values()
                   if conn.status == ServerStatus.CONNECTED)
