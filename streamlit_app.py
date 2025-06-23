import streamlit as st
import pandas as pd
import time
import json
from bs4 import BeautifulSoup
from io import BytesIO

# --- Selenium 相关导入 ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- 核心诊断逻辑 ---
def get_page_diagnostics(query):
    """
    使用Selenium驱动浏览器，获取页面截图和完整的HTML源码用于分析。

    Args:
        query (str): 搜索关键词。

    Returns:
        tuple: (screenshot_bytes, page_source_html) 或 (None, None)
    """
    search_url = f"https://www.homedepot.com/s/{query.replace(' ', '%20')}"
    
    st.write("---")
    st.write("⚙️ **页面诊断工具启动...**")
    
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
        
        st.write("1. **初始化 Chrome 浏览器驱动...**")
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        
        st.write(f"2. **浏览器正在访问目标网址:** {search_url}")
        driver.get(search_url)

        # 固定等待15秒，让所有动态内容充分加载
        st.write("3. **等待页面所有动态脚本加载... (固定等待15秒)**")
        time.sleep(15)
        st.success("   > 页面加载时间结束！")

        st.write("4. **正在截取屏幕快照并复制HTML源码...**")
        screenshot = driver.get_screenshot_as_png()
        html_source = driver.page_source
        
        return screenshot, html_source

    except WebDriverException as e:
        st.error(f"WebDriver 错误: {e}")
        return None, None
    except Exception as e:
        st.error(f"抓取过程中发生未知错误: {e}")
        import traceback
        st.text(traceback.format_exc())
        return None, None
    finally:
        st.write("5. **关闭浏览器驱动，释放资源。**")
        st.write("---")
        if driver:
            driver.quit()

# --- Streamlit 应用界面 ---
st.set_page_config(page_title="Home Depot 页面诊断工具", layout="wide")
st.title("🕵️ Home Depot 页面诊断工具")
st.markdown("""
这个工具的目的是获取 **Selenium 浏览器看到的最终页面**，以便我们进行分析。
""")

search_query = st.text_input("请输入要诊断的搜索关键词:", "milwaukee")

if st.button("🚀 开始诊断页面"):
    if not search_query:
        st.warning("请输入搜索关键词！")
    else:
        with st.spinner(f"正在启动Selenium并加载页面... (请耐心等待，约需30-40秒)"):
            screenshot, html_source = get_page_diagnostics(search_query)

        if screenshot and html_source:
            st.success("🎉 **诊断完成！**")
            
            st.subheader("1. 浏览器快照")
            st.write("这是Selenium在最后时刻看到的浏览器画面。")
            st.image(screenshot, caption="浏览器快照")

            st.subheader("2. 完整HTML源代码")
            st.write("这是浏览器完全渲染后的页面源码。您可以在下方的文本框中使用 `Ctrl+F` 或 `Cmd+F` 来搜索关键词，例如 `__NEXT_DATA__` 或商品名称，来帮助我们找到数据的位置。")
            st.code(html_source, language='html', line_numbers=True)
            
        else:
            st.error("诊断失败。请查看上方的错误日志。")
        
st.markdown("---")
st.markdown("技术说明：此应用使用 `Selenium` 驱动在后台运行的 `Chrome` 浏览器，然后捕获其最终状态。")
