# 项目打包指南

## 1. 编译为可执行文件 (Recommended)

使用 `PyInstaller` 将项目打包为独立的可执行文件（.exe），方便分发给最终用户。

### 前置要求

在此项目环境中安装 PyInstaller：

```bash
pip install pyinstaller
```

### 打包步骤

我们已经为你准备好了 `main.spec` 配置文件，它包含了项目所需的依赖（包括 TUI 界面所需的 textual 库）。

在项目根目录下运行：

```bash
pyinstaller main.spec --clean
```

### 输出产物

打包完成后，可执行文件位于 `dist/mcp-agent/` 目录中：

- **文件夹模式** (默认): `dist/mcp-agent/` (包含 `mcp-agent.exe` 和依赖文件)
  - 优点：启动快，易于排查问题。
  - 分发：将整个 `mcp-agent` 文件夹压缩打包。

### 运行

双击 `dist/mcp-agent/mcp-agent.exe` 或在终端运行：

```bash
./dist/mcp-agent/mcp-agent.exe
```

> **注意**: 首次运行时，请确保目录下有 `.env` 文件（如果使用了环境变量配置API密钥）或者在程序中进行了配置。程序会优先读取当前目录下的 `config/` 或 `config.yaml`。

---

## 2. Python 包分发

如果你想将项目作为 Python 库分发（例如上传到 PyPI 或通过 pip 安装），使用 `setup.py`。

### 打包命令

安装构建工具：
```bash
pip install build wheel
```

构建 Wheel 包：
```bash
python -m build
```

产物将生成在 `dist/` 目录下（`.whl` 和 `.tar.gz` 文件）。

### 安装

用户可以通过 pip 安装：

```bash
pip install dist/mcp_agent-0.1.0-py3-none-any.whl
```
