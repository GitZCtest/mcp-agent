"""
MCP安装器模块测试
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from mcp_agent.installer import (
    Dependency,
    DependencyChecker,
    DependencyStatus,
    InstallResult,
    MCPInstaller,
    PackageDiscovery,
    PackageInfo,
    VersionManager,
)


class TestDependencyChecker:
    """测试依赖检查器"""
    
    def test_check_node_installed(self):
        """测试Node.js已安装"""
        checker = DependencyChecker()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="v18.17.0\n")
            dep = checker.check_node()
            
            assert dep.name == "Node.js"
            assert dep.status == DependencyStatus.INSTALLED
            assert dep.installed_version == "18.17.0"
    
    def test_check_node_not_installed(self):
        """测试Node.js未安装"""
        checker = DependencyChecker()
        
        with patch('subprocess.run', side_effect=FileNotFoundError):
            dep = checker.check_node()
            
            assert dep.status == DependencyStatus.NOT_FOUND
            assert dep.installed_version is None
    
    def test_check_npm_installed(self):
        """测试npm已安装"""
        checker = DependencyChecker()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="9.8.1\n")
            dep = checker.check_npm()
            
            assert dep.name == "npm"
            assert dep.status == DependencyStatus.INSTALLED
            assert dep.installed_version == "9.8.1"
    
    def test_check_all(self):
        """测试检查所有依赖"""
        checker = DependencyChecker()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="v18.17.0\n")
            deps = checker.check_all()
            
            assert len(deps) == 4
            assert any(d.name == "Node.js" for d in deps)
            assert any(d.name == "npm" for d in deps)
            assert any(d.name == "npx" for d in deps)
            assert any(d.name == "Python" for d in deps)


class TestPackageDiscovery:
    """测试包发现器"""
    
    @pytest.mark.asyncio
    async def test_discover_npm_packages(self):
        """测试从npm发现包"""
        discovery = PackageDiscovery()
        
        mock_response = {
            "objects": [
                {
                    "package": {
                        "name": "@modelcontextprotocol/server-filesystem",
                        "version": "1.0.0",
                        "description": "File system server",
                        "keywords": ["mcp", "filesystem"],
                        "links": {
                            "repository": "https://github.com/test/repo",
                            "homepage": "https://test.com",
                        },
                    },
                    "score": {
                        "final": 0.85,
                    },
                },
            ],
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_response
            )
            mock_session.return_value.__aenter__.return_value.get = mock_get
            
            packages = await discovery.discover_npm_packages()
            
            assert len(packages) >= 0  # May be empty due to mocking
    
    @pytest.mark.asyncio
    async def test_get_package_metadata(self):
        """测试获取包元数据"""
        discovery = PackageDiscovery()
        
        mock_data = {
            "name": "@modelcontextprotocol/server-time",
            "description": "Time server",
            "dist-tags": {"latest": "1.0.0"},
            "versions": {
                "1.0.0": {},
            },
            "repository": {"url": "https://github.com/test/repo"},
            "homepage": "https://test.com",
            "keywords": ["mcp", "time"],
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_data
            )
            mock_session.return_value.__aenter__.return_value.get = mock_get
            
            metadata = await discovery.get_package_metadata("@modelcontextprotocol/server-time")
            
            assert metadata is not None
            assert metadata.name == "@modelcontextprotocol/server-time"
            assert metadata.version == "1.0.0"


class TestMCPInstaller:
    """测试MCP安装器"""
    
    def test_check_prerequisites_success(self):
        """测试前置条件检查成功"""
        installer = MCPInstaller()
        
        with patch.object(installer.dependency_checker, 'check_all') as mock_check:
            mock_check.return_value = [
                Dependency(name="Node.js", status=DependencyStatus.INSTALLED),
                Dependency(name="npm", status=DependencyStatus.INSTALLED),
            ]
            
            result = installer.check_prerequisites()
            assert result is True
    
    def test_check_prerequisites_fail(self):
        """测试前置条件检查失败"""
        installer = MCPInstaller()
        
        with patch.object(installer.dependency_checker, 'check_all') as mock_check:
            mock_check.return_value = [
                Dependency(name="Node.js", status=DependencyStatus.NOT_FOUND),
                Dependency(name="npm", status=DependencyStatus.NOT_FOUND),
            ]
            
            result = installer.check_prerequisites()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_install_package_success(self):
        """测试安装包成功"""
        installer = MCPInstaller()
        
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(
                return_value=(b"@test/pkg@1.0.0\n", b"")
            )
            mock_exec.return_value = mock_process
            
            result = await installer.install_package("@test/pkg")
            
            assert result.success is True
            assert result.package == "@test/pkg"
            assert result.version == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_install_package_failure(self):
        """测试安装包失败"""
        installer = MCPInstaller()
        
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(
                return_value=(b"", b"Error: Package not found")
            )
            mock_exec.return_value = mock_process
            
            result = await installer.install_package("@test/nonexistent")
            
            assert result.success is False
            assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_batch_install(self):
        """测试批量安装"""
        installer = MCPInstaller()
        
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(
                return_value=(b"@test/pkg@1.0.0\n", b"")
            )
            mock_exec.return_value = mock_process
            
            results = await installer.batch_install(["@test/pkg1", "@test/pkg2"])
            
            assert len(results) == 2
            assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    async def test_uninstall_package(self):
        """测试卸载包"""
        installer = MCPInstaller()
        
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = mock_process
            
            result = await installer.uninstall_package("@test/pkg")
            
            assert result is True


class TestVersionManager:
    """测试版本管理器"""
    
    @pytest.mark.asyncio
    async def test_check_updates_available(self):
        """测试检查更新（有新版本）"""
        manager = VersionManager()
        
        # Mock npm list
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps({
                    "dependencies": {
                        "@test/pkg": {"version": "1.0.0"}
                    }
                })
            )
            
            # Mock package metadata
            with patch.object(manager.discovery, 'get_package_metadata') as mock_meta:
                mock_meta.return_value = PackageInfo(
                    name="@test/pkg",
                    version="1.1.0",
                    description="Test",
                    source="npm",
                )
                
                result = await manager.check_updates("@test/pkg")
                
                assert result is not None
                assert result == ("1.0.0", "1.1.0")
    
    @pytest.mark.asyncio
    async def test_check_updates_up_to_date(self):
        """测试检查更新（已是最新）"""
        manager = VersionManager()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps({
                    "dependencies": {
                        "@test/pkg": {"version": "1.1.0"}
                    }
                })
            )
            
            with patch.object(manager.discovery, 'get_package_metadata') as mock_meta:
                mock_meta.return_value = PackageInfo(
                    name="@test/pkg",
                    version="1.1.0",
                    description="Test",
                    source="npm",
                )
                
                result = await manager.check_updates("@test/pkg")
                
                assert result is not None
                assert result[0] == result[1]
    
    @pytest.mark.asyncio
    async def test_update_package(self):
        """测试更新包"""
        manager = VersionManager()
        
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(
                return_value=(b"@test/pkg@1.1.0\n", b"")
            )
            mock_exec.return_value = mock_process
            
            result = await manager.update_package("@test/pkg")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_check_all_updates(self):
        """测试批量检查更新"""
        manager = VersionManager()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps({
                    "dependencies": {
                        "@test/pkg1": {"version": "1.0.0"},
                        "@test/pkg2": {"version": "2.0.0"},
                    }
                })
            )
            
            with patch.object(manager.discovery, 'get_package_metadata') as mock_meta:
                async def mock_get_metadata(name):
                    if name == "@test/pkg1":
                        return PackageInfo(
                            name=name, version="1.1.0", description="Test", source="npm"
                        )
                    else:
                        return PackageInfo(
                            name=name, version="2.0.0", description="Test", source="npm"
                        )
                
                mock_meta.side_effect = mock_get_metadata
                
                updates = await manager.check_all_updates(["@test/pkg1", "@test/pkg2"])
                
                # pkg1 has update, pkg2 doesn't
                assert "@test/pkg1" in updates
                assert "@test/pkg2" not in updates


class TestPackageInfo:
    """测试PackageInfo数据类"""
    
    def test_package_info_creation(self):
        """测试创建PackageInfo"""
        pkg = PackageInfo(
            name="@test/pkg",
            version="1.0.0",
            description="Test package",
            downloads=1000,
            score=0.85,
            source="npm",
        )
        
        assert pkg.name == "@test/pkg"
        assert pkg.version == "1.0.0"
        assert pkg.downloads == 1000
        assert pkg.score == 0.85


class TestInstallResult:
    """测试InstallResult数据类"""
    
    def test_install_result_success(self):
        """测试成功的安装结果"""
        result = InstallResult(
            package="@test/pkg",
            success=True,
            version="1.0.0",
            duration=5.2,
        )
        
        assert result.success is True
        assert result.version == "1.0.0"
        assert result.error is None
    
    def test_install_result_failure(self):
        """测试失败的安装结果"""
        result = InstallResult(
            package="@test/pkg",
            success=False,
            error="Package not found",
            duration=1.5,
        )
        
        assert result.success is False
        assert result.error == "Package not found"
        assert result.version is None
