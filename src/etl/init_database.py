import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG


def create_database():
    """创建数据库（如果不存在）"""
    try:
        # 先连接到MySQL服务器（不指定数据库）
        connection = mysql.connector.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
        )

        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
            print(f"数据库 {DB_CONFIG['database']} 创建成功")

            cursor.close()
            connection.close()
    except Error as e:
        print(f"创建数据库失败: {e}")
        raise


if __name__ == "__main__":
    print("初始化数据库...")
    create_database()
