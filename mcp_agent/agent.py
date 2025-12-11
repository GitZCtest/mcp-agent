"""
智能体核心模块

实现与LLM模型的交互逻辑，支持Anthropic Claude和OpenAI。
支持MCP工具调用（Function Calling）和多服务器连接。
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from mcp_agent.config import Config
from mcp_agent.mcp_client import MCPClient, ServerStatus
from mcp_agent.prompts import PromptTemplates
from mcp_agent.ui import ConsoleUI
from mcp_agent.utils.logger import get_logger, get_enhanced_logger
from mcp_agent.utils.errors import (
    MCPAgentError,
    APIError,
    NetworkError,
    MCPServerError,
    ToolExecutionError,
    TimeoutError as AgentTimeoutError,
    RetryConfig,
    async_retry,
    get_user_friendly_error,
    handle_api_error,
)
from mcp_agent.session import SessionManager


logger = get_logger(__name__)
enhanced_logger = get_enhanced_logger(__name__)


class MCPAgent:
    """
    MCP智能体类

    支持：
    - 多LLM提供商（Anthropic、OpenAI）
    - 多MCP服务器并行连接
    - 工具调用和自动执行
    - 对话历史管理
    """

    def __init__(self, config: Config, ui: Optional[ConsoleUI] = None):
        """
        初始化智能体

        Args:
            config: 配置对象
            ui: 可选的UI对象用于显示进度
        """
        self.config = config
        self.ui = ui
        self.client: Optional[Union[AsyncAnthropic, AsyncOpenAI]] = None
        self.mcp_client: Optional[MCPClient] = None
        self.conversation_history: List[Dict[str, Any]] = []
        self._initialized = False

        # 获取配置
        self.provider = config.get("agent.provider", "anthropic")
        self.model = config.get("agent.model")
        self.max_tokens = config.get("agent.max_tokens")
        self.temperature = config.get("agent.temperature")
        self.system_prompt = config.get("agent.system_prompt") or PromptTemplates.DEFAULT_SYSTEM_PROMPT
        self.max_history = config.get("agent.max_history", 50)
        self.max_iterations = config.get("agent.max_iterations", 10)

        # 工具前缀设置
        self.use_tool_prefix = config.get("mcp.use_tool_prefix", True)

        # ========== 新增：会话管理器 ==========
        session_dir = config.get("advanced.session_dir", "sessions")
        auto_save = config.get("features.auto_save", True)
        self.session_manager = SessionManager(session_dir=session_dir, auto_save=auto_save)

        # Token统计（用于会话统计）
        self._last_input_tokens = 0
        self._last_output_tokens = 0

    def _on_server_progress(self, server_name: str, status: str, message: str) -> None:
        """服务器连接进度回调"""
        if self.ui:
            status_colors = {
                "CONNECTING": "yellow",
                "CONNECTED": "green",
                "ERROR": "red",
            }
            color = status_colors.get(status, "white")
            self.ui.console.print(f"  [{color}][{status}][/{color}] {server_name}: {message}")

    async def initialize(self) -> None:
        """初始化智能体"""
        if self._initialized:
            return

        logger.info(f"正在初始化MCP智能体（提供商: {self.provider}）...")

        # 根据提供商初始化客户端
        if self.provider == "anthropic":
            await self._initialize_anthropic()
        elif self.provider == "openai":
            await self._initialize_openai()
        else:
            raise ValueError(f"不支持的提供商: {self.provider}")

        # 初始化MCP客户端
        if self.config.get("mcp.enabled", True):
            await self._initialize_mcp()
            
        # ========== 新增：创建会话 ==========
        self.session_manager.create_session(
            provider=self.provider,
            model=self.model,
            system_prompt=self.system_prompt,
            metadata={
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }
        )

        self._initialized = True
        logger.info("MCP智能体初始化完成")

    async def _initialize_mcp(self) -> None:
        """初始化MCP客户端，并行连接所有服务器"""
        if self.ui:
            self.ui.console.print("\n[bold cyan]正在连接MCP服务器...[/]")

        self.mcp_client = MCPClient(
            config=self.config.mcp,
            use_tool_prefix=self.use_tool_prefix,
            progress_callback=self._on_server_progress
        )

        # 并行连接所有服务器
        results = await self.mcp_client.initialize()

        # 显示连接结果摘要
        if results:
            connected = sum(1 for r in results.values() if r)
            total = len(results)
            if self.ui:
                if connected == total:
                    self.ui.console.print(f"[bold green]所有 {total} 个服务器已连接[/]")
                elif connected > 0:
                    self.ui.console.print(f"[bold yellow]{connected}/{total} 个服务器已连接[/]")
                else:
                    self.ui.console.print(f"[bold red]所有服务器连接失败[/]")

    async def _initialize_anthropic(self) -> None:
        """初始化Anthropic客户端"""
        api_key = self.config.get("api.anthropic.api_key")
        if not api_key:
            raise ValueError("缺少Anthropic API密钥")

        base_url = self.config.get("api.anthropic.base_url")
        timeout = self.config.get("api.timeout", 60)
        max_retries = self.config.get("api.max_retries", 3)

        client_kwargs = {
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }

        if base_url and base_url != "https://api.anthropic.com":
            client_kwargs["base_url"] = base_url

        self.client = AsyncAnthropic(**client_kwargs)
        logger.info("Anthropic客户端初始化完成")

    async def _initialize_openai(self) -> None:
        """初始化OpenAI客户端"""
        api_key = self.config.get("api.openai.api_key")
        if not api_key:
            raise ValueError("缺少OpenAI API密钥")

        base_url = self.config.get("api.openai.base_url")
        organization = self.config.get("api.openai.organization")
        timeout = self.config.get("api.timeout", 60)
        max_retries = self.config.get("api.max_retries", 3)

        client_kwargs = {
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }

        if base_url and base_url != "https://api.openai.com/v1":
            client_kwargs["base_url"] = base_url

        if organization:
            client_kwargs["organization"] = organization

        self.client = AsyncOpenAI(**client_kwargs)
        logger.info("OpenAI客户端初始化完成")

    async def chat(
        self,
        message: str,
        stream: Optional[bool] = None,
    ) -> str:
        """
        发送消息并获取回复

        Args:
            message: 用户消息
            stream: 是否使用流式输出（None表示使用配置）

        Returns:
            助手回复
        """
        if not self._initialized:
            await self.initialize()

        # 添加用户消息到历史
        self.conversation_history.append({
            "role": "user",
            "content": message,
        })

        # 限制历史长度
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

        # 确定是否使用流式输出
        use_stream = stream if stream is not None else self.config.get("features.streaming", True)

        try:
            if self.provider == "anthropic":
                if use_stream:
                    response = await self._chat_anthropic_stream()
                else:
                    response = await self._chat_anthropic_normal()
            elif self.provider == "openai":
                if use_stream:
                    response = await self._chat_openai_stream()
                else:
                    response = await self._chat_openai_normal()
            else:
                raise ValueError(f"不支持的提供商: {self.provider}")

            # 添加助手回复到历史
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
            })

            # ========== 新增：更新会话 ==========
            self.session_manager.update_session(
                conversation_history=self.conversation_history,
                input_tokens=self._last_input_tokens,
                output_tokens=self._last_output_tokens,
            )

            return response

        except Exception as e:
            logger.error(f"对话失败: {e}")
            if self.ui:
                self.ui.display_error(f"对话失败: {e}")
            raise

    async def _chat_anthropic_normal(self) -> str:
        """Anthropic普通对话模式（支持工具调用）"""
        logger.debug("发送消息到Anthropic...")

        # 获取可用工具
        tools = None
        try:
            if self.mcp_client and self.mcp_client.is_initialized():
                mcp_tools = await self.mcp_client.list_tools()
                if mcp_tools:
                    tools = self._convert_mcp_tools_to_anthropic_format(mcp_tools)
                    logger.debug(f"提供 {len(tools)} 个工具给LLM")
        except Exception as e:
            logger.warning(f"获取MCP工具列表失败: {e}，将继续不使用工具")

        # 构建API参数
        api_params = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": self.system_prompt,
            "messages": self.conversation_history,
        }

        # 如果有工具，添加到参数中
        if tools:
            api_params["tools"] = tools

        response = await self.client.messages.create(**api_params)

        # 记录token使用情况
        if hasattr(response, "usage"):
            self._last_input_tokens = response.usage.input_tokens
            self._last_output_tokens = response.usage.output_tokens
            logger.info(
                f"Token使用: 输入={response.usage.input_tokens}, "
                f"输出={response.usage.output_tokens}"
            )

        # 检查是否有工具调用
        if response.stop_reason == "tool_use":
            return await self._handle_anthropic_tool_calls(response)

        # 提取回复内容
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        return content

    async def _chat_anthropic_stream(self) -> str:
        """Anthropic流式对话模式"""
        logger.debug("发送消息到Anthropic（流式）...")

        full_response = ""

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=self.system_prompt,
            messages=self.conversation_history,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text

        # 获取最终消息以记录token使用
        final_message = await stream.get_final_message()
        if hasattr(final_message, "usage"):
            logger.info(
                f"Token使用: 输入={final_message.usage.prompt_tokens}, "
                f"输出={final_message.usage.completion_tokens}, "
                f"总计={final_message.usage.total_tokens}"
            )

        return full_response

    def _convert_mcp_tools_to_anthropic_format(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将MCP工具转换为Anthropic Tool Use格式

        Args:
            mcp_tools: MCP工具列表

        Returns:
            Anthropic格式的工具列表
        """
        anthropic_tools = []
        for tool in mcp_tools:
            anthropic_tool = {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("input_schema", {
                    "type": "object",
                    "properties": {},
                })
            }
            anthropic_tools.append(anthropic_tool)

        return anthropic_tools

    async def _handle_anthropic_tool_calls(self, response: Any) -> str:
        """
        处理Anthropic工具调用（支持多轮迭代）

        Args:
            response: Anthropic API响应

        Returns:
            最终回复内容
        """
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"工具调用迭代 {iteration}/{self.max_iterations}")

            # 检查是否有工具调用
            tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
            if not tool_use_blocks:
                break

            logger.info(f"LLM请求调用 {len(tool_use_blocks)} 个工具")

            # 将助手消息添加到历史（包含工具调用）
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content,
            })

            # 执行所有工具调用并收集结果
            tool_results = []
            for tool_block in tool_use_blocks:
                tool_name = tool_block.name
                tool_input = tool_block.input
                tool_use_id = tool_block.id

                logger.info(f"执行工具: {tool_name}")
                logger.debug(f"工具参数: {tool_input}")

                # 获取工具所属服务器
                server_name = None
                if self.mcp_client:
                    tool_info = self.mcp_client.get_tool_by_name(tool_name)
                    if tool_info:
                        server_name = tool_info.get("server")

                if self.ui:
                    self.ui.display_tool_call(tool_name, tool_input, server_name)

                try:
                    # 调用MCP工具
                    result = await self.mcp_client.call_tool(tool_name, tool_input)

                    # 提取结果内容
                    if hasattr(result, 'content'):
                        if isinstance(result.content, list):
                            tool_result = "\n".join([
                                item.text if hasattr(item, 'text') else str(item)
                                for item in result.content
                            ])
                        else:
                            tool_result = str(result.content)
                    else:
                        tool_result = str(result)

                    success = True
                    logger.info(f"工具执行成功: {tool_name}")
                    logger.debug(f"工具结果: {tool_result[:200]}...")

                except Exception as e:
                    tool_result = f"工具执行失败: {str(e)}"
                    success = False
                    logger.error(f"工具执行失败 {tool_name}: {e}")

                if self.ui:
                    self.ui.display_tool_result(tool_result, success=success)

                # 添加工具结果
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": tool_result,
                })

            # 将工具结果添加到历史
            self.conversation_history.append({
                "role": "user",
                "content": tool_results,
            })

            # 再次调用LLM
            logger.debug("发送工具结果到Anthropic...")

            # 获取工具列表
            tools = None
            if self.mcp_client and self.mcp_client.is_initialized():
                mcp_tools = await self.mcp_client.list_tools()
                if mcp_tools:
                    tools = self._convert_mcp_tools_to_anthropic_format(mcp_tools)

            api_params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "system": self.system_prompt,
                "messages": self.conversation_history,
            }

            if tools:
                api_params["tools"] = tools

            response = await self.client.messages.create(**api_params)

            # 记录token使用
            if hasattr(response, "usage"):
                logger.info(
                    f"Token使用（迭代{iteration}）: 输入={response.usage.input_tokens}, "
                    f"输出={response.usage.output_tokens}"
                )

            # 如果没有更多工具调用，退出循环
            if response.stop_reason != "tool_use":
                break

        if iteration >= self.max_iterations:
            logger.warning(f"达到最大迭代次数 {self.max_iterations}")

        # 提取最终回复内容
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        return content

    def _convert_mcp_tools_to_openai_format(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将MCP工具转换为OpenAI Function Calling格式

        Args:
            mcp_tools: MCP工具列表

        Returns:
            OpenAI格式的工具列表
        """
        openai_tools = []
        for tool in mcp_tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {
                        "type": "object",
                        "properties": {},
                    })
                }
            }
            openai_tools.append(openai_tool)

        return openai_tools

    async def _chat_openai_normal(self) -> str:
        """OpenAI普通对话模式（支持工具调用）"""
        logger.debug("发送消息到OpenAI...")
        start_time = time.perf_counter()

        # 准备消息（OpenAI格式）
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.conversation_history)

        # 获取可用工具
        tools = None
        try:
            if self.mcp_client and self.mcp_client.is_initialized():
                mcp_tools = await self.mcp_client.list_tools()
                if mcp_tools:
                    tools = self._convert_mcp_tools_to_openai_format(mcp_tools)
                    logger.debug(f"提供 {len(tools)} 个工具给LLM")
        except Exception as e:
            logger.warning(f"获取MCP工具列表失败: {e}，将继续不使用工具")

        # 调用API
        api_params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = "auto"

        try:
            response = await self.client.chat.completions.create(**api_params)
        except asyncio.TimeoutError:
            elapsed = time.perf_counter() - start_time
            logger.error(f"OpenAI API调用超时，耗时: {elapsed:.2f}s")
            raise AgentTimeoutError("API调用超时", timeout_seconds=elapsed)
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            enhanced_logger.log_api_call(
                method="POST",
                endpoint=f"openai/{self.model}",
                duration=elapsed,
                error=str(e),
            )
            # 转换为统一的API错误
            raise handle_api_error(e, provider="openai")

        elapsed = time.perf_counter() - start_time

        # 记录token使用情况
        if hasattr(response, "usage"):
            self._last_input_tokens = response.usage.prompt_tokens
            self._last_output_tokens = response.usage.completion_tokens
            logger.info(
                f"Token使用: 输入={response.usage.prompt_tokens}, "
                f"输出={response.usage.completion_tokens}, "
                f"总计={response.usage.total_tokens}"
            )

        enhanced_logger.log_api_call(
            method="POST",
            endpoint=f"openai/{self.model}",
            status=200,
            duration=elapsed,
        )

        # 处理响应
        message = response.choices[0].message

        # 检查是否有工具调用
        if hasattr(message, "tool_calls") and message.tool_calls:
            return await self._handle_tool_calls(message)

        # 没有工具调用，直接返回内容
        return message.content or ""

    async def _handle_tool_calls(self, message: Any) -> str:
        """
        处理工具调用（支持多轮迭代）

        Args:
            message: 包含工具调用的消息

        Returns:
            最终回复内容
        """
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"工具调用迭代 {iteration}/{self.max_iterations}")

            if not hasattr(message, "tool_calls") or not message.tool_calls:
                break

            logger.info(f"LLM请求调用 {len(message.tool_calls)} 个工具")

            # 将助手消息添加到历史（包含工具调用）
            self.conversation_history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ]
            })

            # 执行所有工具调用
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                logger.info(f"执行工具: {tool_name}")
                logger.debug(f"工具参数: {arguments}")

                # 获取工具所属服务器
                server_name = None
                if self.mcp_client:
                    tool_info = self.mcp_client.get_tool_by_name(tool_name)
                    if tool_info:
                        server_name = tool_info.get("server")

                if self.ui:
                    self.ui.display_tool_call(tool_name, arguments, server_name)

                try:
                    # 调用MCP工具
                    result = await self.mcp_client.call_tool(tool_name, arguments)

                    # 提取结果内容
                    if hasattr(result, 'content'):
                        if isinstance(result.content, list):
                            tool_result = "\n".join([
                                item.text if hasattr(item, 'text') else str(item)
                                for item in result.content
                            ])
                        else:
                            tool_result = str(result.content)
                    else:
                        tool_result = str(result)

                    success = True
                    logger.info(f"工具执行成功: {tool_name}")
                    logger.debug(f"工具结果: {tool_result[:200]}...")

                except Exception as e:
                    tool_result = f"工具执行失败: {str(e)}"
                    success = False
                    logger.error(f"工具执行失败 {tool_name}: {e}")

                if self.ui:
                    self.ui.display_tool_result(tool_result, success=success)

                # 将工具结果添加到历史
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                })

            # 再次调用LLM
            logger.debug("发送工具结果到LLM...")

            # 构建消息
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_history)

            # 获取工具列表
            tools = None
            if self.mcp_client and self.mcp_client.is_initialized():
                mcp_tools = await self.mcp_client.list_tools()
                if mcp_tools:
                    tools = self._convert_mcp_tools_to_openai_format(mcp_tools)

            api_params = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = "auto"

            response = await self.client.chat.completions.create(**api_params)

            # 记录token使用
            if hasattr(response, "usage"):
                logger.info(
                    f"Token使用（迭代{iteration}）: 输入={response.usage.prompt_tokens}, "
                    f"输出={response.usage.completion_tokens}"
                )

            message = response.choices[0].message

            # 如果没有更多工具调用，退出循环
            if not hasattr(message, "tool_calls") or not message.tool_calls:
                break

        if iteration >= self.max_iterations:
            logger.warning(f"达到最大迭代次数 {self.max_iterations}")

        return message.content or ""

    async def _chat_openai_stream(self) -> str:
        """OpenAI流式对话模式（暂不支持工具调用）"""
        logger.debug("发送消息到OpenAI（流式）...")
        logger.warning("流式模式暂不支持工具调用，如需使用工具请关闭流式输出")

        # 准备消息（OpenAI格式）
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.conversation_history)

        full_response = ""

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    full_response += delta.content

        return full_response

    def clear_history(self) -> None:
        """清除对话历史"""
        self.conversation_history.clear()
        logger.info("对话历史已清除")

    def get_history(self) -> List[Dict[str, Any]]:
        """获取对话历史"""
        return self.conversation_history.copy()

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示词"""
        self.system_prompt = prompt
        logger.info("系统提示词已更新")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """列出可用工具"""
        if not self.mcp_client:
            return []
        return await self.mcp_client.list_tools()

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """调用工具"""
        if not self.mcp_client:
            raise RuntimeError("MCP客户端未初始化")
        return await self.mcp_client.call_tool(tool_name, arguments)

    # ==================== 服务器管理方法 ====================

    def get_server_info(self) -> List[Dict[str, Any]]:
        """获取所有服务器信息"""
        if not self.mcp_client:
            return []
        return self.mcp_client.get_server_info()

    def get_server_status(self, name: str) -> Optional[Dict[str, Any]]:
        """获取单个服务器状态"""
        if not self.mcp_client:
            return None
        return self.mcp_client.get_server_status(name)

    async def reconnect_server(self, name: str) -> bool:
        """重新连接指定服务器"""
        if not self.mcp_client:
            return False
        return await self.mcp_client.reconnect_server(name)

    async def connect_all_servers(self) -> Dict[str, bool]:
        """连接所有未连接的服务器"""
        if not self.mcp_client:
            return {}
        return await self.mcp_client.connect_servers()

    # ==================== 对话历史管理 ====================

    async def close(self) -> None:
        """关闭智能体"""
        logger.info("正在关闭智能体...")

        if self.mcp_client:
            await self.mcp_client.close()

        self.client = None
        self._initialized = False

        logger.info("智能体已关闭")

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        mcp_servers = self.mcp_client.get_server_info() if self.mcp_client else []
        connected_count = sum(1 for s in mcp_servers if s.get("connected", False))

        return {
            "provider": self.provider,
            "model": self.model,
            "history_length": len(self.conversation_history),
            "max_history": self.max_history,
            "max_iterations": self.max_iterations,
            "mcp_enabled": self.mcp_client is not None,
            "mcp_servers": mcp_servers,
            "mcp_connected_count": connected_count,
            "mcp_total_tools": self.mcp_client.get_total_tool_count() if self.mcp_client else 0,
        }

    def save_history(self, filename: str) -> str:
        """保存对话历史到文件"""
        filepath = Path(filename)
        if not filepath.suffix:
            filepath = filepath.with_suffix('.json')

        data = {
            "saved_at": datetime.now().isoformat(),
            "provider": self.provider,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "conversation_history": self.conversation_history,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"对话历史已保存到: {filepath}")
        return str(filepath)

    def load_history(self, filename: str) -> Dict[str, Any]:
        """从文件加载对话历史"""
        filepath = Path(filename)
        if not filepath.suffix:
            filepath = filepath.with_suffix('.json')

        if not filepath.exists():
            raise FileNotFoundError(f"文件不存在: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.conversation_history = data.get("conversation_history", [])

        if "system_prompt" in data:
            self.system_prompt = data["system_prompt"]

        logger.info(f"对话历史已从 {filepath} 加载，共 {len(self.conversation_history)} 条消息")

        return {
            "saved_at": data.get("saved_at", "未知"),
            "provider": data.get("provider", "未知"),
            "model": data.get("model", "未知"),
            "message_count": len(self.conversation_history),
        }
    
    def get_session_stats(self) -> Dict[str, Any]:
        """获取当前会话统计"""
        return self.session_manager.get_current_stats()

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出所有会话"""
        return self.session_manager.list_sessions(limit=limit)

    def search_sessions(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索会话"""
        return self.session_manager.search_sessions(keyword, limit=limit)

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """获取会话摘要"""
        return self.session_manager.get_session_summary(session_id)

    def export_session(self, session_id: str, format: str = "markdown") -> str:
        """
        导出会话

        Args:
            session_id: 会话ID
            format: 导出格式 (markdown/html)

        Returns:
            导出文件路径
        """
        if format.lower() == "html":
            return self.session_manager.export_to_html(session_id)
        else:
            return self.session_manager.export_to_markdown(session_id)

    def load_session_history(self, session_id: str) -> Dict[str, Any]:
        """
        加载指定会话的历史到当前对话

        Args:
            session_id: 会话ID

        Returns:
            会话信息
        """
        session = self.session_manager.load_session(session_id)
        self.conversation_history = session.conversation_history.copy()

        if session.system_prompt:
            self.system_prompt = session.system_prompt

        logger.info(f"已加载会话 {session_id}，共 {len(self.conversation_history)} 条消息")

        return {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "provider": session.provider,
            "model": session.model,
            "message_count": len(self.conversation_history),
        }

    def get_current_session_id(self) -> Optional[str]:
        """获取当前会话ID"""
        if self.session_manager.current_session:
            return self.session_manager.current_session.session_id
        return None

    # ==================== 模型参数管理 ====================

    def update_model_config(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_iterations: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        动态更新模型配置参数

        Args:
            model: 模型名称
            temperature: 温度参数 (0-2)
            max_tokens: 最大token数
            max_iterations: 最大迭代次数

        Returns:
            更新后的配置信息
        """
        updated = {}

        if model is not None:
            self.model = model
            self.config.set("agent.model", model)
            updated["model"] = model
            logger.info(f"模型已更新为: {model}")

        if temperature is not None:
            if not 0 <= temperature <= 2:
                raise ValueError("temperature 必须在 0 到 2 之间")
            self.temperature = temperature
            self.config.set("agent.temperature", temperature)
            updated["temperature"] = temperature
            logger.info(f"温度参数已更新为: {temperature}")

        if max_tokens is not None:
            if max_tokens <= 0:
                raise ValueError("max_tokens 必须是正整数")
            self.max_tokens = max_tokens
            self.config.set("agent.max_tokens", max_tokens)
            updated["max_tokens"] = max_tokens
            logger.info(f"最大token数已更新为: {max_tokens}")

        if max_iterations is not None:
            if max_iterations <= 0:
                raise ValueError("max_iterations 必须是正整数")
            self.max_iterations = max_iterations
            self.config.set("agent.max_iterations", max_iterations)
            updated["max_iterations"] = max_iterations
            logger.info(f"最大迭代次数已更新为: {max_iterations}")

        return updated

    def get_model_config(self) -> Dict[str, Any]:
        """
        获取当前模型配置

        Returns:
            当前模型配置信息
        """
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "max_iterations": self.max_iterations,
            "max_history": self.max_history,
        }

    def switch_provider(self, provider: str, model: Optional[str] = None) -> None:
        """
        切换LLM提供商（需要重新初始化）

        Args:
            provider: 提供商名称 (anthropic/openai)
            model: 可选的模型名称

        Raises:
            ValueError: 不支持的提供商
        """
        if provider not in ["anthropic", "openai"]:
            raise ValueError(f"不支持的提供商: {provider}，支持: anthropic, openai")

        self.provider = provider
        self.config.set("agent.provider", provider)

        if model:
            self.model = model
            self.config.set("agent.model", model)

        # 标记需要重新初始化
        self._initialized = False
        logger.info(f"提供商已切换为: {provider}，需要重新初始化")

    def get_available_models(self) -> Dict[str, List[str]]:
        """
        获取可用的模型列表

        Returns:
            按提供商分组的模型列表
        """
        return {
            "anthropic": [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ],
            "openai": [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-4",
                "gpt-3.5-turbo",
                "claude-sonnet-4-5-20250929",  # 通过OpenAI兼容接口
            ],
        }
