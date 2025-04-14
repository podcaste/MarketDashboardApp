import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from utils.data_utils import fetch_holdings, download_batched
from inject_font import inject_custom_font, inject_sidebar_logo

# Page setup
st.set_page_config(page_title="Polar Dominance Map", layout="wide")
inject_custom_font()
inject_sidebar_logo()

st.title("🧭 Polar Dominance Map")
st.markdown("""
This module visualizes the **relative dominance** of tickers using a polar layout.
We measure dominance using **cumulative volume × daily price delta**, normalized across tickers.

- Arc length represents dollar volume (how much money is traded)
- Radius represents volatility (how much the price moves)
- Area = Relative Dominance (volume × price delta)
""")

# --- User Mode Selection ---
mode = st.radio("Select Mode:", ["ETF Mode", "Ticker Mode"], horizontal=True)

# --- User Inputs ---
col1, col2, col3 = st.columns(3)
with col1:
    if mode == "ETF Mode":
        etf_ticker = st.text_input("Enter Sector ETF Ticker:", value="XBI", help="Enter an SPDR or other ETF to analyze constituents.").upper()
    else:
        etf_ticker = None
with col2:
    lookback_days = st.slider("Lookback Period (days)", 30, 365, 90)
with col3:
    top_n = st.slider("Top N Tickers to Show", 3, 50, 10)

show_percentage = st.toggle("Show Percentage Labels", value=True)

custom_tickers = []
if mode == "Ticker Mode":
    st.markdown("### Custom Tickers")
    cols = st.columns(5)
    for i in range(5):
        with cols[i]:
            ticker = st.text_input(f"Ticker {i+1}", key=f"custom_ticker_{i}").upper()
            if ticker:
                custom_tickers.append(ticker)

# Determine tickers to use
if mode == "ETF Mode" and etf_ticker:
    try:
        holdings = fetch_holdings(etf_ticker)
        tickers = holdings['Ticker'].dropna().unique().tolist()
        st.success(f"Loaded {len(tickers)} tickers from {etf_ticker}")
    except Exception as e:
        st.error(f"Error loading ETF holdings: {e}")
        tickers = []
elif mode == "Ticker Mode" and custom_tickers:
    tickers = custom_tickers
else:
    tickers = []

# Load and process data
if tickers:
    try:
        end_date = pd.Timestamp.today()
        start_date = end_date - pd.Timedelta(days=lookback_days)

        raw_data, _ = download_batched(tickers, start=start_date, end=end_date)

        # Handle both MultiIndex and single-level DataFrames
        if isinstance(raw_data.columns, pd.MultiIndex):
            prices = raw_data.xs('Close', level=1, axis=1)
            opens = raw_data.xs('Open', level=1, axis=1)
            volumes = raw_data.xs('Volume', level=1, axis=1)
        else:
            prices = raw_data['Close'] if 'Close' in raw_data else raw_data
            opens = raw_data['Open'] if 'Open' in raw_data else yf.download(tickers, start=start_date, end=end_date)["Open"]
            volumes = raw_data['Volume'] if 'Volume' in raw_data else yf.download(tickers, start=start_date, end=end_date)["Volume"]

        valid_tickers = [t for t in tickers if t in prices.columns and t in volumes.columns and t in opens.columns]

        st.markdown("---")
        st.subheader("📊 Polar Chart of Volume × Price Movement")
        st.caption("This radar-style chart shows tickers with highest volume-weighted price deltas in a circular layout.")

        dominance_values = {}
        for t in valid_tickers:
            delta = (prices[t] - opens[t]).abs() / opens[t]
            volume_dollar = volumes[t] * prices[t]
            dominance = (volume_dollar * delta).sum()
            dominance_values[t] = dominance

        dom_df = pd.Series(dominance_values).sort_values(ascending=False).head(top_n)
        labels = dom_df.index.tolist()
        values = dom_df.values

        # Angles by cumulative area
        proportions = values / values.sum()
        angles = proportions * 360
        angles_cumulative = np.cumsum(angles)
        base_angles = np.insert(angles_cumulative[:-1], 0, 0)

        # Custom labels with percent
        if show_percentage:
            text_labels = [f"{label}: {val / values.sum() * 100:.1f}%" for label, val in zip(labels, values)]
        else:
            text_labels = [f"{label}: {val:,.0f}" for label, val in zip(labels, values)]

        # Build a barpolar chart
        fig = go.Figure()
        fig.add_trace(go.Barpolar(
            r=values,
            theta=base_angles,
            width=angles,
            marker_color=values,
            marker_colorscale='Viridis',
            opacity=0.85,
            text=text_labels,
            hoverinfo="text"
        ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, showticklabels=False, ticks=''),
                angularaxis=dict(rotation=90, direction="clockwise")
            ),
            showlegend=False,
            height=700,
            title=f"Daily Relative Dominance — {etf_ticker if mode == 'ETF Mode' else ', '.join(custom_tickers)}"
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading or processing data: {e}")
