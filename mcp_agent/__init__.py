"""
MCP Agent - 基于MCP协议的命令行智能体

一个模块化、可扩展的智能体框架，支持与Claude模型交互。
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from mcp_agent.agent import MCPAgent
from mcp_agent.config import Config

__all__ = ["MCPAgent", "Config"]