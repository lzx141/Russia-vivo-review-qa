# MySQL数据库配置
import os

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': os.getenv('MYSQL_PASSWORD', ''),  # 从环境变量读取
    'database': 'russia_ecommerce',
    'charset': 'utf8mb4'
}

# 原始数据文件路径
DATA_PATHS = {
    "ozon_reviews": [
        "原始数据/ozon_reviews.xlsx",
        "原始数据/ozon_reviews1.xlsx",
        "原始数据/ozon_reviews2.xlsx",
    ],
    "ozon_questions": ["原始数据/ozon_questions.xlsx", "原始数据/ozon_questions2.xlsx"],
    "wildberries_reviews": [
        "原始数据/wildberries_reviews.xlsx",
        "原始数据/wildberries_reviews1.xlsx",
        "原始数据/wildberries_reviews2.xlsx",
        "原始数据/wildberries_reviews3.xlsx",
    ],
    "wildberries_questions": [
        "原始数据/wildberries_qa.xlsx",
        "原始数据/wildberries_qa1.xlsx",
        "原始数据/wildberries_qa2.xlsx",
        "原始数据/wildberries_qa3.xlsx",
    ],
}
