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

# --- 核心抓取逻辑 (适用于服务器环境) ---
def scrape_homedepot_with_selenium(query):
    """
    使用Selenium驱动浏览器来抓取Home Depot的搜索结果页面。
    这个版本专为在Streamlit云服务器等Linux环境部署而优化。

    Args:
        query (str): 你想要搜索的关键词。

    Returns:
        list: 一个包含商品信息的字典列表，或在出错时返回空列表。
    """
    page_results = []
    search_url = f"https://www.homedepot.com/s/{query.replace(' ', '%20')}"
    
    st.write("---")
    st.write("⚙️ **Selenium 自动化流程启动...**")
    
    driver = None
    try:
        # --- 为服务器环境设置Chrome选项 ---
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # 必须使用headless模式
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        # 为每个会话创建唯一的临时用户数据目录，解决 "user data directory is already in use" 错误
        options.add_argument(f"--user-data-dir=/tmp/selenium_user_data_{int(time.time())}")
        # 伪装成一个真实的浏览器
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        st.write("1. **在服务器环境中初始化 Chrome 浏览器驱动...**")
        
        # 在Streamlit Cloud上，Selenium会自动查找通过packages.txt安装的浏览器驱动
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        
        st.write(f"2. **浏览器正在访问目标网址:** {search_url}")
        driver.get(search_url)

        st.write("3. **等待页面动态数据 (`__NEXT_DATA__`) 加载完成...** (最长20秒)")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "__NEXT_DATA__"))
        )
        st.success("   > 关键数据已加载！")

        st.write("4. **获取渲染后的完整页面 HTML...**")
        html_source = driver.page_source
        
        st.write("5. **使用 BeautifulSoup 解析 HTML...**")
        soup = BeautifulSoup(html_source, 'html.parser')
        
        script_tag = soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'})
        
        if not script_tag:
            st.error("严重错误：即使使用Selenium也未能找到 '__NEXT_DATA__'。")
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
            st.warning("在'__NEXT_DATA__'中未找到产品列表。")
            return []

        st.write(f"   > **成功解析到 {len(products_list)} 个产品条目!**")
        for product in products_list:
            item_data = product.get('item', product)
            name = item_data.get('productLabel', item_data.get('name', 'N/A'))
            price_info = item_data.get('pricing', {})
            price = price_info.get('specialPrice', {}).get('price') or price_info.get('originalPrice', {}).get('price')

            link = item_data.get('url', '#')
            if link.startswith('/'):
                link = 'https://www.homedepot.com' + link

            image_url = None
            images_list = item_data.get('media', {}).get('images', [])
            if images_list and isinstance(images_list, list) and len(images_list) > 0:
                image_url = images_list[0].get('url')

            if name != 'N/A':
                page_results.append({
                    'name': name,
                    'price': price,
                    'link': link,
                    'image_url': image_url if image_url else 'https://placehold.co/100x100/e2e8f0/333333?text=No+Image'
                })
        
        return page_results

    except TimeoutException:
        st.error("页面加载超时：在20秒内未能找到'__NEXT_DATA__'。可能是网络问题或网站加载缓慢。")
        return []
    except WebDriverException as e:
        st.error(f"WebDriver 错误: {e}")
        st.error("无法在服务器上启动Chrome。请确认 'packages.txt' 文件已正确配置并包含 'google-chrome-stable'。")
        return []
    except Exception as e:
        st.error(f"抓取过程中发生未知错误: {e}")
        import traceback
        st.text(traceback.format_exc())
        return []
    finally:
        st.write("6. **关闭浏览器驱动，释放资源。**")
        st.write("---")
        if driver:
            driver.quit()

# --- Streamlit 应用界面 ---
st.set_page_config(page_title="Home Depot Selenium 爬虫", layout="wide")

st.title("🛒 Home Depot 商品抓取工具 (Selenium版)")
st.markdown("""
这个版本使用 **Selenium** 来驱动一个真实的浏览器进行数据抓取，可以有效绕过网站的常规反爬虫机制，获取由JavaScript动态加载的完整数据。
""")

search_query = st.text_input("请输入搜索关键词 (例如: 'milwaukee', 'dewalt'):", "milwaukee")

if st.button("🚀 使用 Selenium 开始搜索"):
    if not search_query:
        st.warning("请输入搜索关键词！")
    else:
        with st.spinner(f"正在启动Selenium并搜索 '{search_query}'... (在服务器上首次启动可能需要1-2分钟)"):
            scraped_data = scrape_homedepot_with_selenium(search_query)

        if scraped_data:
            st.success(f"🎉 **抓取完成！共获得 {len(scraped_data)} 条商品信息！**")
            
            df = pd.DataFrame(scraped_data).drop_duplicates(subset=['name'])
            
            display_df_data = []
            for index, row in df.iterrows():
                display_df_data.append({
                    "图片": row['image_url'],
                    "商品名称": row['name'],
                    "价格": f"${row['price']}" if row.get('price') else 'N/A',
                    "链接": row['link']
                })
            
            display_df = pd.DataFrame(display_df_data)

            st.dataframe(
                display_df,
                column_config={
                    "图片": st.column_config.ImageColumn("图片预览", width="small"),
                    "商品名称": st.column_config.TextColumn("商品名称", width="large"),
                    "价格": st.column_config.TextColumn("价格", width="small"),
                    "链接": st.column_config.LinkColumn("详情链接", display_text="🔗 查看商品", width="small")
                },
                hide_index=True,
                use_container_width=True
            )

        else:
            st.error("未能抓取到任何商品信息。请检查上面的日志输出获取详细错误信息。")
        
st.markdown("---")
st.markdown("技术说明：此应用专为服务器部署优化。它使用 `Selenium` 驱动在后台运行的 `Chrome` 浏览器获取页面源码，再由 `BeautifulSoup` 和 `json` 解析数据。")
