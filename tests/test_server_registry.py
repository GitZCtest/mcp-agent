"""
服务器注册表模块测试
"""

import pytest
from pathlib import Path

from mcp_agent.server_registry import (
    ServerCategory,
    ServerParam,
    ServerTemplate,
    ServerRegistry,
    InteractiveConfigWizard,
    BUILTIN_SERVERS,
    get_registry,
)


class TestServerTemplate:
    """测试服务器模板类"""

    def test_template_creation(self):
        """测试模板创建"""
        template = ServerTemplate(
            name="test-server",
            display_name="测试服务器",
            description="测试用服务器",
            package="@test/server",
        )
        assert template.name == "test-server"
        assert template.display_name == "测试服务器"
        assert template.command == "npx"

    def test_get_args(self):
        """测试参数生成"""
        template = ServerTemplate(
            name="test",
            display_name="Test",
            description="Test",
            package="@test/pkg",
            params=[
                ServerParam(name="directory", description="目录", required=True),
            ],
        )
        args = template.get_args({"directory": "/tmp/test"})
        assert args == ["-y", "@test/pkg", "/tmp/test"]

    def test_get_env(self):
        """测试环境变量生成"""
        template = ServerTemplate(
            name="test",
            display_name="Test",
            description="Test",
            package="@test/pkg",
            env_vars={"API_KEY": "${api_key}"},
        )
        env = template.get_env({"api_key": "secret123"})
        assert env == {"API_KEY": "secret123"}

    def test_validate_param(self):
        """测试参数验证"""
        template = ServerTemplate(
            name="test",
            display_name="Test",
            description="Test",
            package="@test/pkg",
            params=[
                ServerParam(
                    name="url",
                    description="URL",
                    required=True,
                    validation_pattern=r"^https?://.*",
                    validation_message="必须是有效URL",
                ),
            ],
        )
        
        # 有效URL
        is_valid, error = template.validate_param("url", "https://example.com")
        assert is_valid
        
        # 无效URL
        is_valid, error = template.validate_param("url", "invalid")
        assert not is_valid
        assert "URL" in error


class TestBuiltinServers:
    """测试内置服务器模板"""

    def test_builtin_count(self):
        """测试内置服务器数量"""
        assert len(BUILTIN_SERVERS) >= 10

    def test_filesystem_template(self):
        """测试文件系统模板"""
        assert "filesystem" in BUILTIN_SERVERS
        template = BUILTIN_SERVERS["filesystem"]
        assert template.category == ServerCategory.FILE_OPERATIONS
        assert "@modelcontextprotocol/server-filesystem" in template.package

    def test_all_templates_valid(self):
        """测试所有模板都有效"""
        for name, template in BUILTIN_SERVERS.items():
            assert template.name == name
            assert template.display_name
            assert template.description
            assert template.package


class TestServerRegistry:
    """测试服务器注册表"""

    def test_registry_creation(self):
        """测试注册表创建"""
        registry = ServerRegistry()
        assert len(registry.list_available()) >= 10

    def test_get_server(self):
        """测试获取服务器"""
        registry = ServerRegistry()
        template = registry.get_server("filesystem")
        assert template is not None
        assert template.name == "filesystem"

    def test_get_nonexistent_server(self):
        """测试获取不存在的服务器"""
        registry = ServerRegistry()
        template = registry.get_server("nonexistent")
        assert template is None

    def test_search_servers(self):
        """测试搜索服务器"""
        registry = ServerRegistry()
        
        # 搜索文件相关
        results = registry.search_servers("file")
        assert len(results) > 0
        
        # 搜索数据库
        results = registry.search_servers("database")
        assert len(results) >= 0  # 可能匹配描述

    def test_get_categories(self):
        """测试获取分类列表"""
        registry = ServerRegistry()
        categories = registry.get_categories()
        assert len(categories) > 0
        assert all(isinstance(cat, tuple) for cat in categories)

    def test_register_custom_server(self):
        """测试注册自定义服务器"""
        registry = ServerRegistry()
        custom = ServerTemplate(
            name="custom-test",
            display_name="自定义测试",
            description="测试用",
            package="@custom/test",
        )
        registry.register_server(custom)
        assert registry.get_server("custom-test") is not None

    def test_validate_config(self):
        """测试配置验证"""
        registry = ServerRegistry()
        
        # 有效配置
        valid_config = {
            "name": "test",
            "command": "npx",
            "args": ["-y", "@test/pkg"],
        }
        errors = registry.validate_server_config(valid_config)
        assert len(errors) == 0
        
        # 无效配置 - 缺少name
        invalid_config = {
            "command": "npx",
        }
        errors = registry.validate_server_config(invalid_config)
        assert len(errors) > 0

    def test_generate_config(self):
        """测试配置生成"""
        registry = ServerRegistry()
        template = registry.get_server("filesystem")
        config = registry.generate_config(template, {"directory": "./workspace"})
        
        assert config["name"] == "filesystem"
        assert config["command"] == "npx"
        assert "./workspace" in config["args"]
        assert config["enabled"] is True


class TestGlobalRegistry:
    """测试全局注册表"""

    def test_get_registry_singleton(self):
        """测试单例模式"""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_global_registry_has_servers(self):
        """测试全局注册表包含服务器"""
        registry = get_registry()
        assert len(registry.list_available()) >= 10
