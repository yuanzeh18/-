#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
潘通色卡爬虫主入口

从 popfashioninfo.com 爬取设计师品牌页面的图片和潘通色卡信息
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config import Config
from src.utils.logger import setup_logger, get_logger
from src.scraper.browser import BrowserManager
from src.scraper.parser import PageParser
from src.scraper.downloader import ImageDownloader
from src.models.pantone import DesignerBrand, DataExporter


def parse_args() -> argparse.Namespace:
    """
    解析命令行参数
    
    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description="潘通色卡爬虫 - 从 popfashioninfo.com 爬取设计师品牌图片和色卡信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py                          # 使用默认配置运行
  python main.py --headless              # 无头模式运行
  python main.py --config my_config.yaml # 使用自定义配置文件
  python main.py --output-dir ./results  # 指定输出目录
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config.yaml',
        help='配置文件路径 (默认: config.yaml)'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        help='无头模式运行（不显示浏览器窗口）'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        help='输出目录路径'
    )
    
    parser.add_argument(
        '--image-dir', '-i',
        type=str,
        help='图片保存目录'
    )
    
    parser.add_argument(
        '--url', '-u',
        type=str,
        help='自定义爬取URL'
    )
    
    parser.add_argument(
        '--no-download',
        action='store_true',
        help='只解析页面，不下载图片'
    )
    
    parser.add_argument(
        '--skip-login',
        action='store_true',
        help='跳过登录步骤'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式，显示详细日志'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='试运行模式，不实际下载'
    )
    
    return parser.parse_args()


def main() -> int:
    """
    主函数
    
    Returns:
        退出码 (0=成功, 1=失败)
    """
    # 解析命令行参数
    args = parse_args()
    
    # 设置日志
    import logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logger(level=log_level)
    logger = get_logger("main")
    
    logger.info("=" * 60)
    logger.info("潘通色卡爬虫启动")
    logger.info("=" * 60)
    
    try:
        # 加载配置
        config_path = Path(args.config)
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            logger.info("使用默认配置...")
            config = Config()
        else:
            logger.info(f"加载配置文件: {config_path}")
            config = Config(str(config_path))
        
        # 应用命令行参数覆盖配置
        if args.headless:
            config._config['browser']['headless'] = True
        if args.output_dir:
            config._config['download']['output_dir'] = args.output_dir
        if args.image_dir:
            config._config['download']['image_dir'] = args.image_dir
        
        # 确保输出目录存在
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        image_dir = Path(config.image_dir)
        image_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取目标URL
        target_url = args.url or config.base_url
        logger.info(f"目标URL: {target_url}")
        
        # 初始化组件
        parser = PageParser(base_url="https://www.popfashioninfo.com")
        downloader = ImageDownloader(config)
        
        all_brands = []
        
        # 使用浏览器管理器
        with BrowserManager(config) as browser:
            # 登录（如果需要）
            if not args.skip_login and (config.username and config.password):
                logger.info("尝试登录...")
                login_success = browser.login(manual_captcha=not args.headless)
                if not login_success:
                    logger.warning("登录失败，继续以访客身份爬取...")
            else:
                logger.info("跳过登录步骤")
            
            # 导航到目标页面
            if not browser.navigate_to(target_url):
                logger.error("无法访问目标页面")
                return 1
            
            # 等待页面加载
            import time
            time.sleep(3)
            
            # 滚动页面加载更多内容
            browser.scroll_to_bottom()
            
            # 获取页面源码
            page_source = browser.get_page_source()
            current_url = browser.get_current_url()
            
            if not page_source:
                logger.error("无法获取页面内容")
                return 1
            
            # 解析页面
            logger.info("正在解析页面内容...")
            brands = parser.parse_designer_page(page_source, current_url)
            
            if not brands:
                logger.warning("未找到任何品牌数据")
                # 保存页面源码用于调试
                debug_file = output_dir / "debug_page.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(page_source)
                logger.info(f"页面源码已保存到: {debug_file}")
            else:
                logger.info(f"找到 {len(brands)} 条品牌数据")
                all_brands.extend(brands)
        
        # 下载图片
        if all_brands and not args.no_download and not args.dry_run:
            logger.info("开始下载图片...")
            
            # 收集所有图片URL
            image_urls = [brand.image_url for brand in all_brands if brand.image_url]
            
            if image_urls:
                # 执行下载
                download_results = downloader.download_all(image_urls)
                
                # 更新品牌数据的本地路径
                for brand in all_brands:
                    if brand.image_url in download_results:
                        brand.local_image_path = download_results[brand.image_url] or ""
                
                stats = downloader.get_download_stats()
                logger.info(f"下载完成: 成功 {stats['downloaded']} 张, 失败 {stats['failed']} 张")
            else:
                logger.warning("没有找到可下载的图片")
        elif args.no_download:
            logger.info("已跳过图片下载")
        elif args.dry_run:
            logger.info("试运行模式，跳过图片下载")
        
        # 导出数据
        if all_brands:
            # 导出 JSON
            json_path = output_dir / "pantone_data.json"
            DataExporter.to_json(all_brands, str(json_path))
            logger.info(f"JSON 数据已保存到: {json_path}")
            
            # 导出 CSV
            csv_path = output_dir / "pantone_data.csv"
            DataExporter.to_csv(all_brands, str(csv_path))
            logger.info(f"CSV 数据已保存到: {csv_path}")
            
            # 显示摘要
            logger.info("=" * 60)
            logger.info("爬取完成！摘要信息：")
            logger.info(f"  - 品牌数量: {len(all_brands)}")
            total_colors = sum(len(b.colors) for b in all_brands)
            logger.info(f"  - 潘通色卡数量: {total_colors}")
            logger.info(f"  - 图片保存目录: {image_dir}")
            logger.info(f"  - 数据输出目录: {output_dir}")
            logger.info("=" * 60)
        else:
            logger.warning("没有数据可导出")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        return 0
    except Exception as e:
        logger.exception(f"运行时错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
