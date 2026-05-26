import pandas as pd
import requests
import re
import os
import time
import random
import json
import warnings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

warnings.filterwarnings("ignore")


def format_review(item: dict) -> str:
    pros = item.get('pros', '')
    cons = item.get('cons', '')
    text = item.get('text', '')
    if not pros and not cons:
        return text or ""
    parts = []
    if pros:
        parts.append(f"Достоинства: {pros}")
    if cons:
        parts.append(f"Недостатки: {cons}")
    if text:
        parts.append(f"Комментарий: {text}")
    return "\n".join(parts)


def crawl_wildberries_reviews_manual(imt_id: str, original_url: str = "https://www.wildberries.ru/",
                                     model_name: str = "Unknown Model",
                                     start_date: str = None, end_date: str = None):
    if not imt_id:
        print("错误: 未提供 imtId")
        return []
    
    start_datetime = None
    end_datetime = None
    if start_date:
        try:
            start_datetime = pd.to_datetime(start_date).tz_localize(None)
            print(f"设置开始日期: {start_date}")
        except Exception as e:
            print(f"开始日期格式错误: {e}")
            start_datetime = None
    
    if end_date:
        try:
            end_datetime = pd.to_datetime(end_date).tz_localize(None)
            print(f"设置结束日期: {end_date}")
        except Exception as e:
            print(f"结束日期格式错误: {e}")
            end_datetime = None
    
    if start_datetime and end_datetime and start_datetime > end_datetime:
        print("错误: 开始日期不能晚于结束日期")
        return []

    print(f"开始爬取 imtId: {imt_id} 的评论...")
    
    # 两个request url各自尝试一遍
    base_url = "https://feedbacks2.wb.ru/feedbacks/v2/{imt_id}"
    fallback_url = "https://feedbacks1.wb.ru/feedbacks/v2/{imt_id}"
    
    session = requests.Session()

    all_reviews = []
    
    # 尝试feedbacks2 URL
    request_url = base_url.format(imt_id=imt_id)
    print(f"API URL: {request_url}")
    
    response = None
    try:
        headers = {
            "Accept": "*/*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": "https://www.wildberries.ru",
            "Referer": original_url,
            "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(110, 130)}.0.0.0 Safari/537.36",
            "sec-ch-ua": f'\"Chromium\";v=\"{random.randint(110, 130)}\", \"Not A(Brand\";v=\"24\", \"Google Chrome\";v=\"{random.randint(110, 130)}\"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '\"Windows\"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site"
        }
        
        response = session.get(request_url, headers=headers, timeout=15)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                feedbacks = data.get('feedbacks', [])
                if feedbacks:
                    print(f"获取到 {len(feedbacks)} 条评论")
                    
                    early_stop = False
                    skipped_count = 0
                    in_range_count = 0
                    
                    for i, fb in enumerate(feedbacks):
                        review_date_str = fb.get('createdDate', '')
                        review_datetime = None
                        
                        if review_date_str:
                            try:
                                review_datetime = pd.to_datetime(review_date_str).tz_localize(None)
                            except Exception:
                                review_datetime = None
                        
                        if review_datetime:
                            if start_datetime and review_datetime <= start_datetime:
                                skipped_count += 1
                                early_stop = True
                                continue
                            
                            if end_datetime and review_datetime >= end_datetime:
                                skipped_count += 1
                                continue
                        
                        review_text = format_review(fb)
                        author = "Аноним"
                        wb_user_details = fb.get('wbUserDetails', {})
                        if isinstance(wb_user_details, dict):
                            author = wb_user_details.get('name', 'Аноним')
                        
                        sku = fb.get('color', '')

                        all_reviews.append({
                            "URL": original_url,
                            "author": author,
                            "publishDate": review_date_str,
                            "rate": fb.get('productValuation', ''),
                            "SKU": sku,
                            "content": review_text,
                            "name": model_name,
                            "siteName": 'wildberries'
                        })
                        in_range_count += 1
                    
                        print(f"统计: 跳过 {skipped_count} 条，保留 {in_range_count} 条")
                    
                    if early_stop:
                        print(f"已发现早于开始日期的评论，提前停止处理")
                        
                else:
                    print(f"未找到评论数据")
                    print(f"响应内容: {response.text[:500]}")
                    
            except Exception as e:
                print(f"解析响应失败: {e}")
                print(f"响应内容: {response.text[:500]}")
                if response.status_code == 429:
                   print(f"请求过多被限制，等待10秒")
            time.sleep(10)
        else:
            print(f"HTTP错误: {response.status_code}")
            print(f"错误响应: {response.text[:200]}")
            
    except Exception as e:
                print(f"请求失败: {e}")
    
    # 如果第一页出错，尝试feedbacks1 URL
    if not all_reviews:
        print(f"第一次请求失败，尝试使用 feedbacks1 URL...")
        request_url = fallback_url.format(imt_id=imt_id)
        print(f"API URL: {request_url}")
        
        try:
            headers = {
                "Accept": "*/*",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Origin": "https://www.wildberries.ru",
                "Referer": original_url,
                "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(110, 130)}.0.0.0 Safari/537.36",
                "sec-ch-ua": f'\"Chromium\";v=\"{random.randint(110, 130)}\", \"Not A(Brand\";v=\"24\", \"Google Chrome\";v=\"{random.randint(110, 130)}\"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '\"Windows\"',
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "cross-site"
            }
            
            response = session.get(request_url, headers=headers, timeout=15)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    feedbacks = data.get('feedbacks', [])
                    if feedbacks:
                        print(f"获取到 {len(feedbacks)} 条评论")
                        
                        early_stop = False
                        skipped_count = 0
                        in_range_count = 0
                        
                        for i, fb in enumerate(feedbacks):
                            review_date_str = fb.get('createdDate', '')
                            review_datetime = None
                            
                            if review_date_str:
                                try:
                                    review_datetime = pd.to_datetime(review_date_str).tz_localize(None)
                                except Exception:
                                    review_datetime = None
                            
                            if review_datetime:
                                if review_datetime.year == 2026 and review_datetime.month == 4:
                                    if start_datetime and review_datetime <= start_datetime:
                                        skipped_count += 1
                                        early_stop = True
                                
                                        continue
                                    
                                    if end_datetime and review_datetime >= end_datetime:
                                        skipped_count += 1
                                        continue
                            
                            review_text = format_review(fb)
                            author = "Аноним"
                            wb_user_details = fb.get('wbUserDetails', {})
                            if isinstance(wb_user_details, dict):
                                author = wb_user_details.get('name', 'Аноним')
                            
                            sku = fb.get('color', '')

                            all_reviews.append({
                                "URL": original_url,
                                "author": author,
                                "publishDate": review_date_str,
                                "rate": fb.get('productValuation', ''),
                                "SKU": sku,
                                "content": review_text,
                                "name": model_name,
                                "siteName": 'wildberries'
                            })
                            in_range_count += 1
                        
                            print(f"统计: 跳过 {skipped_count} 条，保留 {in_range_count} 条")
                        
                        if early_stop:
                            print(f"已发现早于开始日期的评论，提前停止处理")
                            
                    else:
                        print(f"未找到评论数据")        
                        print(f"响应内容: {response.text[:500]}")
                        
                except Exception as e:
                    print(f"解析响应失败: {e}")
                    print(f"响应内容: {response.text[:500]}")
            elif response.status_code == 429:
                print(f"请求过多被限制，等待10秒")
                time.sleep(10)
            else:
                print(f"HTTP错误: {response.status_code}")
                print(f"错误响应: {response.text[:200]}")
                
        except Exception as e:
            print(f"请求失败: {e}") 
    
    if all_reviews:
        df_reviews = pd.DataFrame(all_reviews)
        if 'publishDate' in df_reviews.columns:
            df_reviews['publishDate'] = pd.to_datetime(df_reviews['publishDate'], errors='coerce')
            df_reviews['publishDate'] = df_reviews['publishDate'] + pd.Timedelta(hours=8)
            df_reviews['publishDate'] = df_reviews['publishDate'].dt.strftime('%Y-%m-%d %H:%M')

        print(f"\n总共提取了 {len(all_reviews)} 条评论")
        
        print("\n预览前5条评论:")
        for i, review in enumerate(all_reviews[:5]):
            print(f"{i+1}. {review['author']} - 评分: {review['rate']}")
            print(f" 内容: {review['content'][:100]}..." if review['content'] else " 内容: 无文本")
            print(f" 日期: {review['publishDate']}")
            print()
    else:
        print("没有获取到任何评论")

    return all_reviews


def crawl_wildberries_qa_manual(imt_id: str, original_url: str = "https://www.wildberries.ru/",
                                model_name: str = "Unknown Model",
                                start_date: str = None, end_date: str = None):
    if not imt_id:
        print("错误: 未提供 imtId")
        return []

    start_datetime = None
    end_datetime = None
    if start_date:
        try:
            start_datetime = pd.to_datetime(start_date).tz_localize(None)
            print(f"设置开始日期: {start_date}")
        except Exception as e:
            print(f"开始日期格式错误: {e}")
            start_datetime = None
    
    if end_date:
        try:
            end_datetime = pd.to_datetime(end_date).tz_localize(None)
            print(f"设置结束日期: {end_date}")
        except Exception as e:
            print(f"结束日期格式错误: {e}")
            end_datetime = None
    
    if start_datetime and end_datetime and start_datetime > end_datetime:
        print("错误: 开始日期不能晚于结束日期")
        return []

    print(f"开始爬取 imtId: {imt_id} 的问答...")

    session = requests.Session()
    all_qa = []

    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "deviceid": "site_1545b34386e342ea876cd0b034035632",
        "priority": "u=1, i",
        "sec-ch-ua": "\"Not(A:Brand\";v=\"8\", \"Chromium\";v=\"144\", \"Google Chrome\";v=\"144\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-requested-with": "XMLHttpRequest",
        "x-spa-version": "13.21.2",
        "Referer": original_url,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    }

    total_fetched = 0
    early_stop_flag = False
    
    first_url = f"https://questions.wildberries.ru/api/v1/questions?imtId={imt_id}&take=30&skip=0"
    try:
        resp = session.get(first_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            questions = data.get("questions", [])
            print(f"获取到 {len(questions)} 条问答")
            
            skipped_count = 0
            in_range_count = 0
            
            for q in questions:
                q_date_str = q.get("createdDate")
                q_datetime = None
                
                if q_date_str:
                    try:
                        q_datetime = pd.to_datetime(q_date_str).tz_localize(None)
                    except Exception:
                        q_datetime = None
                
                if q_datetime:
                    if start_datetime and q_datetime < start_datetime:
                        skipped_count += 1
                        early_stop_flag = True
                        continue
                    
                    if end_datetime and q_datetime > end_datetime:
                        skipped_count += 1
                        continue
                
                all_qa.append({
                    "URL": original_url,
                    "author": q.get("wbUserDetails", {}).get("name", "Аноним"),
                    "publishDate": q_date_str,
                    "question": q.get("text", "").strip(),
                    "content": q.get("answer", {}).get("text", "").strip() if q.get("answer") else "",
                    "name": model_name,
                    "siteName": "wildberries-question"
                })
                in_range_count += 1
            
            print(f"统计: 跳过 {skipped_count} 条，保留 {in_range_count} 条")
            total_fetched = in_range_count
            
            if early_stop_flag:
                print(f"已发现早于开始日期的问答，停止分页")
                
        else:
            print(f"请求失败 (HTTP {resp.status_code})")
            total_fetched = 0
            return []
    except Exception as e:
        print(f"出错: {e}")
        total_fetched = 0
        return []

    if total_fetched >= 30 and not early_stop_flag:
        skip = 30
        while True:
            next_url = f"https://questions.wildberries.ru/api/v1/questions?imtId={imt_id}&take=10&skip={skip}"
            try:
                resp = session.get(next_url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    print(f"分页请求失败 (skip={skip}, HTTP {resp.status_code})")
                    break
                data = resp.json()
                questions = data.get("questions", [])
                if not questions:
                    print(f"无更多问答 (skip={skip})，停止分页")
                    break
                
                print(f"获取到 {len(questions)} 条问答 (skip={skip})")
                
                page_skipped_count = 0
                page_in_range_count = 0
                page_early_stop = False
                
                for q in questions:
                    q_date_str = q.get("createdDate")
                    q_datetime = None
                    
                    if q_date_str:
                        try:
                            q_datetime = pd.to_datetime(q_date_str).tz_localize(None)
                        except Exception:
                            q_datetime = None
                    
                    if q_datetime:
                        if start_datetime and q_datetime < start_datetime:
                            page_skipped_count += 1
                            page_early_stop = True
                            continue
                        
                        if end_datetime and q_datetime > end_datetime:
                            page_skipped_count += 1
                            continue
                    
                    all_qa.append({
                        "URL": original_url,
                        "author": q.get("wbUserDetails", {}).get("name", "Аноним"),
                        "publishDate": q_date_str,
                        "question": q.get("text", "").strip(),
                        "content": q.get("answer", {}).get("text", "").strip() if q.get("answer") else "",
                        "name": model_name,
                        "siteName": "wildberries-question"
                    })
                    page_in_range_count += 1
                
                print(f"统计: 跳过 {page_skipped_count} 条，保留 {page_in_range_count} 条")
                
                if page_early_stop:
                    print(f"本页发现早于开始日期的问答，停止分页")
                    break
                
                skip += 10
                
            except Exception as e:
                print(f"出错: {e}")
                break

    if all_qa:
        df_qa = pd.DataFrame(all_qa)
        if 'publishDate' in df_qa.columns:
            df_qa['publishDate'] = pd.to_datetime(df_qa['publishDate'], errors='coerce')
            df_qa['publishDate'] = df_qa['publishDate'] + pd.Timedelta(hours=8)
            df_qa['publishDate'] = df_qa['publishDate'].dt.strftime('%Y-%m-%d %H:%M')

        print(f"\n🎉 总共提取了 {len(all_qa)} 条问答")
        
        print("\n预览前5条问答:")
        for i, qa in enumerate(all_qa[:5]):
            print(f"{i+1}. {qa['author']} - 日期: {qa['publishDate']}")
            print(f" 问题: {qa['question'][:100]}..." if qa['question'] else " 问题: 无文本")
            print(f" 回答: {qa['content'][:100]}..." if qa['content'] else " 回答: 无回答")
            print()
        print("没有获取到任何问答")

    return all_qa


def save_data_to_file(data, file_path, data_type):
    if not data:
        print(f"没有 {data_type} 数据，无法创建或更新文件。")
        return
    
    temp_df = pd.DataFrame(data)
    
    if data_type == 'reviews':
        required_columns = ['author', 'publishDate', 'rate', 'content', 'name', 'SKU', 'URL', 'siteName']
    elif data_type == 'qa':
        required_columns = ['author', 'publishDate', 'question', 'content', 'name', 'URL', 'siteName']
    else:
        print(f"未知的数据类型: {data_type}")
        return
    
    for col in required_columns:
        if col not in temp_df.columns:
            temp_df[col] = ""
    
    new_df = temp_df.reindex(columns=required_columns)
    
    if 'publishDate' in new_df.columns:
        new_df['publishDate'] = pd.to_datetime(new_df['publishDate'], errors='coerce').dt.tz_localize(None)
        new_df['publishDate'] = new_df['publishDate'] + pd.Timedelta(hours=8)
        new_df['publishDate'] = new_df['publishDate'].dt.strftime('%Y-%m-%d %H:%M')
    
    if os.path.exists(file_path):
        print(f"文件 '{file_path}' 已存在，正在读取并追加新数据...")    
        existing_df = pd.read_excel(file_path, engine='openpyxl')
        for col in required_columns:
            if col not in existing_df.columns:
                existing_df[col] = ""
        existing_df = existing_df.reindex(columns=required_columns)
        
        if 'publishDate' in existing_df.columns:
            existing_df['publishDate'] = pd.to_datetime(existing_df['publishDate'], errors='coerce').dt.tz_localize(None)
        
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        print(f"追加成功，总行数: {len(combined_df)}")
    else:
        print(f"文件 '{file_path}' 不存在，正在创建...")
        combined_df = new_df
        print(f"创建成功，初始行数: {len(combined_df)}")
    
    combined_df.to_excel(file_path, index=False, engine='openpyxl')
    print(f"{data_type.capitalize()} 数据已保存/更新到 '{file_path}'")
    
    preview_count = min(5, len(new_df))
    print(f"\n预览新追加的前{preview_count}条{data_type}:")
    for i in range(preview_count):
        row = new_df.iloc[i]
        if data_type == 'reviews':
            print(f"{i+1}. {row['author']} - 评分: {row['rate']}")
            print(f" 内容: {row['content'][:100]}..." if row['content'] else " 内容: 无文本")
            print(f" 日期: {row['publishDate']}")
        elif data_type == 'qa':
            print(f"{i+1}. {row['author']} - 日期: {row['publishDate']}")
            print(f" 问题: {row['question'][:100]}..." if row['question'] else " 问题: 无文本")
            print(f" 回答: {row['content'][:100]}..." if row['content'] else " 回答: 无回答")
        print("-" * 20)


def crawl_from_excel(excel_path: str, start_date: str = "2026-04-01", end_date: str = "2026-04-30"):
    if not os.path.exists(excel_path):
        print(f"Excel文件不存在: {excel_path}")
        return
    
    df = pd.read_excel(excel_path, engine='openpyxl')
    
    if '名称' not in df.columns or '网址' not in df.columns:
        print("Excel文件中未找到'名称'或'网址'列")
        return
    
    wb_df = df[df['名称'].str.contains('wildberries', case=False, na=False)]
    wb_df = wb_df[wb_df['imtId'].notna()]
    
    wb_df['imtId'] = wb_df['imtId'].apply(lambda x: str(int(float(str(x)))) if pd.notna(x) else '')
    
    print(f"从 '{excel_path}' 读取到 {len(df)} 个链接") 
    print(f"    筛选出 {len(wb_df)} 个Wildberries链接")
    
    for idx, row in wb_df.iterrows():
        imt_id = str(row.get('imtId', '')).strip()
        product_url = row.get('网址', '')
        model_name = row.get('机型', 'Unknown Model')
        
        if not imt_id or imt_id.lower() == 'nan':
            continue
        
        
        print(f"\n{'='*60}")
        print(f"处理第 {idx + 1}/{len(wb_df)} 个链接")
        print(f"商品名称: {model_name}")
        print(f"imtId: {imt_id}")
        print(f"URL: {product_url}")
        print(f"{'='*60}\n")
        
        try:
            reviews = crawl_wildberries_reviews_manual(imt_id=imt_id, original_url=product_url,
                                                      model_name=model_name, start_date=start_date, end_date=end_date)
            if reviews:
                save_data_to_file(reviews, 'wildberries_reviews.xlsx', 'reviews')
            
            qa = crawl_wildberries_qa_manual(imt_id=imt_id, original_url=product_url,
                                            model_name=model_name, start_date=start_date, end_date=end_date)
            if qa:
                save_data_to_file(qa, 'wildberries_qa.xlsx', 'qa')
                
        except Exception as e:
            print(f"处理链接时出错: {e}")
            continue
    
    print("\n--- 任务完成 ---")


if __name__ == "__main__":
    print("Wildberries爬虫工具")
    excel_path = r"c:\Users\lenovo\Desktop\益普索\rusisa\Rusisa_new_20260130_all.xlsx"
    crawl_from_excel(excel_path)
