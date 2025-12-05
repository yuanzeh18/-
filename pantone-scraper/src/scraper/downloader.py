# -*- coding: utf-8 -*-
"""
图片下载模块

支持异步下载、断点续传和进度显示
"""

import os
import re
import asyncio
import aiohttp
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor

from ..utils.config import Config
from ..utils.logger import get_logger


class ImageDownloader:
    """
    图片下载器
    
    支持异步批量下载、断点续传和进度显示
    
    Attributes:
        config: 配置对象
        logger: 日志记录器
        download_dir: 下载目录
        downloaded_count: 已下载数量
        failed_count: 失败数量
    """
    
    # 常见的 User-Agent
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    def __init__(self, config: Config):
        """
        初始化下载器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.logger = get_logger("ImageDownloader")
        self.download_dir = Path(config.image_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.downloaded_count = 0
        self.failed_count = 0
        self._download_history: Dict[str, str] = {}
    
    def _get_filename_from_url(self, url: str) -> str:
        """
        从URL中提取文件名
        
        Args:
            url: 图片URL
            
        Returns:
            文件名
        """
        parsed = urlparse(url)
        path = unquote(parsed.path)
        filename = os.path.basename(path)
        
        # 如果没有有效文件名，使用URL的hash
        if not filename or '.' not in filename:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            filename = f"image_{url_hash}.jpg"
        
        # 清理文件名中的非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        return filename
    
    def _get_unique_filepath(self, filename: str) -> Path:
        """
        获取唯一的文件路径
        
        如果文件已存在，添加序号后缀
        
        Args:
            filename: 原始文件名
            
        Returns:
            唯一的文件路径
        """
        filepath = self.download_dir / filename
        
        if not filepath.exists():
            return filepath
        
        # 分离文件名和扩展名
        name, ext = os.path.splitext(filename)
        counter = 1
        
        while filepath.exists():
            new_filename = f"{name}_{counter}{ext}"
            filepath = self.download_dir / new_filename
            counter += 1
        
        return filepath
    
    async def _download_single(
        self, 
        session: aiohttp.ClientSession, 
        url: str,
        semaphore: asyncio.Semaphore
    ) -> Tuple[str, Optional[str]]:
        """
        下载单个图片
        
        Args:
            session: aiohttp会话
            url: 图片URL
            semaphore: 信号量，控制并发
            
        Returns:
            (url, 本地路径) 或 (url, None) 如果下载失败
        """
        async with semaphore:
            try:
                # 检查是否已下载
                if url in self._download_history:
                    return url, self._download_history[url]
                
                filename = self._get_filename_from_url(url)
                filepath = self._get_unique_filepath(filename)
                
                # 检查是否已存在（断点续传）
                if filepath.exists():
                    self.logger.debug(f"文件已存在，跳过: {filepath.name}")
                    self._download_history[url] = str(filepath)
                    return url, str(filepath)
                
                headers = {
                    'User-Agent': self.USER_AGENTS[0],
                    'Referer': 'https://www.popfashioninfo.com/',
                }
                
                self.logger.info(f"正在下载: {filename}")
                
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=self.config.timeout)) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # 验证内容类型
                        content_type = response.headers.get('Content-Type', '')
                        if 'image' not in content_type and len(content) < 1000:
                            self.logger.warning(f"下载的内容可能不是图片: {url}")
                        
                        # 保存文件
                        with open(filepath, 'wb') as f:
                            f.write(content)
                        
                        self.downloaded_count += 1
                        self._download_history[url] = str(filepath)
                        self.logger.info(f"下载完成: {filepath.name} ({len(content) / 1024:.1f} KB)")
                        return url, str(filepath)
                    else:
                        self.logger.warning(f"下载失败 (HTTP {response.status}): {url}")
                        self.failed_count += 1
                        return url, None
                        
            except asyncio.TimeoutError:
                self.logger.warning(f"下载超时: {url}")
                self.failed_count += 1
                return url, None
            except aiohttp.ClientError as e:
                self.logger.warning(f"下载错误: {url} - {e}")
                self.failed_count += 1
                return url, None
            except Exception as e:
                self.logger.error(f"下载异常: {url} - {e}")
                self.failed_count += 1
                return url, None
    
    async def download_all_async(self, urls: List[str]) -> Dict[str, Optional[str]]:
        """
        异步批量下载图片
        
        Args:
            urls: 图片URL列表
            
        Returns:
            URL到本地路径的映射字典
        """
        if not urls:
            return {}
        
        self.logger.info(f"开始下载 {len(urls)} 张图片...")
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.config.concurrent_downloads)
        
        # 配置代理
        proxy = None
        if self.config.proxy_enabled:
            proxy = self.config.proxy.get('http')
        
        # 创建 aiohttp 会话
        connector = aiohttp.TCPConnector(limit=self.config.concurrent_downloads, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [
                self._download_single(session, url, semaphore)
                for url in urls
            ]
            
            results = await asyncio.gather(*tasks)
        
        # 构建结果映射
        result_map = {}
        for url, path in results:
            result_map[url] = path
        
        self.logger.info(f"下载完成！成功: {self.downloaded_count}, 失败: {self.failed_count}")
        return result_map
    
    def download_all(self, urls: List[str]) -> Dict[str, Optional[str]]:
        """
        同步接口：批量下载图片
        
        Args:
            urls: 图片URL列表
            
        Returns:
            URL到本地路径的映射字典
        """
        # 运行异步下载
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.download_all_async(urls))
    
    def download_single_sync(self, url: str) -> Optional[str]:
        """
        同步下载单个图片
        
        Args:
            url: 图片URL
            
        Returns:
            本地文件路径或None
        """
        import requests
        
        try:
            # 检查是否已下载
            if url in self._download_history:
                return self._download_history[url]
            
            filename = self._get_filename_from_url(url)
            filepath = self._get_unique_filepath(filename)
            
            # 检查是否已存在
            if filepath.exists():
                self._download_history[url] = str(filepath)
                return str(filepath)
            
            headers = {
                'User-Agent': self.USER_AGENTS[0],
                'Referer': 'https://www.popfashioninfo.com/',
            }
            
            self.logger.info(f"正在下载: {filename}")
            
            response = requests.get(url, headers=headers, timeout=self.config.timeout, stream=True)
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                self.downloaded_count += 1
                self._download_history[url] = str(filepath)
                self.logger.info(f"下载完成: {filepath.name}")
                return str(filepath)
            else:
                self.logger.warning(f"下载失败 (HTTP {response.status_code}): {url}")
                self.failed_count += 1
                return None
                
        except requests.Timeout:
            self.logger.warning(f"下载超时: {url}")
            self.failed_count += 1
            return None
        except Exception as e:
            self.logger.error(f"下载异常: {url} - {e}")
            self.failed_count += 1
            return None
    
    def get_download_stats(self) -> Dict[str, int]:
        """
        获取下载统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "downloaded": self.downloaded_count,
            "failed": self.failed_count,
            "total": self.downloaded_count + self.failed_count
        }
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.downloaded_count = 0
        self.failed_count = 0


class ProgressBar:
    """
    进度条显示类
    
    用于在控制台显示下载进度
    """
    
    def __init__(self, total: int, prefix: str = "Progress", width: int = 50):
        """
        初始化进度条
        
        Args:
            total: 总任务数
            prefix: 前缀文字
            width: 进度条宽度
        """
        self.total = total
        self.prefix = prefix
        self.width = width
        self.current = 0
    
    def update(self, current: Optional[int] = None) -> None:
        """
        更新进度
        
        Args:
            current: 当前进度，None则自增1
        """
        if current is not None:
            self.current = current
        else:
            self.current += 1
        
        self._display()
    
    def _display(self) -> None:
        """显示进度条"""
        percent = self.current / self.total if self.total > 0 else 0
        filled = int(self.width * percent)
        bar = '█' * filled + '░' * (self.width - filled)
        
        print(f'\r{self.prefix}: |{bar}| {self.current}/{self.total} ({percent:.1%})', end='', flush=True)
    
    def finish(self) -> None:
        """完成进度条"""
        self.current = self.total
        self._display()
        print()  # 换行
