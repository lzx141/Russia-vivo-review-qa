"""
爬虫工具基类 — 统一浏览器驱动 / 数据保存 / 日期解析
"""
import logging
import os
import random
import time

import pandas as pd

logger = logging.getLogger(__name__)


class BrowserDriver:
    """浏览器驱动管理器 —— 统一 Chrome options、CDP 反检测"""

    def __init__(self, lang: str = "ru-RU", headless: bool = False):
        self.lang = lang
        self.headless = headless
        self.driver = None

    def create_options(self):
        """创建统一的 ChromeOptions"""
        from selenium.webdriver.chrome.options import Options

        opts = Options()
        opts.add_argument(f"--lang={self.lang}")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument("--disable-web-security")
        opts.add_argument("--disable-features=IsolateOrigins,site-per-process")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.127 Safari/537.36"
        )
        if self.headless:
            opts.add_argument("--headless=new")
        return opts

    def create_driver(self):
        """创建 WebDriver 实例，注入反检测脚本"""
        from selenium.webdriver import Chrome
        from selenium.webdriver.chrome.service import Service

        opts = self.create_options()
        service = Service()
        self.driver = Chrome(service=service, options=opts)
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            delete navigator.__proto__.webdriver;
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            """
        })
        return self.driver

    def quit(self):
        """安全退出"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def __enter__(self):
        self.create_driver()
        return self.driver

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()


class DataSaver:
    """数据保存工具 —— 统一 Excel 读写、追加、去重"""

    REQUIRED_COLUMNS_MAP = {
        "reviews": ["author", "publishDate", "rate", "content", "name", "SKU", "URL", "siteName"],
        "questions": ["author", "publishDate", "question", "content", "name", "SKU", "URL", "siteName"],
        "qa": ["author", "publishDate", "question", "content", "name", "SKU", "URL", "siteName"],
    }

    @classmethod
    def save(cls, data: list[dict], file_path: str, data_type: str):
        """
        保存数据到 Excel 文件（可追加）
        Args:
            data: 数据列表
            file_path: 保存路径
            data_type: 'reviews' 或 'questions' / 'qa'
        """
        if not data:
            logger.warning("没有 %s 数据可保存", data_type)
            return

        required = cls.REQUIRED_COLUMNS_MAP.get(data_type)
        if not required:
            logger.error("未知数据类型: %s", data_type)
            return

        temp_df = pd.DataFrame(data)
        for col in required:
            if col not in temp_df.columns:
                temp_df[col] = ""
        new_df = temp_df.reindex(columns=required)

        if os.path.exists(file_path):
            logger.info("文件 %s 已存在，追加数据...", file_path)
            existing_df = pd.read_excel(file_path, engine="openpyxl")
            for col in required:
                if col not in existing_df.columns:
                    existing_df[col] = ""
            existing_df = existing_df.reindex(columns=required)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            # 去重
            combined_df = combined_df.drop_duplicates(subset=required[:5])
            logger.info("追加完成，总行数: %d", len(combined_df))
        else:
            combined_df = new_df
            logger.info("创建新文件 %s，%d 行", file_path, len(combined_df))

        combined_df.to_excel(file_path, index=False, engine="openpyxl")
        logger.info("✅ 数据已保存到 %s", file_path)

    @classmethod
    def preview(cls, data: list[dict], data_type: str, count: int = 5):
        """预览前 N 条数据"""
        required = cls.REQUIRED_COLUMNS_MAP.get(data_type, [])
        for i, item in enumerate(data[:count]):
            logger.info(f"--- {i + 1} ---")
            for key in required[:5]:
                val = str(item.get(key, ""))[:80]
                logger.info(f"  {key}: {val}")


class DateParser:
    """俄语日期解析工具"""

    FORMATS = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d.%m.%Y %H:%M",
    ]

    @classmethod
    def parse(cls, date_str: str):
        """解析日期字符串，返回标准格式 YYYY-MM-DD HH:MM:SS 或 None"""
        if not date_str:
            return None

        # 尝试 pd.to_datetime
        for fmt in cls.FORMATS:
            try:
                return pd.to_datetime(date_str, format=fmt).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue

        # 尝试 dateparser（俄语）
        try:
            import dateparser
            dt = dateparser.parse(date_str, languages=["ru"])
            if dt:
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ImportError:
            pass

        # 最后尝试 pandas 宽松解析
        try:
            return pd.to_datetime(date_str, errors="coerce").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    @classmethod
    def filter_by_date_range(cls, data: list[dict], start_date: str = None, end_date: str = None) -> list[dict]:
        """按日期范围过滤数据"""
        import pandas as pd

        start_dt = pd.to_datetime(start_date) if start_date else None
        end_dt = pd.to_datetime(end_date) if end_date else None

        filtered = []
        for item in data:
            dt_str = item.get("publishDate", "")
            if not dt_str:
                continue
            try:
                dt = pd.to_datetime(dt_str)
                if start_dt and dt < start_dt:
                    continue
                if end_dt and dt > end_dt:
                    continue
                filtered.append(item)
            except Exception:
                continue
        return filtered


class CrawlerBase:
    """爬虫基类 —— 组合 BrowserDriver + DataSaver + DateParser"""

    def __init__(self, name: str = "crawler"):
        self.name = name
        self.logger = logging.getLogger(f"crawler.{name}")

    def crawl(self) -> list[dict]:
        """子类实现：返回爬取的数据列表"""
        raise NotImplementedError

    def save(self, data: list[dict], file_path: str, data_type: str):
        """保存数据"""
        DataSaver.save(data, file_path, data_type)

    def run(self, file_path: str, data_type: str):
        """运行爬虫并保存"""
        self.logger.info("=" * 50)
        self.logger.info("爬虫启动: %s", self.name)
        self.logger.info("=" * 50)

        data = self.crawl()
        self.logger.info("共获取 %d 条数据", len(data))

        if data:
            self.save(data, file_path, data_type)
            DataSaver.preview(data, data_type)

        self.logger.info("爬虫完成: %s", self.name)
        return data
