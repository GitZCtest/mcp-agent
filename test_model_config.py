#!/usr/bin/env python3
"""
测试模型配置功能
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from mcp_agent.config import Config
from mcp_agent.agent import MCPAgent


def test_model_config():
    """测试模型配置功能"""
    print("=" * 60)
    print("测试模型配置功能")
    print("=" * 60)

    # 加载配置
    config = Config("config/config.yaml")

    # 创建智能体（不初始化，避免连接API）
    agent = MCPAgent(config)

    print("\n1. 测试获取当前配置")
    print("-" * 60)
    current_config = agent.get_model_config()
    for key, value in current_config.items():
        print(f"  {key}: {value}")

    print("\n2. 测试获取可用模型列表")
    print("-" * 60)
    models = agent.get_available_models()
    for provider, model_list in models.items():
        print(f"\n  {provider.upper()}:")
        for model in model_list:
            print(f"    • {model}")

    print("\n3. 测试更新温度参数")
    print("-" * 60)
    try:
        updated = agent.update_model_config(temperature=0.5)
        print(f"  ✓ 更新成功: {updated}")
        print(f"  当前温度: {agent.temperature}")
    except Exception as e:
        print(f"  ✗ 更新失败: {e}")

    print("\n4. 测试更新最大token数")
    print("-" * 60)
    try:
        updated = agent.update_model_config(max_tokens=4096)
        print(f"  ✓ 更新成功: {updated}")
        print(f"  当前max_tokens: {agent.max_tokens}")
    except Exception as e:
        print(f"  ✗ 更新失败: {e}")

    print("\n5. 测试更新最大迭代次数")
    print("-" * 60)
    try:
        updated = agent.update_model_config(max_iterations=15)
        print(f"  ✓ 更新成功: {updated}")
        print(f"  当前max_iterations: {agent.max_iterations}")
    except Exception as e:
        print(f"  ✗ 更新失败: {e}")

    print("\n6. 测试切换模型")
    print("-" * 60)
    try:
        updated = agent.update_model_config(model="gpt-4o")
        print(f"  ✓ 更新成功: {updated}")
        print(f"  当前模型: {agent.model}")
    except Exception as e:
        print(f"  ✗ 更新失败: {e}")

    print("\n7. 测试参数验证（温度超出范围）")
    print("-" * 60)
    try:
        agent.update_model_config(temperature=3.0)
        print("  ✗ 应该抛出异常但没有")
    except ValueError as e:
        print(f"  ✓ 正确捕获异常: {e}")

    print("\n8. 测试参数验证（负数token）")
    print("-" * 60)
    try:
        agent.update_model_config(max_tokens=-100)
        print("  ✗ 应该抛出异常但没有")
    except ValueError as e:
        print(f"  ✓ 正确捕获异常: {e}")

    print("\n9. 测试最终配置")
    print("-" * 60)
    final_config = agent.get_model_config()
    for key, value in final_config.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("✓ 所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_model_config()
