import streamlit as st
import pandas as pd
import time
import json
from bs4 import BeautifulSoup
import random

# --- Selenium 和 Stealth 相关导入 ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium_stealth import stealth # 导入stealth

# --- 核心抓取逻辑 (高级反侦测版) ---
def scrape_homedepot_with_selenium(query):
    """
    使用Selenium Stealth驱动浏览器，模拟真人用户行为，进行全自动翻页抓取。

    Args:
        query (str): 搜索关键词。

    Returns:
        list: 包含所有页面商品信息的字典列表。
    """
    all_results = []
    
    status_placeholder = st.empty()
    
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-data-dir=/tmp/selenium_user_data_{int(time.time())}")
        
        # 隐藏自动化特征
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        
        # --- 应用 Selenium Stealth ---
        status_placeholder.info(f"🚀 应用高级反侦测模式 (Stealth)...")
        stealth(driver,
              languages=["en-US", "en"],
              vendor="Google Inc.",
              platform="Win32",
              webgl_vendor="Intel Inc.",
              renderer="Intel Iris OpenGL Engine",
              fix_hairline=True,
              )
        # ---------------------------
        
        search_url = f"https://www.homedepot.com/s/{query.replace(' ', '%20')}"
        status_placeholder.info(f"🕵️ 浏览器已伪装，正在访问初始页面...")
        driver.get(search_url)

        current_page = 1
        total_pages_str = "?"
        
        while True:
            status_text = f"⏳ 正在处理第 {current_page} / {total_pages_str} 页 | 已抓取 {len(all_results)} 个商品..."
            status_placeholder.info(status_text)
            
            wait = WebDriverWait(driver, 30)
            
            try:
                wait.until(EC.presence_of_element_located((By.ID, "thd-helmet__script--browseSearchStructuredData")))
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                if current_page == 1:
                    try:
                        page_buttons = soup.select('nav[aria-label="Pagination Navigation"] a[aria-label*="Go to Page"]')
                        if page_buttons:
                            total_pages_str = page_buttons[-1].text.strip()
                    except Exception:
                        total_pages_str = "?" 

                script_tag = soup.find('script', {'id': 'thd-helmet__script--browseSearchStructuredData', 'type': 'application/ld+json'})
                
                if not script_tag: break

                json_data = json.loads(script_tag.string)
                products_list = json_data[0].get('mainEntity', {}).get('offers', {}).get('itemOffered', [])
                
                if not products_list: break
                
                for product in products_list:
                    item_data = product.get('item', product)
                    name = item_data.get('productLabel', item_data.get('name', 'N/A'))
                    
                    # 提取详细价格
                    pricing_info = item_data.get('pricing', item_data.get('offers', {}))
                    original_price = None
                    current_price = None

                    if isinstance(pricing_info, dict):
                        # __NEXT_DATA__ 结构
                        if 'originalPrice' in pricing_info and isinstance(pricing_info['originalPrice'], dict):
                            original_price = pricing_info['originalPrice'].get('price')
                        if 'specialPrice' in pricing_info and isinstance(pricing_info['specialPrice'], dict):
                             current_price = pricing_info['specialPrice'].get('price')
                        
                        # 如果没有special_price，则current_price就是original_price
                        if not current_price:
                            current_price = original_price if original_price else pricing_info.get('price')
                        
                        # 如果有special_price，但original_price和它一样，则不算有折扣
                        if original_price == current_price:
                            original_price = None
                            
                    # ld+json 结构 (备用)
                    else:
                        current_price = pricing_info.get('price')


                    link = item_data.get('url', '#')
                    if link.startswith('/'):
                        link = 'https://www.homedepot.com' + link

                    image_url = item_data.get('image')
                    if not image_url and 'media' in item_data:
                        images = item_data.get('media', {}).get('images', [])
                        if images:
                            image_url = images[0].get('url')

                    if name != 'N/A':
                        all_results.append({
                            'name': name, 
                            'current_price': current_price,
                            'original_price': original_price,
                            'link': link, 
                            'image_url': image_url or 'https://placehold.co/100x100/e2e8f0/333333?text=No+Image'
                        })

            except TimeoutException:
                status_placeholder.error(f"页面加载超时（第 {current_page} 页）。很可能被反爬虫机制拦截。")
                st.image(driver.get_screenshot_as_png(), caption="超时快照")
                break 

            try:
                next_page_element = driver.find_element(By.CSS_SELECTOR, 'a[aria-label="Skip to Next Page"]')
                next_page_url = next_page_element.get_attribute('href')
                
                driver.get(next_page_url)
                current_page += 1
                time.sleep(random.uniform(1.5, 3.5)) # 使用随机延迟

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

if st.button("🚀 开始搜索 (抓取全部分页)"):
    if not search_query:
        st.warning("请输入搜索关键词！")
    else:
        all_scraped_data = scrape_homedepot_with_selenium(search_query)

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
                "原价": f"${row['original_price']}" if pd.notna(row['original_price']) else " ",
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
