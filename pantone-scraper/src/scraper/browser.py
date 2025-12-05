# -*- coding: utf-8 -*-
"""
浏览器自动化模块

使用 Selenium 实现浏览器自动化，支持登录和页面导航
"""

import time
import random
from typing import Optional, List
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from ..utils.config import Config
from ..utils.logger import get_logger


# 随机 User-Agent 列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class BrowserManager:
    """
    浏览器管理类
    
    负责浏览器初始化、登录、页面导航和关闭等操作
    
    Attributes:
        config: 配置对象
        driver: Selenium WebDriver 实例
        logger: 日志记录器
    """
    
    def __init__(self, config: Config):
        """
        初始化浏览器管理器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.driver: Optional[webdriver.Remote] = None
        self.logger = get_logger("BrowserManager")
        self._logged_in = False
    
    def _get_random_user_agent(self) -> str:
        """获取随机 User-Agent"""
        return random.choice(USER_AGENTS)
    
    def _setup_chrome(self) -> webdriver.Chrome:
        """
        设置 Chrome 浏览器
        
        Returns:
            Chrome WebDriver 实例
        """
        options = ChromeOptions()
        
        # 设置 User-Agent
        options.add_argument(f"user-agent={self._get_random_user_agent()}")
        
        # 无头模式
        if self.config.headless:
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
        
        # 禁用自动化检测
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # 其他优化选项
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        # 设置代理
        if self.config.proxy_enabled:
            proxy_http = self.config.proxy.get("http", "")
            if proxy_http:
                options.add_argument(f"--proxy-server={proxy_http}")
        
        # 使用 webdriver_manager 自动管理驱动
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # 执行 CDP 命令隐藏 webdriver 标识
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        return driver
    
    def _setup_firefox(self) -> webdriver.Firefox:
        """
        设置 Firefox 浏览器
        
        Returns:
            Firefox WebDriver 实例
        """
        options = FirefoxOptions()
        
        # 设置 User-Agent
        options.set_preference("general.useragent.override", self._get_random_user_agent())
        
        # 无头模式
        if self.config.headless:
            options.add_argument("--headless")
        
        # 设置代理
        if self.config.proxy_enabled:
            proxy_http = self.config.proxy.get("http", "")
            proxy_https = self.config.proxy.get("https", "")
            if proxy_http:
                # 解析代理地址
                proxy_parts = proxy_http.replace("http://", "").split(":")
                if len(proxy_parts) == 2:
                    options.set_preference("network.proxy.type", 1)
                    options.set_preference("network.proxy.http", proxy_parts[0])
                    options.set_preference("network.proxy.http_port", int(proxy_parts[1]))
        
        service = FirefoxService(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=options)
        driver.set_window_size(1920, 1080)
        
        return driver
    
    def start(self) -> None:
        """
        启动浏览器
        
        根据配置选择 Chrome 或 Firefox
        """
        self.logger.info(f"正在启动 {self.config.driver} 浏览器...")
        
        try:
            if self.config.driver.lower() == "chrome":
                self.driver = self._setup_chrome()
            elif self.config.driver.lower() == "firefox":
                self.driver = self._setup_firefox()
            else:
                raise ValueError(f"不支持的浏览器类型: {self.config.driver}")
            
            # 设置隐式等待
            self.driver.implicitly_wait(10)
            self.logger.info("浏览器启动成功")
            
        except WebDriverException as e:
            self.logger.error(f"浏览器启动失败: {e}")
            raise
    
    def login(self, manual_captcha: bool = True) -> bool:
        """
        登录网站
        
        Args:
            manual_captcha: 是否手动处理验证码
            
        Returns:
            登录是否成功
        """
        if not self.driver:
            self.logger.error("浏览器未启动，请先调用 start()")
            return False
        
        username = self.config.username
        password = self.config.password
        
        if not username or not password:
            self.logger.warning("未配置用户名或密码，跳过登录步骤")
            return False
        
        self.logger.info("正在访问登录页面...")
        
        try:
            # 访问登录页面
            login_url = "https://www.popfashioninfo.com/login/"
            self.driver.get(login_url)
            self._random_delay()
            
            # 等待登录表单加载
            wait = WebDriverWait(self.driver, self.config.timeout)
            
            # 查找用户名输入框（根据实际页面调整选择器）
            username_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username'], input[type='text']"))
            )
            username_input.clear()
            username_input.send_keys(username)
            self._random_delay(0.5, 1)
            
            # 查找密码输入框
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[name='password'], input[type='password']")
            password_input.clear()
            password_input.send_keys(password)
            self._random_delay(0.5, 1)
            
            # 如果需要手动处理验证码
            if manual_captcha:
                self.logger.warning("=" * 50)
                self.logger.warning("请在浏览器中手动完成验证码验证")
                self.logger.warning("完成后请按 Enter 继续...")
                self.logger.warning("=" * 50)
                input()
            
            # 点击登录按钮
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            login_button.click()
            
            # 等待登录完成
            time.sleep(3)
            
            # 检查登录是否成功（根据实际页面调整）
            if self._check_login_success():
                self.logger.info("登录成功！")
                self._logged_in = True
                return True
            else:
                self.logger.error("登录失败，请检查用户名和密码")
                return False
                
        except TimeoutException:
            self.logger.error("登录页面加载超时")
            return False
        except NoSuchElementException as e:
            self.logger.error(f"找不到登录元素: {e}")
            return False
        except Exception as e:
            self.logger.error(f"登录过程中发生错误: {e}")
            return False
    
    def _check_login_success(self) -> bool:
        """
        检查登录是否成功
        
        Returns:
            是否登录成功
        """
        try:
            # 检查URL是否跳转
            if "login" not in self.driver.current_url.lower():
                return True
            
            # 检查是否存在登出按钮或用户信息
            logout_elements = self.driver.find_elements(By.CSS_SELECTOR, ".logout, .user-info, .user-name")
            if logout_elements:
                return True
            
            return False
        except Exception:
            return False
    
    def navigate_to(self, url: str) -> bool:
        """
        导航到指定URL
        
        Args:
            url: 目标URL
            
        Returns:
            导航是否成功
        """
        if not self.driver:
            self.logger.error("浏览器未启动")
            return False
        
        try:
            self.logger.info(f"正在导航到: {url}")
            self.driver.get(url)
            self._random_delay()
            return True
        except Exception as e:
            self.logger.error(f"导航失败: {e}")
            return False
    
    def get_page_source(self) -> str:
        """
        获取当前页面源码
        
        Returns:
            页面HTML源码
        """
        if not self.driver:
            return ""
        return self.driver.page_source
    
    def get_current_url(self) -> str:
        """
        获取当前页面URL
        
        Returns:
            当前URL
        """
        if not self.driver:
            return ""
        return self.driver.current_url
    
    def scroll_to_bottom(self, step: int = 500, delay: float = 0.5) -> None:
        """
        滚动到页面底部
        
        用于加载懒加载的内容
        
        Args:
            step: 每次滚动的像素数
            delay: 每次滚动后的延迟
        """
        if not self.driver:
            return
        
        self.logger.info("正在滚动页面以加载更多内容...")
        
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # 滚动到底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(delay)
            
            # 计算新的滚动高度
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                break
            
            last_height = new_height
        
        self.logger.info("页面滚动完成")
    
    def wait_for_element(
        self, 
        selector: str, 
        by: By = By.CSS_SELECTOR, 
        timeout: Optional[int] = None
    ) -> Optional[any]:
        """
        等待元素出现
        
        Args:
            selector: 元素选择器
            by: 定位方式
            timeout: 超时时间
            
        Returns:
            找到的元素或None
        """
        if not self.driver:
            return None
        
        timeout = timeout or self.config.timeout
        
        try:
            wait = WebDriverWait(self.driver, timeout)
            element = wait.until(EC.presence_of_element_located((by, selector)))
            return element
        except TimeoutException:
            self.logger.warning(f"等待元素超时: {selector}")
            return None
    
    def find_elements(self, selector: str, by: By = By.CSS_SELECTOR) -> List:
        """
        查找多个元素
        
        Args:
            selector: 元素选择器
            by: 定位方式
            
        Returns:
            元素列表
        """
        if not self.driver:
            return []
        
        try:
            return self.driver.find_elements(by, selector)
        except Exception:
            return []
    
    def _random_delay(self, min_delay: Optional[float] = None, max_delay: Optional[float] = None) -> None:
        """
        随机延迟
        
        Args:
            min_delay: 最小延迟（秒）
            max_delay: 最大延迟（秒）
        """
        min_d = min_delay if min_delay is not None else self.config.delay_min
        max_d = max_delay if max_delay is not None else self.config.delay_max
        delay = random.uniform(min_d, max_d)
        time.sleep(delay)
    
    def take_screenshot(self, filename: str = "screenshot.png") -> str:
        """
        截取当前页面截图
        
        Args:
            filename: 截图文件名
            
        Returns:
            截图文件路径
        """
        if not self.driver:
            return ""
        
        filepath = Path("data") / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        self.driver.save_screenshot(str(filepath))
        self.logger.info(f"截图已保存: {filepath}")
        return str(filepath)
    
    def close(self) -> None:
        """关闭浏览器"""
        if self.driver:
            self.logger.info("正在关闭浏览器...")
            self.driver.quit()
            self.driver = None
            self._logged_in = False
            self.logger.info("浏览器已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False
    
    @property
    def is_logged_in(self) -> bool:
        """是否已登录"""
        return self._logged_in
