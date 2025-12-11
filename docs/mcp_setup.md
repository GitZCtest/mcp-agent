# MCP文件系统配置指南

## 📋 前提条件

你已经完成：
- ✅ 下载了官方的filesystem MCP服务器
- ✅ 配置文件中已有MCP服务器配置

## 🚀 快速开始

### 1. 安装MCP Python SDK

```bash
pip install mcp
```

### 2. 验证Node.js和npx

确保已安装Node.js：

```bash
node --version
npx --version
```

### 3. 测试MCP服务器

```bash
# 测试filesystem服务器是否可用
npx -y @modelcontextprotocol/server-filesystem --help
```

### 4. 配置允许访问的目录

编辑 `config/config.yaml`：

```yaml
mcp:
  enabled: true
  servers:
    - name: "filesystem"
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "E:/Projects/AI/Agent"  # 修改为你想要访问的目录
      env:
        NODE_ENV: "production"
```

**重要提示：**
- 路径必须是绝对路径
- Windows使用正斜杠 `/` 或双反斜杠 `\\`
- Agent只能访问这个目录及其子目录

### 5. 当前状态

⚠️ **注意：** 当前的`mcp_client.py`是占位实现，还不能真正连接到MCP服务器。

要启用真实的MCP功能，需要实现真实的MCP客户端连接。

## 🔧 实现真实MCP连接（待完成）

当前`mcp_client.py`需要以下改进：

```python
# 需要实现的功能
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def _connect_server(self, server_config):
    """真实的MCP服务器连接"""
    server_params = StdioServerParameters(
        command=server_config["command"],
        args=server_config["args"],
        env=server_config.get("env", {})
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 获取可用工具
            tools_result = await session.list_tools()
            self.tools[name] = tools_result.tools
            
            # 保存会话
            self.servers[name] = session
```

## 📝 配置示例

### 单个目录访问

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

### 多个目录访问

```yaml
mcp:
  enabled: true
  servers:
    - name: "project-files"
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "E:/Projects/AI/Agent"
    
    - name: "documents"
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "C:/Users/YourName/Documents"
```

### 只读模式

```yaml
mcp:
  enabled: true
  servers:
    - name: "filesystem-readonly"
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "E:/Projects/AI/Agent"
        - "--readonly"  # 只读模式
```

## 🎯 完成后可用的功能

一旦MCP客户端实现完成，你将能够：

### 读取文件
```
MCP Agent> 读取 README.md 的内容
MCP Agent> 显示 config/config.yaml 文件
```

### 写入文件
```
MCP Agent> 创建一个新文件 test.txt，内容是"Hello World"
MCP Agent> 在 notes.md 中添加一行"今天的任务完成了"
```

### 列出目录
```
MCP Agent> 列出当前目录下的所有文件
MCP Agent> 显示 mcp_agent 目录的结构
```

### 搜索文件
```
MCP Agent> 在项目中搜索包含"config"的文件
MCP Agent> 找出所有的Python文件
```

### 文件操作
```
MCP Agent> 删除 temp.txt 文件
MCP Agent> 重命名 old.txt 为 new.txt
MCP Agent> 复制 file1.txt 到 backup/file1.txt
```

## 🔒 安全建议

1. **限制访问目录**
   - 只授权必要的目录
   - 避免授权系统目录（如C:/Windows）

2. **使用只读模式**
   - 对于敏感目录，使用`--readonly`标志

3. **定期审查日志**
   - 检查`logs/mcp-agent.log`中的文件操作记录

4. **备份重要文件**
   - 在让Agent操作重要文件前先备份

## 🐛 故障排查

### 问题1：找不到npx命令

**解决方案：**
```bash
# 安装Node.js
# 下载：https://nodejs.org/

# 验证安装
node --version
npm --version
npx --version
```

### 问题2：MCP服务器启动失败

**检查：**
1. Node.js版本是否>=18
2. 网络连接是否正常（首次运行需要下载）
3. 路径是否正确（使用绝对路径）

**测试命令：**
```bash
npx -y @modelcontextprotocol/server-filesystem E:/Projects/AI/Agent
```

### 问题3：权限错误

**Windows：**
- 确保目录有读写权限
- 以管理员身份运行（如果需要）

**Linux/Mac：**
```bash
chmod -R 755 /path/to/directory
```

## 📚 更多资源

- [MCP官方文档](https://modelcontextprotocol.io/)
- [Filesystem服务器文档](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## 🚧 当前限制

由于MCP客户端还是占位实现，目前：

❌ 不能真正连接到MCP服务器  
❌ 不能执行文件操作  
❌ 工具列表为空  

✅ 配置已就绪  
✅ 框架已搭建  
✅ 只需实现真实的MCP连接逻辑  

## 📞 需要帮助？

如果需要实现真实的MCP连接功能，请告诉我，我可以：

1. 完善`mcp_client.py`的实现
2. 添加工具调用逻辑
3. 实现文件操作功能
4. 创建使用示例