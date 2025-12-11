"""
安全代码执行模块

提供在隔离环境中执行Python代码和Bash命令的功能。
包含多层安全机制：命令过滤、超时控制、资源限制等。
"""

import asyncio
import io
import os
import re
import signal
import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from mcp_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ExecutionStatus(Enum):
    """执行状态枚举"""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    RESOURCE_LIMIT = "resource_limit"


@dataclass
class ExecutionResult:
    """执行结果数据类"""
    status: ExecutionStatus
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    error_message: str = ""
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_value": str(self.return_value) if self.return_value is not None else None,
            "error_message": self.error_message,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }

    @property
    def success(self) -> bool:
        """是否执行成功"""
        return self.status == ExecutionStatus.SUCCESS


@dataclass
class SecurityConfig:
    """安全配置"""
    # Python执行限制
    python_timeout: float = 30.0
    python_max_output_size: int = 100000  # 100KB
    python_blocked_modules: Set[str] = field(default_factory=lambda: {
        "os.system", "os.popen", "os.spawn", "os.exec",
        "subprocess", "multiprocessing",
        "socket", "urllib", "requests", "httplib", "ftplib",
        "ctypes", "cffi",
        "pickle", "marshal", "shelve",
        "__import__", "importlib",
        "eval", "exec", "compile",
        "open",  # 文件操作需要特殊处理
    })
    python_allowed_builtins: Set[str] = field(default_factory=lambda: {
        "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
        "callable", "chr", "classmethod", "complex", "dict", "dir", "divmod",
        "enumerate", "filter", "float", "format", "frozenset", "getattr",
        "hasattr", "hash", "hex", "id", "int", "isinstance", "issubclass",
        "iter", "len", "list", "map", "max", "min", "next", "object", "oct",
        "ord", "pow", "print", "property", "range", "repr", "reversed", "round",
        "set", "setattr", "slice", "sorted", "staticmethod", "str", "sum",
        "super", "tuple", "type", "vars", "zip",
        "True", "False", "None",
    })

    # Bash执行限制
    bash_timeout: float = 30.0
    bash_max_output_size: int = 100000  # 100KB
    bash_blocked_commands: Set[str] = field(default_factory=lambda: {
        # 系统危险命令
        "rm", "rmdir", "del", "format", "fdisk", "mkfs",
        "dd", "shred", "wipe",
        # 权限相关
        "sudo", "su", "chmod", "chown", "chgrp",
        # 网络相关
        "curl", "wget", "nc", "netcat", "ncat",
        "ssh", "scp", "sftp", "ftp", "telnet",
        # 进程相关
        "kill", "killall", "pkill",
        # 系统修改
        "shutdown", "reboot", "halt", "poweroff",
        "systemctl", "service",
        # 用户管理
        "useradd", "userdel", "usermod", "passwd",
        "groupadd", "groupdel",
        # 包管理
        "apt", "apt-get", "yum", "dnf", "pacman", "pip", "npm",
        # 其他危险命令
        "eval", "exec", "source", ".",
        "crontab", "at",
        "mount", "umount",
        "iptables", "firewall-cmd",
    })
    bash_allowed_commands: Set[str] = field(default_factory=lambda: {
        # 文件查看
        "ls", "dir", "cat", "head", "tail", "less", "more",
        "find", "locate", "which", "whereis",
        "file", "stat", "wc", "du", "df",
        # 文本处理
        "grep", "awk", "sed", "cut", "sort", "uniq",
        "tr", "tee", "xargs",
        # 其他安全命令
        "echo", "printf", "date", "cal",
        "pwd", "cd", "basename", "dirname",
        "env", "printenv",
        "diff", "cmp", "comm",
        "tar", "gzip", "gunzip", "zip", "unzip",  # 仅在workspace内
        "python", "python3",  # 受限执行
        "node", "deno",  # 受限执行
    })

    # 工作目录限制
    workspace_dir: Optional[Path] = None
    allow_file_write: bool = False
    max_file_size: int = 10 * 1024 * 1024  # 10MB


class CodeExecutor:
    """
    安全代码执行器

    提供Python代码和Bash命令的安全执行环境。

    安全特性：
    - 命令白名单/黑名单过滤
    - 执行超时控制
    - 输出大小限制
    - 工作目录隔离
    - 危险模式检测
    """

    def __init__(
        self,
        workspace_dir: Optional[Union[str, Path]] = None,
        security_config: Optional[SecurityConfig] = None,
    ):
        """
        初始化代码执行器

        Args:
            workspace_dir: 工作目录路径，None则创建临时目录
            security_config: 安全配置，None则使用默认配置
        """
        self.security_config = security_config or SecurityConfig()

        # 设置工作目录
        if workspace_dir:
            self.workspace = Path(workspace_dir).resolve()
            self.workspace.mkdir(parents=True, exist_ok=True)
            self._temp_workspace = False
        else:
            self._temp_dir = tempfile.mkdtemp(prefix="mcp_executor_")
            self.workspace = Path(self._temp_dir)
            self._temp_workspace = True

        self.security_config.workspace_dir = self.workspace

        logger.info(f"代码执行器初始化完成，工作目录: {self.workspace}")

    # ==================== Python 执行 ====================

    async def execute_python(
        self,
        code: str,
        timeout: Optional[float] = None,
        globals_dict: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        在隔离环境中执行Python代码

        Args:
            code: 要执行的Python代码
            timeout: 超时时间（秒），None则使用默认值
            globals_dict: 额外的全局变量

        Returns:
            ExecutionResult: 执行结果
        """
        timeout = timeout or self.security_config.python_timeout
        start_time = datetime.now()

        # 安全检查
        security_check = self._check_python_security(code)
        if not security_check[0]:
            return ExecutionResult(
                status=ExecutionStatus.BLOCKED,
                error_message=security_check[1],
                metadata={"blocked_reason": security_check[1]}
            )

        # 准备执行环境
        safe_globals = self._create_safe_globals(globals_dict)

        # 捕获输出
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        result = ExecutionResult(status=ExecutionStatus.SUCCESS)

        try:
            # 使用asyncio在线程池中执行，支持超时
            loop = asyncio.get_event_loop()

            def execute_code():
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(code, safe_globals)
                return safe_globals.get("_result_", None)

            return_value = await asyncio.wait_for(
                loop.run_in_executor(None, execute_code),
                timeout=timeout
            )

            result.return_value = return_value
            result.stdout = self._truncate_output(stdout_capture.getvalue())
            result.stderr = self._truncate_output(stderr_capture.getvalue())

        except asyncio.TimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error_message = f"执行超时（{timeout}秒）"
            logger.warning(f"Python代码执行超时: {code[:100]}...")

        except Exception as e:
            result.status = ExecutionStatus.ERROR
            result.error_message = str(e)
            result.stderr = traceback.format_exc()
            logger.error(f"Python代码执行错误: {e}")

        finally:
            result.execution_time = (datetime.now() - start_time).total_seconds()
            result.stdout = self._truncate_output(stdout_capture.getvalue())
            result.stderr = self._truncate_output(stderr_capture.getvalue())

        return result

    def _check_python_security(self, code: str) -> Tuple[bool, str]:
        """
        检查Python代码安全性

        Args:
            code: Python代码

        Returns:
            (是否安全, 错误信息)
        """
        # 检查危险导入
        dangerous_imports = [
            r'\bimport\s+os\b',
            r'\bfrom\s+os\s+import\b',
            r'\bimport\s+subprocess\b',
            r'\bimport\s+socket\b',
            r'\bimport\s+requests\b',
            r'\bimport\s+urllib\b',
            r'\bimport\s+ctypes\b',
            r'\bimport\s+pickle\b',
            r'\b__import__\s*\(',
            r'\bimportlib\b',
        ]

        for pattern in dangerous_imports:
            if re.search(pattern, code):
                return False, f"检测到危险导入模式: {pattern}"

        # 检查危险函数调用
        dangerous_calls = [
            r'\beval\s*\(',
            r'\bexec\s*\(',
            r'\bcompile\s*\(',
            r'\bopen\s*\([^)]*["\']w["\']',  # 写模式打开文件
            r'\bos\.system\s*\(',
            r'\bos\.popen\s*\(',
            r'\bsubprocess\.',
            r'\b__builtins__\b',
            r'\b__class__\b',
            r'\b__bases__\b',
            r'\b__subclasses__\b',
            r'\b__globals__\b',
            r'\b__code__\b',
        ]

        for pattern in dangerous_calls:
            if re.search(pattern, code):
                return False, f"检测到危险函数调用: {pattern}"

        return True, ""

    def _create_safe_globals(
        self,
        extra_globals: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建安全的全局变量环境

        Args:
            extra_globals: 额外的全局变量

        Returns:
            安全的全局变量字典
        """
        import math
        import json
        import re as re_module
        import datetime as dt_module
        from collections import Counter, defaultdict, OrderedDict, deque
        from itertools import (
            chain, combinations, permutations, product,
            islice, takewhile, dropwhile, groupby
        )
        from functools import reduce, partial

        # 创建受限的builtins
        safe_builtins = {}
        for name in self.security_config.python_allowed_builtins:
            if hasattr(__builtins__, name) if isinstance(__builtins__, dict) else hasattr(__builtins__, name):
                if isinstance(__builtins__, dict):
                    safe_builtins[name] = __builtins__.get(name)
                else:
                    safe_builtins[name] = getattr(__builtins__, name, None)

        # 安全的open函数（只读）
        def safe_open(file, mode='r', *args, **kwargs):
            if 'w' in mode or 'a' in mode or '+' in mode:
                raise PermissionError("不允许写入文件")
            filepath = Path(file).resolve()
            # 检查是否在workspace内
            if self.workspace not in filepath.parents and filepath != self.workspace:
                raise PermissionError(f"只能访问工作目录内的文件: {self.workspace}")
            return open(file, mode, *args, **kwargs)

        safe_builtins['open'] = safe_open

        safe_globals = {
            "__builtins__": safe_builtins,
            "__name__": "__main__",
            "__doc__": None,
            # 安全的标准库模块
            "math": math,
            "json": json,
            "re": re_module,
            "datetime": dt_module,
            # collections
            "Counter": Counter,
            "defaultdict": defaultdict,
            "OrderedDict": OrderedDict,
            "deque": deque,
            # itertools
            "chain": chain,
            "combinations": combinations,
            "permutations": permutations,
            "product": product,
            "islice": islice,
            "takewhile": takewhile,
            "dropwhile": dropwhile,
            "groupby": groupby,
            # functools
            "reduce": reduce,
            "partial": partial,
            # 工作目录
            "_workspace_": str(self.workspace),
        }

        # 添加额外的全局变量
        if extra_globals:
            for key, value in extra_globals.items():
                if not key.startswith("_"):
                    safe_globals[key] = value

        return safe_globals

    # ==================== Bash 执行 ====================

    async def execute_bash(
        self,
        command: str,
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        """
        执行Bash命令

        Args:
            command: 要执行的命令
            timeout: 超时时间（秒），None则使用默认值
            env: 环境变量

        Returns:
            ExecutionResult: 执行结果
        """
        timeout = timeout or self.security_config.bash_timeout
        start_time = datetime.now()

        # 安全检查
        security_check = self._check_bash_security(command)
        if not security_check[0]:
            return ExecutionResult(
                status=ExecutionStatus.BLOCKED,
                error_message=security_check[1],
                metadata={"blocked_reason": security_check[1], "command": command}
            )

        # 准备环境变量
        exec_env = os.environ.copy()
        exec_env["HOME"] = str(self.workspace)
        exec_env["PWD"] = str(self.workspace)
        if env:
            exec_env.update(env)

        result = ExecutionResult(status=ExecutionStatus.SUCCESS)

        try:
            # 使用asyncio subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
                env=exec_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                result.stdout = self._truncate_output(
                    stdout.decode('utf-8', errors='replace')
                )
                result.stderr = self._truncate_output(
                    stderr.decode('utf-8', errors='replace')
                )

                if process.returncode != 0:
                    result.status = ExecutionStatus.ERROR
                    result.error_message = f"命令返回非零退出码: {process.returncode}"

                result.metadata["return_code"] = process.returncode

            except asyncio.TimeoutError:
                # 超时，终止进程
                process.kill()
                await process.wait()
                result.status = ExecutionStatus.TIMEOUT
                result.error_message = f"命令执行超时（{timeout}秒）"
                logger.warning(f"Bash命令执行超时: {command}")

        except Exception as e:
            result.status = ExecutionStatus.ERROR
            result.error_message = str(e)
            logger.error(f"Bash命令执行错误: {e}")

        finally:
            result.execution_time = (datetime.now() - start_time).total_seconds()

        return result

    def _check_bash_security(self, command: str) -> Tuple[bool, str]:
        """
        检查Bash命令安全性

        Args:
            command: Bash命令

        Returns:
            (是否安全, 错误信息)
        """
        # 解析命令获取主命令
        command_parts = command.strip().split()
        if not command_parts:
            return False, "空命令"

        # 获取主命令（处理管道和重定向）
        main_commands = []
        current_cmd = []

        for part in command_parts:
            if part in ['|', '&&', '||', ';', '>', '>>', '<', '2>', '2>>']:
                if current_cmd:
                    main_commands.append(current_cmd[0])
                    current_cmd = []
            else:
                current_cmd.append(part)

        if current_cmd:
            main_commands.append(current_cmd[0])

        # 检查每个命令
        for cmd in main_commands:
            # 移除路径前缀
            cmd_name = os.path.basename(cmd)

            # 检查黑名单
            if cmd_name in self.security_config.bash_blocked_commands:
                return False, f"命令被禁止: {cmd_name}"

            # 如果设置了白名单，检查是否在白名单中
            if self.security_config.bash_allowed_commands:
                if cmd_name not in self.security_config.bash_allowed_commands:
                    return False, f"命令不在允许列表中: {cmd_name}"

        # 检查危险模式
        dangerous_patterns = [
            r'\$\(.*\)',  # 命令替换
            r'`.*`',  # 反引号命令替换
            r'>\s*/dev/',  # 写入设备文件
            r'>\s*/etc/',  # 写入系统配置
            r'>\s*/usr/',  # 写入系统目录
            r'>\s*/bin/',  # 写入系统目录
            r'\.\.',  # 目录遍历
            r'/etc/passwd',
            r'/etc/shadow',
            r'~/',  # 用户目录
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                return False, f"检测到危险模式: {pattern}"

        return True, ""

    # ==================== 工具方法 ====================

    def _truncate_output(self, output: str) -> str:
        """
        截断过长的输出

        Args:
            output: 原始输出

        Returns:
            截断后的输出
        """
        max_size = self.security_config.python_max_output_size
        if len(output) > max_size:
            return output[:max_size] + f"\n... [输出被截断，超过{max_size}字节]"
        return output

    def get_workspace(self) -> Path:
        """获取工作目录"""
        return self.workspace

    def cleanup(self) -> None:
        """清理临时文件"""
        if self._temp_workspace and self.workspace.exists():
            import shutil
            try:
                shutil.rmtree(self.workspace)
                logger.info(f"已清理临时工作目录: {self.workspace}")
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")

    def __del__(self):
        """析构函数"""
        self.cleanup()

    # ==================== 工具定义（用于LLM） ====================

    @staticmethod
    def get_tool_definitions() -> List[Dict[str, Any]]:
        """
        获取工具定义（用于LLM Function Calling）

        Returns:
            工具定义列表
        """
        return [
            {
                "name": "execute_python",
                "description": "在安全的沙箱环境中执行Python代码。支持基本的数学运算、数据处理、字符串操作等。不支持文件写入、网络请求、系统命令等危险操作。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "要执行的Python代码。可以使用print()输出结果，或将结果赋值给_result_变量。"
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "execute_bash",
                "description": "在受限环境中执行Bash命令。仅支持安全的只读命令如ls、cat、grep、find等。不支持rm、sudo、curl等危险命令。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的Bash命令。命令将在隔离的工作目录中执行。"
                        }
                    },
                    "required": ["command"]
                }
            }
        ]


# ==================== 便捷函数 ====================

_default_executor: Optional[CodeExecutor] = None


def get_executor(workspace_dir: Optional[str] = None) -> CodeExecutor:
    """
    获取默认的代码执行器实例

    Args:
        workspace_dir: 工作目录，None则使用临时目录

    Returns:
        CodeExecutor实例
    """
    global _default_executor
    if _default_executor is None:
        _default_executor = CodeExecutor(workspace_dir=workspace_dir)
    return _default_executor


async def execute_python(code: str, **kwargs) -> ExecutionResult:
    """便捷函数：执行Python代码"""
    executor = get_executor()
    return await executor.execute_python(code, **kwargs)


async def execute_bash(command: str, **kwargs) -> ExecutionResult:
    """便捷函数：执行Bash命令"""
    executor = get_executor()
    return await executor.execute_bash(command, **kwargs)
