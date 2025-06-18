# === app.py ===
import streamlit as st
import pandas as pd
import requests
import gspread
from google.oauth2.service_account import Credentials

# === CONFIG ===
CSE_API_KEY = st.secrets["CSE_API_KEY"]
CSE_CX = st.secrets["CSE_CX"]
SHEET_NAME = "Brand Social Profiles"
LOGO_PATH = "logo.png"  # Ensure this file is present in your directory

# === Load Google Credentials from JSON file ===
@st.cache_resource
def get_gsheet_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("fresh-gravity-462706-n2-c53b22d702f7.json", scopes=scopes)
    return gspread.authorize(creds)

def search_google(query):
    url = f"https://www.googleapis.com/customsearch/v1"
    params = {
        "key": CSE_API_KEY,
        "cx": CSE_CX,
        "q": query
    }
    res = requests.get(url, params=params)
    return res.json().get("items", [])

def extract_link(results, keyword):
    for item in results:
        link = item.get("link", "")
        if keyword in link:
            return link
    return ""

def fetch_links_for_brand(brand):
    website_results = search_google(f"{brand} official site")
    website = extract_link(website_results, ".")

    insta_results = search_google(f"{brand} site:instagram.com")
    instagram = extract_link(insta_results, "instagram.com")

    linkedin_results = search_google(f"{brand} site:linkedin.com/company")
    linkedin = extract_link(linkedin_results, "linkedin.com/company")

    return {
        "Brand Name": brand,
        "Website": website,
        "Instagram": instagram,
        "LinkedIn": linkedin
    }

def update_sheet(df):
    client = get_gsheet_client()
    try:
        sheet = client.open(SHEET_NAME).sheet1
    except:
        sheet = client.create(SHEET_NAME).sheet1
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())
    return sheet.url

# === Streamlit UI ===
st.set_page_config(page_title="Brand Social Link Finder", layout="wide")

# --- Custom Styles ---
st.markdown("""
    <style>
        body {
            background-color: #ffffff;
        }
        .main {
            color: #FFD700;
            font-family: 'Segoe UI', sans-serif;
        }
        .stButton>button {
            background-color: #FFD700;
            color: #ffffff;
            font-weight: bold;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1.2rem;
        }
        .stTextInput>div>input, .stTextArea>div>textarea {
            background-color: #fffbe6;
            border-radius: 5px;
            color: #FFD700;
        }
        .stDataFrame, .stTable {
            background-color: #ffffff;
        }
    </style>
""", unsafe_allow_html=True)

# --- Logo and Title ---
st.image(LOGO_PATH, width=150)
st.title("🔗 Brand Social Link Finder")
st.markdown("""Easily fetch **Instagram**, **LinkedIn**, and **Website** links for your target brands and export to a **Google Sheet**.""")

# --- Input Section ---
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

# --- Action Button ---
if st.button("🔍 Fetch Social Links") and brand_names:
    st.info("Fetching data... Please wait.")
    results = []
    for brand in brand_names:
        data = fetch_links_for_brand(brand)
        results.append(data)
    df_result = pd.DataFrame(results)
    st.success("✅ Done! Here's a preview:")
    st.dataframe(df_result)

    sheet_url = update_sheet(df_result)
    st.markdown(f"📄 [View the public Google Sheet here]({sheet_url})")
