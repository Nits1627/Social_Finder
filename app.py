# === app.py ===
import streamlit as st
import pandas as pd
import requests
import gspread
from google.oauth2.service_account import Credentials
import asyncio
from playwright.async_api import async_playwright
import google.generativeai as genai
import io
from datetime import datetime
import matplotlib.pyplot as plt
import os

# === CONFIG ===
CSE_API_KEY = os.environ["CSE_API_KEY"]
CSE_CX = os.environ["CSE_CX"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
LOGO_PATH = "logo.png"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# === Load Google Credentials from JSON file ===
@st.cache_resource
def get_gsheet_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("fresh-gravity-462706-n2-c53b22d702f7.json", scopes=scopes)
    return gspread.authorize(creds)

# === Google Search Utilities ===
def search_google(query):
    url = f"https://www.googleapis.com/customsearch/v1"
    params = {"key": CSE_API_KEY, "cx": CSE_CX, "q": query}
    res = requests.get(url, params=params)
    return res.json().get("items", [])

def extract_link(results, keyword):
    for item in results:
        link = item.get("link", "")
        if keyword in link:
            return link
    return ""

def fetch_links_for_brand(brand):
    website = extract_link(search_google(f"{brand} official site"), ".")
    instagram = extract_link(search_google(f"{brand} site:instagram.com"), "instagram.com")
    linkedin = extract_link(search_google(f"{brand} site:linkedin.com/company"), "linkedin.com/company")
    return {"Brand Name": brand, "Website": website, "Instagram": instagram, "LinkedIn": linkedin}

# === Instagram Scraper and Analyzer ===
async def scrape_instagram(handle_or_url):
    handle = handle_or_url.strip().split("/")[-1].replace("@", "")
    post_data = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"https://www.instagram.com/{handle}/")
        await page.wait_for_selector("article", timeout=10000)
        posts = await page.query_selector_all('article a')
        for post in posts[:20]:
            href = await post.get_attribute("href")
            url = f"https://www.instagram.com{href}"
            caption = await page.evaluate("""el => {
                const fig = el.closest('article').querySelector('img[alt]');
                return fig ? fig.alt : '';
            }""", post)
            timestamp = datetime.now().strftime("%Y-%m-%d")
            post_data.append({"Post URL": url, "Caption": caption, "Date": timestamp})
        await browser.close()
    return post_data

def analyze_instagram_posts(post_list):
    captions = "\n\n".join([f"- {p['Caption']}" for p in post_list if p['Caption']])
    prompt = f"""
    You are a social media strategist. Analyze the following Instagram post captions to detect:
    1. Type of content (reels, promotions, memes, influencer, educational, etc.)
    2. Campaign patterns (themes or launches)
    3. Posting tone and frequency
    4. Brand image or positioning
    5. Recommend a content strategy

    Captions:
    {captions}
    """
    result = model.generate_content(prompt)
    return result.text

# === Streamlit UI ===
st.set_page_config(page_title="Brand Social Tool", layout="wide")
st.markdown("""
    <style>
        body { background-color: white; }
        .stButton>button { background-color: #FFD700; color: #fff; font-weight: bold; border: none; border-radius: 8px; padding: 0.5rem 1.2rem; }
        .stTextInput>div>input, .stTextArea>div>textarea { background-color: #fffbe6; border-radius: 5px; color: #FFD700; }
        .stDataFrame, .stTable { background-color: #ffffff; }
    </style>
""", unsafe_allow_html=True)
st.image(LOGO_PATH, width=150)

# === Radio-based navigation ===
page = st.radio("Choose a section", ["🔗 Brand Link Finder", "📸 Instagram Profile Analyzer"])

# === Section 1: Brand Link Finder ===
if page == "🔗 Brand Link Finder":
    st.title("🔗 Brand Social Link Finder")
    st.markdown("Fetch **Instagram**, **LinkedIn**, and **Website** links for brands.")

    input_method = st.radio("Choose input method:", ["Manual Entry", "Upload CSV"])
    brand_names = []
    if input_method == "Manual Entry":
        user_input = st.text_area("Enter brand names (one per line):")
        if user_input:
            brand_names = [b.strip() for b in user_input.split("\n") if b.strip()]
    else:
        uploaded_file = st.file_uploader("Upload CSV with a 'Brand Name' column:", type=["csv"])
        if uploaded_file:
            df_csv = pd.read_csv(uploaded_file)
            if "Brand Name" in df_csv.columns:
                brand_names = df_csv["Brand Name"].dropna().tolist()
            else:
                st.error("CSV must have a column named 'Brand Name'.")

    if st.button("🔍 Fetch Social Links") and brand_names:
        st.info("Fetching data... Please wait.")
        results = [fetch_links_for_brand(brand) for brand in brand_names]
        df_result = pd.DataFrame(results)
        st.success("✅ Done! Here's a preview:")
        st.dataframe(df_result)
        csv = df_result.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", data=csv, file_name="brand_links.csv", mime="text/csv")

# === Section 2: Instagram Profile Analyzer ===
elif page == "📸 Instagram Profile Analyzer":
    st.title("📸 Instagram Profile Analyzer")
    handle_input = st.text_input("Enter Instagram profile link or handle (public only):")

    if st.button("🔍 Analyze Instagram") and handle_input:
        with st.spinner("Scraping Instagram..."):
            try:
                post_list = asyncio.run(scrape_instagram(handle_input))
                if not post_list:
                    st.warning("No posts found or profile may be private.")
                else:
                    df_posts = pd.DataFrame(post_list)
                    st.dataframe(df_posts, use_container_width=True)
                    csv_buffer = io.StringIO()
                    df_posts.to_csv(csv_buffer, index=False)
                    st.download_button("Download CSV", data=csv_buffer.getvalue(), file_name="instagram_posts.csv", mime="text/csv")

                    st.markdown("### 📊 Posting Frequency")
                    df_posts['Date'] = pd.to_datetime(df_posts['Date'])
                    df_freq = df_posts.groupby(df_posts['Date'].dt.date).size()
                    fig, ax = plt.subplots()
                    df_freq.plot(kind='bar', ax=ax)
                    ax.set_xlabel("Date")
                    ax.set_ylabel("# of Posts")
                    st.pyplot(fig)

                    with st.spinner("Analyzing with Gemini..."):
                        insights = analyze_instagram_posts(post_list)
                        st.markdown("### 🔎 Campaign & Content Insights")
                        st.markdown(insights)
            except Exception as e:
                st.error(f"Error analyzing profile: {e}")
