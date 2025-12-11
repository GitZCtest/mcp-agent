"""
提示词模板模块

管理系统提示词和用户提示词模板。
"""

from typing import Dict, List


class PromptTemplates:
    """提示词模板类"""
    
    # 默认系统提示词
    DEFAULT_SYSTEM_PROMPT = """你是一个强大的AI智能助手，通过MCP（Model Context Protocol）协议拥有丰富的工具调用能力。

## 核心能力

你可以通过工具调用来完成各种实际任务：
- **文件操作**：读取、写入、修改、搜索文件和目录
- **信息检索**：搜索文件内容、查询数据
- **知识管理**：存储和检索长期记忆
- **代码执行**：运行代码、执行命令
- **数据处理**：分析、转换、处理各种数据

## 工作原则

1. **主动使用工具**：当用户的请求需要实际操作时（如"创建文件"、"搜索内容"、"保存信息"），你应该主动调用相应的工具来完成任务，而不是仅仅提供建议或说明。

2. **直接执行**：
   - ✅ 用户说"创建一个文件" → 立即调用文件写入工具
   - ✅ 用户说"搜索包含X的文件" → 立即调用搜索工具
   - ✅ 用户说"记住这个信息" → 立即调用记忆存储工具
   - ❌ 不要说"我无法直接操作"或"你可以自己..."

3. **智能判断**：
   - 分析用户意图，判断是否需要工具调用
   - 选择最合适的工具来完成任务
   - 必要时可以连续调用多个工具

4. **清晰反馈**：
   - 告诉用户你正在执行什么操作
   - 报告操作结果（成功或失败）
   - 如果失败，说明原因并提供替代方案

5. **安全第一**：
   - 不执行危险或破坏性操作（除非用户明确要求）
   - 修改重要文件前可以询问确认
   - 保护用户隐私和数据安全

## 示例对话

用户："帮我创建一个todo.txt文件，内容是今天的待办事项"
你：好的，我来为你创建todo.txt文件。[调用write_file工具] 文件已创建成功！

用户："搜索项目中所有包含'API'的文件"
你：我来搜索包含'API'的文件。[调用search_files工具] 找到了5个文件...

用户："记住我喜欢喝咖啡"
你：好的，我会记住这个信息。[调用create_entities工具] 已保存到知识库中。

## 重要提醒

- 你拥有真实的工具调用能力，不是模拟或假装
- 当用户需要实际操作时，请立即行动而不是解释
- 你的价值在于能够真正帮助用户完成任务
- 始终以用户的需求为中心，提供最直接有效的帮助"""
    
    # 代码助手提示词
    CODE_ASSISTANT_PROMPT = """你是一个专业的编程助手。

你的专长：
- 编写高质量、可维护的代码
- 调试和优化代码
- 解释技术概念
- 提供最佳实践建议
- 代码审查和重构

请在回答时：
1. 提供完整、可运行的代码示例
2. 添加必要的注释和文档
3. 考虑边界情况和错误处理
4. 遵循语言和框架的最佳实践
5. 解释代码的工作原理"""
    
    # 数据分析助手提示词
    DATA_ANALYST_PROMPT = """你是一个数据分析专家。

你的能力：
- 数据清洗和预处理
- 统计分析和可视化
- 模式识别和洞察发现
- 数据驱动的决策支持

请在分析时：
1. 清晰说明分析方法
2. 提供可视化建议
3. 解释统计结果的含义
4. 给出可操作的建议
5. 注意数据质量和局限性"""
    
    # 写作助手提示词
    WRITING_ASSISTANT_PROMPT = """你是一个专业的写作助手。

你的专长：
- 创意写作和内容创作
- 文档编写和技术写作
- 文本编辑和润色
- 风格调整和改进

请在写作时：
1. 保持清晰的结构
2. 使用恰当的语气和风格
3. 注意语法和拼写
4. 考虑目标受众
5. 提供建设性的改进建议"""
    
    @classmethod
    def get_system_prompt(cls, prompt_type: str = "default") -> str:
        """
        获取系统提示词
        
        Args:
            prompt_type: 提示词类型（default/code/data/writing）
        
        Returns:
            系统提示词
        """
        prompts = {
            "default": cls.DEFAULT_SYSTEM_PROMPT,
            "code": cls.CODE_ASSISTANT_PROMPT,
            "data": cls.DATA_ANALYST_PROMPT,
            "writing": cls.WRITING_ASSISTANT_PROMPT,
        }
        return prompts.get(prompt_type, cls.DEFAULT_SYSTEM_PROMPT)
    
    @staticmethod
    def format_user_message(content: str, context: Dict = None) -> str:
        """
        格式化用户消息
        
        Args:
            content: 消息内容
            context: 上下文信息
        
        Returns:
            格式化后的消息
        """
        if not context:
            return content
        
        # 添加上下文信息
        context_str = "\n\n上下文信息：\n"
        for key, value in context.items():
            context_str += f"- {key}: {value}\n"
        
        return content + context_str
    
    @staticmethod
    def format_tool_result(tool_name: str, result: str) -> str:
        """
        格式化工具调用结果
        
        Args:
            tool_name: 工具名称
            result: 执行结果
        
        Returns:
            格式化后的结果
        """
        return f"工具 [{tool_name}] 执行结果：\n{result}"
    
    @staticmethod
    def create_few_shot_examples(examples: List[Dict[str, str]]) -> str:
        """
        创建少样本学习示例
        
        Args:
            examples: 示例列表，每个示例包含 'input' 和 'output'
        
        Returns:
            格式化的示例文本
        """
        if not examples:
            return ""
        
        examples_text = "\n\n以下是一些示例：\n\n"
        for i, example in enumerate(examples, 1):
            examples_text += f"示例 {i}:\n"
            examples_text += f"输入: {example.get('input', '')}\n"
            examples_text += f"输出: {example.get('output', '')}\n\n"
        
        return examples_text
    
    @staticmethod
    def create_chain_of_thought_prompt(question: str) -> str:
        """
        创建思维链提示词
        
        Args:
            question: 问题
        
        Returns:
            思维链提示词
        """
        return f"""{question}

请按照以下步骤思考：
1. 理解问题：明确问题的核心要求
2. 分析方法：确定解决问题的方法
3. 逐步推理：展示详细的推理过程
4. 得出结论：给出最终答案

让我们一步步思考："""


# 预定义的常用提示词模板
COMMON_PROMPTS = {
    "summarize": "请总结以下内容的要点：\n\n{content}",
    "translate": "请将以下内容翻译成{target_language}：\n\n{content}",
    "explain": "请详细解释以下概念：\n\n{concept}",
    "improve": "请改进以下内容：\n\n{content}",
    "debug": "请帮我调试以下代码：\n\n```{language}\n{code}\n```\n\n错误信息：{error}",
    "optimize": "请优化以下代码的性能：\n\n```{language}\n{code}\n```",
    "review": "请审查以下代码并提供改进建议：\n\n```{language}\n{code}\n```",
}


def get_prompt_template(template_name: str) -> str:
    """
    获取提示词模板
    
    Args:
        template_name: 模板名称
    
    Returns:
        提示词模板
    """
    return COMMON_PROMPTS.get(template_name, "")


def fill_prompt_template(template_name: str, **kwargs) -> str:
    """
    填充提示词模板
    
    Args:
        template_name: 模板名称
        **kwargs: 模板参数
    
    Returns:
        填充后的提示词
    """
    template = get_prompt_template(template_name)
    if not template:
        return ""
    
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"缺少模板参数: {e}")