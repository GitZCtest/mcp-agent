# MCP Agent 使用指南

## 快速开始

### 1. 安装

```bash
# 克隆项目
git clone <repository-url>
cd mcp-agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

```bash
# 复制配置文件
cp config/config.example.yaml config/config.yaml

# 复制环境变量文件
cp .env.example .env

# 编辑.env文件，添加你的API密钥
# ANTHROPIC_API_KEY=your_api_key_here
```

### 3. 运行

```bash
python main.py
```

## 基本使用

### 对话交互

启动程序后，直接输入消息即可与助手对话：

```
MCP Agent> 你好，请介绍一下自己

🤖 助手
你好！我是一个基于MCP协议的智能助手...
```

### 命令列表

#### `/help` - 显示帮助

显示所有可用命令的说明。

```
MCP Agent> /help
```

#### `/clear` - 清除历史

清除当前对话历史。

```
MCP Agent> /clear
✅ 对话历史已清除
```

#### `/history` - 查看历史

显示当前会话的对话历史。

```
MCP Agent> /history
ℹ️  对话历史（共 5 条）：
1. [user] 你好
2. [assistant] 你好！有什么我可以帮助你的吗？
...
```

#### `/stats` - 统计信息

显示当前会话的统计信息。

```
MCP Agent> /stats
ℹ️  === 统计信息 ===
ℹ️  模型: claude-3-5-sonnet-20241022
ℹ️  对话历史: 5/50
ℹ️  MCP启用: 是
ℹ️  MCP服务器: 1 个
```

#### `/tools` - 列出工具

列出所有可用的MCP工具。

```
MCP Agent> /tools
ℹ️  可用工具（共 3 个）：
ℹ️    - read_file
ℹ️    - write_file
ℹ️    - list_directory
```

#### `/system` - 设置系统提示词

自定义系统提示词。

```
MCP Agent> /system 你是一个Python编程专家
✅ 系统提示词已更新
```

#### `/save` - 保存会话

保存当前会话到文件（功能开发中）。

```
MCP Agent> /save my_session
```

#### `/load` - 加载会话

从文件加载会话（功能开发中）。

```
MCP Agent> /load my_session
```

#### `/exit` 或 `/quit` - 退出

退出程序。

```
MCP Agent> /exit
ℹ️  正在退出...
✅ 再见！
```

## 高级配置

### 配置文件说明

编辑 `config/config.yaml` 来自定义智能体行为：

```yaml
# 智能体配置
agent:
  model: "claude-3-5-sonnet-20241022"  # 模型名称
  max_tokens: 4096                      # 最大token数
  temperature: 0.7                      # 温度参数
  system_prompt: ""                     # 自定义系统提示词
  max_history: 50                       # 历史记录条数

# MCP服务器配置
mcp:
  enabled: true
  servers:
    - name: "filesystem"
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "/path/to/directory"
```

### 环境变量

在 `.env` 文件中设置：

```bash
# Anthropic API密钥（必需）
ANTHROPIC_API_KEY=your_api_key_here

# API基础URL（可选，用于代理）
ANTHROPIC_BASE_URL=https://api.anthropic.com

# 日志级别
LOG_LEVEL=INFO

# 调试模式
DEBUG=false
```

### 命令行参数

```bash
# 使用自定义配置文件
python main.py --config /path/to/config.yaml

# 启用详细输出
python main.py --verbose

# 查看帮助
python main.py --help
```

## MCP服务器配置

### 文件系统服务器

允许智能体访问指定目录：

```yaml
mcp:
  servers:
    - name: "filesystem"
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "/path/to/allowed/directory"
```

### 自定义服务器

添加你自己的MCP服务器：

```yaml
mcp:
  servers:
    - name: "my-server"
      command: "python"
      args:
        - "path/to/my_server.py"
      env:
        CUSTOM_VAR: "value"
```

## 常见问题

### Q: 如何更换模型？

A: 编辑 `config/config.yaml`，修改 `agent.model` 字段：

```yaml
agent:
  model: "claude-3-opus-20240229"  # 或其他可用模型
```

### Q: 如何增加输出长度？

A: 修改 `agent.max_tokens` 参数：

```yaml
agent:
  max_tokens: 8192  # 增加到8192
```

### Q: 如何禁用MCP功能？

A: 设置 `mcp.enabled` 为 `false`：

```yaml
mcp:
  enabled: false
```

### Q: 日志文件在哪里？

A: 默认在 `logs/mcp-agent.log`，可在配置文件中修改：

```yaml
logging:
  file: "logs/mcp-agent.log"
```

## 开发和扩展

### 添加新功能

项目采用模块化设计，易于扩展：

- `mcp_agent/agent.py` - 智能体核心逻辑
- `mcp_agent/mcp_client.py` - MCP客户端
- `mcp_agent/cli.py` - 命令行界面
- `mcp_agent/prompts.py` - 提示词模板
- `mcp_agent/utils/` - 工具函数

### 运行测试

```bash
pytest tests/
```

### 代码格式化

```bash
black mcp_agent/
flake8 mcp_agent/
```

## 更多资源

- [Anthropic API文档](https://docs.anthropic.com/)
- [MCP协议文档](https://modelcontextprotocol.io/)
- [项目GitHub](https://github.com/yourusername/mcp-agent)

## 获取帮助

如有问题，请：

1. 查看本文档
2. 查看项目README
3. 提交Issue到GitHub
4. 联系项目维护者