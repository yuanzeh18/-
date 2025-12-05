# -*- coding: utf-8 -*-
"""
HTML解析模块

解析页面内容，提取图片URL和潘通色卡信息
"""

import re
from typing import List, Tuple, Optional, Dict
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from ..models.pantone import PantoneColor, DesignerBrand
from ..utils.logger import get_logger


class PageParser:
    """
    页面解析器
    
    负责解析HTML页面，提取图片和潘通色卡信息
    
    Attributes:
        base_url: 基础URL，用于处理相对路径
        logger: 日志记录器
    """
    
    # 潘通色号正则表达式模式（按从最具体到最一般的顺序排列）
    # 颜色名通常为1-2个首字母大写的英文单词
    PANTONE_PATTERNS = [
        # PANTONE 19-4052 TCX Classic Blue（带TCX/TPX等后缀）
        r'PANTONE\s+(\d{2}-\d{4})\s*(?:TCX|TPX|TPG|C|U)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        # PANTONE 19-4052 Classic Blue（标准格式）
        r'PANTONE\s+(\d{2}-\d{4})\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        # PANTONE Classic Blue 19-4052（颜色名在前）
        r'PANTONE\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(\d{2}-\d{4})(?!\d)',
    ]
    
    def __init__(self, base_url: str = "https://www.popfashioninfo.com"):
        """
        初始化解析器
        
        Args:
            base_url: 基础URL
        """
        self.base_url = base_url
        self.logger = get_logger("PageParser")
    
    def parse_designer_page(self, html: str, page_url: str = "") -> List[DesignerBrand]:
        """
        解析设计师品牌页面
        
        Args:
            html: 页面HTML内容
            page_url: 页面URL
            
        Returns:
            设计师品牌信息列表
        """
        soup = BeautifulSoup(html, 'html.parser')
        brands = []
        
        self.logger.info("开始解析页面内容...")
        
        # 尝试多种可能的页面结构
        # 方案1: 查找带有图片和颜色信息的卡片/容器
        containers = self._find_content_containers(soup)
        
        if containers:
            for container in containers:
                brand = self._parse_container(container, page_url)
                if brand:
                    brands.append(brand)
        else:
            # 方案2: 分别提取图片和颜色，尝试建立关联
            images = self._extract_all_images(soup)
            colors = self._extract_all_pantone_colors(soup)
            
            self.logger.info(f"找到 {len(images)} 张图片, {len(colors)} 个潘通色卡")
            
            # 如果只有一组图片和颜色，认为它们相关联
            if images:
                for img_url in images:
                    brand = DesignerBrand(
                        brand_name=self._extract_brand_name(soup) or "Unknown",
                        image_url=img_url,
                        page_url=page_url,
                        colors=colors if colors else []
                    )
                    brands.append(brand)
        
        self.logger.info(f"共解析出 {len(brands)} 条设计师品牌数据")
        return brands
    
    def _find_content_containers(self, soup: BeautifulSoup) -> List:
        """
        查找内容容器
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            容器元素列表
        """
        # 常见的容器类名和标签
        selectors = [
            '.product-item',
            '.brand-item',
            '.design-item',
            '.gallery-item',
            '.trend-item',
            '.color-card',
            'article.item',
            '.card',
            '[data-pantone]',
            '.style-item',
        ]
        
        for selector in selectors:
            containers = soup.select(selector)
            if containers:
                self.logger.debug(f"使用选择器 '{selector}' 找到 {len(containers)} 个容器")
                return containers
        
        return []
    
    def _parse_container(self, container, page_url: str) -> Optional[DesignerBrand]:
        """
        解析单个容器元素
        
        Args:
            container: BeautifulSoup元素
            page_url: 页面URL
            
        Returns:
            设计师品牌对象或None
        """
        # 提取图片
        img = container.find('img')
        if not img:
            return None
        
        img_url = self._get_image_url(img)
        if not img_url:
            return None
        
        # 提取品牌名称
        brand_name = self._extract_brand_name_from_container(container)
        
        # 提取潘通色卡
        colors = self._extract_pantone_from_container(container)
        
        return DesignerBrand(
            brand_name=brand_name,
            image_url=img_url,
            page_url=page_url,
            colors=colors
        )
    
    def _extract_all_images(self, soup: BeautifulSoup) -> List[str]:
        """
        提取页面中所有相关图片URL
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            图片URL列表
        """
        images = []
        
        # 查找所有img标签
        img_tags = soup.find_all('img')
        
        for img in img_tags:
            url = self._get_image_url(img)
            if url and self._is_valid_image(url):
                images.append(url)
        
        # 查找背景图片
        for elem in soup.find_all(style=True):
            style = elem.get('style', '')
            bg_urls = re.findall(r'url\(["\']?([^"\'()]+)["\']?\)', style)
            for url in bg_urls:
                full_url = urljoin(self.base_url, url)
                if self._is_valid_image(full_url):
                    images.append(full_url)
        
        # 去重
        return list(dict.fromkeys(images))
    
    def _get_image_url(self, img) -> Optional[str]:
        """
        从img标签获取图片URL
        
        支持 src, data-src, data-original 等属性
        
        Args:
            img: img标签元素
            
        Returns:
            图片URL或None
        """
        # 优先获取高清图
        url_attrs = ['data-original', 'data-src', 'data-lazy-src', 'src']
        
        for attr in url_attrs:
            url = img.get(attr)
            if url:
                # 处理相对路径
                return urljoin(self.base_url, url)
        
        return None
    
    def _is_valid_image(self, url: str) -> bool:
        """
        检查是否为有效的图片URL
        
        过滤掉小图标、logo等
        
        Args:
            url: 图片URL
            
        Returns:
            是否有效
        """
        # 排除的模式
        exclude_patterns = [
            r'/icon',
            r'/logo',
            r'\.ico$',
            r'/placeholder',
            r'/loading',
            r'data:image',
            r'/avatar',
            r'/thumb',
            r'_small',
            r'_mini',
        ]
        
        url_lower = url.lower()
        for pattern in exclude_patterns:
            if re.search(pattern, url_lower):
                return False
        
        # 检查是否为图片文件
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # 如果有扩展名，检查是否为图片
        if any(path.endswith(ext) for ext in image_extensions):
            return True
        
        # 如果没有扩展名，但URL看起来像图片CDN
        if 'image' in url_lower or 'img' in url_lower or 'photo' in url_lower:
            return True
        
        return True  # 默认保留
    
    def _extract_all_pantone_colors(self, soup: BeautifulSoup) -> List[PantoneColor]:
        """
        从页面中提取所有潘通色卡信息
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            潘通色卡列表
        """
        colors = []
        # 获取文本并规范化空白字符（将换行符替换为单个空格，多个空格合并为一个）
        text = soup.get_text(separator=' ')
        text = ' '.join(text.split())
        
        # 使用正则表达式匹配
        for pattern in self.PANTONE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) >= 2:
                    # 根据匹配顺序确定色号和名称
                    if re.match(r'\d{2}-\d{4}', match[0]):
                        code = match[0]
                        name = match[1].strip()
                    else:
                        code = match[1]
                        name = match[0].strip()
                    
                    color = PantoneColor(
                        color_code=code,
                        color_name=name
                    )
                    
                    # 避免重复
                    if not any(c.color_code == code for c in colors):
                        colors.append(color)
        
        # 查找带有颜色数据属性的元素
        color_elements = soup.find_all(attrs={'data-color': True})
        for elem in color_elements:
            color_info = elem.get('data-color')
            hex_color = elem.get('data-hex')
            color = self._parse_color_attribute(color_info, hex_color)
            if color and not any(c.color_code == color.color_code for c in colors):
                colors.append(color)
        
        # 查找色卡容器
        color_containers = soup.select('.pantone, .color-info, .color-block, .pantone-color')
        for container in color_containers:
            container_colors = self._extract_pantone_from_container(container)
            for color in container_colors:
                if not any(c.color_code == color.color_code for c in colors):
                    colors.append(color)
        
        return colors
    
    def _extract_pantone_from_container(self, container) -> List[PantoneColor]:
        """
        从容器元素中提取潘通色卡
        
        Args:
            container: BeautifulSoup元素
            
        Returns:
            潘通色卡列表
        """
        colors = []
        # 规范化空白字符
        text = container.get_text(separator=' ')
        text = ' '.join(text.split())
        
        for pattern in self.PANTONE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) >= 2:
                    if re.match(r'\d{2}-\d{4}', match[0]):
                        code = match[0]
                        name = match[1].strip()
                    else:
                        code = match[1]
                        name = match[0].strip()
                    
                    # 尝试获取hex颜色值
                    hex_value = self._extract_hex_from_container(container)
                    
                    color = PantoneColor(
                        color_code=code,
                        color_name=name,
                        hex_value=hex_value
                    )
                    
                    if not any(c.color_code == code for c in colors):
                        colors.append(color)
        
        return colors
    
    def _extract_hex_from_container(self, container) -> Optional[str]:
        """
        从容器中提取十六进制颜色值
        
        Args:
            container: BeautifulSoup元素
            
        Returns:
            十六进制颜色值或None
        """
        # 查找style属性中的颜色
        style = container.get('style', '')
        hex_match = re.search(r'#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})', style)
        if hex_match:
            return f"#{hex_match.group(1)}"
        
        # 查找data-hex属性
        hex_attr = container.get('data-hex')
        if hex_attr:
            if not hex_attr.startswith('#'):
                hex_attr = f"#{hex_attr}"
            return hex_attr
        
        # 在子元素中查找
        for child in container.find_all(style=True):
            style = child.get('style', '')
            hex_match = re.search(r'#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})', style)
            if hex_match:
                return f"#{hex_match.group(1)}"
        
        return None
    
    def _parse_color_attribute(self, color_info: str, hex_value: Optional[str] = None) -> Optional[PantoneColor]:
        """
        解析颜色属性
        
        Args:
            color_info: 颜色信息字符串
            hex_value: 十六进制颜色值
            
        Returns:
            潘通色卡对象或None
        """
        if not color_info:
            return None
        
        for pattern in self.PANTONE_PATTERNS:
            match = re.search(pattern, color_info, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    if re.match(r'\d{2}-\d{4}', groups[0]):
                        code = groups[0]
                        name = groups[1].strip()
                    else:
                        code = groups[1]
                        name = groups[0].strip()
                    
                    return PantoneColor(
                        color_code=code,
                        color_name=name,
                        hex_value=hex_value
                    )
        
        return None
    
    def _extract_brand_name(self, soup: BeautifulSoup) -> Optional[str]:
        """
        从页面中提取品牌名称
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            品牌名称或None
        """
        # 尝试从标题提取
        title = soup.find('title')
        if title:
            title_text = title.get_text()
            # 清理标题
            brand = title_text.split('|')[0].split('-')[0].strip()
            if brand:
                return brand
        
        # 尝试从h1提取
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()
        
        # 尝试从特定类名提取
        for selector in ['.brand-name', '.designer-name', '.title']:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text().strip()
        
        return None
    
    def _extract_brand_name_from_container(self, container) -> str:
        """
        从容器元素中提取品牌名称
        
        Args:
            container: BeautifulSoup元素
            
        Returns:
            品牌名称
        """
        # 查找标题元素
        for tag in ['h1', 'h2', 'h3', 'h4', '.title', '.name', '.brand']:
            elem = container.select_one(tag) if isinstance(tag, str) and tag.startswith('.') else container.find(tag)
            if elem:
                text = elem.get_text().strip()
                if text:
                    return text
        
        # 查找data属性
        brand = container.get('data-brand') or container.get('data-name')
        if brand:
            return brand
        
        # 使用alt文本
        img = container.find('img')
        if img:
            alt = img.get('alt', '')
            if alt:
                return alt
        
        return "Unknown Brand"
    
    def extract_pagination_links(self, soup: BeautifulSoup) -> List[str]:
        """
        提取分页链接
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            分页链接列表
        """
        links = []
        
        # 查找分页容器
        pagination_selectors = ['.pagination', '.pager', '.page-nav', 'nav[aria-label="pagination"]']
        
        for selector in pagination_selectors:
            pagination = soup.select_one(selector)
            if pagination:
                for a in pagination.find_all('a', href=True):
                    href = a['href']
                    full_url = urljoin(self.base_url, href)
                    if full_url not in links:
                        links.append(full_url)
                break
        
        return links
