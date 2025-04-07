import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
from utils.data_utils import download_batched

st.set_page_config(page_title="ETF Similarity Detector", layout="wide")
st.title("🔎 ETF Similarity Detector")

with st.form("ticker_form"):
    target_ticker = st.text_input("Enter Ticker to Compare:", value="XLK").upper()
    submitted = st.form_submit_button("Compare")

if not target_ticker or target_ticker.upper() in ['TICKER', '-', 'NONE', ''] or not target_ticker.isalnum():
    st.warning("Please enter a valid ticker symbol to continue.")
    st.stop()

try:
    test = yf.Ticker(target_ticker).info
    if not test or test.get("shortName") is None:
        st.warning(f"{target_ticker} appears invalid or delisted. Please check your ticker symbol.")
        st.stop()
except Exception:
    st.warning(f"{target_ticker} could not be validated. Please try a different ticker.")
    st.stop()

correlation_window = st.selectbox("Correlation Window (days)", [10, 20, 30, 60, 90, 120], index=2)
lookback_days = st.selectbox("Lookback Period (days)", [60, 90, 120, 180, 250, 365, 500], index=4)

spy_holdings_url = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx"

@st.cache_data
def get_spy_constituents():
    df = pd.read_excel(spy_holdings_url, skiprows=3)
    tickers = df.iloc[:, 1].dropna().astype(str)
    tickers = [t.replace('/', '-').strip().upper() for t in tickers if isinstance(t, str) and t.isalnum() and t.upper() not in ['TICKER', '-', 'NONE'] and len(t) <= 5]
    tickers = [t for t in tickers if t != 'CTAS']  # Hard-code exclusion
    return sorted(list(set(tickers)))

sector_etfs = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY", "XBI", "XRT", "KRE", "ITB", "IBB"]

@st.cache_data
def download_price_data(tickers, start, end):
    price_data, failed = download_batched(
        tickers,
        start=start,
        end=end,
        auto_adjust=True
    )
    if isinstance(price_data.columns, pd.MultiIndex):
        close_prices = price_data.xs('Close', axis=1, level=1)
    else:
        close_prices = price_data
    return close_prices.dropna(axis=1, how='all')

# You can now continue with the rest of your logic from `if submitted:` onward.
