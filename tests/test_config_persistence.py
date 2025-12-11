"""
Test script to verify configuration persistence across add/remove operations.
This tests that server configurations are properly saved to disk.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_agent.config import Config
import yaml


def test_config_persistence():
    """Test that add_server and remove_server properly save to disk"""
    print("Testing configuration persistence...")
    
    # Create a temporary config file for testing
    test_config_path = Path(__file__).parent / "test_config_temp.yaml"
    
    try:
        # Create initial config file
        print("\nSetting up test environment...")
        initial_config = {
            "mcp": {
                "servers": []
            }
        }
        with open(test_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(initial_config, f)
        print(f"✓ Created test config file: {test_config_path}")
        
        # Initialize config with test file
        config = Config(str(test_config_path))
        
        # Test 1: Add a server
        print("\nTest 1: Adding server...")
        test_server = {
            "name": "test-server",
            "command": "npx",
            "args": ["-y", "@test/package"]
        }
        
        config.add_server(test_server)
        config.save()  # This is what CLI code should call
        
        # Verify it's in memory
        server = config.get_server_by_name("test-server")
        assert server is not None, "Server not found in memory after add"
        print("✓ Server added to memory successfully")
        
        # Verify it's on disk
        with open(test_config_path, 'r', encoding='utf-8') as f:
            disk_config = yaml.safe_load(f)
        
        servers_on_disk = disk_config.get("mcp", {}).get("servers", [])
        assert any(s.get("name") == "test-server" for s in servers_on_disk), \
            "Server not found on disk after save"
        print("✓ Server persisted to disk successfully")
        
        # Test 2: Load config from disk (simulating restart)
        print("\nTest 2: Loading config from disk (simulating restart)...")
        config2 = Config(str(test_config_path))
        server_after_reload = config2.get_server_by_name("test-server")
        assert server_after_reload is not None, "Server not found after reload"
        print("✓ Server loaded from disk successfully")
        
        # Test 3: Remove the server
        print("\nTest 3: Removing server...")
        result = config2.remove_server("test-server")
        assert result is True, "Remove server failed"
        config2.save()  # This is what CLI code should call
        
        # Verify it's gone from memory
        server = config2.get_server_by_name("test-server")
        assert server is None, "Server still in memory after remove"
        print("✓ Server removed from memory successfully")
        
        # Verify it's gone from disk
        with open(test_config_path, 'r', encoding='utf-8') as f:
            disk_config = yaml.safe_load(f)
        
        servers_on_disk = disk_config.get("mcp", {}).get("servers", [])
        assert not any(s.get("name") == "test-server" for s in servers_on_disk), \
            "Server still on disk after remove and save"
        print("✓ Server removal persisted to disk successfully")
        
        # Test 4: Verify removal persists across restart
        print("\nTest 4: Verifying removal persists across restart...")
        config3 = Config(str(test_config_path))
        server_after_reload = config3.get_server_by_name("test-server")
        assert server_after_reload is None, "Server found after reload (should be removed)"
        print("✓ Server removal persisted across restart")
        
        print("\n" + "="*50)
        print("All tests passed! ✓")
        print("Configuration persistence is working correctly.")
        print("="*50)
        
    finally:
        # Clean up test file
        if test_config_path.exists():
            test_config_path.unlink()
            print(f"\nCleaned up test file: {test_config_path}")


if __name__ == "__main__":
    test_config_persistence()
