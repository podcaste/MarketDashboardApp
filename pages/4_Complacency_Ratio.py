import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from inject_font import inject_custom_font, inject_sidebar_logo

# --- Set config FIRST ---
st.set_page_config(page_title="Complacency Ratio", layout="wide")

# Inject custom font after config
inject_custom_font()
inject_sidebar_logo()
# --- Page Title & Description ---
st.title("😌 Complacency Ratio Dashboard (VVIX / VIX)")
st.caption("This tool visualizes market complacency by tracking the ratio of VVIX to VIX. Breakdowns below the lower bound often precede market inflection points.")

# --- Date selection ---
st.markdown("### ⚙️ Configuration")
col1, col2 = st.columns(2)
with col1:
    default_start = "2021-11-09"
    start_date = st.date_input("Start Date", value=pd.to_datetime(default_start), key="start_date", help="Start date for analysis (default: Nov 2021)")
with col2:
    end_date = datetime.today()
    st.markdown(f"**End Date:** {end_date.strftime('%Y-%m-%d')}")

# --- Download data ---
tickers = ["^VVIX", "^VIX", "^GSPC"]
data = yf.download(tickers, start=start_date, end=end_date, auto_adjust=False)["Close"]

if data.empty or data.isnull().all().all():
    st.warning("No data found for the selected date range.")
else:
    data.columns = ["SPX", "VIX", "VVIX"]
    data = data.dropna()

    # --- Complacency Ratio Calculations ---
    data["Complacency_Ratio"] = data["VVIX"] / data["VIX"]
    data["Complacency_50DMA"] = data["Complacency_Ratio"].rolling(window=50).mean()
    rolling_stddev = data["Complacency_Ratio"].rolling(window=50).std()
    std_multiplier = 1.67
    data["Upper_Bound_1.67SD"] = data["Complacency_50DMA"] + std_multiplier * rolling_stddev
    data["Lower_Bound_1.67SD"] = data["Complacency_50DMA"] - std_multiplier * rolling_stddev

    breaks_below = data[data["Complacency_Ratio"] < data["Lower_Bound_1.67SD"]].index

    # --- Plotting ---
    fig, axs = plt.subplots(2, 1, figsize=(14, 10), sharex=True, gridspec_kw={'height_ratios': [2, 1]})

    # --- Upper Chart: Complacency Ratio ---
    axs[0].plot(data.index, data["Complacency_Ratio"], label="Complacency Ratio", color="#1f77b4", linewidth=1.5, alpha=0.8)
    axs[0].plot(data.index, data["Complacency_50DMA"], label="50-Day SMA", color="#ff7f0e", linewidth=2)
    axs[0].fill_between(data.index, data["Lower_Bound_1.67SD"], data["Upper_Bound_1.67SD"],
                        color="#d1e5f0", alpha=0.4, label="±1.67 SD Band")

    for date in breaks_below:
        axs[0].axvline(date, color="green", linestyle="--", linewidth=1)

    axs[0].set_title("Complacency Ratio (VVIX / VIX) with ±1.67 SD & 50-Day SMA", fontsize=16, fontweight='bold')
    axs[0].set_ylabel("Complacency Ratio")
    axs[0].legend(fontsize=12, frameon=True, loc="upper right")
    axs[0].grid(True, linestyle="--", alpha=0.5)

    # --- Lower Chart: SPX ---
    axs[1].plot(data.index, data["SPX"], label="S&P 500 (SPX)", color="#2ca02c", linewidth=1.5)
    for date in breaks_below:
        axs[1].axvline(date, color="green", linestyle="--", linewidth=1)

    axs[1].set_title("S&P 500 (SPX) Price", fontsize=16, fontweight='bold')
    axs[1].set_ylabel("SPX Value")
    axs[1].set_xlabel("Date")
    axs[1].legend(fontsize=12, frameon=True, loc="upper left")
    axs[1].grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    st.pyplot(fig)

    # --- Explanation ---
    st.markdown("""
    🔍 **How to Read This Chart**

    - The **Complacency Ratio** (VVIX/VIX) helps gauge the volatility-of-volatility vs. vanilla volatility.
    - The ±1.67 SD band around the 50-day moving average highlights abnormal breakdowns.
    - **Vertical green lines** show moments where complacency dips significantly below normal, potentially indicating **fear-driven market bottoms**.
    """)

    # --- Export Options ---
    st.markdown("### 📥 Export Data")
    csv_data = data.to_csv(index=True).encode("utf-8")
    st.download_button("Download Full Dataset (CSV)", data=csv_data, file_name="complacency_ratio.csv", mime="text/csv")
