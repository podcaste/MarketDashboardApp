import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from utils.data_utils import download_batched  # Corrected import
from inject_font import inject_custom_font, inject_sidebar_logo

st.set_page_config(page_title="ETF Similarity Detector", layout="wide")
inject_custom_font()
inject_sidebar_logo()

st.title("🔎 ETF Similarity Detector")
st.caption("This tool compares the selected ETF to SPY constituents and sector ETFs, based on rolling correlation.")

with st.form("ticker_form"):
    st.markdown("### 🔧 Comparison Configuration")
    target_ticker = st.text_input("Enter Ticker to Compare:", value="XLK", help="Enter a valid stock or ETF ticker symbol (e.g., XLK, AAPL, SPY, etc.)").upper()
    col1, col2 = st.columns(2)
    with col1:
        correlation_window = st.selectbox("Correlation Window (days)", [10, 20, 30, 60, 90, 120], index=2, help="Size of the rolling window for computing correlation")
    with col2:
        lookback_days = st.selectbox("Lookback Period (days)", [60, 90, 120, 180, 250, 365, 500], index=4, help="Total number of calendar days to look back for analysis")
    submitted = st.form_submit_button("Compare")

if not target_ticker or target_ticker.upper() in ['TICKER', '-', 'NONE', ''] or not target_ticker.isalnum():
    st.warning("⚠️ Please enter a valid ticker symbol to continue.")
    st.stop()

try:
    test = yf.Ticker(target_ticker).info
    if not test or test.get("shortName") is None:
        st.warning(f"⚠️ {target_ticker} appears invalid or delisted. Please check your ticker symbol.")
        st.stop()
except Exception:
    st.warning(f"⚠️ {target_ticker} could not be validated. Please try a different ticker.")
    st.stop()

spy_holdings_url = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx"

@st.cache_data
def get_spy_constituents():
    df = pd.read_excel(spy_holdings_url, skiprows=3)
    tickers = df.iloc[:, 1].dropna().astype(str)
    tickers = [t.replace('/', '-').strip().upper() for t in tickers if isinstance(t, str) and t.isalnum() and t.upper() not in ['TICKER', '-', 'NONE', ''] and len(t) <= 5]
    return sorted(list(set(tickers)))

sector_etfs = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY", "XBI", "XRT", "KRE", "ITB", "IBB"]

if submitted:
    end_date = datetime.today()
    start_date = end_date - timedelta(days=lookback_days + correlation_window)
    universe = get_spy_constituents() + sector_etfs
    universe = list(set(universe) - {target_ticker})
    tickers_to_fetch = [target_ticker] + universe + ["^GSPC"]

    price_data_raw, _ = download_batched(tickers_to_fetch, start=start_date, end=end_date)
    if isinstance(price_data_raw.columns, pd.MultiIndex):
        price_data = price_data_raw.xs("Close", axis=1, level=1)
    else:
        price_data = price_data_raw
    price_data = price_data.dropna(axis=1, how='any')

    returns = price_data.pct_change().dropna()
    corr_matrix = returns.corr()

    st.markdown("---")
    st.subheader("📌 Correlation Heatmap")
    st.caption("This heatmap highlights which tickers have the strongest, weakest, and lowest correlation to the selected target.")

    if not corr_matrix.empty:
        corr_target = corr_matrix[target_ticker].drop(target_ticker)

        top_positive = corr_target.sort_values(ascending=False).head(10)
        top_negative = corr_target.sort_values(ascending=True).head(10)
        low_correlation = corr_target[(corr_target > -0.2) & (corr_target < 0.2)].sort_values(ascending=False).head(10)

        top_positive.name = "Correlation"
        top_positive.index.name = "Ticker"
        top_positive_df = top_positive.reset_index()
        top_positive_df["Category"] = "Positive Correlation"

        top_negative.name = "Correlation"
        top_negative.index.name = "Ticker"
        top_negative_df = top_negative.reset_index()
        top_negative_df["Category"] = "Negative Correlation"

        low_correlation.name = "Correlation"
        low_correlation.index.name = "Ticker"
        low_correlation_df = low_correlation.reset_index()
        low_correlation_df["Category"] = "Low Correlation"

        combined_df = pd.concat([top_positive_df, top_negative_df, low_correlation_df])
        combined_df = combined_df.drop_duplicates(subset="Ticker")

        tickers_ordered = combined_df.sort_values(by="Correlation", ascending=False)["Ticker"]

        fig_heatmap = px.imshow(
            corr_matrix.loc[tickers_ordered, tickers_ordered],
            labels=dict(color="Correlation"),
            x=tickers_ordered,
            y=tickers_ordered,
            color_continuous_scale="RdBu",
            zmin=-1,
            zmax=1,
            title=f"Top Correlation Overview with {target_ticker}"
        )
        fig_heatmap.update_layout(width=800, height=800)
        st.plotly_chart(fig_heatmap, use_container_width=True)

        st.download_button("📥 Download Correlation Matrix (CSV)", data=corr_matrix.to_csv().encode("utf-8"), file_name=f"{target_ticker}_correlation_matrix.csv", mime="text/csv")
