# MCP Agent 项目结构说明

## 完整目录树

```
mcp-agent/
├── mcp_agent/                      # 主包目录
│   ├── __init__.py                # 包初始化，导出主要类
│   ├── agent.py                   # 智能体核心逻辑（293行）
│   ├── config.py                  # 配置管理模块（258行）
│   ├── cli.py                     # 命令行接口（362行）
│   ├── mcp_client.py              # MCP客户端封装（243行）
│   ├── prompts.py                 # 提示词模板管理（213行）
│   └── utils/                     # 工具模块目录
│       ├── __init__.py           # 工具包初始化
│       ├── logger.py             # 基础日志工具（103行）
│       ├── log_config.py         # 日志配置管理（363行）
│       ├── log_filters.py        # 日志过滤器（330行）
│       ├── log_analyzer.py       # 日志分析工具（339行）
│       └── formatter.py          # 输出格式化（189行）
├── config/                         # 配置文件目录
│   └── config.example.yaml       # 配置示例文件（128行）
├── logs/                           # 日志目录
│   └── .gitkeep                  # 保持目录存在
├── tests/                          # 测试目录
│   ├── __init__.py               # 测试包初始化
│   └── test_config.py            # 配置模块测试（59行）
├── docs/                           # 文档目录
│   ├── usage.md                  # 使用指南（293行）
│   └── logging.md                # 日志系统指南（485行）
├── .env.example                   # 环境变量示例（10行）
├── .gitignore                     # Git忽略文件（63行）
├── requirements.txt               # 依赖列表（23行）
├── setup.py                       # 安装配置（53行）
├── README.md                      # 项目说明（172行）
├── main.py                        # 主入口文件（11行）
└── PROJECT_STRUCTURE.md           # 本文件

总计：约3,600行代码
```

## 目录和文件说明

### 1. 核心代码目录 (`mcp_agent/`)

#### 1.1 [`__init__.py`](mcp_agent/__init__.py)
- **用途**：包初始化文件
- **功能**：
  - 定义包的版本信息
  - 导出主要类（MCPAgent, Config）
  - 提供包级别的文档字符串

#### 1.2 [`agent.py`](mcp_agent/agent.py)
- **用途**：智能体核心逻辑
- **主要类**：`MCPAgent`
- **功能**：
  - 与Anthropic Claude API交互
  - 管理对话历史
  - 支持流式和普通输出模式
  - 集成MCP客户端
  - 提供工具调用接口
- **关键方法**：
  - `initialize()` - 初始化智能体
  - `chat()` - 发送消息并获取回复
  - `clear_history()` - 清除对话历史
  - `list_tools()` - 列出可用工具
  - `call_tool()` - 调用MCP工具

#### 1.3 [`config.py`](mcp_agent/config.py)
- **用途**：配置管理
- **主要类**：`Config`
- **功能**：
  - 加载YAML配置文件
  - 合并默认配置和用户配置
  - 支持环境变量覆盖
  - 配置验证
  - 提供便捷的配置访问接口
- **关键方法**：
  - `load_config()` - 加载配置文件
  - `get()` - 获取配置值（支持点号路径）
  - `set()` - 设置配置值
  - `validate()` - 验证配置

#### 1.4 [`cli.py`](mcp_agent/cli.py)
- **用途**：命令行接口
- **主要类**：`CLI`
- **功能**：
  - 提供交互式命令行界面
  - 处理用户输入和命令
  - 美观的输出格式
  - 命令解析和执行
- **支持的命令**：
  - `/help` - 帮助信息
  - `/clear` - 清除历史
  - `/history` - 查看历史
  - `/stats` - 统计信息
  - `/tools` - 列出工具
  - `/save` / `/load` - 会话管理
  - `/system` - 设置系统提示词
  - `/exit` / `/quit` - 退出

#### 1.5 [`mcp_client.py`](mcp_agent/mcp_client.py)
- **用途**：MCP协议客户端
- **主要类**：`MCPClient`
- **功能**：
  - 连接MCP服务器
  - 管理工具和资源
  - 执行工具调用
  - 读取资源
- **关键方法**：
  - `initialize()` - 初始化客户端
  - `list_tools()` - 列出工具
  - `call_tool()` - 调用工具
  - `list_resources()` - 列出资源
  - `read_resource()` - 读取资源
- **注意**：当前为占位实现，需要集成实际的MCP SDK

#### 1.6 [`prompts.py`](mcp_agent/prompts.py)
- **用途**：提示词模板管理
- **主要类**：`PromptTemplates`
- **功能**：
  - 预定义系统提示词
  - 提供不同角色的提示词（默认、代码、数据、写作）
  - 格式化用户消息
  - 创建少样本学习示例
  - 思维链提示词生成
- **预定义模板**：
  - 总结、翻译、解释
  - 改进、调试、优化
  - 代码审查

### 2. 工具模块 (`mcp_agent/utils/`)

#### 2.1 [`logger.py`](mcp_agent/utils/logger.py)
- **用途**：日志管理
- **功能**：
  - 统一的日志配置
  - 彩色控制台输出
  - 文件日志轮转
  - 多级别日志支持
- **关键函数**：
  - `setup_logger()` - 设置日志记录器
  - `get_logger()` - 获取日志记录器

#### 2.2 [`log_config.py`](mcp_agent/utils/log_config.py)
- **用途**：日志配置管理
- **主要类**：`LogConfig`
- **功能**：
  - 灵活的日志配置
  - 支持多种日志格式
  - 文件和控制台处理器
  - 日志轮转（基于大小和时间）
  - 全局日志配置管理
- **关键方法**：
  - `setup_logger()` - 设置日志记录器
  - `get_logger()` - 获取日志记录器
  - `set_level()` - 设置日志级别
  - `add_handler()` / `remove_handler()` - 管理处理器

#### 2.3 [`log_filters.py`](mcp_agent/utils/log_filters.py)
- **用途**：日志过滤器
- **功能**：
  - 级别过滤（LevelFilter）
  - 模块过滤（ModuleFilter）
  - 模式过滤（PatternFilter）
  - 速率限制（RateLimitFilter）
  - 敏感数据屏蔽（SensitiveDataFilter）
  - 上下文添加（ContextFilter）
  - 重复消息过滤（DuplicateFilter）
- **关键函数**：
  - `create_filter()` - 过滤器工厂函数

#### 2.4 [`log_analyzer.py`](mcp_agent/utils/log_analyzer.py)
- **用途**：日志分析工具
- **主要类**：`LogAnalyzer`
- **功能**：
  - 日志文件分析
  - 级别统计
  - 错误提取
  - 时间范围分析
  - 模块统计
  - 按小时分布
  - 日志搜索和过滤
- **关键方法**：
  - `analyze()` - 分析日志
  - `search()` - 搜索日志
  - `filter_by_level()` - 按级别过滤
  - `filter_by_time_range()` - 按时间过滤
  - `get_summary()` - 获取摘要
  - `export_errors()` - 导出错误

#### 2.5 [`formatter.py`](mcp_agent/utils/formatter.py)
- **用途**：输出格式化
- **功能**：
  - Rich库集成
  - 美观的消息显示
  - Markdown渲染
  - 代码高亮
  - 表格显示
  - 错误格式化
- **关键函数**：
  - `format_message()` - 格式化消息
  - `format_error()` - 格式化错误
  - `format_code()` - 格式化代码
  - `format_welcome()` - 欢迎信息
  - `print_info/success/warning/error()` - 快捷打印

### 3. 配置目录 (`config/`)

#### 3.1 [`config.example.yaml`](config/config.example.yaml)
- **用途**：配置文件示例
- **包含的配置项**：
  - `agent` - 智能体配置（模型、token、温度等）
  - `mcp` - MCP服务器配置
  - `logging` - 日志配置
  - `cli` - 命令行界面配置
  - `api` - API配置
  - `features` - 功能开关
  - `advanced` - 高级配置

### 4. 测试目录 (`tests/`)

#### 4.1 [`test_config.py`](tests/test_config.py)
- **用途**：配置模块测试
- **测试内容**：
  - 默认配置
  - 配置获取和设置
  - 配置属性
  - 配置验证

### 5. 文档目录 (`docs/`)

#### 5.1 [`usage.md`](docs/usage.md)
- **用途**：详细使用指南
- **内容**：
  - 快速开始
  - 基本使用
  - 命令说明
  - 高级配置
  - 常见问题
  - 开发指南

#### 5.2 [`logging.md`](docs/logging.md)
- **用途**：日志系统使用指南
- **内容**：
  - 基础日志使用
  - 高级配置
  - 日志过滤器详解
  - 日志分析工具
  - 最佳实践
  - 故障排查

### 6. 根目录文件

#### 6.1 [`.env.example`](.env.example)
- **用途**：环境变量示例
- **包含**：API密钥、日志级别、调试模式等

#### 6.2 [`.gitignore`](.gitignore)
- **用途**：Git忽略规则
- **忽略内容**：
  - Python缓存文件
  - 虚拟环境
  - IDE配置
  - 日志文件
  - 实际配置文件

#### 6.3 [`requirements.txt`](requirements.txt)
- **用途**：Python依赖列表
- **主要依赖**：
  - anthropic - Claude API
  - mcp - MCP协议
  - rich - 终端美化
  - pyyaml - YAML解析
  - click - 命令行框架
  - python-dotenv - 环境变量

#### 6.4 [`setup.py`](setup.py)
- **用途**：包安装配置
- **功能**：
  - 定义包信息
  - 声明依赖
  - 配置命令行入口点

#### 6.5 [`README.md`](README.md)
- **用途**：项目主文档
- **内容**：
  - 项目简介
  - 特性列表
  - 安装说明
  - 使用方法
  - 开发指南

#### 6.6 [`main.py`](main.py)
- **用途**：程序入口
- **功能**：启动CLI应用

## 模块依赖关系

```
main.py
  └── cli.py
      ├── agent.py
      │   ├── config.py
      │   ├── mcp_client.py
      │   └── prompts.py
      ├── config.py
      └── utils/
          ├── logger.py
          ├── log_config.py
          ├── log_filters.py
          ├── log_analyzer.py
          └── formatter.py
```

## 扩展点

### 1. 添加新的MCP工具
- 在 `mcp_client.py` 中实现工具注册和调用逻辑

### 2. 自定义提示词
- 在 `prompts.py` 中添加新的提示词模板

### 3. 新增CLI命令
- 在 `cli.py` 的 `_handle_command()` 方法中添加命令处理

### 4. 自定义输出格式
- 在 `utils/formatter.py` 中添加新的格式化函数

### 5. 添加新的配置项
- 在 `config.py` 的 `_get_default_config()` 中添加默认值
- 在 `config.example.yaml` 中添加示例

## 代码规范

- **Python版本**：3.10+
- **代码风格**：遵循PEP 8
- **文档字符串**：使用Google风格
- **类型提示**：使用typing模块
- **异步编程**：使用asyncio
- **错误处理**：适当的异常捕获和日志记录

## 性能考虑

- 使用异步I/O提高并发性能
- 对话历史限制避免内存溢出
- 日志文件轮转避免磁盘占用过大
- 配置缓存减少重复加载

## 安全考虑

- API密钥通过环境变量管理
- 配置文件不包含敏感信息
- MCP服务器访问权限控制
- 输入验证和清理

## 未来改进方向

1. **完善MCP集成**：实现真实的MCP SDK集成
2. **会话管理**：实现会话保存和加载功能
3. **插件系统**：支持动态加载插件
4. **Web界面**：提供Web UI选项
5. **多模型支持**：支持其他LLM提供商
6. **流式输出优化**：实时显示流式响应
7. **性能监控**：添加性能分析工具
8. **更多测试**：增加单元测试和集成测试覆盖率

## 贡献指南

1. Fork项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 许可证

MIT License - 详见LICENSE文件