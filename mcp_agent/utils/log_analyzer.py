"""
日志分析工具模块

提供日志文件分析和统计功能。
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import Counter, defaultdict


class LogAnalyzer:
    """日志分析器类"""
    
    # 日志级别模式
    LEVEL_PATTERN = re.compile(r"\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b")
    
    # 时间戳模式
    TIMESTAMP_PATTERN = re.compile(
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
    )
    
    def __init__(self, log_file: str):
        """
        初始化日志分析器
        
        Args:
            log_file: 日志文件路径
        """
        self.log_file = Path(log_file)
        self.lines: List[str] = []
        self.stats: Dict = {}
    
    def load(self) -> None:
        """加载日志文件"""
        if not self.log_file.exists():
            raise FileNotFoundError(f"日志文件不存在: {self.log_file}")
        
        with open(self.log_file, "r", encoding="utf-8") as f:
            self.lines = f.readlines()
    
    def analyze(self) -> Dict:
        """
        分析日志文件
        
        Returns:
            分析结果字典
        """
        if not self.lines:
            self.load()
        
        self.stats = {
            "total_lines": len(self.lines),
            "level_counts": self._count_levels(),
            "error_messages": self._extract_errors(),
            "time_range": self._get_time_range(),
            "module_stats": self._count_modules(),
            "hourly_distribution": self._get_hourly_distribution(),
        }
        
        return self.stats
    
    def _count_levels(self) -> Dict[str, int]:
        """
        统计各级别日志数量
        
        Returns:
            级别计数字典
        """
        level_counts = Counter()
        
        for line in self.lines:
            match = self.LEVEL_PATTERN.search(line)
            if match:
                level = match.group(1)
                level_counts[level] += 1
        
        return dict(level_counts)
    
    def _extract_errors(self) -> List[str]:
        """
        提取错误消息
        
        Returns:
            错误消息列表
        """
        errors = []
        
        for line in self.lines:
            if "ERROR" in line or "CRITICAL" in line:
                errors.append(line.strip())
        
        return errors
    
    def _get_time_range(self) -> Optional[Tuple[str, str]]:
        """
        获取日志时间范围
        
        Returns:
            (开始时间, 结束时间) 或 None
        """
        timestamps = []
        
        for line in self.lines:
            match = self.TIMESTAMP_PATTERN.search(line)
            if match:
                timestamps.append(match.group(1))
        
        if timestamps:
            return (timestamps[0], timestamps[-1])
        
        return None
    
    def _count_modules(self) -> Dict[str, int]:
        """
        统计各模块日志数量
        
        Returns:
            模块计数字典
        """
        module_counts = Counter()
        module_pattern = re.compile(r" - (\w+(?:\.\w+)*) - ")
        
        for line in self.lines:
            match = module_pattern.search(line)
            if match:
                module = match.group(1)
                module_counts[module] += 1
        
        return dict(module_counts.most_common(10))
    
    def _get_hourly_distribution(self) -> Dict[int, int]:
        """
        获取按小时的日志分布
        
        Returns:
            小时分布字典
        """
        hourly_counts = defaultdict(int)
        
        for line in self.lines:
            match = self.TIMESTAMP_PATTERN.search(line)
            if match:
                timestamp_str = match.group(1)
                try:
                    dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    hourly_counts[dt.hour] += 1
                except ValueError:
                    continue
        
        return dict(hourly_counts)
    
    def search(
        self,
        pattern: str,
        case_sensitive: bool = False,
    ) -> List[str]:
        """
        搜索日志内容
        
        Args:
            pattern: 搜索模式（正则表达式）
            case_sensitive: 是否区分大小写
        
        Returns:
            匹配的日志行列表
        """
        if not self.lines:
            self.load()
        
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)
        
        matches = []
        for line in self.lines:
            if regex.search(line):
                matches.append(line.strip())
        
        return matches
    
    def filter_by_level(self, level: str) -> List[str]:
        """
        按级别过滤日志
        
        Args:
            level: 日志级别
        
        Returns:
            过滤后的日志行列表
        """
        if not self.lines:
            self.load()
        
        filtered = []
        for line in self.lines:
            if level.upper() in line:
                filtered.append(line.strip())
        
        return filtered
    
    def filter_by_time_range(
        self,
        start_time: str,
        end_time: str,
    ) -> List[str]:
        """
        按时间范围过滤日志
        
        Args:
            start_time: 开始时间（格式：YYYY-MM-DD HH:MM:SS）
            end_time: 结束时间（格式：YYYY-MM-DD HH:MM:SS）
        
        Returns:
            过滤后的日志行列表
        """
        if not self.lines:
            self.load()
        
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            raise ValueError(f"时间格式错误: {e}")
        
        filtered = []
        for line in self.lines:
            match = self.TIMESTAMP_PATTERN.search(line)
            if match:
                timestamp_str = match.group(1)
                try:
                    dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    if start_dt <= dt <= end_dt:
                        filtered.append(line.strip())
                except ValueError:
                    continue
        
        return filtered
    
    def get_summary(self) -> str:
        """
        获取日志摘要
        
        Returns:
            摘要文本
        """
        if not self.stats:
            self.analyze()
        
        summary = []
        summary.append("=" * 50)
        summary.append("日志分析摘要")
        summary.append("=" * 50)
        summary.append(f"日志文件: {self.log_file}")
        summary.append(f"总行数: {self.stats['total_lines']}")
        
        # 级别统计
        summary.append("\n级别统计:")
        for level, count in sorted(self.stats['level_counts'].items()):
            percentage = (count / self.stats['total_lines']) * 100
            summary.append(f"  {level}: {count} ({percentage:.1f}%)")
        
        # 时间范围
        if self.stats['time_range']:
            start, end = self.stats['time_range']
            summary.append(f"\n时间范围: {start} 至 {end}")
        
        # 错误数量
        error_count = len(self.stats['error_messages'])
        if error_count > 0:
            summary.append(f"\n错误/严重错误数: {error_count}")
            summary.append("最近的错误:")
            for error in self.stats['error_messages'][-5:]:
                summary.append(f"  {error[:100]}...")
        
        # 模块统计
        if self.stats['module_stats']:
            summary.append("\n活跃模块 (Top 5):")
            for module, count in list(self.stats['module_stats'].items())[:5]:
                summary.append(f"  {module}: {count}")
        
        summary.append("=" * 50)
        
        return "\n".join(summary)
    
    def export_errors(self, output_file: str) -> None:
        """
        导出错误日志到文件
        
        Args:
            output_file: 输出文件路径
        """
        if not self.stats:
            self.analyze()
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("错误日志导出\n")
            f.write("=" * 50 + "\n\n")
            
            for error in self.stats['error_messages']:
                f.write(error + "\n")
        
        print(f"错误日志已导出到: {output_path}")


def analyze_log_file(log_file: str) -> Dict:
    """
    分析日志文件的便捷函数
    
    Args:
        log_file: 日志文件路径
    
    Returns:
        分析结果字典
    """
    analyzer = LogAnalyzer(log_file)
    return analyzer.analyze()


def print_log_summary(log_file: str) -> None:
    """
    打印日志摘要的便捷函数
    
    Args:
        log_file: 日志文件路径
    """
    analyzer = LogAnalyzer(log_file)
    analyzer.analyze()
    print(analyzer.get_summary())