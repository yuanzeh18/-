# -*- coding: utf-8 -*-
"""
配置管理模块

从YAML配置文件读取项目配置，支持默认值和环境变量覆盖
"""

import os
from pathlib import Path
from typing import Any, Optional
import yaml


class Config:
    """
    配置管理类
    
    从config.yaml读取配置，提供便捷的配置项访问方法
    
    Attributes:
        config_path: 配置文件路径
        _config: 配置数据字典
    """
    
    # 默认配置
    DEFAULT_CONFIG = {
        "auth": {
            "username": "",
            "password": ""
        },
        "scraper": {
            "base_url": "https://www.popfashioninfo.com/styles/designerbrand/",
            "delay_min": 2,
            "delay_max": 5,
            "timeout": 30,
            "max_retries": 3
        },
        "download": {
            "image_dir": "data/images",
            "output_dir": "output",
            "concurrent_downloads": 3
        },
        "proxy": {
            "enabled": False,
            "http": "",
            "https": ""
        },
        "browser": {
            "headless": False,
            "driver": "chrome"
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为项目根目录的config.yaml
        """
        self.config_path = config_path
        self._config = self.DEFAULT_CONFIG.copy()
        
        if config_path and Path(config_path).exists():
            self._load_config()
        else:
            # 尝试加载默认路径的配置文件
            default_path = Path(__file__).parent.parent.parent / "config.yaml"
            if default_path.exists():
                self.config_path = str(default_path)
                self._load_config()
    
    def _load_config(self) -> None:
        """从YAML文件加载配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f) or {}
            
            # 深度合并配置
            self._merge_config(self._config, file_config)
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件格式错误: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
    
    def _merge_config(self, base: dict, override: dict) -> None:
        """
        深度合并配置字典
        
        Args:
            base: 基础配置
            override: 覆盖配置
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        支持点号分隔的多级key，如 "scraper.delay_min"
        
        Args:
            key: 配置项键名
            default: 默认值
            
        Returns:
            配置值或默认值
        """
        keys = key.split(".")
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    @property
    def auth(self) -> dict:
        """获取认证配置"""
        return self._config.get("auth", {})
    
    @property
    def username(self) -> str:
        """获取用户名"""
        # 优先从环境变量获取
        return os.getenv("POP_USERNAME", self.auth.get("username", ""))
    
    @property
    def password(self) -> str:
        """获取密码"""
        # 优先从环境变量获取
        return os.getenv("POP_PASSWORD", self.auth.get("password", ""))
    
    @property
    def scraper(self) -> dict:
        """获取爬虫配置"""
        return self._config.get("scraper", {})
    
    @property
    def base_url(self) -> str:
        """获取基础URL"""
        return self.scraper.get("base_url", self.DEFAULT_CONFIG["scraper"]["base_url"])
    
    @property
    def delay_min(self) -> int:
        """获取最小延迟"""
        return self.scraper.get("delay_min", 2)
    
    @property
    def delay_max(self) -> int:
        """获取最大延迟"""
        return self.scraper.get("delay_max", 5)
    
    @property
    def timeout(self) -> int:
        """获取请求超时时间"""
        return self.scraper.get("timeout", 30)
    
    @property
    def max_retries(self) -> int:
        """获取最大重试次数"""
        return self.scraper.get("max_retries", 3)
    
    @property
    def download(self) -> dict:
        """获取下载配置"""
        return self._config.get("download", {})
    
    @property
    def image_dir(self) -> str:
        """获取图片存储目录"""
        return self.download.get("image_dir", "data/images")
    
    @property
    def output_dir(self) -> str:
        """获取输出目录"""
        return self.download.get("output_dir", "output")
    
    @property
    def concurrent_downloads(self) -> int:
        """获取并发下载数"""
        return self.download.get("concurrent_downloads", 3)
    
    @property
    def proxy(self) -> dict:
        """获取代理配置"""
        return self._config.get("proxy", {})
    
    @property
    def proxy_enabled(self) -> bool:
        """代理是否启用"""
        return self.proxy.get("enabled", False)
    
    @property
    def browser(self) -> dict:
        """获取浏览器配置"""
        return self._config.get("browser", {})
    
    @property
    def headless(self) -> bool:
        """是否无头模式"""
        return self.browser.get("headless", False)
    
    @property
    def driver(self) -> str:
        """获取浏览器驱动类型"""
        return self.browser.get("driver", "chrome")
    
    def to_dict(self) -> dict:
        """返回完整配置字典"""
        return self._config.copy()
    
    def __repr__(self) -> str:
        return f"Config(config_path={self.config_path})"
