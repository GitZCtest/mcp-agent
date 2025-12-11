"""
会话管理模块

提供会话的自动保存、列表、搜索、导出和统计功能。
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

from mcp_agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SessionStats:
    """会话统计信息"""
    total_turns: int = 0
    user_messages: int = 0
    assistant_messages: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: float = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SessionData:
    """会话数据"""
    session_id: str
    created_at: str
    updated_at: str
    provider: str
    model: str
    system_prompt: str
    conversation_history: List[Dict[str, Any]]
    stats: SessionStats
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['stats'] = self.stats.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionData':
        stats_data = data.get('stats', {})
        stats = SessionStats(**stats_data) if stats_data else SessionStats()
        return cls(
            session_id=data.get('session_id', ''),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            provider=data.get('provider', ''),
            model=data.get('model', ''),
            system_prompt=data.get('system_prompt', ''),
            conversation_history=data.get('conversation_history', []),
            stats=stats,
            metadata=data.get('metadata', {}),
        )


class SessionManager:
    """
    会话管理器

    功能：
    - 自动保存会话
    - 会话列表和搜索
    - 会话导出（Markdown、HTML）
    - 会话统计
    """

    def __init__(self, session_dir: str = "sessions", auto_save: bool = True):
        """
        初始化会话管理器

        Args:
            session_dir: 会话保存目录
            auto_save: 是否启用自动保存
        """
        self.session_dir = Path(session_dir)
        self.auto_save = auto_save
        self.current_session: Optional[SessionData] = None
        self._stats = SessionStats()

        # 确保会话目录存在
        self.session_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"会话管理器初始化完成，目录: {self.session_dir}")

    def create_session(
        self,
        provider: str,
        model: str,
        system_prompt: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        创建新会话

        Args:
            provider: LLM提供商
            model: 模型名称
            system_prompt: 系统提示词
            metadata: 额外元数据

        Returns:
            会话ID
        """
        now = datetime.now()
        session_id = now.strftime("session_%Y%m%d_%H%M%S")

        self._stats = SessionStats(start_time=now.isoformat())

        self.current_session = SessionData(
            session_id=session_id,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            conversation_history=[],
            stats=self._stats,
            metadata=metadata or {},
        )

        logger.info(f"创建新会话: {session_id}")
        return session_id

    def update_session(
        self,
        conversation_history: List[Dict[str, Any]],
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """
        更新当前会话

        Args:
            conversation_history: 对话历史
            input_tokens: 本次输入token数
            output_tokens: 本次输出token数
        """
        if not self.current_session:
            logger.warning("没有活动会话，无法更新")
            return

        now = datetime.now()
        self.current_session.updated_at = now.isoformat()
        self.current_session.conversation_history = conversation_history

        # 更新统计
        self._update_stats(conversation_history, input_tokens, output_tokens)
        self.current_session.stats = self._stats

        # 自动保存
        if self.auto_save:
            self.save_session()

    def _update_stats(
        self,
        history: List[Dict[str, Any]],
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> None:
        """更新统计信息"""
        user_count = sum(1 for msg in history if msg.get("role") == "user")
        assistant_count = sum(1 for msg in history if msg.get("role") == "assistant")
        tool_count = sum(
            len(msg.get("tool_calls", []))
            for msg in history
            if msg.get("role") == "assistant" and "tool_calls" in msg
        )

        self._stats.user_messages = user_count
        self._stats.assistant_messages = assistant_count
        self._stats.total_turns = min(user_count, assistant_count)
        self._stats.tool_calls = tool_count
        self._stats.input_tokens += input_tokens
        self._stats.output_tokens += output_tokens
        self._stats.total_tokens = self._stats.input_tokens + self._stats.output_tokens

        # 计算持续时间
        if self._stats.start_time:
            start = datetime.fromisoformat(self._stats.start_time)
            self._stats.end_time = datetime.now().isoformat()
            self._stats.duration_seconds = (datetime.now() - start).total_seconds()

    def save_session(self, session_id: Optional[str] = None) -> str:
        """
        保存会话到文件

        Args:
            session_id: 会话ID，默认使用当前会话

        Returns:
            保存的文件路径
        """
        session = self.current_session
        if not session:
            raise ValueError("没有活动会话可保存")

        if session_id:
            session.session_id = session_id

        filename = f"{session.session_id}.json"
        filepath = self.session_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

        logger.debug(f"会话已保存: {filepath}")
        return str(filepath)

    def load_session(self, session_id: str) -> SessionData:
        """
        加载会话

        Args:
            session_id: 会话ID

        Returns:
            会话数据
        """
        # 支持带或不带.json后缀
        if not session_id.endswith('.json'):
            filename = f"{session_id}.json"
        else:
            filename = session_id
            session_id = session_id[:-5]

        filepath = self.session_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"会话文件不存在: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        session = SessionData.from_dict(data)
        self.current_session = session
        self._stats = session.stats

        logger.info(f"会话已加载: {session_id}")
        return session

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        列出所有会话

        Args:
            limit: 最大返回数量

        Returns:
            会话摘要列表
        """
        sessions = []

        for filepath in sorted(self.session_dir.glob("session_*.json"), reverse=True):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 提取摘要信息
                history = data.get('conversation_history', [])
                first_user_msg = next(
                    (msg.get('content', '')[:50] for msg in history if msg.get('role') == 'user'),
                    '(空会话)'
                )

                sessions.append({
                    'session_id': data.get('session_id', filepath.stem),
                    'created_at': data.get('created_at', ''),
                    'updated_at': data.get('updated_at', ''),
                    'provider': data.get('provider', ''),
                    'model': data.get('model', ''),
                    'message_count': len(history),
                    'preview': first_user_msg + ('...' if len(first_user_msg) >= 50 else ''),
                    'stats': data.get('stats', {}),
                })

                if len(sessions) >= limit:
                    break

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"读取会话文件失败 {filepath}: {e}")
                continue

        return sessions

    def search_sessions(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索会话内容

        Args:
            keyword: 搜索关键词
            limit: 最大返回数量

        Returns:
            匹配的会话列表
        """
        results = []
        keyword_lower = keyword.lower()
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)

        for filepath in sorted(self.session_dir.glob("session_*.json"), reverse=True):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                history = data.get('conversation_history', [])
                matches = []

                for i, msg in enumerate(history):
                    content = msg.get('content', '')
                    if content and keyword_lower in content.lower():
                        # 提取匹配上下文
                        match = pattern.search(content)
                        if match:
                            start = max(0, match.start() - 30)
                            end = min(len(content), match.end() + 30)
                            context = content[start:end]
                            if start > 0:
                                context = '...' + context
                            if end < len(content):
                                context = context + '...'
                            matches.append({
                                'index': i,
                                'role': msg.get('role'),
                                'context': context,
                            })

                if matches:
                    results.append({
                        'session_id': data.get('session_id', filepath.stem),
                        'created_at': data.get('created_at', ''),
                        'provider': data.get('provider', ''),
                        'model': data.get('model', ''),
                        'match_count': len(matches),
                        'matches': matches[:3],
                    })

                    if len(results) >= limit:
                        break

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"搜索会话文件失败 {filepath}: {e}")
                continue

        return results

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话摘要

        Args:
            session_id: 会话ID

        Returns:
            会话摘要信息
        """
        session = self.load_session(session_id)

        # 提取关键信息
        history = session.conversation_history
        user_messages = [msg for msg in history if msg.get('role') == 'user']
        assistant_messages = [msg for msg in history if msg.get('role') == 'assistant']

        # 获取首尾消息
        first_user = user_messages[0].get('content', '')[:100] if user_messages else ''
        last_assistant = assistant_messages[-1].get('content', '')[:100] if assistant_messages else ''

        return {
            'session_id': session.session_id,
            'created_at': session.created_at,
            'updated_at': session.updated_at,
            'provider': session.provider,
            'model': session.model,
            'total_messages': len(history),
            'stats': session.stats.to_dict(),
            'first_message': first_user + ('...' if len(first_user) >= 100 else ''),
            'last_response': last_assistant + ('...' if len(last_assistant) >= 100 else ''),
        }

    def get_current_stats(self) -> Dict[str, Any]:
        """获取当前会话统计"""
        if not self.current_session:
            return {}
        return self._stats.to_dict()

    def export_to_markdown(self, session_id: str, output_path: Optional[str] = None) -> str:
        """
        导出会话为Markdown格式

        Args:
            session_id: 会话ID
            output_path: 输出路径，默认为会话目录

        Returns:
            导出文件路径
        """
        session = self.load_session(session_id)

        lines = [
            f"# 会话记录: {session.session_id}",
            "",
            "## 会话信息",
            "",
            f"- **创建时间**: {session.created_at}",
            f"- **更新时间**: {session.updated_at}",
            f"- **提供商**: {session.provider}",
            f"- **模型**: {session.model}",
            f"- **总消息数**: {len(session.conversation_history)}",
            "",
            "## 统计信息",
            "",
            f"- **对话轮数**: {session.stats.total_turns}",
            f"- **工具调用**: {session.stats.tool_calls} 次",
            f"- **Token使用**: 输入 {session.stats.input_tokens}, 输出 {session.stats.output_tokens}, 总计 {session.stats.total_tokens}",
            f"- **持续时间**: {session.stats.duration_seconds:.1f} 秒",
            "",
            "---",
            "",
            "## 对话内容",
            "",
        ]

        for msg in session.conversation_history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')

            if role == 'user':
                lines.append(f"### 👤 用户")
                lines.append("")
                lines.append(content)
                lines.append("")
            elif role == 'assistant':
                lines.append(f"### 🤖 助手")
                lines.append("")
                if 'tool_calls' in msg and msg['tool_calls']:
                    lines.append("**工具调用:**")
                    for tc in msg['tool_calls']:
                        func = tc.get('function', {})
                        lines.append(f"- `{func.get('name', 'unknown')}`")
                    lines.append("")
                if content:
                    lines.append(content)
                    lines.append("")
            elif role == 'tool':
                lines.append(f"### 🔧 工具结果")
                lines.append("")
                lines.append("```")
                lines.append(content[:500] + ('...' if len(content) > 500 else ''))
                lines.append("```")
                lines.append("")

        # 确定输出路径
        if output_path:
            filepath = Path(output_path)
        else:
            filepath = self.session_dir / f"{session.session_id}.md"

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        logger.info(f"会话已导出为Markdown: {filepath}")
        return str(filepath)

    def export_to_html(self, session_id: str, output_path: Optional[str] = None) -> str:
        """
        导出会话为HTML格式

        Args:
            session_id: 会话ID
            output_path: 输出路径，默认为会话目录

        Returns:
            导出文件路径
        """
        session = self.load_session(session_id)

        html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>会话记录: {session_id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .stats {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .message {{ margin-bottom: 15px; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .user {{ background: #e3f2fd; border-left: 4px solid #2196f3; }}
        .assistant {{ background: white; border-left: 4px solid #4caf50; }}
        .tool {{ background: #fff3e0; border-left: 4px solid #ff9800; font-family: monospace; font-size: 0.9em; }}
        .role {{ font-weight: bold; margin-bottom: 10px; }}
        .content {{ white-space: pre-wrap; word-wrap: break-word; }}
        pre {{ background: #263238; color: #aed581; padding: 10px; border-radius: 4px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📝 会话记录</h1>
        <p>ID: {session_id}</p>
        <p>创建: {created_at} | 更新: {updated_at}</p>
        <p>模型: {provider} / {model}</p>
    </div>
    <div class="stats">
        <h3>📊 统计信息</h3>
        <p>对话轮数: {turns} | 工具调用: {tool_calls} 次 | Token: {tokens}</p>
    </div>
    <div class="messages">
        {messages}
    </div>
</body>
</html>'''

        messages_html = []
        for msg in session.conversation_history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '') or ''
            # 转义HTML
            content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            if role == 'user':
                messages_html.append(f'''
                <div class="message user">
                    <div class="role">👤 用户</div>
                    <div class="content">{content}</div>
                </div>''')
            elif role == 'assistant':
                tool_info = ''
                if 'tool_calls' in msg and msg['tool_calls']:
                    tools = ', '.join(tc.get('function', {}).get('name', '') for tc in msg['tool_calls'])
                    tool_info = f'<p><strong>工具调用:</strong> {tools}</p>'
                messages_html.append(f'''
                <div class="message assistant">
                    <div class="role">🤖 助手</div>
                    {tool_info}
                    <div class="content">{content}</div>
                </div>''')
            elif role == 'tool':
                preview = content[:500] + ('...' if len(content) > 500 else '')
                messages_html.append(f'''
                <div class="message tool">
                    <div class="role">🔧 工具结果</div>
                    <pre>{preview}</pre>
                </div>''')

        html = html_template.format(
            session_id=session.session_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            provider=session.provider,
            model=session.model,
            turns=session.stats.total_turns,
            tool_calls=session.stats.tool_calls,
            tokens=f"输入 {session.stats.input_tokens}, 输出 {session.stats.output_tokens}",
            messages='\n'.join(messages_html),
        )

        # 确定输出路径
        if output_path:
            filepath = Path(output_path)
        else:
            filepath = self.session_dir / f"{session.session_id}.html"

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"会话已导出为HTML: {filepath}")
        return str(filepath)

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话ID

        Returns:
            是否删除成功
        """
        if not session_id.endswith('.json'):
            filename = f"{session_id}.json"
        else:
            filename = session_id

        filepath = self.session_dir / filename

        if filepath.exists():
            filepath.unlink()
            logger.info(f"会话已删除: {session_id}")
            return True

        return False
