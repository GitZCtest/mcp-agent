# ConsoleUI 增强功能使用示例

本文档展示了 `mcp_agent.ui.ConsoleUI` 类的所有功能及使用方法。

## 功能概览

ConsoleUI 提供了以下功能：

1. **欢迎页面** - 展示应用标题和命令列表
2. **用户消息** - 显示用户输入
3. **助手消息** - 显示 AI 助手回复（支持 Markdown）
4. **系统消息** - 显示系统通知
5. **工具调用** - 展示 MCP 工具调用信息
6. **工具结果** - 展示工具执行结果
7. **思考状态** - 显示等待/处理中的动画
8. **成功消息** - 显示操作成功提示
9. **警告消息** - 显示警告信息
10. **错误消息** - 显示错误信息
11. **JSON 展示** - 格式化显示 JSON 数据（语法高亮）
12. **步骤进度** - 显示多步骤操作的进度
13. **标题展示** - 显示大标题和副标题
14. **分隔线** - 显示文字分隔线
15. **用户输入** - 获取用户输入（支持多行）

---

## 使用示例

### 1. 基本初始化

```python
from mcp_agent.ui import ConsoleUI

# 创建 UI 实例
ui = ConsoleUI()

# 自定义提示符
ui = ConsoleUI(prompt="MyApp> ")
```

### 2. 欢迎页面

```python
# 显示欢迎信息和命令列表
ui.display_welcome()
```

### 3. 标题和分隔线

```python
# 显示大标题
ui.display_title("我的应用", "版本 1.0.0")

# 显示分隔线
ui.display_divider()

# 带文字的分隔线
ui.display_divider("初始化阶段")
```

### 4. 消息显示

```python
# 用户消息
ui.display_user_message("你好，请帮我分析这段代码")

# 助手消息（支持 Markdown）
ui.display_assistant_message("""
**分析结果：**

这段代码实现了以下功能：
1. 数据验证
2. 错误处理

```python
def validate(data):
    return data is not None
```
""")

# 系统消息
ui.display_system_message("系统已初始化完成")
ui.display_system_message("配置已加载", title="配置管理")
```

### 5. 状态消息

```python
# 成功消息
ui.display_success("文件保存成功！")

# 警告消息
ui.display_warning("磁盘空间不足，请及时清理")

# 错误消息
ui.display_error("无法连接到服务器")
```

### 6. 思考状态（等待动画）

```python
import time

# 使用上下文管理器显示等待动画
with ui.display_thinking():
    # 执行耗时操作
    time.sleep(2)
    result = some_long_operation()

# 动画会自动结束
```

### 7. 工具调用展示

```python
# 显示工具调用
ui.display_tool_call(
    tool_name="search_database",
    args={"query": "用户信息", "limit": 10},
    server="database_mcp"
)

# 显示工具结果（成功）
ui.display_tool_result("找到 5 条匹配记录", success=True)

# 显示工具结果（失败）
ui.display_tool_result("连接超时", success=False)
```

### 8. JSON 数据展示

```python
# 展示字典数据
data = {
    "status": "success",
    "user": {
        "name": "张三",
        "age": 25,
        "roles": ["admin", "user"]
    },
    "count": 42
}

ui.display_json(data)
ui.display_json(data, title="用户信息")

# 展示 JSON 字符串
json_str = '{"key": "value"}'
ui.display_json(json_str)
```

### 9. 步骤进度展示

```python
# 显示步骤进度
ui.display_step(1, 5, "加载配置文件", "完成")
ui.display_step(2, 5, "连接数据库", "进行中")
ui.display_step(3, 5, "初始化服务", "等待")
ui.display_step(4, 5, "启动应用", "等待")

# 支持的状态：
# - "进行中" (黄色)
# - "完成" (绿色)
# - "失败" (红色)
# - "等待" (蓝色)
```

### 10. 用户输入

```python
# 获取单行输入
user_input = ui.get_user_input()

# 支持多行输入（在行尾添加 \ 继续输入）
# 示例：
# MCP Agent> 这是第一行\
# ... 这是第二行\
# ... 这是第三行
```

---

## 完整工作流示例

### 示例 1：数据处理流程

```python
from mcp_agent.ui import ConsoleUI

ui = ConsoleUI()

# 1. 显示欢迎信息
ui.display_title("数据处理工具", "v1.0.0")

# 2. 显示初始化步骤
ui.display_divider("初始化")
ui.display_step(1, 3, "加载配置", "完成")
ui.display_step(2, 3, "连接数据库", "进行中")

# 3. 显示工具调用
with ui.display_thinking():
    # 模拟数据库查询
    import time
    time.sleep(1)

ui.display_tool_call(
    tool_name="query_database",
    args={"table": "users", "filter": {"active": True}},
    server="postgres_mcp"
)

# 4. 显示结果
ui.display_tool_result("查询成功，找到 100 条记录", success=True)

# 5. 显示数据
ui.display_json({
    "total": 100,
    "active_users": 85,
    "inactive_users": 15
}, title="统计信息")

# 6. 完成提示
ui.display_success("数据处理完成！")
```

### 示例 2：错误处理流程

```python
from mcp_agent.ui import ConsoleUI

ui = ConsoleUI()

try:
    ui.display_step(1, 3, "验证输入", "进行中")
    # ... 验证逻辑

    ui.display_step(2, 3, "处理数据", "进行中")
    # ... 处理逻辑
    raise ValueError("数据格式错误")

except ValueError as e:
    ui.display_error(f"处理失败: {e}")
    ui.display_warning("请检查输入数据格式")

    # 显示详细错误信息
    ui.display_json({
        "error": str(e),
        "error_type": type(e).__name__,
        "step": "数据处理"
    }, title="错误详情")
```

### 示例 3：交互式对话

```python
from mcp_agent.ui import ConsoleUI

ui = ConsoleUI()
ui.display_welcome()

while True:
    # 获取用户输入
    user_input = ui.get_user_input()

    if not user_input:
        continue

    # 处理退出命令
    if user_input.lower() in ['/exit', '/quit']:
        ui.display_system_message("再见！")
        break

    # 显示用户消息
    ui.display_user_message(user_input)

    # 显示思考状态
    with ui.display_thinking():
        # 调用 AI 处理
        response = process_message(user_input)

    # 显示助手回复
    ui.display_assistant_message(response)
```

---

## 样式和颜色说明

各类消息使用不同的颜色边框和标题前缀：

- **用户消息**: 蓝色前缀 "You:"
- **助手消息**: 绿色边框，标题 "Assistant"
- **系统消息**: 青色边框，标题 "[INFO] 系统消息"
- **成功消息**: 绿色边框，标题 "[OK] 成功"
- **警告消息**: 黄色边框，标题 "[WARN] 警告"
- **错误消息**: 红色边框，标题 "[ERROR] 错误"
- **工具调用**: 青色边框，标题 "工具调用"
- **工具结果**: 绿色（成功）或红色（失败）边框
- **JSON 数据**: 洋红色边框，标题 "[JSON] ..."
- **执行步骤**: 蓝色边框，标题 "[STEP] 执行步骤"

---

## 在 Agent 中集成

ConsoleUI 已经集成到 `MCPAgent` 和 `CLI` 类中，使用示例：

```python
from mcp_agent.config import Config
from mcp_agent.agent import MCPAgent
from mcp_agent.ui import ConsoleUI

# 创建 UI 实例
ui = ConsoleUI()

# 创建配置
config = Config()

# 创建 Agent 并传入 UI
agent = MCPAgent(config, ui=ui)

# Agent 会自动使用 UI 显示：
# - 工具调用信息
# - 工具执行结果
# - 错误信息
```

---

## 运行演示

运行内置演示查看所有功能：

```bash
python -m mcp_agent.ui
```

这将展示所有 UI 组件的效果。

---

## 注意事项

1. **编码问题**: 在 Windows 系统上，如果终端编码为 GBK，某些 Unicode 字符可能无法正确显示。建议使用 UTF-8 终端。

2. **终端宽度**: 某些显示效果依赖于终端宽度，建议终端宽度至少 80 字符。

3. **颜色支持**: 确保终端支持 ANSI 颜色代码。现代终端（Windows Terminal、iTerm2、终端.app 等）都支持。

4. **Markdown 渲染**: `display_assistant_message()` 支持完整的 Markdown 语法，包括代码块、列表、表格等。

---

## 扩展和自定义

### 自定义提示符

```python
ui = ConsoleUI(prompt="MyApp>>> ")
ui.set_prompt("NewPrompt> ")
```

### 自定义结果预览长度

```python
ui = ConsoleUI()
ui.max_result_preview = 1000  # 默认 800 字符
```

### 直接访问 Rich Console

```python
ui = ConsoleUI()

# 使用底层 Rich Console 进行更复杂的操作
ui.console.print("[bold red]自定义样式文本[/]")
```

---

## API 参考

### ConsoleUI 类方法

#### `__init__(prompt: str = "MCP Agent> ")`
初始化 UI 实例。

#### `set_prompt(prompt: str) -> None`
设置输入提示符。

#### `display_welcome() -> None`
显示欢迎页面。

#### `display_title(title: str, subtitle: Optional[str] = None) -> None`
显示大标题和副标题。

#### `display_divider(text: Optional[str] = None) -> None`
显示分隔线。

#### `display_user_message(message: str) -> None`
显示用户消息。

#### `display_assistant_message(message: str) -> None`
显示助手消息（支持 Markdown）。

#### `display_system_message(message: str, title: str = "系统消息") -> None`
显示系统消息。

#### `display_success(message: str) -> None`
显示成功消息。

#### `display_warning(warning: str) -> None`
显示警告消息。

#### `display_error(error: str) -> None`
显示错误消息。

#### `display_tool_call(tool_name: str, args: dict, server: Optional[str]) -> None`
显示工具调用信息。

#### `display_tool_result(result: str, success: bool) -> None`
显示工具执行结果。

#### `display_json(data: Any, title: str = "JSON 数据") -> None`
显示 JSON 数据（语法高亮）。

#### `display_step(current: int, total: int, description: str, status: str = "进行中") -> None`
显示步骤进度。

#### `display_thinking() -> ContextManager[Status]`
返回等待动画的上下文管理器。

#### `get_user_input() -> str`
获取用户输入（支持多行）。

---

## 更新日志

### v1.1.0 (2025-12-10)
- ✅ 新增 `display_success()` - 成功消息
- ✅ 新增 `display_warning()` - 警告消息
- ✅ 新增 `display_system_message()` - 系统消息
- ✅ 新增 `display_json()` - JSON 格式化输出
- ✅ 新增 `display_step()` - 步骤进度显示
- ✅ 新增 `display_title()` - 标题展示
- ✅ 新增 `display_divider()` - 分隔线
- ✅ 增强 `display_error()` - 添加 [ERROR] 标记
- ✅ 移除 emoji 字符以兼容 Windows GBK 编码

### v1.0.0
- 初始版本，包含基础 UI 功能
