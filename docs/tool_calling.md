# MCP工具调用功能说明

## 概述

MCP Agent现在支持自动调用MCP工具来完成任务。当你向Agent提出需要文件操作的请求时，Agent会自动识别并调用相应的MCP工具。

## 功能特性

### ✅ 已实现

1. **自动工具识别**：Agent能够理解用户意图并选择合适的工具
2. **工具调用执行**：自动调用MCP服务器提供的工具
3. **结果整合**：将工具执行结果整合到对话中
4. **多工具支持**：支持在一次对话中调用多个工具
5. **错误处理**：优雅地处理工具调用失败的情况

### ⚠️ 限制

1. **流式输出不支持**：工具调用功能需要关闭流式输出
2. **仅支持OpenAI**：目前仅OpenAI提供商支持工具调用
3. **普通模式**：必须使用普通对话模式（非流式）

## 配置要求

### 1. 关闭流式输出

在 `config.yaml` 中设置：

```yaml
features:
  streaming: false  # 必须关闭流式输出
```

### 2. 使用OpenAI提供商

```yaml
agent:
  provider: "openai"
  model: "gpt-4"  # 或其他OpenAI模型
```

### 3. 启用MCP服务器

```yaml
mcp:
  enabled: true
  servers:
    - name: "filesystem"
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "E:/Projects/AI/Agent"
```

## 使用示例

### 示例1：创建文件

**用户输入：**
```
请在当前目录创建一个名为test.txt的文件，内容是"Hello, MCP!"
```

**Agent行为：**
1. 识别需要使用 `write_file` 工具
2. 调用工具创建文件
3. 返回执行结果

**预期输出：**
```
我已经成功创建了test.txt文件，内容为"Hello, MCP!"
```

### 示例2：读取文件

**用户输入：**
```
读取test.txt文件的内容
```

**Agent行为：**
1. 识别需要使用 `read_file` 工具
2. 调用工具读取文件
3. 返回文件内容

### 示例3：列出目录

**用户输入：**
```
列出当前目录下的所有文件
```

**Agent行为：**
1. 识别需要使用 `list_directory` 工具
2. 调用工具获取文件列表
3. 格式化并返回结果

### 示例4：多步骤操作

**用户输入：**
```
创建一个目录叫做test_dir，然后在里面创建一个文件hello.txt
```

**Agent行为：**
1. 调用 `create_directory` 工具创建目录
2. 调用 `write_file` 工具创建文件
3. 返回完整的执行结果

## 可用工具

当前filesystem服务器提供以下工具：

1. **read_file** - 读取文件内容
2. **read_multiple_files** - 读取多个文件
3. **write_file** - 写入文件
4. **edit_file** - 编辑文件
5. **create_directory** - 创建目录
6. **list_directory** - 列出目录内容
7. **directory_tree** - 显示目录树
8. **move_file** - 移动文件
9. **search_files** - 搜索文件
10. **get_file_info** - 获取文件信息
11. **list_allowed_directories** - 列出允许访问的目录

使用 `/tools` 命令可以查看所有可用工具的详细信息。

## 工作原理

### 1. 工具定义转换

Agent将MCP工具定义转换为OpenAI Function Calling格式：

```python
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the complete contents of a file",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file"
                }
            },
            "required": ["path"]
        }
    }
}
```

### 2. API调用

在调用OpenAI API时传递工具定义：

```python
response = await client.chat.completions.create(
    model="gpt-4",
    messages=messages,
    tools=tools,
    tool_choice="auto"
)
```

### 3. 工具调用处理

当LLM返回工具调用请求时：

1. 解析工具名称和参数
2. 调用MCP客户端执行工具
3. 将结果添加到对话历史
4. 再次调用LLM获取最终响应

### 4. 对话流程

```
用户消息
    ↓
LLM分析（带工具定义）
    ↓
返回工具调用请求
    ↓
执行MCP工具
    ↓
工具结果返回LLM
    ↓
LLM生成最终回复
    ↓
返回给用户
```

## 日志输出

启用工具调用后，你会在日志中看到：

```
INFO - 提供 14 个工具给LLM
INFO - LLM请求调用 1 个工具
INFO - 执行工具: write_file
DEBUG - 工具参数: {'path': 'test.txt', 'content': 'Hello, MCP!'}
INFO - 工具执行成功: write_file
INFO - Token使用（第二轮）: 输入=150, 输出=50, 总计=200
```

## 故障排除

### 问题1：Agent不调用工具

**可能原因：**
- 流式输出未关闭
- 使用了Anthropic提供商
- MCP服务器未正确连接

**解决方案：**
1. 检查 `config.yaml` 中 `features.streaming` 是否为 `false`
2. 确认使用 `openai` 提供商
3. 使用 `/tools` 命令检查工具是否可用

### 问题2：工具调用失败

**可能原因：**
- 工具参数不正确
- MCP服务器权限问题
- 文件路径错误

**解决方案：**
1. 查看日志中的错误信息
2. 检查MCP服务器配置的允许目录
3. 确认文件路径是否正确

### 问题3：性能问题

**说明：**
工具调用需要两次LLM API调用（一次识别工具，一次生成最终响应），因此：
- Token消耗会增加
- 响应时间会变长

**优化建议：**
- 使用更快的模型（如gpt-3.5-turbo）
- 减少不必要的工具调用
- 合理设置max_tokens

## 最佳实践

### 1. 明确的指令

❌ 不好的指令：
```
处理一下那个文件
```

✅ 好的指令：
```
读取config.yaml文件的内容
```

### 2. 合理的任务拆分

对于复杂任务，可以分步骤进行：

```
1. 先列出目录内容
2. 然后读取特定文件
3. 最后创建新文件
```

### 3. 验证结果

使用 `/tools` 命令查看可用工具，确保你需要的工具存在。

### 4. 监控日志

关注日志输出，了解工具调用的详细过程。

## 未来计划

- [ ] 支持Anthropic的工具调用
- [ ] 支持流式模式下的工具调用
- [ ] 添加工具调用缓存
- [ ] 支持自定义工具
- [ ] 添加工具调用统计

## 参考资料

- [OpenAI Function Calling文档](https://platform.openai.com/docs/guides/function-calling)
- [MCP协议规范](https://modelcontextprotocol.io/)
- [项目README](../README.md)