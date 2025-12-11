# MCP Agent - 命令行智能体

一个基于MCP（Model Context Protocol）的命令行智能体项目，支持多个LLM提供商，提供强大的TUI管理界面和自动化工具。

## 项目简介

MCP Agent是一个模块化、可扩展的命令行智能体框架，支持通过MCP协议与多种LLM模型进行交互，提供丰富的命令行界面、会话管理、可视化TUI管理和灵活的配置选项。

## 特性

### 核心功能
- 🤖 **多LLM支持**：Anthropic Claude / OpenAI，支持自定义API地址
- 🔌 **MCP协议集成**：可扩展工具和资源
- 🛠️ **自动工具调用**：OpenAI Function Calling
- 🎨 **美观的CLI界面**：基于Rich库的彩色终端输出

### TUI管理界面 🆕
- 📊 **可视化Dashboard**：实时查看服务器状态和工具列表
- ⚙️ **表单化配置**：无需手动编辑YAML/JSON
- 🔍 **安装向导**：搜索并安装npm/GitHub上的MCP服务器包
- 🎯 **交互式操作**：键盘导航，快捷键支持

### 模型管理 🆕
- 🌐 **API模型获取**：直接从OpenAI/Anthropic API获取可用模型列表
- 💾 **模型持久化**：自动保存上次使用的模型
- 🔄 **交互式选择**：通过序号快速切换模型

### 服务器管理 🆕
- 📦 **自动发现**：从npm/GitHub搜索MCP服务器包
- ⚡ **一键安装**：自动安装并配置服务器
- 🔧 **依赖检查**：检测Node.js、npm、Python等系统依赖
- 📝 **模板库**：内置常用服务器配置模板

### 会话与日志
- 💾 **会话管理**：自动保存、搜索、导出（Markdown/HTML）
- 📝 **增强日志**：敏感信息脱敏、按日期轮转、性能记录
- 🔄 **智能重试**：网络错误自动重试
- 🛡️ **错误处理**：用户友好的错误提示

## 项目结构

```
mcp-agent/
├── mcp_agent/              # 主包目录
│   ├── agent.py           # 智能体核心逻辑
│   ├── config.py          # 配置管理
│   ├── cli.py             # 命令行接口
│   ├── tui.py             # TUI界面 🆕
│   ├── mcp_client.py      # MCP客户端
│   ├── installer.py       # 包安装器 🆕
│   ├── server_registry.py # 服务器注册表 🆕
│   ├── session.py         # 会话管理
│   ├── prompts.py         # 提示词模板
│   └── utils/             # 工具模块
│       ├── logger.py      # 增强日志系统
│       ├── errors.py      # 错误处理
│       └── ...
├── config/                 # 配置文件
├── logs/                   # 日志文件
├── sessions/               # 会话文件
└── tests/                  # 测试文件
```

## 安装

### 环境要求

- Python 3.10+
- Node.js 18+ (用于MCP服务器)
- npm
- pip

### 安装步骤

1. 克隆项目：
```bash
git clone <repository-url>
cd mcp-agent
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 配置环境变量：
```bash
cp .env.example .env
# 编辑.env文件，添加你的API密钥
```

**使用Anthropic Claude:**
```bash
API_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_key_here
```

**使用OpenAI:**
```bash
API_PROVIDER=openai
OPENAI_API_KEY=your_openai_key_here
```

5. 配置项目（可选）：
```bash
cp config/config.example.yaml config/config.yaml
# 根据需要编辑config.yaml
```

## 使用方法

### 启动

```bash
python main.py
```

### TUI管理界面 🆕

使用 `/config` 命令启动可视化管理界面：

```bash
MCP Agent> /config
```

**Dashboard功能：**
- **导航**：↑/↓ 选择服务器
- **快捷键**：
  - `N` - 新建服务器
  - `D` - 删除服务器
  - `I` - 安装向导
  - `Enter` - 查看详情
  - `R` - 刷新状态

**安装向导：**
1. 搜索：输入关键词（如 "filesystem", "git"）
2. 选择：从搜索结果中选择包
3. 安装：自动安装并配置

### 模型管理 🆕

**查看和选择模型：**
```bash
MCP Agent> /models
```

**从API获取模型：**
```bash
MCP Agent> /models
请选择操作> fetch
# 输入序号选择模型，如: 1,3,5
```

**快速切换模型：**
```bash
MCP Agent> /model gpt-4o
# 或在 /models 界面输入序号
```

模型选择会自动保存，下次启动时自动加载。

### 服务器管理 🆕

**添加服务器（交互式）：**
```bash
MCP Agent> /add-server
# 或指定模板名称
MCP Agent> /add-server filesystem
```

**列出可用模板：**
```bash
MCP Agent> /list-available
# 或搜索
MCP Agent> /list-available git
```

**测试服务器连接：**
```bash
MCP Agent> /test-server filesystem
```

**移除服务器：**
```bash
MCP Agent> /remove-server filesystem
```

### 包管理 🆕

**搜索可用包：**
```bash
MCP Agent> /discover
# 或指定关键词
MCP Agent> /discover filesystem
```

**安装包：**
```bash
MCP Agent> /install @modelcontextprotocol/server-filesystem
```

**检查系统依赖：**
```bash
MCP Agent> /check-deps
```

### 基础命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/tools` | 列出可用工具 |
| `/servers` | 显示MCP服务器状态 |
| `/reconnect <name>` | 重新连接指定服务器 |
| `/clear` | 清除对话历史 |
| `/history` | 查看对话历史 |
| `/save <filename>` | 保存对话到文件 |
| `/load <filename>` | 加载对话历史 |
| `/stats` | 显示统计信息 |
| `/system <prompt>` | 设置系统提示词 |
| `/exit`, `/quit` | 退出程序 |

### 会话管理

| 命令 | 说明 |
|------|------|
| `/sessions` | 列出所有保存的会话 |
| `/search <keyword>` | 搜索会话内容 |
| `/export [id] [format]` | 导出会话 (markdown/html) |
| `/session-stats` | 显示当前会话统计 |

**示例：**
```bash
# 列出会话
MCP Agent> /sessions

# 搜索会话
MCP Agent> /search python

# 导出会话
MCP Agent> /export                              # 导出当前会话
MCP Agent> /export session_20241201_120000      # 导出指定会话
MCP Agent> /export session_20241201_120000 html # 导出为HTML
```

### 工具调用

Agent支持自动调用MCP工具！当你提出需要文件操作的请求时，Agent会自动识别并执行相应的工具。

**配置要求：**
1. 使用OpenAI提供商
2. 关闭流式输出（`features.streaming: false`）
3. 启用MCP服务器

**示例：**
```
用户: 请在当前目录创建一个test.txt文件，内容是"Hello, MCP!"
Agent: [自动调用write_file工具]
Agent: 我已经成功创建了test.txt文件，内容为"Hello, MCP!"
```

## 配置说明

### 基础配置

编辑 `config/config.yaml` 文件：

**Agent配置：**
```yaml
agent:
  provider: openai              # anthropic 或 openai
  model: gpt-4o
  max_tokens: 8192
  temperature: 0.7
  available_models: []          # 用户选择的模型列表 🆕
```

**API配置：**
```yaml
api:
  openai:
    api_key: ""                 # 或使用环境变量
    base_url: "https://api.openai.com/v1"
  anthropic:
    api_key: ""
    base_url: "https://api.anthropic.com"
```

**MCP服务器配置：**
```yaml
mcp:
  enabled: true
  servers:
    - name: filesystem
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "./workspace"]
```

### 会话管理配置

```yaml
features:
  auto_save: true          # 自动保存会话
  save_interval: 300       # 保存间隔（秒）

advanced:
  session_dir: sessions    # 会话保存目录
```

### 日志配置

```yaml
logging:
  level: INFO                    # DEBUG, INFO, WARNING, ERROR
  file: logs/mcp-agent.log
  console: false
  max_size: 10                   # MB
  backup_count: 5
```

## 命令行参数

```bash
python main.py --help                          # 查看帮助
python main.py --config custom.yaml            # 使用自定义配置
python main.py --verbose                       # 详细输出模式
python main.py --analyze-log logs/app.log      # 分析日志文件
```

## 开发

### 运行测试

```bash
pytest tests/
```

### 代码格式化

```bash
black mcp_agent/
flake8 mcp_agent/
```

### 类型检查

```bash
mypy mcp_agent/
```

## 扩展

### 添加新的MCP服务器模板

编辑 `mcp_agent/server_registry.py`，在 `ServerRegistry` 中添加新的 `ServerTemplate`。

### 自定义提示词

编辑 `mcp_agent/prompts.py` 文件来自定义系统提示词和用户提示词模板。

### 使用增强日志

```python
from mcp_agent.utils.logger import get_enhanced_logger

logger = get_enhanced_logger("my_module")

# 记录API调用
logger.log_api_call(method="POST", endpoint="api/chat", status=200, duration=1.5)

# 性能测量
with logger.perf.measure("数据处理"):
    # 执行代码
    pass
```

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License

## 文档

- [使用指南](docs/usage.md) - 详细的使用说明
- [日志系统](docs/logging.md) - 日志配置和分析
- [MCP配置](docs/mcp_setup.md) - MCP服务器配置指南
- [工具调用](docs/tool_calling.md) - 自动工具调用功能说明
- [项目结构](PROJECT_STRUCTURE.md) - 完整的项目结构文档

## 更新日志

### v0.4.0 (2024-12-11) 🆕
- ✨ 新增：TUI可视化管理界面（基于textual）
- ✨ 新增：模型管理（API获取、交互式选择、自动持久化）
- ✨ 新增：服务器注册表和模板系统
- ✨ 新增：包自动发现和安装（npm/GitHub）
- ✨ 新增：系统依赖检查
- 📝 新增命令：`/config`、`/models`、`/add-server`、`/list-available`、`/test-server`、`/remove-server`、`/discover`、`/install`、`/check-deps`
- 🔧 改进：配置持久化机制
- 📝 更新：README文档

### v0.3.0 (2024-12-11)
- ✨ 新增：会话管理功能（自动保存、搜索、导出）
- ✨ 新增：增强日志系统（敏感信息脱敏、性能记录）
- ✨ 新增：错误处理模块（智能重试、用户友好提示）
- 📝 新增命令：`/sessions`、`/search`、`/export`、`/session-stats`

### v0.2.0 (2024-12-10)
- ✨ 新增：OpenAI Function Calling支持
- ✨ 新增：自动MCP工具调用

### v0.1.0 (2024-12-10)
- 初始版本
- 基础MCP智能体功能
