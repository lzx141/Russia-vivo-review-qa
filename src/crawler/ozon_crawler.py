import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import os
import dateparser


def _safe_console_text(value: str, encoding: str | None = None) -> str:
    """Return text that the active console encoding can print safely."""
    target = encoding or getattr(__import__("sys").stdout, "encoding", None) or "utf-8"
    return value.encode(target, errors="ignore").decode(target)


def _console_print(value: str = "") -> None:
    print(_safe_console_text(value))


def clear_proxy_environment():
    """
    移除进程内的 HTTP(S)_PROXY 环境变量。

    本机常驻 Clash 等代理软件并设置了 HTTP_PROXY/HTTPS_PROXY，这会导致：
      1. Selenium 与 chromedriver 之间的本地 HTTP 通信被代理转发（错误 Bad Gateway）；
      2. 浏览器走代理出口，OZON 识别为 VPN 并返回 403「Похоже, нет соединения」拦截页。
    OZON 对国内直连的真实浏览器是放行的，因此爬虫必须直连、绕过代理环境变量。
    """
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                 "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(name, None)


def _create_driver(headless: bool = True):
    """
    创建 Google Chrome 浏览器驱动。
    headless=True 时使用无头模式（更快，适合批量爬取）。
    """
    clear_proxy_environment()
    common_args = [
        "--lang=ru-RU",
        "--disable-blink-features=AutomationControlled",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        # 强制直连：忽略系统代理与 HTTP_PROXY 环境变量
        "--no-proxy-server",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.127 Safari/537.36",
    ]
    if headless:
        common_args.append("--headless=new")

    chrome_opts = ChromeOptions()
    for arg in common_args:
        chrome_opts.add_argument(arg)
    chrome_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_opts.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(service=Service(), options=chrome_opts)
    _inject_anti_detect(driver)
    return driver


def _inject_anti_detect(driver):
    """注入反爬虫检测脚本"""
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        delete navigator.__proto__.webdriver;
        window.chrome = {runtime: {}};
        Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru']});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """
    })


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
        time.sleep(random.uniform(2, 3))
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
        time.sleep(random.uniform(3, 5))

        # 验证是否进入详情页
        if not _is_search_redirect_page(driver):
            # 重新加载并追加 sort=published_at_desc，确保评论按时间倒序
            current = driver.current_url
            if "sort=" not in current:
                sep = "&" if "?" in current else "?"
                detail_url = current.split("#")[0] + sep + "sort=published_at_desc"
                driver.get(detail_url)
                time.sleep(random.uniform(3, 5))
            print(f"✅ 已进入商品详情页: {driver.current_url[:80]}")
            return True
        else:
            print("⚠️ 点击后仍在搜索页，可能该商品确实无货")
            return False

    except Exception as e:
        print(f"⚠️ 自动进入详情页失败: {e}")
        return False


# 星级图标：OZON 的 class 名带构建哈希（如 a5d5_5_1-a9）会随前端发版失效，
# 因此改为按「星形 path 的填充色」判定，亮星为品牌橙。
_RATING_STAR_COLOR = "rgb(255, 168, 0)"
_RATING_STAR_PATH = "M9.358 6.136"
_RATING_JS = """
const card = arguments[0];
const orange = arguments[1];
const prefix = arguments[2];
let stars = 0;
let filled = 0;
for (const svg of card.querySelectorAll('svg')) {
  const path = svg.querySelector('path');
  if (!path) continue;
  const d = path.getAttribute('d') || '';
  if (!d.startsWith(prefix)) continue;
  stars += 1;
  if (getComputedStyle(path).fill === orange) filled += 1;
}
return [stars, filled];
"""


def _read_rating(driver, element) -> int:
    """
    读取单条评论的星级（1-5）。

    新版详情页把星级渲染成 5 个 <svg> 星形，亮星填充品牌橙色；
    XPath 的 `//svg` 在这些节点上匹配不到（需 local-name()），
    所以改用 JS 读取计算样式。旧版结构则回退到 class 统计。
    """
    try:
        stars, filled = driver.execute_script(
            _RATING_JS, element, _RATING_STAR_COLOR, _RATING_STAR_PATH)
    except Exception:
        stars = filled = 0

    if filled:
        return max(1, min(5, int(filled)))
    if stars:
        # 页面只渲染已点亮的星时，星的个数即星级
        return max(1, min(5, int(stars)))

    # 旧版结构回退：按 hashed class 统计同 class 的 svg 个数
    try:
        legacy = element.find_elements(
            By.XPATH, './/*[local-name()="svg"][contains(@class, "-a9")]')
        if legacy:
            first_class = legacy[0].get_attribute("class")
            count = sum(1 for svg in legacy
                        if svg.get_attribute("class") == first_class)
            if count:
                return max(1, min(5, count))
    except Exception:
        pass

    # 默认没有零星，至少 1 星
    return 1


def _url_without_sort(url: str) -> str:
    """去掉 URL 中的 sort 参数（OZON 商品页实际不按该参数排序，留着只影响渲染成功率）"""
    base, sep, query = (url or "").partition("?")
    if not sep:
        return url
    kept = [part for part in query.split("&")
            if part and not part.lower().startswith("sort=")]
    return base + ("?" + "&".join(kept) if kept else "")


def _ensure_detail_page(driver, model_name: str, wait: WebDriverWait) -> None:
    """确保停留在商品详情页（若被重定向到搜索页则自动进入）"""
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        body_text = ""

    access_markers = (
        "Похоже, нет соединения",
        "Попробуйте отключить VPN",
        "Доступ ограничен",
        "Access denied",
    )
    matched_marker = next(
        (marker for marker in access_markers if marker.lower() in body_text.lower()),
        None,
    )
    if matched_marker:
        os.makedirs("artifacts", exist_ok=True)
        try:
            driver.save_screenshot("artifacts/ozon-access-blocked.png")
        except Exception:
            pass
        current_url = getattr(driver, "current_url", "")
        title = getattr(driver, "title", "")
        raise RuntimeError(
            f"OZON access blocked: {matched_marker}; title={title!r}; url={current_url}"
        )

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

    driver = _create_driver(headless=False)
    wait = WebDriverWait(driver, 15)
    
    print(f"正在打开商品页面: {product_url}")
    driver.get(product_url)
    time.sleep(random.uniform(5, 8))

    # 若被重定向到搜索页（商品售罄），自动点击进入商品详情页
    try:
        _ensure_detail_page(driver, model_name, wait)
    except Exception:
        driver.quit()
        raise

    print("正在滚动到评论区域...")
    try:
        reviews_section = wait.until(
            EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "Отзывы о товаре")]'))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reviews_section)
        time.sleep(random.uniform(1, 2))
        print("✅ 已滚动到评论区域")
    except Exception as e:
        print(f"⚠️ 未找到评论区域: {e}")
    
    reviews = []
    seen_uuids = set()
    print("正在智能滚动加载评论...")
    
    all_review_containers = []
    try:
        initial_container = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, '//*[@data-widget="webListReviews"]'))
        )
    except Exception as e:
        print(f"❌ 未找到评论容器: {e}")
    else:
        all_review_containers = [initial_container]

    # 评论组件偶发不渲染：去掉 sort 参数重开一次（该参数实际不生效，见下方注释）
    if not all_review_containers:
        fallback_url = _url_without_sort(driver.current_url or product_url)
        if fallback_url != (driver.current_url or product_url):
            print(f"↻ 去掉排序参数重试: {fallback_url}")
            try:
                driver.get(fallback_url)
                time.sleep(random.uniform(5, 8))
                _ensure_detail_page(driver, model_name, WebDriverWait(driver, 15))
                try:
                    section = WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located(
                            (By.XPATH, '//span[contains(text(), "Отзывы о товаре")]'))
                    )
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", section)
                    time.sleep(random.uniform(1, 2))
                except Exception:
                    pass
                retry_container = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located(
                        (By.XPATH, '//*[@data-widget="webListReviews"]'))
                )
                all_review_containers = [retry_container]
                print("✅ 重试后已找到评论容器")
            except Exception as e:
                print(f"❌ 重试仍未找到评论容器: {e}")
                all_review_containers = []
    
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
            time.sleep(random.uniform(1.5, 2.5))
        
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
            
            rating = _read_rating(driver, el)
            
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

def _crawl_ozon_qa_legacy(product_url: str, model_name: str = "Unknown Model",
                          start_date: str = None, end_date: str = None):
    """
    爬取 Ozon 商品问答（旧版页面结构：data-question-id / data-answer-id）

    OZON 在 2026-09 前后把问答组件换成了 webPDPListQuestions
    （data-question-uuid / data-answer-uuid），本函数仅作为旧结构回退保留。
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

    driver = _create_driver(headless=False)
    wait = WebDriverWait(driver, 15)

    print(f"正在打开商品页面: {product_url}")
    driver.get(product_url)
    time.sleep(random.uniform(5, 8))

    # 若被重定向到搜索页（商品售罄），自动点击进入商品详情页
    try:
        _ensure_detail_page(driver, model_name, wait)
    except Exception:
        driver.quit()
        raise

    print("正在滚动到评论区域...")
    try:
        reviews_section = wait.until(
            EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "Отзывы о товаре")]'))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reviews_section)
        time.sleep(random.uniform(1, 2))
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
        time.sleep(random.uniform(2, 3))
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
            time.sleep(random.uniform(2, 3))
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


# ══════════════════════════════════════════════════════════════════
# 问答爬虫（新版页面结构，2026-09 起 OZON 使用的 webPDPListQuestions）
# ══════════════════════════════════════════════════════════════════

# 单条问答内的相对路径（已在 OZON 实际页面上逐条核对）
_QA_QUESTION_TEXT = (
    "./div[1]/div[2]/div[2]/div[1]",
    "./div[1]/div[2]/div[2]/div[1]/span[1]",
)
_QA_QUESTION_AUTHOR = (
    "./div[1]/div[2]/div[2]/div[2]",
    "./div[1]/div[2]/div[2]/div[2]//span[1]",
)
_QA_QUESTION_DATE = (
    "./div[1]/div[2]/div[1]/div[1]",
    "./div[1]/div[2]/div[1]/div[1]//span[1]",
)
_QA_PRODUCT_LINK = (
    "./div[1]/div[2]/div[1]/a",
)
_QA_ANSWER_TEXT = (
    ".//div[@data-answer-uuid]/div[1]/div[3]/div[1]",
    ".//div[@data-answer-uuid]//div[@data-answer-uuid]/div[1]/div[3]/div[1]",
)
_QA_ANSWER_AUTHOR = (
    ".//div[@data-answer-uuid]/div[1]/div[2]/div[1]",
)
_QA_ANSWER_DATE = (
    ".//div[@data-answer-uuid]/div[1]/div[2]/div[2]",
)


def _qa_text(element, xpaths) -> str:
    """按候选 XPath 依次取第一段非空文本"""
    for xpath in xpaths:
        try:
            candidates = element.find_elements(By.XPATH, xpath)
        except Exception:
            continue
        for candidate in candidates:
            text = " ".join((candidate.text or "").split())
            if text:
                return text
    return ""


def _parse_qa_item(item) -> dict | None:
    """解析一条问答卡片（新版结构），问题为空视为无效卡片"""
    question = _qa_text(item, _QA_QUESTION_TEXT)
    if not question:
        return None
    return {
        "author": _qa_text(item, _QA_QUESTION_AUTHOR) or "Аноним",
        "publishDate": _qa_text(item, _QA_QUESTION_DATE),
        "SKU": _qa_text(item, _QA_PRODUCT_LINK),
        "question": question,
        "content": _qa_text(item, _QA_ANSWER_TEXT),
        # 回答者与回答时间目前未入库，保留原始文本便于排查
        "answer_author": _qa_text(item, _QA_ANSWER_AUTHOR),
        "answer_date": _qa_text(item, _QA_ANSWER_DATE),
    }


def _collect_qa_items(driver, max_rounds: int = 12) -> list:
    """滚动加载问答列表并去重解析（新版：div[@data-question-uuid]）"""
    seen: set = set()
    pairs: list = []

    def collect() -> int:
        found = 0
        try:
            items = driver.find_elements(By.XPATH, "//div[@data-question-uuid]")
        except Exception:
            return 0
        for item in items:
            try:
                qid = item.get_attribute("data-question-uuid")
            except Exception:
                continue
            found += 1
            if not qid or qid in seen:
                continue
            parsed = _parse_qa_item(item)
            if not parsed:
                continue
            seen.add(qid)
            pairs.append(parsed)
        return found

    collect()
    stable = 0
    for _ in range(max_rounds):
        try:
            widget = driver.find_element(
                By.XPATH, '//*[@data-widget="webPDPListQuestions"]')
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'end'});", widget)
        except Exception:
            pass
        driver.execute_script("window.scrollBy(0, 1400)")
        time.sleep(random.uniform(2, 3))
        before = len(pairs)
        collect()
        stable = stable + 1 if len(pairs) == before else 0
        print(f"🔄 问答加载：已解析 {len(pairs)} 条（连续无新增 {stable} 次）")
        if stable >= 2:
            break
    return pairs


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

    driver = _create_driver(headless=False)
    wait = WebDriverWait(driver, 15)

    print(f"正在打开商品页面: {product_url}")
    driver.get(product_url)
    time.sleep(random.uniform(5, 8))

    try:
        _ensure_detail_page(driver, model_name, wait)

        print("正在滚动到评论区域...")
        try:
            reviews_section = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, '//span[contains(text(), "Отзывы о товаре")]'))
            )
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", reviews_section)
            time.sleep(random.uniform(1, 2))
            print("✅ 已滚动到评论区域")
        except Exception as e:
            print(f"⚠️ 未找到评论区域: {e}")

        print("正在切换到'Вопросы о товаре'标签...")
        clicked = False
        for attempt in range(3):
            try:
                qa_button = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH,
                         '//button[.//span[contains(text(), "Вопросы")]]'))
                )
                driver.execute_script("arguments[0].click();", qa_button)
                clicked = True
                break
            except Exception as e:
                print(f"⚠️ 无法点击'Вопросы'按钮（第 {attempt + 1} 次）: {e}")
                time.sleep(2)
        if clicked:
            print("✅ 已点击'Вопросы'按钮")
        time.sleep(random.uniform(3, 4))

        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.XPATH, '//div[@data-question-uuid]'))
            )
        except Exception:
            print("⚠️ 未加载到新版问答列表")
            driver.quit()
            print("↩️ 回退到旧版问答解析")
            return _crawl_ozon_qa_legacy(
                product_url, model_name, start_date, end_date)

        qa_pairs = _collect_qa_items(driver)
    except Exception:
        driver.quit()
        raise

    print(f"🎯 共抓取 {len(qa_pairs)} 条问答")

    start_datetime = pd.to_datetime(start_date) if start_date else None
    end_datetime = pd.to_datetime(end_date) if end_date else None

    filtered_qa = []
    skipped_count = 0
    for q in qa_pairs:
        q_datetime = None
        if q.get("publishDate"):
            try:
                q_datetime = dateparser.parse(q["publishDate"], languages=["ru"])
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
        q["publishDate"] = q_datetime.strftime("%Y-%m-%d %H:%M")
        q["name"] = model_name
        q["URL"] = product_url
        q["siteName"] = "OZON-question"
        filtered_qa.append(q)

    print(f"📊 统计: 跳过 {skipped_count} 条，保留 {len(filtered_qa)} 条")

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

    # 数据已在 crawl_* 函数中按传入的日期范围过滤，这里不做二次月份过滤
    if 'publishDate' in new_df.columns:
        new_df['publishDate'] = pd.to_datetime(new_df['publishDate'], errors='coerce')
        # 仅丢弃无效日期，保留有效记录
        new_df = new_df[new_df['publishDate'].notna()]
        if new_df.empty:
            print(f"⚠️ 没有有效的 {data_type} 数据（日期解析失败），无法创建或更新文件。")
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


def crawl_from_excel(excel_path: str, start_date: str = None, end_date: str = None,
                     only: str = "all"):
    """
    从Excel文件读取链接并爬取Ozon评论
    Args:
        excel_path: Excel文件路径
        start_date: 开始日期 (格式: 'YYYY-MM-DD')，默认自动取上月
        end_date: 结束日期 (格式: 'YYYY-MM-DD')，默认自动取上月
        only: 'all' 同时抓评论与问答；'reviews' / 'qa' 只抓其中一类
    """
    if only not in ("all", "reviews", "qa"):
        raise ValueError(f"only 只能是 all / reviews / qa，收到: {only!r}")
    if start_date is None or end_date is None:
        auto_start, auto_end = _default_last_month()
        start_date = start_date or auto_start
        end_date = end_date or auto_end
        _console_print(f"📅 动态日期范围: {start_date} ~ {end_date}")

    clear_proxy_environment()

    if not os.path.exists(excel_path):
        _console_print(f"❌ Excel文件不存在: {excel_path}")
        return

    df = pd.read_excel(excel_path, engine='openpyxl')

    if '网址' not in df.columns or '名称' not in df.columns:
        _console_print("❌ Excel文件中未找到'网址'或'名称'列")
        return
    
    ozon_df = df[df['名称'].str.contains('OZON', case=False, na=False)]
    ozon_df = ozon_df[ozon_df['网址'].notna()]
    
    _console_print(f"📝 从 '{excel_path}' 读取到 {len(df)} 个链接")
    _console_print(f"🔍 筛选出 {len(ozon_df)} 个OZON链接")

    failures = []
    total_records = 0
    
    for ordinal, (idx, row) in enumerate(ozon_df.iterrows(), 1):
        url = row.get('网址', '')
        model_name = row.get('机型', 'Unknown Model')

        if not url:
            continue

        # OZON 评论区排序：追加 sort=published_at_desc。
        # 实测该参数已不生效（返回顺序并非按时间倒序），且偶发导致评论组件不渲染；
        # 因此仅作为默认 URL 保留，渲染失败时由 crawl_ozon_reviews_by_url 去掉后重试。
        sep = '&' if '?' in url else '?'
        url = url.split('#')[0] + sep + 'sort=published_at_desc'
        _console_print(f"🔀 已启用按时间排序: {url}")

        print(f"\n{'='*60}")
        print(f"处理第 {ordinal}/{len(ozon_df)} 个链接")
        print(f"商品名称: {model_name}")
        print(f"URL: {url}")
        print(f"{'='*60}\n")
        
        try:
            if only in ("all", "reviews"):
                reviews = crawl_ozon_reviews_by_url(url, model_name, start_date, end_date)
                if reviews:
                    total_records += len(reviews)
                    save_data_to_file(reviews, 'ozon_reviews.xlsx', 'reviews')

            if only in ("all", "qa"):
                questions = crawl_ozon_qa_by_url(url, model_name, start_date, end_date)
                if questions:
                    total_records += len(questions)
                    save_data_to_file(questions, 'ozon_questions.xlsx', 'questions')

        except Exception as e:
            _console_print(f"❌ 处理链接时出错: {e}")
            if "OZON access blocked" in str(e):
                raise
            failures.append(f"{model_name}: {e}")
            continue

    if len(ozon_df) > 0 and len(failures) == len(ozon_df):
        details = "; ".join(failures[:3])
        raise RuntimeError(
            f"all {len(ozon_df)} OZON products failed; first errors: {details}"
        )

    if len(ozon_df) > 0 and total_records == 0:
        raise RuntimeError(
            f"OZON crawler produced 0 records for {start_date} through {end_date}"
        )
    
    print("\n--- 任务完成 ---")

def main(argv=None):
    """本地命令行入口；试运行只检查输入，不启动浏览器。"""
    import argparse
    import sys

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from config.config import PRODUCT_URLS_EXCEL

    parser = argparse.ArgumentParser(description="Ozon 上月评论与问答采集")
    parser.add_argument('--excel', default=PRODUCT_URLS_EXCEL, help="商品链接 Excel 路径")
    parser.add_argument('--start-date', help="开始日期，例如 2026-08-01")
    parser.add_argument('--end-date', help="结束日期，例如 2026-08-31")
    parser.add_argument('--dry-run', action='store_true', help="仅检查路径、日期和商品链接")
    parser.add_argument('--only', choices=('all', 'reviews', 'qa'), default='all',
                        help="只抓评论或只抓问答（默认两者都抓）")
    args = parser.parse_args(argv)
    clear_proxy_environment()
    auto_start, auto_end = _default_last_month()
    start, end = args.start_date or auto_start, args.end_date or auto_end
    try:
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        if pd.isna(start_ts) or pd.isna(end_ts) or start_ts > end_ts:
            raise ValueError('开始日期必须早于或等于结束日期')
    except (ValueError, TypeError) as exc:
        parser.error(f'日期范围无效: {exc}')
    excel_path = os.path.abspath(args.excel)
    print(f'商品链接: {excel_path}')
    print(f'日期范围: {start} ~ {end}')
    if not os.path.isfile(excel_path):
        print(f'错误: 商品链接 Excel 不存在: {excel_path}')
        return 1
    try:
        frame = pd.read_excel(excel_path, engine='openpyxl')
        if not {'名称', '网址'}.issubset(frame.columns):
            raise ValueError("Excel 必须包含 '名称' 和 '网址' 列")
        links = frame[frame['名称'].astype(str).str.contains('OZON', case=False, na=False)
                      & frame['网址'].notna()]
        if links.empty:
            raise ValueError('Excel 中没有可用的 Ozon 商品链接')
        print(f'Ozon 商品链接数: {len(links)}')
        if args.dry_run:
            print('检查通过；未启动浏览器、未修改数据。')
            return 0
        previous_dir = os.getcwd()
        try:
            os.chdir(project_root)
            crawl_from_excel(excel_path, start, end, only=args.only)
        finally:
            os.chdir(previous_dir)
    except Exception as exc:
        print(f'采集未完成: {type(exc).__name__}: {exc}')
        return 1
    return 0


if __name__ == "__main__":
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    sys.exit(main())
