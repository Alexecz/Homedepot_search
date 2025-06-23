import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import json

# --- 核心抓取逻辑 (仅使用 Requests) ---
def scrape_homedepot_with_requests(query, max_pages=1):
    """
    尝试仅使用 requests 和 BeautifulSoup 来抓取 Home Depot。
    这个方法旨在验证网站是否会向非浏览器环境返回数据。

    Args:
        query (str): 搜索关键词。
        max_pages (int): 要抓取的最大页数。

    Returns:
        list: 包含所有商品信息的字典列表。
    """
    all_results = []
    
    # 使用会话来保持 cookies
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    session.headers.update(headers)

    for page_num in range(1, max_pages + 1):
        # 构造带有页码的搜索URL
        search_url = f"https://www.homedepot.com/s/{query.replace(' ', '%20')}?page={page_num}"
        
        try:
            st.write("---")
            st.write(f"**正在处理第 {page_num} 页...**")
            st.write(f"  > 请求URL: {search_url}")
            
            response = session.get(search_url, timeout=20)
            response.raise_for_status()
            st.success(f"  > 请求成功，状态码: {response.status_code}")

            soup = BeautifulSoup(response.text, 'html.parser')

            # --- 关键验证步骤 ---
            # 1. 尝试寻找我们之前在Selenium中找到的ld+json数据块
            st.write("  > **策略1: 寻找 `ld+json` 数据脚本...**")
            script_tag = soup.find('script', {'id': 'thd-helmet__script--browseSearchStructuredData', 'type': 'application/ld+json'})
            
            if script_tag:
                st.success("   > 找到了 `ld+json` 数据脚本！正在解析...")
                json_data = json.loads(script_tag.string)
                products_list = json_data[0].get('mainEntity', {}).get('offers', {}).get('itemOffered', [])
                
                if products_list:
                    st.write(f"  > **从 `ld+json` 成功解析到 {len(products_list)} 个产品!**")
                    for product in products_list:
                        name = product.get('name', 'N/A')
                        offers = product.get('offers', {})
                        price = offers.get('price', 'N/A') if isinstance(offers, dict) else 'N/A'
                        link = offers.get('url', '#') if isinstance(offers, dict) else '#'
                        image_url = product.get('image')

                        if name != 'N/A':
                            all_results.append({'name': name, 'price': price, 'link': link, 'image_url': image_url})
                else:
                    st.warning("  > `ld+json` 脚本中没有商品数据。")
            else:
                st.error("  > **未找到 `ld+json` 数据脚本。** 这意味着服务器没有向我们发送包含数据的HTML。")
                st.info("这是预期的行为，证实了网站的反爬虫机制。下面是获取到的部分HTML源码：")
                st.code(soup.prettify()[:2000], language='html')
                # 既然最可靠的数据源没有，就没有必要继续尝试解析其他标签了
                break
            
            # 如果是多页抓取，则需要找到下一页的链接
            if page_num < max_pages:
                st.write("  > 正在寻找下一页的链接...")
                # 从分页器中寻找下一页的链接
                pagination = soup.find('nav', {'aria-label': 'Pagination Navigation'})
                if pagination:
                    next_page_element = pagination.find('a', {'aria-label': 'Skip to Next Page'})
                    if next_page_element and next_page_element.has_attr('href'):
                        next_page_url = "https://www.homedepot.com" + next_page_element['href']
                        st.info(f"  > 找到下一页链接: {next_page_url}")
                        # 在循环的下一次迭代中，我们将使用这个新URL
                        search_url = next_page_url 
                        time.sleep(1) # 礼貌性延迟
                    else:
                        st.success("✅ 未找到 'Next' 按钮，已到达最后一页，抓取结束。")
                        break
                else:
                    st.warning("  > 未找到分页器，无法进行翻页。")
                    break
        
        except requests.exceptions.RequestException as e:
            st.error(f"请求时发生网络错误: {e}")
            break
        except Exception as e:
            st.error(f"处理第 {page_num} 页时发生意外错误: {e}")
            break
            
    return all_results

# --- Streamlit 应用界面 ---
st.set_page_config(page_title="Home Depot Requests 爬虫", layout="wide")
st.title("🛒 Home Depot 商品抓取工具 (纯Requests版)")

search_query = st.text_input("请输入搜索关键词:", "milwaukee")
num_pages = st.number_input("最多抓取的页数:", min_value=1, max_value=5, value=1)

if st.button("🚀 开始搜索"):
    if not search_query:
        st.warning("请输入搜索关键词！")
    else:
        with st.spinner(f"正在使用 Requests 直接请求页面..."):
            scraped_data = scrape_homedepot_with_requests(search_query, num_pages)

        if scraped_data:
            st.success(f"🎉 **抓取完成！共获得 {len(scraped_data)} 条商品信息！**")
            df = pd.DataFrame(scraped_data).drop_duplicates(subset=['name'])
            display_df_data = [{
                "图片": row['image_url'] or 'https://placehold.co/100x100/e2e8f0/333333?text=No+Image',
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
            st.error("未能通过直接请求抓取到任何商品信息。")
            st.warning("这强烈表明网站内容是动态加载的，必须使用 **Selenium** 模拟真实浏览器才能成功。")

st.markdown("---")
st.markdown("技术说明：此应用使用 `requests` + `BeautifulSoup` 尝试直接解析HTML。")
