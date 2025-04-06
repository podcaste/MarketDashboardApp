import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from utils.data_utils import fetch_holdings, fetch_returns, calculate_sma_percentages, download_batched

st.set_page_config(page_title="ETF Performance", layout="wide")
st.title("📈 ETF Performance Dashboard")

# --- Sidebar advanced options ---
st.sidebar.markdown("⚙️ **Advanced Settings**")
retry_limit = st.sidebar.slider("Max Retry Attempts", 0, 5, 3)
sleep_delay = st.sidebar.slider("Sleep Backoff Base (seconds)", 1, 10, 2)

# --- User input ---
performance_ticker = st.text_input("Enter SPDR ETF Ticker (e.g., XLK, XLF, SPY):", "XBI").upper()
top_n = st.slider("Number of top performers to display:", 3, 20, 5)
show_relative = st.toggle("Show relative performance chart (vs ETF)", True)

# --- ETF Processing ---
if performance_ticker:
    try:
        tickers = fetch_holdings(performance_ticker)
        if tickers:
            st.success(f"Loaded {len(tickers)} tickers from {performance_ticker}")
            
            # --- Returns table and line chart ---
            returns_df, price_data = fetch_returns(tickers, performance_ticker)
            st.dataframe(returns_df, use_container_width=True)

            leaders = returns_df[returns_df['Ticker'] != performance_ticker].sort_values(by='1D', ascending=False).head(top_n)['Ticker']
            rel_prices = price_data[leaders.tolist() + [performance_ticker]]

            st.subheader(f"Top {top_n} Performers {'(Relative)' if show_relative else ''}")
            fig, ax = plt.subplots(figsize=(12, 6))
            if show_relative:
                normed = rel_prices / rel_prices.iloc[0]
                for col in normed.columns:
                    ax.plot(normed.index, normed[col], label=col)
                ax.set_title("Normalized Price (Base = 1.0)")
            else:
                for col in rel_prices.columns:
                    ax.plot(rel_prices.index, rel_prices[col], label=col)
                ax.set_title("Absolute Price Chart")
            ax.legend()
            st.pyplot(fig)

            # --- SMA chart ---
            st.subheader("% of Constituents Above Key SMAs")
            sma_stats = calculate_sma_percentages(price_data, start_date="2024-09-11")
            fig2, ax2 = plt.subplots(figsize=(12, 6))
            sma_stats.plot(ax=ax2)
            ax2.axhline(80, color='red', linestyle='--', alpha=0.5)
            ax2.axhline(20, color='green', linestyle='--', alpha=0.5)
            ax2.set_title("% of Constituents Above 20D / 50D / 200D SMAs")
            ax2.set_ylabel("Percentage")
            st.pyplot(fig2)

            # --- Waterfall plots ---
            st.subheader("📊 Waterfall Plots: YTD and Last Day")
            today = pd.Timestamp.today()
            start_ytd = pd.Timestamp(today.year, 1, 1)

            ytd_data, ytd_failed = download_batched(
                tickers,
                start=start_ytd,
                end=today + pd.Timedelta(days=1),
                max_retries=retry_limit,
                sleep_base=sleep_delay
            )

            ytd_perf = {}
            if isinstance(ytd_data.columns, pd.MultiIndex):
                for ticker in tickers:
                    try:
                        prices = ytd_data[ticker]['Close'].dropna()
                        if len(prices) >= 2:
                            perf = (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0] * 100
                            ytd_perf[ticker] = perf
                    except:
                        continue

            last_day_data, last_day_failed = download_batched(
                tickers,
                period="5d",
                max_retries=retry_limit,
                sleep_base=sleep_delay
            )

            last_day_perf = {}
            if isinstance(last_day_data.columns, pd.MultiIndex):
                for ticker in tickers:
                    try:
                        prices = last_day_data[ticker]['Close'].dropna()
                        if len(prices) >= 2:
                            perf = (prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2] * 100
                            last_day_perf[ticker] = perf
                    except:
                        continue

            def plot_waterfall(perf_dict, title):
                sorted_data = sorted(perf_dict.items(), key=lambda x: x[1], reverse=True)
                labels, values = zip(*sorted_data)
                colors = ['green' if x >= 0 else 'red' for x in values]
                fig, ax = plt.subplots(figsize=(14, 5))
                ax.bar(range(len(values)), values, color=colors)
                ax.axhline(np.median(values), color='blue', linestyle='--', label=f"Median: {np.median(values):.2f}%")
                ax.set_title(title)
                ax.set_ylabel("Performance (%)")
                ax.set_xticks([])
                ax.legend()
                ax.grid(True, linestyle='--', alpha=0.4)
                return fig

            if ytd_perf:
                st.markdown("### YTD Performance")
                st.pyplot(plot_waterfall(ytd_perf, "YTD Performance of ETF Constituents"))

            if last_day_perf:
                st.markdown("### Last Day Performance")
                st.pyplot(plot_waterfall(last_day_perf, "Last Day Performance of ETF Constituents"))

            # --- Report failed tickers ---
            if ytd_failed or last_day_failed:
                st.markdown("### ⚠️ Failed Downloads")
                if ytd_failed:
                    st.warning(f"**YTD failures** ({len(ytd_failed)}): {', '.join(ytd_failed[:15])}" + (" ..." if len(ytd_failed) > 15 else ""))
                if last_day_failed:
                    st.warning(f"**Last Day failures** ({len(last_day_failed)}): {', '.join(last_day_failed[:15])}" + (" ..." if len(last_day_failed) > 15 else ""))

        else:
            st.warning("No tickers found in the ETF holdings file.")
    except Exception as e:
        st.error(f"Error loading data for {performance_ticker.upper()}: {e}")
