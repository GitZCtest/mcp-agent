"""
配置管理模块

负责加载和验证配置文件，支持环境变量覆盖。
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from dotenv import load_dotenv


class Config:
    """
    配置管理类

    支持：
    - 从 YAML 文件加载配置
    - 环境变量覆盖（格式：MCP_AGENT_SECTION_KEY）
    - 配置验证
    - 默认值
    - 工作目录自动创建
    """

    # 环境变量前缀
    ENV_PREFIX = "MCP_AGENT_"

    # 环境变量映射（特殊处理的环境变量）
    ENV_MAPPINGS = {
        "ANTHROPIC_API_KEY": "api.anthropic.api_key",
        "ANTHROPIC_BASE_URL": "api.anthropic.base_url",
        "OPENAI_API_KEY": "api.openai.api_key",
        "OPENAI_BASE_URL": "api.openai.base_url",
        "OPENAI_ORGANIZATION": "api.openai.organization",
        "API_PROVIDER": "agent.provider",
        "MCP_AGENT_MODEL": "agent.model",
        "MCP_AGENT_MAX_TOKENS": "agent.max_tokens",
        "MCP_AGENT_TEMPERATURE": "agent.temperature",
        "MCP_AGENT_DEBUG": "advanced.debug",
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置

        Args:
            config_path: 配置文件路径，可选
        """
        # 加载 .env 文件
        load_dotenv()

        # 初始化默认配置
        self._config: Dict[str, Any] = self._get_default_config()
        self._config_path: Optional[str] = None  # 存储配置文件路径

        # 加载配置文件
        if config_path:
            self.load_config(config_path)
        else:
            # 尝试加载默认配置文件位置
            loaded = False
            for default_path in ["config/config.yaml", "config.yaml", ".mcp-agent.yaml"]:
                if Path(default_path).exists():
                    self.load_config(default_path)
                    loaded = True
                    break
            
            # 如果没有找到配置文件，自动创建默认配置
            if not loaded:
                try:
                    default_file = Path("config/config.yaml")
                    # 确保目录存在
                    if not default_file.parent.exists():
                        default_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 设置路径并保存默认配置
                    self._config_path = str(default_file.absolute())
                    self.save()
                    # 也可以选择打印提示，但在cli应用中可能不需要
                except Exception as e:
                    # 如果创建失败（如权限问题），仅保留默认配置在内存中
                    # 但不设置 _config_path，避免后续 save() 误以为有文件
                    pass

        # 应用环境变量覆盖
        self._apply_env_overrides()

        # 自动创建工作目录
        if self.get("workspace.auto_create", True):
            self._ensure_workspace()

    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置

        Returns:
            默认配置字典
        """
        return {
            # Agent 配置
            "agent": {
                "provider": "openai",  # anthropic 或 openai
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 8192,
                "temperature": 0.7,
                "max_iterations": 10,  # 最大工具调用轮数
                "system_prompt": "",
                "max_history": 50,
                "available_models": [],  # 用户选择的可用模型列表
            },

            # MCP 配置
            "mcp": {
                "enabled": True,
                "servers": [],
                "connection_timeout": 30,
                "request_timeout": 60,
            },

            # 工作目录配置
            "workspace": {
                "path": "./workspace",
                "auto_create": True,
            },

            # UI 配置
            "ui": {
                "theme": "monokai",
                "show_thinking": True,
                "show_tool_calls": True,
                "markdown_code_theme": "monokai",
                "max_result_preview": 800,
                "truncate_long_output": True,
            },

            # 日志配置
            "logging": {
                "level": "INFO",
                "file": "logs/mcp-agent.log",
                "console": True,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "max_size": 10,  # MB
                "backup_count": 5,
            },

            # CLI 配置
            "cli": {
                "prompt": "MCP Agent> ",
                "color": True,
                "show_welcome": True,
                "show_token_usage": True,
                "width": 0,  # 0 表示自动检测
            },

            # API 配置
            "api": {
                "anthropic": {
                    "api_key": "",
                    "base_url": "https://api.anthropic.com",
                },
                "openai": {
                    "api_key": "",
                    "base_url": "https://api.openai.com/v1",
                    "organization": "",
                },
                "timeout": 60,
                "max_retries": 3,
            },

            # 功能开关
            "features": {
                "enable_history": True,
                "auto_save": True,
                "save_interval": 300,
                "streaming": True,
                "enable_tools": True,
            },

            # 高级配置
            "advanced": {
                "cache_dir": ".cache",
                "session_dir": "sessions",
                "debug": False,
                "profiling": False,
            },
        }

    def load_config(self, config_path: str) -> None:
        """
        加载配置文件

        Args:
            config_path: 配置文件路径

        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML 解析错误
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        # 存储配置文件路径（用于后续保存）
        self._config_path = str(path.absolute())

        with open(path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}

        # 处理 mcp_servers 字段（兼容简化格式）
        if "mcp_servers" in user_config:
            servers = user_config.pop("mcp_servers")
            if "mcp" not in user_config:
                user_config["mcp"] = {}
            user_config["mcp"]["servers"] = self._normalize_servers(servers)

        # 合并配置
        self._merge_config(self._config, user_config)

    def _normalize_servers(self, servers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        标准化 MCP 服务器配置

        Args:
            servers: 服务器配置列表

        Returns:
            标准化后的服务器配置
        """
        normalized = []
        for server in servers:
            if not isinstance(server, dict):
                continue

            # 确保必要字段存在
            norm_server = {
                "name": server.get("name", "unknown"),
                "command": server.get("command", ""),
                "args": server.get("args", []),
                "env": server.get("env", {}),
                "description": server.get("description", ""),
                "enabled": server.get("enabled", True),
            }

            # 处理环境变量中的占位符
            norm_server["env"] = self._resolve_env_vars(norm_server["env"])

            normalized.append(norm_server)

        return normalized

    def _resolve_env_vars(self, env_dict: Dict[str, str]) -> Dict[str, str]:
        """
        解析环境变量占位符

        支持格式：${VAR_NAME} 或 ${VAR_NAME:default}

        Args:
            env_dict: 环境变量字典

        Returns:
            解析后的环境变量字典
        """
        resolved = {}
        pattern = re.compile(r'\$\{([^}:]+)(?::([^}]*))?\}')

        for key, value in env_dict.items():
            if isinstance(value, str):
                def replacer(match):
                    var_name = match.group(1)
                    default = match.group(2) or ""
                    return os.getenv(var_name, default)

                resolved[key] = pattern.sub(replacer, value)
            else:
                resolved[key] = value

        return resolved

    def _apply_env_overrides(self) -> None:
        """应用环境变量覆盖"""
        # 应用预定义的环境变量映射
        for env_var, config_path in self.ENV_MAPPINGS.items():
            value = os.getenv(env_var)
            if value is not None:
                # 类型转换
                converted = self._convert_env_value(value, config_path)
                self.set(config_path, converted)

        # 应用通用前缀的环境变量（MCP_AGENT_*）
        for key, value in os.environ.items():
            if key.startswith(self.ENV_PREFIX) and key not in self.ENV_MAPPINGS:
                # 转换环境变量名为配置路径
                # 例如: MCP_AGENT_AGENT_MODEL -> agent.model
                config_key = key[len(self.ENV_PREFIX):].lower().replace("_", ".")

                # 尝试找到匹配的配置路径
                if self._config_path_exists(config_key):
                    converted = self._convert_env_value(value, config_key)
                    self.set(config_key, converted)

    def _config_path_exists(self, path: str) -> bool:
        """检查配置路径是否存在"""
        try:
            self.get(path)
            return True
        except (KeyError, TypeError):
            return False

    def _convert_env_value(self, value: str, config_path: str) -> Any:
        """
        根据配置路径转换环境变量值的类型

        Args:
            value: 环境变量值
            config_path: 配置路径

        Returns:
            转换后的值
        """
        # 获取当前配置值以推断类型
        current = self.get(config_path)

        if current is None:
            return value

        if isinstance(current, bool):
            return value.lower() in ("true", "1", "yes", "on")
        elif isinstance(current, int):
            try:
                return int(value)
            except ValueError:
                return current
        elif isinstance(current, float):
            try:
                return float(value)
            except ValueError:
                return current
        else:
            return value

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """
        递归合并配置

        Args:
            base: 基础配置
            override: 覆盖配置
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _ensure_workspace(self) -> None:
        """确保工作目录存在"""
        workspace_path = self.get("workspace.path", "./workspace")
        path = Path(workspace_path)

        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持点号分隔的路径）

        Args:
            key: 配置键（如 "agent.model"）
            default: 默认值

        Returns:
            配置值

        Examples:
            >>> config.get("agent.model")
            'claude-3-5-sonnet-20241022'
            >>> config.get("agent.unknown", "default")
            'default'
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值（支持点号分隔的路径）

        Args:
            key: 配置键（如 "agent.model"）
            value: 配置值

        Examples:
            >>> config.set("agent.model", "gpt-4")
            >>> config.get("agent.model")
            'gpt-4'
        """
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def validate(self) -> List[str]:
        """
        验证配置

        Returns:
            错误列表（空列表表示验证通过）

        Examples:
            >>> errors = config.validate()
            >>> if errors:
            ...     for error in errors:
            ...         print(f"Error: {error}")
        """
        errors = []

        # 验证提供商
        provider = self.get("agent.provider", "anthropic")
        if provider not in ["anthropic", "openai"]:
            errors.append(f"不支持的提供商: {provider}，支持: anthropic, openai")

        # 验证 API 密钥
        if provider == "anthropic":
            if not self.get("api.anthropic.api_key"):
                errors.append("缺少 Anthropic API 密钥 (ANTHROPIC_API_KEY)")
        elif provider == "openai":
            if not self.get("api.openai.api_key"):
                errors.append("缺少 OpenAI API 密钥 (OPENAI_API_KEY)")

        # 验证模型名称
        model = self.get("agent.model")
        if not model or not isinstance(model, str):
            errors.append("无效的模型名称")

        # 验证 token 数量
        max_tokens = self.get("agent.max_tokens")
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            errors.append("max_tokens 必须是正整数")

        # 验证温度参数
        temperature = self.get("agent.temperature")
        if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
            errors.append("temperature 必须在 0 到 2 之间")

        # 验证最大迭代次数
        max_iterations = self.get("agent.max_iterations")
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            errors.append("max_iterations 必须是正整数")

        # 验证 MCP 服务器配置
        if self.get("mcp.enabled", True):
            servers = self.get("mcp.servers", [])
            for i, server in enumerate(servers):
                if not server.get("name"):
                    errors.append(f"MCP 服务器 #{i+1} 缺少名称")
                if not server.get("command"):
                    errors.append(f"MCP 服务器 '{server.get('name', i+1)}' 缺少命令")

        # 验证工作目录
        workspace_path = self.get("workspace.path")
        if workspace_path:
            path = Path(workspace_path)
            if path.exists() and not path.is_dir():
                errors.append(f"工作目录路径不是目录: {workspace_path}")

        return errors

    def get_enabled_servers(self) -> List[Dict[str, Any]]:
        """
        获取所有启用的 MCP 服务器配置

        Returns:
            启用的服务器配置列表
        """
        servers = self.get("mcp.servers", [])
        return [s for s in servers if s.get("enabled", True)]

    def get_server_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称获取服务器配置

        Args:
            name: 服务器名称

        Returns:
            服务器配置，不存在则返回 None
        """
        servers = self.get("mcp.servers", [])
        for server in servers:
            if server.get("name") == name:
                return server
        return None

    def add_server(self, server_config: Dict[str, Any]) -> bool:
        """
        添加 MCP 服务器配置

        Args:
            server_config: 服务器配置字典

        Returns:
            是否添加成功

        Raises:
            ValueError: 服务器名称已存在
        """
        name = server_config.get("name")
        if not name:
            raise ValueError("服务器配置必须包含 name 字段")

        # 检查是否已存在
        if self.get_server_by_name(name):
            raise ValueError(f"服务器 '{name}' 已存在")

        # 标准化配置
        normalized = self._normalize_servers([server_config])
        if not normalized:
            raise ValueError("无效的服务器配置")

        # 添加到配置
        servers = self.get("mcp.servers", [])
        servers.append(normalized[0])
        self.set("mcp.servers", servers)
        return True

    def remove_server(self, name: str) -> bool:
        """
        移除 MCP 服务器

        Args:
            name: 服务器名称

        Returns:
            是否移除成功
        """
        servers = self.get("mcp.servers", [])
        original_count = len(servers)
        servers = [s for s in servers if s.get("name") != name]

        if len(servers) == original_count:
            return False  # 没有找到要移除的服务器

        self.set("mcp.servers", servers)
        return True

    def update_server(self, name: str, updates: Dict[str, Any]) -> bool:
        """
        更新 MCP 服务器配置

        Args:
            name: 服务器名称
            updates: 更新的配置项

        Returns:
            是否更新成功
        """
        servers = self.get("mcp.servers", [])
        for i, server in enumerate(servers):
            if server.get("name") == name:
                # 合并更新
                servers[i] = {**server, **updates}
                # 重新解析环境变量
                servers[i]["env"] = self._resolve_env_vars(servers[i].get("env", {}))
                self.set("mcp.servers", servers)
                return True
        return False

    def toggle_server(self, name: str, enabled: Optional[bool] = None) -> bool:
        """
        切换服务器启用状态

        Args:
            name: 服务器名称
            enabled: 目标状态，None 表示切换

        Returns:
            是否操作成功
        """
        server = self.get_server_by_name(name)
        if not server:
            return False

        current = server.get("enabled", True)
        new_state = not current if enabled is None else enabled
        return self.update_server(name, {"enabled": new_state})

    def validate_server_config(self, server_config: Dict[str, Any]) -> List[str]:
        """
        验证单个服务器配置

        Args:
            server_config: 服务器配置

        Returns:
            错误列表，空表示验证通过
        """
        errors = []
        name = server_config.get("name", "unknown")

        if not server_config.get("name"):
            errors.append(f"服务器缺少名称")
        if not server_config.get("command"):
            errors.append(f"服务器 '{name}' 缺少启动命令")

        # 检查命令是否存在
        import shutil
        command = server_config.get("command", "")
        if command and command not in ["npx", "node", "uvx"]:
            if not shutil.which(command):
                errors.append(f"服务器 '{name}' 的命令 '{command}' 未找到")

        return errors

    def get_server_names(self) -> List[str]:
        """
        获取所有服务器名称列表

        Returns:
            服务器名称列表
        """
        servers = self.get("mcp.servers", [])
        return [s.get("name", "") for s in servers if s.get("name")]

    def save(self, config_path: Optional[str] = None) -> None:
        """
        保存配置到文件

        Args:
            config_path: 配置文件路径（可选，默认使用加载时的路径）
        
        Raises:
            ValueError: 没有指定config_path且没有加载过配置文件
        """
        # 使用提供的路径或存储的路径
        save_path = config_path or self._config_path
        if not save_path:
            raise ValueError("没有指定配置文件路径，且没有加载过配置文件")
        
        # 创建保存用的配置副本（排除敏感信息）
        save_config = self._config.copy()

        # 隐藏 API 密钥
        if "api" in save_config:
            api_config = save_config["api"].copy()
            if "anthropic" in api_config:
                api_config["anthropic"] = api_config["anthropic"].copy()
                if api_config["anthropic"].get("api_key"):
                    api_config["anthropic"]["api_key"] = "***"
            if "openai" in api_config:
                api_config["openai"] = api_config["openai"].copy()
                if api_config["openai"].get("api_key"):
                    api_config["openai"]["api_key"] = "***"
            save_config["api"] = api_config

        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(save_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # 属性访问器
    @property
    def agent(self) -> Dict[str, Any]:
        """获取智能体配置"""
        return self._config["agent"]

    @property
    def mcp(self) -> Dict[str, Any]:
        """获取 MCP 配置"""
        return self._config["mcp"]

    @property
    def workspace(self) -> Dict[str, Any]:
        """获取工作目录配置"""
        return self._config["workspace"]

    @property
    def ui(self) -> Dict[str, Any]:
        """获取 UI 配置"""
        return self._config["ui"]

    @property
    def logging(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self._config["logging"]

    @property
    def cli(self) -> Dict[str, Any]:
        """获取 CLI 配置"""
        return self._config["cli"]

    @property
    def api(self) -> Dict[str, Any]:
        """获取 API 配置"""
        return self._config["api"]

    @property
    def features(self) -> Dict[str, Any]:
        """获取功能配置"""
        return self._config["features"]

    @property
    def advanced(self) -> Dict[str, Any]:
        """获取高级配置"""
        return self._config["advanced"]

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        Returns:
            配置字典的副本
        """
        return self._config.copy()

    def __repr__(self) -> str:
        """返回配置的字符串表示"""
        return f"Config(provider={self.get('agent.provider')}, model={self.get('agent.model')})"
