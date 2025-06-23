import streamlit as st
import pandas as pd
import time
import json
from bs4 import BeautifulSoup

# --- Selenium 相关导入 ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

# --- 核心抓取逻辑 (Selenium智能翻页 + ld+json解析) ---
def scrape_homedepot_with_selenium(query, max_pages_to_scrape):
    """
    使用Selenium驱动浏览器，通过提取并导航到分页器中的URL进行智能翻页抓取。
    这是针对当前网站结构最可靠的方法。

    Args:
        query (str): 搜索关键词。
        max_pages_to_scrape (int): 本次运行最多抓取的页面数。

    Returns:
        list: 包含所有页面商品信息的字典列表。
    """
    search_url = f"https://www.homedepot.com/s/{query.replace(' ', '%20')}"
    all_results = []
    
    status_placeholder = st.empty() # 创建一个用于动态更新的占位符
    
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-data-dir=/tmp/selenium_user_data_{int(time.time())}")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        
        status_placeholder.info(f"🚀 浏览器已启动，正在访问初始页面...")
        driver.get(search_url)

        current_page = 1
        
        while True:
            if current_page > max_pages_to_scrape:
                st.info(f"已达到设定的最大抓取页数 ({max_pages_to_scrape})。")
                break
                
            status_placeholder.info(f"⏳ 正在处理第 {current_page} 页 | 已抓取 {len(all_results)} 个商品...")
            wait = WebDriverWait(driver, 30)
            
            try:
                # 1. 等待当前页数据加载
                wait.until(EC.presence_of_element_located((By.ID, "thd-helmet__script--browseSearchStructuredData")))

                # 2. 解析数据
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                script_tag = soup.find('script', {'id': 'thd-helmet__script--browseSearchStructuredData', 'type': 'application/ld+json'})
                
                if not script_tag:
                    st.warning(f"第 {current_page} 页未找到数据，抓取结束。")
                    break

                json_data = json.loads(script_tag.string)
                products_list = json_data[0].get('mainEntity', {}).get('offers', {}).get('itemOffered', [])
                
                if not products_list:
                    st.info(f"第 {current_page} 页未解析到产品，抓取结束。")
                    break
                
                for product in products_list:
                    name = product.get('name', 'N/A')
                    offers = product.get('offers', {})
                    price = offers.get('price', 'N/A') if isinstance(offers, dict) else 'N/A'
                    link = offers.get('url', '#') if isinstance(offers, dict) else '#'
                    image_url = product.get('image')

                    if name != 'N/A':
                        all_results.append({
                            'name': name, 'price': price, 'link': link, 
                            'image_url': image_url or 'https://placehold.co/100x100/e2e8f0/333333?text=No+Image'
                        })

            except TimeoutException:
                st.error(f"页面加载超时（第 {current_page} 页）。")
                break 

            # 3. 寻找下一页的URL并导航
            try:
                next_page_element = driver.find_element(By.CSS_SELECTOR, 'a[aria-label="Skip to Next Page"]')
                next_page_url = next_page_element.get_attribute('href')
                
                driver.get(next_page_url)
                current_page += 1
                time.sleep(1) 

            except NoSuchElementException:
                status_placeholder.success("✅ 未找到 'Next' 按钮，已到达最后一页，抓取完成！")
                break 
    
    except Exception as e:
        status_placeholder.error(f"抓取过程中发生未知错误: {e}")
    finally:
        if driver:
            driver.quit()
            
    return all_results

# --- Streamlit 应用界面 ---
st.set_page_config(page_title="Home Depot Selenium 爬虫", layout="wide")
st.title("🛒 Home Depot 商品抓取工具 (Selenium智能翻页版)")

search_query = st.text_input("请输入搜索关键词:", "milwaukee")
max_pages = st.number_input("最多抓取的页数:", min_value=1, max_value=25, value=3, help="设定一个抓取上限，以避免运行时间过长或被封禁。")


if st.button("🚀 使用 Selenium 开始搜索"):
    if not search_query:
        st.warning("请输入搜索关键词！")
    else:
        all_scraped_data = scrape_homedepot_with_selenium(search_query, max_pages)

        if all_scraped_data:
            st.success(f"🎉 **抓取完成！共获得 {len(all_scraped_data)} 条商品信息！**")
            
            df = pd.DataFrame(all_scraped_data).drop_duplicates(subset=['name'])
            st.info(f"去重后剩余 {len(df)} 条独立商品信息。")
            
            display_df_data = [{
                "图片": row['image_url'],
                "商品名称": row['name'],
                "价格": f"${row['price']}" if row.get('price') else 'N/A',
                "链接": row['link']
            } for _, row in df.iterrows()]
            
            st.dataframe(
                display_df_data,
                column_config={
                    "图片": st.column_config.ImageColumn("图片预览", width="small"),
                    "商品名称": st.column_config.TextColumn("商品名称", width="large"),
                    "价格": st.column_config.TextColumn("价格", width="small"),
                    "链接": st.column_config.LinkColumn("详情链接", display_text="🔗 查看商品", width="small")
                }, hide_index=True, use_container_width=True)
        else:
            st.error("未能抓取到任何商品信息，请查看上方的日志分析原因。")
        
st.markdown("---")
st.markdown("技术说明：此应用通过 `Selenium` 模拟浏览器，从分页器中提取URL进行智能翻页，并从渲染后的 `ld+json` 脚本中提取数据。")
