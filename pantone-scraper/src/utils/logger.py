# -*- coding: utf-8 -*-
"""
日志记录模块

提供彩色控制台输出和文件日志记录功能
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


# 日志级别颜色映射
COLORS = {
    'DEBUG': '\033[36m',     # 青色
    'INFO': '\033[32m',      # 绿色
    'WARNING': '\033[33m',   # 黄色
    'ERROR': '\033[31m',     # 红色
    'CRITICAL': '\033[35m',  # 紫色
    'RESET': '\033[0m'       # 重置
}


class ColoredFormatter(logging.Formatter):
    """
    彩色日志格式化器
    
    为不同级别的日志添加不同的颜色
    """
    
    def __init__(self, fmt: str = None, datefmt: str = None, use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        if self.use_colors and record.levelname in COLORS:
            color = COLORS[record.levelname]
            reset = COLORS['RESET']
            record.levelname = f"{color}{record.levelname}{reset}"
            record.msg = f"{color}{record.msg}{reset}"
        
        return super().format(record)


def setup_logger(
    name: str = "pantone_scraper",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_dir: str = "logs"
) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件名，None则使用默认名称
        log_dir: 日志文件目录
        
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 日志格式
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 控制台处理器（带颜色）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # 检测是否支持颜色输出
    use_colors = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    console_formatter = ColoredFormatter(log_format, date_format, use_colors)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（不带颜色）
    if log_file is not None or log_dir:
        # 创建日志目录
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # 生成日志文件名
        if log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"scraper_{timestamp}.log"
        
        file_path = log_path / log_file
        
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(log_format, date_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "pantone_scraper") -> logging.Logger:
    """
    获取已存在的日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        日志记录器实例
    """
    logger = logging.getLogger(name)
    
    # 如果没有handler，创建一个基本的
    if not logger.handlers:
        return setup_logger(name)
    
    return logger


class LoggerMixin:
    """
    日志混入类
    
    为类提供便捷的日志记录方法
    """
    
    @property
    def logger(self) -> logging.Logger:
        """获取类专用的日志记录器"""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger
    
    def log_info(self, message: str) -> None:
        """记录信息日志"""
        self.logger.info(message)
    
    def log_debug(self, message: str) -> None:
        """记录调试日志"""
        self.logger.debug(message)
    
    def log_warning(self, message: str) -> None:
        """记录警告日志"""
        self.logger.warning(message)
    
    def log_error(self, message: str) -> None:
        """记录错误日志"""
        self.logger.error(message)
    
    def log_exception(self, message: str) -> None:
        """记录异常日志（包含堆栈信息）"""
        self.logger.exception(message)
