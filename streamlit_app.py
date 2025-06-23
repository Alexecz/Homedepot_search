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

# --- 核心抓取逻辑 (全自动智能翻页 + 动态状态更新) ---
def scrape_homedepot_with_selenium(query):
    """
    使用Selenium驱动浏览器，通过提取并导航到分页器中的URL进行全自动翻页抓取。
    使用 st.empty() 提供简洁的动态状态更新。

    Args:
        query (str): 搜索关键词。

    Returns:
        list: 包含所有页面商品信息的字典列表。
    """
    search_url = f"https://www.homedepot.com/s/{query.replace(' ', '%20')}"
    all_results = []
    
    st.write("---")
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
        total_pages_str = "?" # 默认为未知
        
        while True:
            # 更新状态
            status_text = f"⏳ 正在处理第 {current_page} / {total_pages_str} 页 | 已抓取 {len(all_results)} 个商品..."
            status_placeholder.info(status_text)
            
            wait = WebDriverWait(driver, 30)
            
            try:
                # 1. 等待当前页数据加载
                wait.until(EC.presence_of_element_located((By.ID, "thd-helmet__script--browseSearchStructuredData")))

                # 2. 解析数据
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # 首次运行时，尝试获取总页数
                if current_page == 1:
                    try:
                        # 查找所有代表页码的链接
                        page_buttons = soup.select('nav[aria-label="Pagination Navigation"] a[aria-label*="Go to Page"]')
                        if page_buttons:
                            # 最后一个 "Go to Page X" 链接通常就是总页数
                            last_page_num = page_buttons[-1].text.strip()
                            if last_page_num.isdigit():
                                total_pages_str = last_page_num
                    except Exception:
                        total_pages_str = "?" # 获取失败则保持未知

                script_tag = soup.find('script', {'id': 'thd-helmet__script--browseSearchStructuredData', 'type': 'application/ld+json'})
                
                if not script_tag:
                    break

                json_data = json.loads(script_tag.string)
                products_list = json_data[0].get('mainEntity', {}).get('offers', {}).get('itemOffered', [])
                
                if not products_list:
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
                status_placeholder.error(f"页面加载超时（第 {current_page} 页）。")
                break 

            # 3. 寻找下一页的URL并导航
            try:
                next_page_element = driver.find_element(By.CSS_SELECTOR, 'a[aria-label="Skip to Next Page"]')
                next_page_url = next_page_element.get_attribute('href')
                
                driver.get(next_page_url)
                current_page += 1
                time.sleep(1) # 礼貌性延迟

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
st.set_page_config(page_title="Home Depot Selenium 爬虫", layout="wide")
st.title("🛒 Home Depot 商品抓取工具 (全自动翻页版)")

search_query = st.text_input("请输入搜索关键词:", "milwaukee")

if st.button("🚀 开始搜索 (抓取全部分页)"):
    if not search_query:
        st.warning("请输入搜索关键词！")
    else:
        all_scraped_data = scrape_homedepot_with_selenium(search_query)

        if all_scraped_data:
            st.success(f"🎉 **任务结束！共获得 {len(all_scraped_data)} 条商品信息！**")
            
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
st.markdown("技术说明：此应用通过 `Selenium` 模拟浏览器，智能寻找并导航至下一页，直至最后一页，并从渲染后的 `ld+json` 脚本中提取数据。")
