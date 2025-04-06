import streamlit as st

st.set_page_config(page_title="Market Dashboard", layout="wide")
st.title("📊 Welcome to MarketDashboard")

st.markdown("""
This app includes:
- 📈 **ETF Performance**: Explore SPDR ETF constituents and compare short-term and long-term performance.
- 📅 **Seasonality**: Analyze seasonal patterns and statistical significance of returns across the year.

Use the sidebar to navigate.
""")