import pandas as pd
import os
from database import Database
from config import DATA_PATHS


class ETLProcessor:
    def __init__(self):
        self.db = Database()
        self.total_reviews = 0
        self.total_questions = 0

    def extract_excel_data(self, file_paths):
        """从多个Excel文件提取数据"""
        all_data = []
        for file_path in file_paths:
            full_path = os.path.join(os.path.dirname(__file__), file_path)
            # 检查文件是否存在
            if not os.path.exists(full_path):
                print(f"文件不存在: {full_path}")
                continue

            try:
                df = pd.read_excel(full_path, engine="openpyxl")
                print(f"读取文件: {file_path}, 行数: {len(df)}")

                # 将DataFrame转换为字典列表
                data = df.to_dict("records")
                all_data.extend(data)
            except Exception as e:
                print(f"读取文件失败 {file_path}: {e}")

        return all_data

    def transform_reviews(self, raw_data):
        """转换评论数据"""
        transformed = []
        for item in raw_data:
            # 标准化字段名
            record = {
                "author": item.get("author", item.get("Author", "")),
                "publishDate": self._parse_datetime(
                    item.get("publishDate", item.get("PublishDate", ""))
                ),
                "rate": item.get("rate", item.get("Rate", item.get("rating", ""))),
                "content": item.get("content", item.get("Content", "")),
                "name": item.get("name", item.get("Name", "")),
                "SKU": item.get("SKU", item.get("sku", "")),
                "URL": item.get("URL", item.get("url", "")),
                "siteName": item.get("siteName", item.get("SiteName", "")),
            }
            transformed.append(record)

        # 去重
        unique_data = self._remove_duplicates(transformed)
        print(f"转换完成，原始数据: {len(raw_data)}，去重后: {len(unique_data)}")
        return unique_data

    def transform_questions(self, raw_data):
        """转换问答数据"""
        transformed = []
        for item in raw_data:
            # 标准化字段名
            record = {
                "author": item.get("author", item.get("Author", "")),
                "publishDate": self._parse_datetime(
                    item.get("publishDate", item.get("PublishDate", ""))
                ),
                "question": item.get("question", item.get("Question", "")),
                "content": item.get(
                    "content", item.get("Content", item.get("answer", ""))
                ),
                "name": item.get("name", item.get("Name", "")),
                "SKU": item.get("SKU", item.get("sku", "")),
                "URL": item.get("URL", item.get("url", "")),
                "siteName": item.get("siteName", item.get("SiteName", "")),
            }
            transformed.append(record)

        # 去重
        unique_data = self._remove_duplicates(transformed)
        print(f"转换完成，原始数据: {len(raw_data)}，去重后: {len(unique_data)}")
        return unique_data

    def _parse_datetime(self, datetime_str):
        """解析日期时间字符串"""
        if not datetime_str:
            return None

        try:
            # 尝试多种日期格式
            formats = [
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%d.%m.%Y %H:%M",
            ]
            for fmt in formats:
                try:
                    return pd.to_datetime(datetime_str, format=fmt).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except:
                    continue

            # 默认解析
            return pd.to_datetime(datetime_str, errors="coerce").strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except:
            return None

    def _remove_duplicates(self, data):
        """基于完整数据去重，只有所有字段都完全相同时才认为是重复"""
        seen = set()
        unique = []
        for item in data:
            # 将字典转换为可哈希的元组，包含所有字段
            # 按固定顺序提取字段值，确保相同内容的记录生成相同的键
            fields = [
                item.get("author", ""),
                item.get("publishDate", ""),
                item.get("rate", ""),
                item.get("content", ""),
                item.get("question", ""),  # 问答数据专用字段
                item.get("name", ""),
                item.get("SKU", ""),
                item.get("URL", ""),
                item.get("siteName", ""),
            ]
            # 将所有字段转换为字符串，处理 None 和非字符串类型
            key = tuple(str(f) if f is not None else "" for f in fields)
            if key not in seen:
                seen.add(key)
                unique.append(item)
        print(f"去重完成，原始数据: {len(data)} 条，去重后: {len(unique)} 条")
        return unique

    def load_data(self, reviews_data, questions_data):
        """加载数据到数据库"""
        # 批量插入评论数据（每批1000条）
        if reviews_data:
            batch_size = 1000
            for i in range(0, len(reviews_data), batch_size):
                batch = reviews_data[i : i + batch_size]
                count = self.db.insert_reviews_batch(batch)
                self.total_reviews += count
                print(f"已插入 {i+count}/{len(reviews_data)} 条评论")

        # 批量插入问答数据（每批1000条）
        if questions_data:
            batch_size = 1000
            for i in range(0, len(questions_data), batch_size):
                batch = questions_data[i : i + batch_size]
                count = self.db.insert_questions_batch(batch)
                self.total_questions += count
                print(f"已插入 {i+count}/{len(questions_data)} 条问答")

    def run(self):
        """执行完整ETL流程"""
        print("开始执行ETL流程...")

        try:
            # 连接数据库并创建表
            self.db.connect()
            self.db.create_tables()

            # 提取评论数据
            print("\n处理评论数据...")
            all_reviews = []
            for paths in [
                DATA_PATHS["ozon_reviews"],
                DATA_PATHS["wildberries_reviews"],
            ]:
                raw_data = self.extract_excel_data(paths)
                all_reviews.extend(raw_data)

            # 转换评论数据
            transformed_reviews = self.transform_reviews(all_reviews)

            # 提取问答数据
            print("\n处理问答数据...")
            all_questions = []
            for paths in [
                DATA_PATHS["ozon_questions"],
                DATA_PATHS["wildberries_questions"],
            ]:
                raw_data = self.extract_excel_data(paths)
                all_questions.extend(raw_data)

            # 转换问答数据
            transformed_questions = self.transform_questions(all_questions)

            # 加载数据到数据库
            print("\n加载数据到数据库...")
            self.load_data(transformed_reviews, transformed_questions)

            # 输出统计信息
            print("\nETL流程完成!")
            print(f"评论数据: {self.total_reviews} 条")
            print(f"问答数据: {self.total_questions} 条")
            print(f"数据库评论表总数: {self.db.get_table_count('reviews')} 条")
            print(f"数据库问答表总数: {self.db.get_table_count('questions')} 条")

        finally:
            # 关闭数据库连接
            if self.db.connection and self.db.connection.is_connected():
                self.db.disconnect()


if __name__ == "__main__":
    etl = ETLProcessor()
    etl.run()
