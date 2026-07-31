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


def _is_search_redirect_page(driver) -> bool:
    """判断当前页面是否是被重定向的 OZON 搜索/推荐页（原商品已售罄）"""
    try:
        current_url = driver.current_url or ""
        if "/search/" in current_url or "product_id=" in current_url:
            return True
        # 检查售罄提示
        body_text = driver.find_element(By.TAG_NAME, "body").text
        if "Этот товар закончился" in body_text or "этот товар закончился" in body_text.lower():
            return True
    except Exception:
        pass
    return False


def _click_product_card_to_detail(driver, model_name: str, wait: WebDriverWait) -> bool:
    """
    在 OZON 搜索/推荐页中，自动点击匹配的商品卡片进入详情页。

    策略：
      1. 优先按 URL slug / 标题文本匹配机型名称
      2. 若找不到精确匹配，点击第一个商品卡片

    Returns:
        True 表示成功进入商品详情页
    """
    try:
        # 等待商品卡片链接加载
        time.sleep(random.uniform(3, 5))
        links = driver.find_elements(By.XPATH, '//a[contains(@href, "/product/")]')
        if not links:
            print("⚠️ 搜索页未找到商品卡片链接")
            return False

        # 规范化机型名用于匹配
        model_key = model_name.lower().replace(" ", "-").replace("(", "").replace(")", "")
        matched = None

        # 策略1: 匹配 href 中包含机型 slug 的链接
        for link in links:
            href = (link.get_attribute("href") or "").lower()
            if model_key and model_key in href:
                matched = link
                break

        # 策略2: 匹配链接文本中包含机型名
        if not matched:
            for link in links:
                text = (link.text or "").lower()
                if model_name.lower() in text:
                    matched = link
                    break

        # 策略3: 回退到第一个链接
        if not matched:
            matched = links[0]
            print(f"⚠️ 未找到匹配「{model_name}」的商品，回退点击第一个卡片")

        # 点击进入详情页
        driver.execute_script("arguments[0].click();", matched)
        time.sleep(random.uniform(6, 9))

        # 验证是否进入详情页
        if not _is_search_redirect_page(driver):
            # 重新加载并追加 sort=published_at_desc，确保评论按时间倒序
            current = driver.current_url
            if "sort=" not in current:
                sep = "&" if "?" in current else "?"
                detail_url = current.split("#")[0] + sep + "sort=published_at_desc"
                driver.get(detail_url)
                time.sleep(random.uniform(6, 9))
            print(f"✅ 已进入商品详情页: {driver.current_url[:80]}")
            return True
        else:
            print("⚠️ 点击后仍在搜索页，可能该商品确实无货")
            return False

    except Exception as e:
        print(f"⚠️ 自动进入详情页失败: {e}")
        return False


def _ensure_detail_page(driver, model_name: str, wait: WebDriverWait) -> None:
    """确保停留在商品详情页（若被重定向到搜索页则自动进入）"""
    if _is_search_redirect_page(driver):
        print("🔍 检测到 OZON 搜索/推荐页（原商品售罄），正在自动进入商品详情页...")
        _click_product_card_to_detail(driver, model_name, wait)
    else:
        print("✅ 已打开商品详情页")

def crawl_ozon_reviews_by_url(product_url: str, model_name: str = "Unknown Model",
                               start_date: str = None, end_date: str = None):
    """
    爬取Ozon商品评论
    Args:
        product_url: 商品页面URL
        model_name: 商品名称
        start_date: 开始日期 (格式: 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM')
        end_date: 结束日期 (格式: 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM')
    Returns:
        评论列表
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

    # 若被重定向到搜索页（商品售罄），自动点击进入商品详情页
    _ensure_detail_page(driver, model_name, wait)

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
    
    reviews = []
    seen_uuids = set()
    print("正在智能滚动加载评论...")
    
    try:
        initial_container = wait.until(
            EC.presence_of_element_located((By.XPATH, '//*[@data-widget="webListReviews"]'))
        )
    except Exception as e:
        print(f"❌ 未找到评论容器: {e}")
        all_review_containers = []
    else:
        all_review_containers = [initial_container]
    
    max_load_attempts = 200
    no_change_count = 0
    last_page_height = 0
    
    for attempt in range(max_load_attempts):
        if not all_review_containers:
            break
        
        current_reviews = []
        for container in all_review_containers:
            try:
                current_reviews.extend(
                    container.find_elements(By.XPATH, ".//*[@data-review-uuid]")
                )
            except:
                continue
        
        current_total = len(current_reviews)
        print(f"🔄 尝试 {attempt + 1}/{max_load_attempts} | 已加载评论数: {current_total}")
        
        current_page_height = driver.execute_script("return document.body.scrollHeight")
        
        if current_page_height == last_page_height:
            no_change_count += 1
            if no_change_count >= 3:
                print("⏹️ 页面尺寸未变化，停止加载")
                break
        else:
            no_change_count = 0
            last_page_height = current_page_height
        
        if current_reviews:
            last_review = current_reviews[-1]
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", last_review
            )
            time.sleep(random.uniform(2.5, 4.0))
        
        try:
            all_review_containers = driver.find_elements(
                By.XPATH, '//*[@data-widget="webListReviews"]'
            )
        except:
            pass
    
    total_raw_reviews = []
    for container in all_review_containers:
        try:
            reviews_in_container = container.find_elements(
                By.XPATH, ".//*[@data-review-uuid]"
            )
            total_raw_reviews.extend(reviews_in_container)
        except:
            continue
    
    print(f"🔍 共定位到 {len(total_raw_reviews)} 条原始评论元素")
    
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
    
    skipped_count = 0
    in_range_count = 0
    
    for el in total_raw_reviews:
        try:
            uuid = el.get_attribute("data-review-uuid")
            if not uuid or uuid in seen_uuids:
                continue
            seen_uuids.add(uuid)
            
            author = el.find_element(By.XPATH, ".//div[1]/div[2]//span[1]").text.strip()
            date_text = el.find_element(By.XPATH, "./div[1]/div[2]/div[1]").text.strip()
            
            rating_svg = el.find_elements(
                By.XPATH,
                './/svg[contains(@class, "a5d5_4_0-a9")]',
            )
            rating = 0
            if rating_svg:
                first_class = rating_svg[0].get_attribute('class')
                if first_class:
                    for svg in rating_svg:
                        svg_class = svg.get_attribute('class')
                        if svg_class == first_class:
                            rating += 1
            # 默认没有零星，至少1星
            if rating == 0:
                rating = 1
            
            comment_text = ""
            try:
                candidate_spans = el.find_elements(By.XPATH, "./div[2]/div[2]//span")
                if candidate_spans:
                    comment_text = candidate_spans[0].text.strip()
            except:
                comment_text = ""
            
            SKU_elem = el.find_elements(By.XPATH, "./div[2]/div[1]//a")
            SKU = SKU_elem[0].text.strip() if SKU_elem else ""
            
            siteName = 'OZON'
            name = model_name
            
            review_datetime = None
            if date_text:
                try:
                    # 使用 dateparser 处理俄罗斯语日期格式
                    review_datetime = dateparser.parse(date_text, languages=['ru'])
                except Exception:
                    review_datetime = None
            
            # 按传入的日期范围过滤（不再硬编码月份）
            if review_datetime:
                if start_datetime and review_datetime < start_datetime:
                    skipped_count += 1
                    continue
                if end_datetime and review_datetime > end_datetime:
                    skipped_count += 1
                    continue
                publish_date_standard = review_datetime.strftime('%Y-%m-%d %H:%M')
            else:
                skipped_count += 1
                continue
            
            reviews.append(
                {
                    "author": author,
                    "publishDate": publish_date_standard,
                    "rate": rating,
                    "content": comment_text,
                    "name": name,
                    "SKU": SKU,
                    "URL": product_url,
                    "siteName": siteName,
                }
            )
            in_range_count += 1
            
        except Exception as e:
            continue
    
    print(f"📊 统计: 跳过 {skipped_count} 条，保留 {in_range_count} 条")
    print(f"✅ 最终成功抓取 {len(reviews)} 条唯一评论")
    
    driver.quit()
    
    return reviews

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

    # 若被重定向到搜索页（商品售罄），自动点击进入商品详情页
    _ensure_detail_page(driver, model_name, wait)

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

                        if idx < 2:
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

        if not q_datetime:
            skipped_count += 1
            continue

        if start_datetime and q_datetime < start_datetime:
            skipped_count += 1
            continue
        if end_datetime and q_datetime > end_datetime:
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
        data_type: 'reviews'
    """
    if not data:
        print(f"⚠️ 没有 {data_type} 数据，无法创建或更新文件。")
        return
    
    temp_df = pd.DataFrame(data)
    
    if data_type == 'reviews':
        required_columns = ['author', 'publishDate', 'rate', 'content', 'name', 'SKU', 'URL', 'siteName']
    elif data_type == 'questions':
        required_columns = ['author', 'publishDate', 'SKU', 'question', 'content', 'name', 'URL', 'siteName']
    else:
        print(f"❌ 未知的数据类型: {data_type}")
        return
    
    for col in required_columns:
        if col not in temp_df.columns:
            temp_df[col] = ""
    
    new_df = temp_df.reindex(columns=required_columns)

    if 'publishDate' in new_df.columns and data_type == 'reviews':
        new_df['publishDate'] = pd.to_datetime(new_df['publishDate'], errors='coerce')
        # 按当前目标月份（上月）过滤，与 crawl_from_excel 的日期范围保持一致
        target_start, target_end = _default_last_month()
        target_start_dt = pd.to_datetime(target_start)
        target_end_dt = pd.to_datetime(target_end)
        new_df = new_df[new_df['publishDate'].between(target_start_dt, target_end_dt)]

        if new_df.empty:
            print(f"⚠️ 没有{target_start} ~ {target_end}的{data_type}数据，无法创建或更新文件。")
            return

        new_df['publishDate'] = new_df['publishDate'].dt.strftime('%Y-%m-%d %H:%M')
    
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
        if data_type == 'reviews':
            print(f"{i+1}. {row['author']} - 评分: {row['rate']}")
            print(f" 内容: {row['content'][:100]}..." if row['content'] else " 内容: 无文本")
            print(f" 日期: {row['publishDate']}")
        elif data_type == 'questions':
            print(f"{i+1}. {row['author']} - SKU: {row['SKU']}")
            print(f" 问题: {row['question'][:100]}..." if row['question'] else " 问题: 无文本")
            print(f" 回答: {row['content'][:100]}..." if row['content'] else " 回答: 无文本")
            print(f" 日期: {row['publishDate']}")
        print("-" * 20)

def _default_last_month() -> tuple[str, str]:
    """
    动态计算上个月的起止日期（每月3号跑定时任务时，爬取完整的上月数据）
    Returns:
        (start_date, end_date) 格式 'YYYY-MM-DD'
    """
    today = pd.Timestamp.today()
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - pd.Timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    return last_month_start.strftime('%Y-%m-%d'), last_month_end.strftime('%Y-%m-%d')


def crawl_from_excel(excel_path: str, start_date: str = None, end_date: str = None):
    """
    从Excel文件读取链接并爬取Ozon评论
    Args:
        excel_path: Excel文件路径
        start_date: 开始日期 (格式: 'YYYY-MM-DD')，默认自动取上月
        end_date: 结束日期 (格式: 'YYYY-MM-DD')，默认自动取上月
    """
    if start_date is None or end_date is None:
        auto_start, auto_end = _default_last_month()
        start_date = start_date or auto_start
        end_date = end_date or auto_end
        print(f"📅 动态日期范围: {start_date} ~ {end_date}")

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

        # OZON 评论区排序：追加 sort=published_at_desc，按发布时间倒序展示
        # 这样无需手动点击"Сортировать"下拉框，即可让评论按时间顺序加载
        sep = '&' if '?' in url else '?'
        url = url.split('#')[0] + sep + 'sort=published_at_desc'
        print(f"🔀 已启用按时间排序: {url}")

        print(f"\n{'='*60}")
        print(f"处理第 {idx + 1}/{len(ozon_df)} 个链接")
        print(f"商品名称: {model_name}")
        print(f"URL: {url}")
        print(f"{'='*60}\n")
        
        try:
            reviews = crawl_ozon_reviews_by_url(url, model_name, start_date, end_date)
            if reviews:
                save_data_to_file(reviews, 'ozon_reviews.xlsx', 'reviews')

            questions = crawl_ozon_qa_by_url(url, model_name, start_date, end_date)
            if questions:
                save_data_to_file(questions, 'ozon_questions.xlsx', 'questions')

        except Exception as e:
            print(f"❌ 处理链接时出错: {e}")
            continue
    
    print("\n--- 任务完成 ---")

if __name__ == "__main__":
    print("Ozon爬虫工具")
    excel_path = r"c:\Users\lenovo\Desktop\益普索\rusisa\Rusisa_new_20260130_all.xlsx"
    crawl_from_excel(excel_path)
