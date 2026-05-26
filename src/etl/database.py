import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG


class Database:
    def __init__(self):
        self.connection = None
        self.cursor = None

    def connect(self):
        """建立数据库连接"""
        try:
            self.connection = mysql.connector.connect(
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                database=DB_CONFIG["database"],
                charset=DB_CONFIG["charset"],
            )
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(buffered=True)
                print("数据库连接成功")
        except Error as e:
            print(f"数据库连接失败: {e}")
            raise

    def disconnect(self):
        """关闭数据库连接"""
        if self.connection.is_connected():
            self.cursor.close()
            self.connection.close()
            print("数据库连接已关闭")

    def execute_query(self, query, params=None):
        """执行SQL查询"""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            self.connection.commit()
            return self.cursor.rowcount
        except Error as e:
            print(f"SQL执行失败: {e}")
            self.connection.rollback()
            raise

    def fetch_query(self, query, params=None):
        """执行查询并返回结果"""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return self.cursor.fetchall()
        except Error as e:
            print(f"SQL查询失败: {e}")
            raise

    def create_tables(self):
        """创建数据库表"""
        create_reviews_table = """
        CREATE TABLE IF NOT EXISTS reviews (
            id INT AUTO_INCREMENT PRIMARY KEY,
            author VARCHAR(255) DEFAULT NULL,
            publish_date DATETIME DEFAULT NULL,
            rate INT DEFAULT NULL,
            content TEXT DEFAULT NULL,
            name VARCHAR(255) DEFAULT NULL,
            sku VARCHAR(255) DEFAULT NULL,
            url TEXT DEFAULT NULL,
            site_name VARCHAR(50) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_site_name (site_name),
            INDEX idx_publish_date (publish_date),
            INDEX idx_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        create_questions_table = """
        CREATE TABLE IF NOT EXISTS questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            author VARCHAR(255) DEFAULT NULL,
            publish_date DATETIME DEFAULT NULL,
            question TEXT DEFAULT NULL,
            content TEXT DEFAULT NULL,
            name VARCHAR(255) DEFAULT NULL,
            sku VARCHAR(255) DEFAULT NULL,
            url TEXT DEFAULT NULL,
            site_name VARCHAR(50) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_site_name (site_name),
            INDEX idx_publish_date (publish_date),
            INDEX idx_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        try:
            self.execute_query(create_reviews_table)
            self.execute_query(create_questions_table)
            print("表创建成功")
        except Error as e:
            print(f"表创建失败: {e}")
            raise

    def insert_review(self, review):
        """插入单条评论数据"""
        insert_query = """
        INSERT INTO reviews (author, publish_date, rate, content, name, sku, url, site_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            review.get("author"),
            review.get("publishDate"),
            review.get("rate"),
            review.get("content"),
            review.get("name"),
            review.get("SKU"),
            review.get("URL"),
            review.get("siteName"),
        )
        self.execute_query(insert_query, params)

    def insert_question(self, question):
        """插入单条问答数据"""
        insert_query = """
        INSERT INTO questions (author, publish_date, question, content, name, sku, url, site_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            question.get("author"),
            question.get("publishDate"),
            question.get("question"),
            question.get("content"),
            question.get("name"),
            question.get("SKU"),
            question.get("URL"),
            question.get("siteName"),
        )
        self.execute_query(insert_query, params)

    def insert_reviews_batch(self, reviews):
        """批量插入评论数据"""
        if not reviews:
            return 0

        insert_query = """
        INSERT INTO reviews (author, publish_date, rate, content, name, sku, url, site_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            (
                review.get("author"),
                review.get("publishDate"),
                review.get("rate"),
                review.get("content"),
                review.get("name"),
                review.get("SKU"),
                review.get("URL"),
                review.get("siteName"),
            )
            for review in reviews
        ]

        try:
            self.cursor.executemany(insert_query, params)
            self.connection.commit()
            return len(params)
        except Error as e:
            print(f"批量插入失败: {e}")
            self.connection.rollback()
            raise

    def insert_questions_batch(self, questions):
        """批量插入问答数据"""
        if not questions:
            return 0

        insert_query = """
        INSERT INTO questions (author, publish_date, question, content, name, sku, url, site_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            (
                question.get("author"),
                question.get("publishDate"),
                question.get("question"),
                question.get("content"),
                question.get("name"),
                question.get("SKU"),
                question.get("URL"),
                question.get("siteName"),
            )
            for question in questions
        ]

        try:
            self.cursor.executemany(insert_query, params)
            self.connection.commit()
            return len(params)
        except Error as e:
            print(f"批量插入失败: {e}")
            self.connection.rollback()
            raise

    def get_table_count(self, table_name):
        """获取表记录数"""
        query = f"SELECT COUNT(*) FROM {table_name}"
        result = self.fetch_query(query)
        return result[0][0]
