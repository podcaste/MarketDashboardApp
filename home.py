import streamlit as st
from PIL import Image
from inject_font import inject_custom_font

# Set page config first
st.set_page_config(page_title="MarketDashboard by TTZ/Pod - Home", layout="wide")

# Inject custom font (Roboto or whatever you're using)
inject_custom_font()

# --- Add Logo at Top ---
logo = Image.open("static/dash_logo.png")
st.image(logo, width=250)  # You can tweak the width

# --- Title & Intro ---
st.title("📊 Welcome to MarketDashboard by TTZ/Pod")

st.markdown("""
This app gives you a powerful lens into market structure and ETF dynamics, including:

### 🚀 ETF Performance
Explore SPDR sector ETFs and their constituents. Compare short- and long-term performance, track key SMAs, heatmaps, and visualize YTD/1D movers.

### 📅 Seasonality
Analyze historical trading day patterns. View average returns by day, half-month, and month with confidence bands and statistical testing.

### 🔁 Sector Rotation Map
Visualize sector movement across momentum and breadth quadrants. Animated transitions reveal money flow trends over time.

### 🧠 OVERLAYORRRR 🔥
Your secret weapon. Find past time windows that closely resemble the current SPX pattern. Visualize how those setups evolved and overlay them for context.

### 🤝 ETF Similarity Detector
Enter any ticker to find:
- Most correlated SPY stocks and Sector ETFs
- Correlation fingerprints over time
- Rolling beta vs SPX
- Beta stability plots & animations
- Downloadable insights

---

Use the sidebar to navigate. Built for insights, speed, and sharing alpha with your crew.
""")
