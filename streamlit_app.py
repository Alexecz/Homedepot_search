import streamlit as st
import pandas as pd
import time
import json
from bs4 import BeautifulSoup
import random
import re

# --- Selenium 相关导入 ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

# --- 核心抓取逻辑 (简化了日志输出) ---
def scrape_homedepot_with_selenium(query, max_pages_to_scrape):
    """
    使用标准Selenium驱动浏览器，通过解析__APOLLO_STATE__数据块并智能翻页，抓取完整数据。

    Args:
        query (str): 搜索关键词。
        max_pages_to_scrape (int): 用户指定的最大抓取页数。

    Returns:
        list: 包含所有页面商品信息的字典列表。
    """
    all_results = []
    status_placeholder = st.empty()
    driver = None
    
    try:
        status_placeholder.info(f"🚀 正在配置标准版浏览器...")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-data-dir=/tmp/selenium_user_data_{int(time.time())}")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
        
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        
        search_url = f"https://www.homedepot.com/s/{query.replace(' ', '%20')}"
        status_placeholder.info(f"🕵️ 浏览器已启动，正在访问初始页面...")
        driver.get(search_url)

        current_page = 1
        
        while True:
            if current_page > max_pages_to_scrape:
                status_placeholder.info(f"已达到设定的最大抓取页数 ({max_pages_to_scrape})，任务结束。")
                break

            status_text = f"⏳ 正在处理第 {current_page} 页 | 已抓取 {len(all_results)} 个商品..."
            status_placeholder.info(status_text)
            
            wait = WebDriverWait(driver, 30)
            
            try:
                # 1. 等待页面加载完成
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'nav[aria-label="Pagination Navigation"]')))
                
                # 2. 从HTML中提取APOLLO_STATE
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                script_tag = soup.find('script', string=re.compile(r"window\.__APOLLO_STATE__"))
                
                if not script_tag:
                    st.warning(f"第 {current_page} 页未找到 __APOLLO_STATE__ 数据块。")
                    break

                # 3. 精确提取并解析JSON
                match = re.search(r'window\.__APOLLO_STATE__\s*=\s*({.*});', script_tag.string)
                if not match:
                    st.warning(f"第 {current_page} 页无法从脚本中正确提取JSON数据。")
                    break
                
                json_text = match.group(1)
                apollo_data = json.loads(json_text)
                
                products_list = []
                for key in apollo_data:
                    if isinstance(apollo_data[key], dict) and 'products' in str(apollo_data[key]):
                        for sub_key, sub_value in apollo_data[key].items():
                            if isinstance(sub_value, list) and sub_value and isinstance(sub_value[0], dict) and sub_value[0].get('__ref'):
                                product_refs = sub_value
                                for ref in product_refs:
                                    product_id = ref.get('__ref')
                                    if product_id and product_id in apollo_data:
                                        products_list.append(apollo_data[product_id])
                                if products_list: break
                        if products_list: break

                if not products_list:
                    st.info(f"第 {current_page} 页未解析到产品，抓取结束。")
                    break
                
                for product in products_list:
                    name = product.get('identifiers', {}).get('productLabel', 'N/A')
                    pricing_key = next((k for k in product if k.startswith('pricing')), None)
                    pricing_info = product.get(pricing_key, {}) if pricing_key else {}
                    original_price = pricing_info.get('original')
                    current_price = pricing_info.get('value')
                    link = "https://www.homedepot.com" + product.get('identifiers', {}).get('canonicalUrl', '#')
                    image_url = product.get('media', {}).get('images', [{}])[0].get('url')
                    if image_url:
                        image_url = image_url.replace("<SIZE>", "400")

                    if name != 'N/A':
                        all_results.append({
                            'name': name, 'current_price': current_price, 'original_price': original_price,
                            'link': link, 'image_url': image_url or 'https://placehold.co/100x100/e2e8f0/333333?text=No+Image'
                        })

            except TimeoutException:
                status_placeholder.error(f"页面加载超时（第 {current_page} 页）。")
                st.image(driver.get_screenshot_as_png(), caption="超时快照")
                break 

            # 4. 寻找下一页的URL并导航
            try:
                next_page_element = driver.find_element(By.CSS_SELECTOR, 'a[aria-label="Skip to Next Page"]')
                next_page_url = next_page_element.get_attribute('href')
                driver.get(next_page_url)
                current_page += 1
                time.sleep(random.uniform(1.5, 3.5))
            except NoSuchElementException:
                status_placeholder.success(f"✅ 已到达最后一页，抓取完成！共处理 {current_page} 页。")
                break 
    
    except Exception as e:
        status_placeholder.error(f"抓取过程中发生未知错误: {e}")
    finally:
        if driver:
            driver.quit()
            
    return all_results

# --- Streamlit 应用界面 ---
st.set_page_config(page_title="在线商品信息工具", layout="wide")
st.title("🛒 在线商品信息工具")

search_query = st.text_input("请输入搜索关键词:", "milwaukee")

# --- 新的交互UI ---
col1, col2 = st.columns([1, 4])
with col1:
    limit_pages = st.checkbox("限制页数", value=False)
with col2:
    if limit_pages:
        max_pages_to_scrape = st.number_input("要抓取的页数:", min_value=1, max_value=50, value=3, key="max_pages_limited")
    else:
        max_pages_to_scrape = 999  # 设置一个很大的数代表“全部”
        st.write("将抓取所有可用的页面。")


if st.button("🚀 开始搜索"):
    if not search_query:
        st.warning("请输入搜索关键词！")
    else:
        all_scraped_data = scrape_homedepot_with_selenium(search_query, max_pages_to_scrape)

        if all_scraped_data:
            st.success(f"🎉 **任务结束！共获得 {len(all_scraped_data)} 条商品信息！**")
            
            full_df = pd.DataFrame(all_scraped_data)
            duplicates_mask = full_df.duplicated(subset=['name'], keep='first')
            unique_df = full_df[~duplicates_mask]
            duplicate_df = full_df[duplicates_mask]
            
            st.info(f"去重后剩余 {len(unique_df)} 条独立商品信息。")
            
            st.subheader("独立商品信息")
            display_unique_data = [{
                "图片": row['image_url'],
                "商品名称": row['name'],
                "原价": f"${row['original_price']}" if pd.notna(row['original_price']) and row['original_price'] != row['current_price'] else " ",
                "现售价": f"${row['current_price']}" if pd.notna(row['current_price']) else 'N/A',
                "链接": row['link']
            } for _, row in unique_df.iterrows()]
            
            st.dataframe(
                display_unique_data,
                column_config={
                    "图片": st.column_config.ImageColumn("图片预览", width="small"),
                    "商品名称": st.column_config.TextColumn("商品名称", width="large"),
                    "原价": st.column_config.TextColumn("原价", width="small"),
                    "现售价": st.column_config.TextColumn("现售价", width="small"),
                    "链接": st.column_config.LinkColumn("详情链接", display_text="🔗 查看商品", width="small")
                }, hide_index=True, use_container_width=True)

            if not duplicate_df.empty:
                with st.expander(f"查看 {len(duplicate_df)} 条重复的商品信息"):
                    st.dataframe(duplicate_df)
            
        else:
            st.error("未能抓取到任何商品信息，请查看上方的日志分析原因。")
