"""
MCP服务器安装器模块

提供自动发现、依赖检查、安装和版本管理功能。
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich import box


class DependencyStatus(Enum):
    """依赖状态"""
    INSTALLED = "已安装"
    NOT_FOUND = "未找到"
    VERSION_MISMATCH = "版本不匹配"


@dataclass
class Dependency:
    """依赖信息"""
    name: str
    required_version: Optional[str] = None
    installed_version: Optional[str] = None
    status: DependencyStatus = DependencyStatus.NOT_FOUND
    command: Optional[str] = None
    install_url: Optional[str] = None


@dataclass
class PackageInfo:
    """包信息"""
    name: str
    version: str
    description: str
    downloads: int = 0
    repository: Optional[str] = None
    homepage: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    score: float = 0.0
    source: str = "npm"  # npm or github


@dataclass
class InstallResult:
    """安装结果"""
    package: str
    success: bool
    version: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0


class DependencyChecker:
    """依赖检查器"""
    
    def __init__(self, console: Optional[Console] = None):
        """
        初始化依赖检查器
        
        Args:
            console: Rich控制台
        """
        self.console = console or Console()
    
    def check_node(self) -> Dependency:
        """检查Node.js"""
        dep = Dependency(
            name="Node.js",
            required_version=">=16.0.0",
            command="node",
            install_url="https://nodejs.org/",
        )
        
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip().lstrip('v')
                dep.installed_version = version
                dep.status = DependencyStatus.INSTALLED
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return dep
    
    def check_npm(self) -> Dependency:
        """检查npm"""
        dep = Dependency(
            name="npm",
            required_version=">=8.0.0",
            command="npm",
            install_url="https://nodejs.org/",
        )
        
        try:
            # 在Windows上需要使用shell=True
            result = subprocess.run(
                ["npm", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=True,  # Windows兼容性
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                dep.installed_version = version
                dep.status = DependencyStatus.INSTALLED
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            # 如果subprocess失败，尝试使用shutil.which检查
            if shutil.which("npm"):
                dep.status = DependencyStatus.INSTALLED
                # 尝试再次获取版本
                try:
                    result = subprocess.run(
                        "npm --version",
                        capture_output=True,
                        text=True,
                        timeout=5,
                        shell=True,
                    )
                    if result.returncode == 0:
                        dep.installed_version = result.stdout.strip()
                except:
                    pass
        
        return dep
    
    def check_npx(self) -> Dependency:
        """检查npx"""
        dep = Dependency(
            name="npx",
            command="npx",
            install_url="https://nodejs.org/",
        )
        
        if shutil.which("npx"):
            dep.status = DependencyStatus.INSTALLED
            try:
                result = subprocess.run(
                    ["npx", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    dep.installed_version = result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        return dep
    
    def check_python(self) -> Dependency:
        """检查Python"""
        import sys
        
        dep = Dependency(
            name="Python",
            required_version=">=3.8.0",
            command="python",
        )
        
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        dep.installed_version = version
        dep.status = DependencyStatus.INSTALLED
        
        return dep
    
    def check_all(self) -> List[Dependency]:
        """检查所有依赖"""
        return [
            self.check_node(),
            self.check_npm(),
            self.check_npx(),
            self.check_python(),
        ]
    
    def display_status(self, dependencies: Optional[List[Dependency]] = None) -> None:
        """
        显示依赖状态
        
        Args:
            dependencies: 依赖列表，为None则检查所有
        """
        if dependencies is None:
            dependencies = self.check_all()
        
        table = Table(
            title="[bold cyan]系统依赖检查[/]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("依赖", style="cyan", width=12)
        table.add_column("状态", width=10)
        table.add_column("已安装版本", width=15)
        table.add_column("要求版本", width=15)
        table.add_column("安装地址", width=30)
        
        for dep in dependencies:
            if dep.status == DependencyStatus.INSTALLED:
                status = "[green]✓ 已安装[/]"
            else:
                status = "[red]✗ 未安装[/]"
            
            table.add_row(
                dep.name,
                status,
                dep.installed_version or "-",
                dep.required_version or "-",
                dep.install_url or "-",
            )
        
        self.console.print(table)
        
        # 检查是否有缺失依赖
        missing = [d for d in dependencies if d.status != DependencyStatus.INSTALLED]
        if missing:
            self.console.print("\n[yellow]警告: 以下依赖缺失，可能影响功能:[/]")
            for dep in missing:
                self.console.print(f"  • {dep.name}: {dep.install_url}")


class PackageDiscovery:
    """包发现器"""
    
    NPM_REGISTRY = "https://registry.npmjs.org"
    NPM_SEARCH = "https://registry.npmjs.com/-/v1/search"
    GITHUB_API = "https://api.github.com/search/repositories"
    
    def __init__(self, console: Optional[Console] = None):
        """
        初始化包发现器
        
        Args:
            console: Rich控制台
        """
        self.console = console or Console()
        self._cache: Dict[str, List[PackageInfo]] = {}
    
    async def discover_npm_packages(
        self,
        query: str = "@modelcontextprotocol/server-",
        limit: int = 50,
    ) -> List[PackageInfo]:
        """
        从npm registry发现包
        
        Args:
            query: 搜索关键词
            limit: 结果数量限制
            
        Returns:
            包信息列表
        """
        # 检查缓存
        cache_key = f"npm:{query}:{limit}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        packages = []
        
        try:
            async with aiohttp.ClientSession() as session:
                # 搜索包
                params = {
                    "text": query,
                    "size": limit,
                }
                
                async with session.get(self.NPM_SEARCH, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        for item in data.get("objects", []):
                            pkg = item.get("package", {})
                            
                            # 计算评分
                            score_data = item.get("score", {})
                            final_score = score_data.get("final", 0.0)
                            
                            package_info = PackageInfo(
                                name=pkg.get("name", ""),
                                version=pkg.get("version", ""),
                                description=pkg.get("description", ""),
                                repository=pkg.get("links", {}).get("repository", ""),
                                homepage=pkg.get("links", {}).get("homepage", ""),
                                keywords=pkg.get("keywords", []),
                                score=final_score,
                                source="npm",
                            )
                            
                            # 获取下载量
                            downloads = await self._get_npm_downloads(
                                session, package_info.name
                            )
                            package_info.downloads = downloads
                            
                            packages.append(package_info)
        
        except Exception as e:
            self.console.print(f"[red]搜索npm包失败: {e}[/]")
        
        # 按评分和下载量排序
        packages.sort(key=lambda p: (p.score, p.downloads), reverse=True)
        
        # 缓存结果
        self._cache[cache_key] = packages
        
        return packages
    
    async def _get_npm_downloads(
        self,
        session: aiohttp.ClientSession,
        package_name: str,
    ) -> int:
        """
        获取npm包的下载量
        
        Args:
            session: aiohttp会话
            package_name: 包名
            
        Returns:
            最近一周的下载量
        """
        try:
            url = f"https://api.npmjs.org/downloads/point/last-week/{package_name}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("downloads", 0)
        except:
            pass
        
        return 0
    
    async def discover_github_repos(
        self,
        query: str = "mcp server",
        limit: int = 30,
    ) -> List[PackageInfo]:
        """
        从GitHub发现仓库
        
        Args:
            query: 搜索关键词
            limit: 结果数量限制
            
        Returns:
            包信息列表
        """
        # 检查缓存
        cache_key = f"github:{query}:{limit}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        packages = []
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": limit,
                }
                
                headers = {}
                # 如果有GitHub token，使用它以提高rate limit
                github_token = os.getenv("GITHUB_TOKEN")
                if github_token:
                    headers["Authorization"] = f"token {github_token}"
                
                async with session.get(
                    self.GITHUB_API,
                    params=params,
                    headers=headers,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        for item in data.get("items", []):
                            # 计算评分（基于stars和更新时间）
                            stars = item.get("stargazers_count", 0)
                            score = min(stars / 100.0, 1.0)  # 归一化到0-1
                            
                            package_info = PackageInfo(
                                name=item.get("full_name", ""),
                                version="",  # GitHub没有版本信息
                                description=item.get("description", ""),
                                repository=item.get("html_url", ""),
                                homepage=item.get("homepage", ""),
                                keywords=item.get("topics", []),
                                downloads=stars,  # 用stars代替下载量
                                score=score,
                                source="github",
                            )
                            
                            packages.append(package_info)
        
        except Exception as e:
            self.console.print(f"[red]搜索GitHub仓库失败: {e}[/]")
        
        # 缓存结果
        self._cache[cache_key] = packages
        
        return packages
    
    async def get_package_metadata(self, package_name: str) -> Optional[PackageInfo]:
        """
        获取包的详细元数据
        
        Args:
            package_name: 包名
            
        Returns:
            包信息
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.NPM_REGISTRY}/{package_name}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        latest_version = data.get("dist-tags", {}).get("latest", "")
                        version_data = data.get("versions", {}).get(latest_version, {})
                        
                        return PackageInfo(
                            name=package_name,
                            version=latest_version,
                            description=data.get("description", ""),
                            repository=data.get("repository", {}).get("url", ""),
                            homepage=data.get("homepage", ""),
                            keywords=data.get("keywords", []),
                            source="npm",
                        )
        except Exception as e:
            self.console.print(f"[red]获取包元数据失败: {e}[/]")
        
        return None
    
    def display_packages(self, packages: List[PackageInfo]) -> None:
        """
        显示包列表
        
        Args:
            packages: 包信息列表
        """
        if not packages:
            self.console.print("[yellow]未找到包[/]")
            return
        
        table = Table(
            title=f"[bold cyan]发现的MCP服务器 ({len(packages)})[/]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("名称", style="green", width=35)
        table.add_column("版本", width=12)
        table.add_column("描述", width=40)
        table.add_column("来源", width=8)
        
        for pkg in packages[:20]:  # 只显示前20个
            desc = pkg.description[:40] + "..." if len(pkg.description) > 40 else pkg.description
            table.add_row(
                pkg.name,
                pkg.version or "-",
                desc or "-",
                pkg.source,
            )
        
        self.console.print(table)
        
        if len(packages) > 20:
            self.console.print(f"\n[dim]还有 {len(packages) - 20} 个包未显示[/]")


class MCPInstaller:
    """MCP安装器"""
    
    def __init__(self, console: Optional[Console] = None):
        """
        初始化安装器
        
        Args:
            console: Rich控制台
        """
        self.console = console or Console()
        self.dependency_checker = DependencyChecker(console)
    
    def check_prerequisites(self) -> bool:
        """
        检查前置条件
        
        Returns:
            是否满足前置条件
        """
        deps = self.dependency_checker.check_all()
        
        # 检查Node.js和npm
        node_ok = any(d.name == "Node.js" and d.status == DependencyStatus.INSTALLED for d in deps)
        npm_ok = any(d.name == "npm" and d.status == DependencyStatus.INSTALLED for d in deps)
        
        if not (node_ok and npm_ok):
            self.console.print("[red]错误: 缺少必需的依赖[/]")
            self.dependency_checker.display_status(deps)
            return False
        
        return True
    
    async def install_package(
        self,
        package_name: str,
        global_install: bool = True,
        show_progress: bool = True,
    ) -> InstallResult:
        """
        安装npm包
        
        Args:
            package_name: 包名
            global_install: 是否全局安装
            show_progress: 是否显示进度
            
        Returns:
            安装结果
        """
        start_time = datetime.now()
        
        # 构建命令（Windows需要使用shell）
        if global_install:
            cmd = f"npm install -g {package_name}"
        else:
            cmd = f"npm install {package_name}"
        
        try:
            if show_progress:
                with self.console.status(f"[cyan]正在安装 {package_name}...[/]"):
                    process = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    
                    stdout, stderr = await process.communicate()
            else:
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                
                stdout, stderr = await process.communicate()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if process.returncode == 0:
                # 提取版本信息
                version = self._extract_version(stdout.decode())
                
                return InstallResult(
                    package=package_name,
                    success=True,
                    version=version,
                    duration=duration,
                )
            else:
                error_msg = stderr.decode()[:200]
                return InstallResult(
                    package=package_name,
                    success=False,
                    error=error_msg,
                    duration=duration,
                )
        
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return InstallResult(
                package=package_name,
                success=False,
                error=str(e),
                duration=duration,
            )
    
    def _extract_version(self, output: str) -> Optional[str]:
        """
        从npm输出中提取版本号
        
        Args:
            output: npm输出
            
        Returns:
            版本号
        """
        # 匹配 package@version 格式
        match = re.search(r'(\S+)@([\d.]+)', output)
        if match:
            return match.group(2)
        return None
    
    async def batch_install(
        self,
        packages: List[str],
        global_install: bool = True,
    ) -> List[InstallResult]:
        """
        批量安装包
        
        Args:
            packages: 包名列表
            global_install: 是否全局安装
            
        Returns:
            安装结果列表
        """
        results = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task(
                "[cyan]批量安装中...",
                total=len(packages),
            )
            
            for package in packages:
                progress.update(task, description=f"[cyan]安装 {package}...")
                
                result = await self.install_package(
                    package,
                    global_install=global_install,
                    show_progress=False,
                )
                results.append(result)
                
                progress.advance(task)
        
        # 显示结果摘要
        self._display_install_summary(results)
        
        return results
    
    def _display_install_summary(self, results: List[InstallResult]) -> None:
        """
        显示安装摘要
        
        Args:
            results: 安装结果列表
        """
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        
        self.console.print(f"\n[bold cyan]安装完成:[/]")
        self.console.print(f"  • 成功: [green]{success_count}[/]")
        self.console.print(f"  • 失败: [red]{fail_count}[/]")
        
        if fail_count > 0:
            self.console.print("\n[yellow]失败的包:[/]")
            for result in results:
                if not result.success:
                    error = result.error[:50] + "..." if result.error and len(result.error) > 50 else result.error
                    self.console.print(f"  • {result.package}: {error}")
    
    async def uninstall_package(self, package_name: str, global_uninstall: bool = True) -> bool:
        """
        卸载npm包
        
        Args:
            package_name: 包名
            global_uninstall: 是否全局卸载
            
        Returns:
            是否成功
        """
        # 构建命令（Windows需要使用shell）
        if global_uninstall:
            cmd = f"npm uninstall -g {package_name}"
        else:
            cmd = f"npm uninstall {package_name}"
        
        try:
            with self.console.status(f"[cyan]正在卸载 {package_name}...[/]"):
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                
                await process.communicate()
            
            return process.returncode == 0
        
        except Exception as e:
            self.console.print(f"[red]卸载失败: {e}[/]")
            return False


class VersionManager:
    """版本管理器"""
    
    def __init__(self, console: Optional[Console] = None):
        """
        初始化版本管理器
        
        Args:
            console: Rich控制台
        """
        self.console = console or Console()
        self.discovery = PackageDiscovery(console)
    
    async def check_updates(self, package_name: str) -> Optional[Tuple[str, str]]:
        """
        检查包更新
        
        Args:
            package_name: 包名
            
        Returns:
            (当前版本, 最新版本) 或 None
        """
        try:
            # 获取已安装版本
            result = subprocess.run(
                ["npm", "list", "-g", package_name, "--depth=0", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                dependencies = data.get("dependencies", {})
                current_version = dependencies.get(package_name, {}).get("version")
                
                if current_version:
                    # 获取最新版本
                    metadata = await self.discovery.get_package_metadata(package_name)
                    if metadata and metadata.version:
                        return (current_version, metadata.version)
        
        except Exception as e:
            self.console.print(f"[red]检查更新失败: {e}[/]")
        
        return None
    
    async def check_all_updates(self, packages: List[str]) -> Dict[str, Tuple[str, str]]:
        """
        检查多个包的更新
        
        Args:
            packages: 包名列表
            
        Returns:
            {包名: (当前版本, 最新版本)}
        """
        updates = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task("[cyan]检查更新中...", total=len(packages))
            
            for package in packages:
                result = await self.check_updates(package)
                if result:
                    current, latest = result
                    if current != latest:
                        updates[package] = (current, latest)
                
                progress.advance(task)
        
        return updates
    
    def display_updates(self, updates: Dict[str, Tuple[str, str]]) -> None:
        """
        显示可用更新
        
        Args:
            updates: {包名: (当前版本, 最新版本)}
        """
        if not updates:
            self.console.print("[green]所有包都是最新版本[/]")
            return
        
        table = Table(
            title=f"[bold cyan]可用更新 ({len(updates)})[/]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("包名", style="green", width=35)
        table.add_column("当前版本", width=15)
        table.add_column("最新版本", width=15, style="yellow")
        
        for package, (current, latest) in updates.items():
            table.add_row(package, current, latest)
        
        self.console.print(table)
    
    async def update_package(
        self,
        package_name: str,
        version: Optional[str] = None,
    ) -> bool:
        """
        更新包到指定版本
        
        Args:
            package_name: 包名
            version: 目标版本，None表示最新版本
            
        Returns:
            是否成功
        """
        installer = MCPInstaller(self.console)
        
        # 构建包名@版本
        target = package_name
        if version:
            target = f"{package_name}@{version}"
        
        result = await installer.install_package(target, global_install=True)
        
        if result.success:
            self.console.print(f"[green]✓ {package_name} 已更新到 {result.version or version or '最新版本'}[/]")
            return True
        else:
            self.console.print(f"[red]✗ 更新失败: {result.error}[/]")
            return False
    
    async def update_all(self, packages: List[str]) -> Dict[str, bool]:
        """
        更新所有包
        
        Args:
            packages: 包名列表
            
        Returns:
            {包名: 是否成功}
        """
        results = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task("[cyan]更新中...", total=len(packages))
            
            for package in packages:
                progress.update(task, description=f"[cyan]更新 {package}...")
                success = await self.update_package(package)
                results[package] = success
                progress.advance(task)
        
        # 显示摘要
        success_count = sum(1 for s in results.values() if s)
        self.console.print(f"\n[bold cyan]更新完成:[/]")
        self.console.print(f"  • 成功: [green]{success_count}[/]")
        self.console.print(f"  • 失败: [red]{len(packages) - success_count}[/]")
        
        return results
