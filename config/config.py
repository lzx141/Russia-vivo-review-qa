"""
项目配置文件
支持通过环境变量覆盖默认值（.env 文件自动加载）
"""
import os
from dotenv import load_dotenv

load_dotenv()

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 数据库配置
# ============================================================
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "russia_ecommerce"),
    "charset": "utf8mb4",
}

# ============================================================
# 原始数据文件路径（相对于项目根目录）
# ============================================================
DATA_PATHS = {
    "ozon_reviews": [
        "原始数据/ozon_reviews.xlsx",
        "原始数据/ozon_reviews1.xlsx",
        "原始数据/ozon_reviews2.xlsx",
        "原始数据/ozon_reviews3.xlsx",
        "原始数据/ozon_reviews4.xlsx",
        "原始数据/ozon_reviews5.xlsx",
    ],
    "ozon_questions": [
        "原始数据/ozon_questions.xlsx",
        "原始数据/ozon_questions2.xlsx",
        "原始数据/ozon_questions3.xlsx",
        "原始数据/ozon_questions4.xlsx",
        "原始数据/ozon_questions5.xlsx",
    ],
    "wildberries_reviews": [
        "原始数据/wildberries_reviews.xlsx",
        "原始数据/wildberries_reviews1.xlsx",
        "原始数据/wildberries_reviews2.xlsx",
        "原始数据/wildberries_reviews3.xlsx",
        "原始数据/wildberries_reviews4.xlsx",
        "原始数据/wildberries_reviews5.xlsx",
        "原始数据/wildberries_reviews6.xlsx",
    ],
    "wildberries_questions": [
        "原始数据/wildberries_qa.xlsx",
        "原始数据/wildberries_qa1.xlsx",
        "原始数据/wildberries_qa2.xlsx",
        "原始数据/wildberries_qa3.xlsx",
        "原始数据/wildberries_qa4.xlsx",
        "原始数据/wildberries_qa5.xlsx",
        "原始数据/wildberries_qa6.xlsx",
    ],
    "yandex_reviews": [
        "原始数据/yandex_reviews4.xlsx",
    ],
}

# 商品链接 Excel（爬虫用）
PRODUCT_URLS_EXCEL = os.getenv(
    "PRODUCT_URLS_EXCEL",
    os.path.join(PROJECT_ROOT, "Rusisa_new_20260130_all.xlsx"),
)

# ============================================================
# 翻译后数据文件
# ============================================================
MERGED_TRANSLATED_CSV = os.path.join(PROJECT_ROOT, "merged_data_translated.csv")
MERGED_TRANSLATED_XLSX = os.path.join(PROJECT_ROOT, "merged_data_translated.xlsx")

# ============================================================
# 火山引擎翻译 API 配置（token 留空，使用前需填写）
# ============================================================
VOLC_ACCESS_KEY = os.getenv("VOLC_ACCESS_KEY", "")
VOLC_SECRET_KEY = os.getenv("VOLC_SECRET_KEY", "")
# 火山引擎翻译 API 端点
VOLC_TRANSLATE_URL = "https://translate.volcengine.com/api/v1/translate"
VOLC_TRANSLATE_BATCH_SIZE = int(os.getenv("VOLC_TRANSLATE_BATCH_SIZE", "50"))

# ============================================================
# DeepSeek V4 Flash API 配置（token 留空，使用前需填写）
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL", "https://api.deepseek.com"
)
# 分析批处理大小（每次调用分析多少条）
ANALYSIS_BATCH_SIZE = int(os.getenv("ANALYSIS_BATCH_SIZE", "100"))
# 分析模型名称
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ============================================================
# 输出目录
# ============================================================
OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(PROJECT_ROOT, "output"))
DASHBOARD_DIR = os.path.join(PROJECT_ROOT, "src", "dashboard")
DASHBOARD_DATA_JS = os.path.join(DASHBOARD_DIR, "dashboard_data.js")

# ============================================================
# 数据管道配置
# ============================================================
PIPELINE_CONFIG = {
    "run_id_prefix": "etl",
    "batch_size": int(os.getenv("ETL_BATCH_SIZE", "1000")),
    "enable_quality_check": os.getenv("ENABLE_QUALITY_CHECK", "true").lower() == "true",
    "alert_on_failure": os.getenv("ALERT_ON_FAILURE", "false").lower() == "true",
}

# ============================================================
# 环境标识
# ============================================================
ENV = os.getenv("APP_ENV", "development")  # development / staging / production
