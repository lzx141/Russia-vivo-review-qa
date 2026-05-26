import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import os
import dateparser

def crawl_ozon_qa_by_url(product_url: str, model_name: str = "Unknown Model",
                         start_date: str = None, end_date: str = None):
    """
    爬取Ozon商品问答
    Args:
        product_url: 商品页面URL
        model_name: 商品名称
        start_date: 开始日期 (格式: 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM')
        end_date: 结束日期 (格式: 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM')
    Returns:
        问答列表
    """
    if not product_url:
        return []

    chrome_options = Options()
    chrome_options.add_argument("--lang=ru-RU")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.127 Safari/537.36")

    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        delete navigator.__proto__.webdriver;
        window.chrome = {runtime: {}};
        Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru']});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """
    })
    wait = WebDriverWait(driver, 15)

    print(f"正在打开商品页面: {product_url}")
    driver.get(product_url)
    time.sleep(random.uniform(10, 15))

    print("正在滚动到评论区域...")
    try:
        reviews_section = wait.until(
            EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "Отзывы о товаре")]'))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reviews_section)
        time.sleep(random.uniform(2, 3))
        print("✅ 已滚动到评论区域")
    except Exception as e:
        print(f"⚠️ 未找到评论区域: {e}")

    qa_pairs = []
    seen_question_ids = set()

    print("正在切换到'Вопросы о товаре'标签...")
    try:
        qa_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, '//button[.//span[contains(text(), "Вопросы о товаре")]]')
            )
        )
        driver.execute_script("arguments[0].click();", qa_button)
        print("✅ 已点击'Вопросы'按钮")
        time.sleep(random.uniform(4, 6))
    except Exception as e:
        print(f"⚠️ 无法点击'Вопросы'按钮: {e}")

    def extract_current_qa():
        new_pairs = []
        try:
            all_items = driver.find_elements(By.XPATH, ".//div[@data-question-id]")
            print(f"🔍 当前页面共找到 {len(all_items)} 个问答元素")

            for idx, item in enumerate(all_items):
                qid = item.get_attribute("data-question-id")
                if not qid or qid in seen_question_ids:
                    continue
                seen_question_ids.add(qid)

                try:
                    question_text = ""
                    question_author = "Аноним"
                    question_date = ""

                    try:
                        question_elem = WebDriverWait(item, 5).until(
                            EC.presence_of_element_located(
                              (By.XPATH, "./div[1]/div[2]/div[2]/div[1]")
                            )
                        )
                        question_text = question_elem.text.strip()
                    except:
                        print(f"⚠️ 问答 {idx+1} (qid={qid})：问题文本未加载")
                        continue

                    try:
                        author_elem = item.find_element(
                            By.XPATH, "./div[1]/div[2]/div[2]/div[2]"
                        )
                        txt = author_elem.text.strip()
                        if txt:
                            question_author = txt
                    except:
                        pass

                    try:
                        date_elem = item.find_element(
                            By.XPATH, "./div[1]/div[2]/div[1]/div"
                        )
                        question_date = date_elem.text.strip()
                    except:
                        pass

                    SKU = item.find_element(By.XPATH, "./div[1]/div[2]/div[1]/a").text

                    answer_text = ""
                    answer_author = ""

                    try:
                        answer_container = item.find_element(By.XPATH, ".//*[@data-answer-id]")

                        best_answer_elem = answer_container.find_elements(By.XPATH, ".//*[contains(text(), 'Лучший ответ')]")
                        if best_answer_elem:
                            answer_divs = answer_container.find_elements(By.XPATH, "./div/div[3]/div[1]")
                        else:
                            answer_divs = answer_container.find_elements(By.XPATH, "./div/div[2]/div[1]")

                        for div in answer_divs:
                            txt = div.text.strip()
                            if txt:
                                answer_text = txt
                                break

                        try:
                            answer_first_div = answer_container.find_element(
                                By.XPATH, ".//div[2]/div[1]/span"
                            )
                            answer_author = answer_first_div.text.strip()
                        except:
                            answer_author = ""

                    except Exception as e:
                        pass

                    siteName = 'OZON-question'

                    if question_text:
                        new_pairs.append(
                            {
                                "author": question_author,
                                "publishDate": question_date,
                                "SKU": SKU,
                                "question": question_text,
                                "content": answer_text,
                            }
                        )
                    else:
                        print(f"⚠️ 问答 {idx+1} (qid={qid})：问题内容为空，跳过")

                except Exception as e:
                    print(f"解析问答 {idx+1} (qid={qid}) 时出错: {e}")
                    continue

        except Exception as e:
            print(f"提取问答时出错: {e}")

        return new_pairs

    print("⏳ 等待初始问答加载...")
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, '//div[@data-question-id]'))
        )
    except:
        print("❌ 初始问答加载失败")
        driver.quit()
        return []

    qa_pairs.extend(extract_current_qa())

    round_clicks = 0
    max_round_clicks = 10

    while round_clicks < max_round_clicks:
        try:
            btn = driver.find_element(
                By.XPATH,
                '//a[contains(text(), "показать больше вопросов")] | '
                '//button[contains(., "показать больше вопросов")]',
            )
            driver.execute_script("arguments[0].click();", btn)
            print(f"✅ 点击'加载更多'按钮，第 {round_clicks + 1} 次")
            time.sleep(random.uniform(3, 5))
            qa_pairs.extend(extract_current_qa())
            round_clicks += 1
        except (NoSuchElementException, TimeoutException):
            print("⏹️ '加载更多'按钮已消失，停止加载。")
            break

    print(f"🎯 共抓取 {len(qa_pairs)} 条问答")

    start_datetime = None
    end_datetime = None

    if start_date:
        try:
            start_datetime = pd.to_datetime(start_date)
            print(f"⏰ 设置开始日期: {start_date}")
        except Exception as e:
            print(f"❌ 开始日期格式错误: {e}")

    if end_date:
        try:
            end_datetime = pd.to_datetime(end_date)
            print(f"⏰ 设置结束日期: {end_date}")
        except Exception as e:
            print(f"❌ 结束日期格式错误: {e}")

    filtered_qa = []
    skipped_count = 0
    in_range_count = 0

    for q in qa_pairs:
        q_date_str = q.get("publishDate", "")
        q_datetime = None

        if q_date_str:
            try:
                q_datetime = dateparser.parse(q_date_str, languages=['ru'])
            except Exception:
                q_datetime = None

        if not q_datetime or not (q_datetime.year == 2026 and q_datetime.month == 4):
            skipped_count += 1
            continue

        q["publishDate"] = q_datetime.strftime('%Y-%m-%d %H:%M')
        q["name"] = model_name
        q["URL"] = product_url
        q["siteName"] = "OZON-question"
        filtered_qa.append(q)
        in_range_count += 1

    print(f"📊 统计: 跳过 {skipped_count} 条，保留 {in_range_count} 条")

    driver.quit()

    return filtered_qa

def save_data_to_file(data, file_path, data_type):
    """
    将数据保存到指定文件，如果文件存在则追加
    Args:
        data: 数据列表
        file_path: 文件路径
        data_type: 'questions'
    """
    if not data:
        print(f"⚠️ 没有 {data_type} 数据，无法创建或更新文件。")
        return

    temp_df = pd.DataFrame(data)

    if data_type == 'questions':
        required_columns = ['author', 'publishDate', 'SKU', 'question', 'content', 'name', 'URL', 'siteName']
    else:
        print(f"❌ 未知的数据类型: {data_type}")
        return

    for col in required_columns:
        if col not in temp_df.columns:
            temp_df[col] = ""

    new_df = temp_df.reindex(columns=required_columns)

    if os.path.exists(file_path):
        print(f"📝 文件 '{file_path}' 已存在，正在读取并追加新数据...")
        existing_df = pd.read_excel(file_path, engine='openpyxl')
        for col in required_columns:
            if col not in existing_df.columns:
                existing_df[col] = ""
        existing_df = existing_df.reindex(columns=required_columns)

        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        print(f"✅ 追加成功，总行数: {len(combined_df)}")
    else:
        print(f"📝 文件 '{file_path}' 不存在，正在创建...")
        combined_df = new_df
        print(f"✅ 创建成功，初始行数: {len(combined_df)}")

    combined_df.to_excel(file_path, index=False, engine='openpyxl')
    print(f"✅ {data_type.capitalize()} 数据已保存/更新到 '{file_path}'")

    preview_count = min(5, len(new_df))
    print(f"\n预览新追加的前{preview_count}条{data_type}:")
    for i in range(preview_count):
        row = new_df.iloc[i]
        if data_type == 'questions':
            print(f"{i+1}. {row['author']} - SKU: {row['SKU']}")
            print(f" 问题: {row['question'][:100]}..." if row['question'] else " 问题: 无文本")
            print(f" 回答: {row['content'][:100]}..." if row['content'] else " 回答: 无文本")
            print(f" 日期: {row['publishDate']}")
        print("-" * 20)

def crawl_from_excel(excel_path: str, start_date: str = "2026-02-01", end_date: str = "2026-03-31"):
    """
    从Excel文件读取链接并爬取Ozon问答
    Args:
        excel_path: Excel文件路径
        start_date: 开始日期 (格式: 'YYYY-MM-DD')
        end_date: 结束日期 (格式: 'YYYY-MM-DD')
    """
    if not os.path.exists(excel_path):
        print(f"❌ Excel文件不存在: {excel_path}")
        return

    df = pd.read_excel(excel_path, engine='openpyxl')

    if '网址' not in df.columns or '名称' not in df.columns:
        print("❌ Excel文件中未找到'网址'或'名称'列")
        return

    ozon_df = df[df['名称'].str.contains('OZON', case=False, na=False)]
    ozon_df = ozon_df[ozon_df['网址'].notna()]

    print(f"📝 从 '{excel_path}' 读取到 {len(df)} 个链接")
    print(f"🔍 筛选出 {len(ozon_df)} 个OZON链接")

    for idx, row in ozon_df.iterrows():
        url = row.get('网址', '')
        model_name = row.get('机型', 'Unknown Model')

        if not url:
            continue

        print(f"\n{'='*60}")
        print(f"处理第 {idx + 1}/{len(ozon_df)} 个链接")
        print(f"商品名称: {model_name}")
        print(f"URL: {url}")
        print(f"{'='*60}\n")

        try:
            questions = crawl_ozon_qa_by_url(url, model_name, start_date, end_date)
            if questions:
                save_data_to_file(questions, 'ozon_questions.xlsx', 'questions')

        except Exception as e:
            print(f"❌ 处理链接时出错: {e}")
            continue

    print("\n--- 任务完成 ---")

if __name__ == "__main__":
    print("Ozon问答爬虫工具")
    excel_path = r"c:\Users\lenovo\Desktop\益普索\rusisa\Rusisa_new_20260130_all.xlsx"
    crawl_from_excel(excel_path)