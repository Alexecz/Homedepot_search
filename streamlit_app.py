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
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- 核心抓取逻辑 (最终版) ---
def scrape_homedepot_page(query, page_num=1):
    """
    使用Selenium驱动浏览器，从单个搜索结果页面抓取完整的商品数据。
    这个版本专为在Streamlit云服务器等Linux环境部署而优化。

    Args:
        query (str): 搜索关键词。
        page_num (int): 要抓取的页码。

    Returns:
        list: 包含该页面商品信息的字典列表，或在出错时返回None。
    """
    search_url = f"https://www.homedepot.com/s/{query.replace(' ', '%20')}?page={page_num}"
    
    st.write("---")
    st.write(f"⚙️ **正在处理第 {page_num} 页...**")
    
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-data-dir=/tmp/selenium_user_data_{int(time.time())}_{page_num}")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        
        st.write(f"  > 浏览器正在访问: {search_url}")
        driver.get(search_url)

        # 等待 __NEXT_DATA__ 脚本标签加载完成
        st.write("  > 等待页面动态数据加载...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "__NEXT_DATA__"))
        )
        st.success("   > 关键数据已加载！")

        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        
        script_tag = soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'})
        
        if not script_tag:
            st.error("错误：未能找到 '__NEXT_DATA__' 数据块。")
            return []

        json_data = json.loads(script_tag.string)
        
        products_list = []
        page_props = json_data.get('props', {}).get('pageProps', {})
        if page_props.get('search', {}).get('contentLayouts'):
            content_layouts = page_props['search']['contentLayouts']
            for layout in content_layouts:
                if isinstance(layout, dict) and layout.get('type') == 'PRODUCT_POD' and layout.get('products'):
                    products_list.extend(layout.get('products', []))
        
        if not products_list:
            st.warning(f"第 {page_num} 页未解析到产品，可能已是最后一页。")
            return []

        page_results = []
        for product in products_list:
            item_data = product.get('item', product)
            name = item_data.get('productLabel', 'N/A')
            price_info = item_data.get('pricing', {})
            price = price_info.get('specialPrice', {}).get('price') or price_info.get('originalPrice', {}).get('price')
            link = 'https://www.homedepot.com' + item_data.get('url', '#')
            image_url = item_data.get('media', {}).get('images', [{}])[0].get('url')

            if name != 'N/A':
                page_results.append({
                    'name': name, 'price': price, 'link': link, 
                    'image_url': image_url or 'https://placehold.co/100x100/e2e8f0/333333?text=No+Image'
                })
        
        st.write(f"  > **成功解析到 {len(page_results)} 个产品!**")
        return page_results

    except TimeoutException:
        st.error(f"页面加载超时（第 {page_num} 页）。可能是被反爬虫机制拦截。")
        return None
    except Exception as e:
        st.error(f"抓取过程中发生未知错误: {e}")
        return None
    finally:
        if driver:
            driver.quit()

# --- Streamlit 应用界面 ---
st.set_page_config(page_title="Home Depot Selenium 爬虫", layout="wide")
st.title("🛒 Home Depot 商品抓取工具 (最终版)")

search_query = st.text_input("请输入搜索关键词:", "milwaukee")
num_pages = st.number_input("要抓取的页数:", min_value=1, max_value=10, value=2, help="建议不要一次性抓取太多页，以避免被封禁。")

if st.button("🚀 使用 Selenium 开始搜索"):
    if not search_query:
        st.warning("请输入搜索关键词！")
    else:
        all_scraped_data = []
        with st.spinner(f"正在启动Selenium并搜索 '{search_query}'..."):
            for i in range(1, num_pages + 1):
                page_data = scrape_homedepot_page(search_query, i)
                if page_data is None:
                    st.error("抓取过程中断。")
                    break
                if not page_data:
                    st.info("已到达最后一页，抓取结束。")
                    break
                all_scraped_data.extend(page_data)
                if i < num_pages:
                    time.sleep(2) # 翻页之间礼貌性等待

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
st.markdown("技术说明：此应用使用 `Selenium` 驱动在后台运行的 `Chrome` 浏览器获取页面源码，再由 `BeautifulSoup` 和 `json` 解析数据。")
