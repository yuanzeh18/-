# -*- coding: utf-8 -*-
"""
潘通色卡数据模型

定义用于存储潘通色卡和设计师品牌信息的数据结构
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import json


@dataclass
class PantoneColor:
    """
    潘通色卡数据类
    
    Attributes:
        color_code: 潘通色号，如 "19-4052"
        color_name: 颜色名称，如 "Classic Blue"
        full_name: 完整名称，如 "PANTONE 19-4052 Classic Blue"
        hex_value: 十六进制颜色值（可选）
        rgb: RGB颜色值（可选），格式为 (R, G, B)
    """
    color_code: str
    color_name: str
    full_name: str = ""
    hex_value: Optional[str] = None
    rgb: Optional[tuple] = None
    
    def __post_init__(self):
        """初始化后处理，自动生成完整名称"""
        if not self.full_name:
            self.full_name = f"PANTONE {self.color_code} {self.color_name}"
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "color_code": self.color_code,
            "color_name": self.color_name,
            "full_name": self.full_name,
            "hex_value": self.hex_value,
            "rgb": list(self.rgb) if self.rgb else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PantoneColor':
        """从字典创建实例"""
        rgb = tuple(data.get("rgb")) if data.get("rgb") else None
        return cls(
            color_code=data.get("color_code", ""),
            color_name=data.get("color_name", ""),
            full_name=data.get("full_name", ""),
            hex_value=data.get("hex_value"),
            rgb=rgb
        )


@dataclass
class DesignerBrand:
    """
    设计师品牌数据类
    
    存储单个设计师品牌的完整信息，包括图片和色卡
    
    Attributes:
        brand_name: 品牌名称
        image_url: 原始图片URL
        local_image_path: 本地保存路径
        colors: 关联的潘通色卡列表
        page_url: 来源页面URL
        scraped_at: 爬取时间
        extra_info: 额外信息（如季节、系列等）
    """
    brand_name: str
    image_url: str
    local_image_path: str = ""
    colors: List[PantoneColor] = field(default_factory=list)
    page_url: str = ""
    scraped_at: str = ""
    extra_info: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理，自动记录爬取时间"""
        if not self.scraped_at:
            self.scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def add_color(self, color: PantoneColor) -> None:
        """添加潘通色卡"""
        self.colors.append(color)
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "brand_name": self.brand_name,
            "image_url": self.image_url,
            "local_image_path": self.local_image_path,
            "colors": [c.to_dict() for c in self.colors],
            "page_url": self.page_url,
            "scraped_at": self.scraped_at,
            "extra_info": self.extra_info
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DesignerBrand':
        """从字典创建实例"""
        colors = [PantoneColor.from_dict(c) for c in data.get("colors", [])]
        return cls(
            brand_name=data.get("brand_name", ""),
            image_url=data.get("image_url", ""),
            local_image_path=data.get("local_image_path", ""),
            colors=colors,
            page_url=data.get("page_url", ""),
            scraped_at=data.get("scraped_at", ""),
            extra_info=data.get("extra_info", {})
        )
    
    def to_csv_row(self) -> dict:
        """
        转换为CSV行格式
        
        将颜色信息平铺为字符串，便于CSV导出
        """
        color_codes = "|".join([c.color_code for c in self.colors])
        color_names = "|".join([c.color_name for c in self.colors])
        full_names = "|".join([c.full_name for c in self.colors])
        
        return {
            "brand_name": self.brand_name,
            "image_url": self.image_url,
            "local_image_path": self.local_image_path,
            "color_codes": color_codes,
            "color_names": color_names,
            "pantone_full_names": full_names,
            "page_url": self.page_url,
            "scraped_at": self.scraped_at
        }


class DataExporter:
    """
    数据导出工具类
    
    支持将爬取结果导出为JSON和CSV格式
    """
    
    @staticmethod
    def to_json(brands: List[DesignerBrand], filepath: str) -> None:
        """
        导出为JSON格式
        
        Args:
            brands: 设计师品牌列表
            filepath: 输出文件路径
        """
        data = {
            "total_count": len(brands),
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "brands": [b.to_dict() for b in brands]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def to_csv(brands: List[DesignerBrand], filepath: str) -> None:
        """
        导出为CSV格式
        
        Args:
            brands: 设计师品牌列表
            filepath: 输出文件路径
        """
        import csv
        
        if not brands:
            return
        
        fieldnames = [
            "brand_name", "image_url", "local_image_path",
            "color_codes", "color_names", "pantone_full_names",
            "page_url", "scraped_at"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for brand in brands:
                writer.writerow(brand.to_csv_row())
