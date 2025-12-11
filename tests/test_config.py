"""
配置模块测试
"""

import pytest
from pathlib import Path

from mcp_agent.config import Config


def test_default_config():
    """测试默认配置"""
    config = Config()
    
    assert config.get("agent.model") == "claude-3-5-sonnet-20241022"
    assert config.get("agent.max_tokens") == 4096
    assert config.get("agent.temperature") == 0.7


def test_config_get():
    """测试配置获取"""
    config = Config()
    
    # 测试存在的键
    assert config.get("agent.model") is not None
    
    # 测试不存在的键
    assert config.get("nonexistent.key") is None
    assert config.get("nonexistent.key", "default") == "default"


def test_config_set():
    """测试配置设置"""
    config = Config()
    
    config.set("agent.model", "test-model")
    assert config.get("agent.model") == "test-model"
    
    config.set("new.nested.key", "value")
    assert config.get("new.nested.key") == "value"


def test_config_properties():
    """测试配置属性"""
    config = Config()
    
    assert isinstance(config.agent, dict)
    assert isinstance(config.mcp, dict)
    assert isinstance(config.logging, dict)
    assert isinstance(config.cli, dict)
    assert isinstance(config.api, dict)
    assert isinstance(config.features, dict)
    assert isinstance(config.advanced, dict)


def test_config_validation():
    """测试配置验证"""
    config = Config()
    
    # 默认配置可能缺少API密钥
    errors = config.validate()
    # 可能有错误（如缺少API密钥）
    assert isinstance(errors, list)