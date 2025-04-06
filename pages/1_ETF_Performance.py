import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from utils.data_utils import fetch_holdings, fetch_returns, calculate_sma_percentages, download_batched

st.set_page_config(page_title="ETF Performance", layout="wide")
st.title("📈 ETF Performance Dashboard")

# --- Sidebar Advanced Settings ---
st.sidebar.markdown("⚙️ **Advanced Settings**")
retry_limit = st.sidebar.slider("Max Retry Attempts", 0, 5, 3)
sleep_delay = st.sidebar.slider("Sleep Backoff Base (seconds)", 1, 10, 6)

# --- Inputs ---
performance_ticker = st.text_input("Enter SPDR ETF Ticker (e.g., XLK, XLF, SPY):", "XBI").upper()
selected_period = st.selectbox("Select period for treemap:", ["1D", "3D", "5D", "30D", "1Y"])

if performance_ticker:
    try:
        # --- Get holdings with weights ---
        holdings_df = fetch_holdings(performance_ticker)
        tickers = holdings_df['Ticker'].tolist()
        st.success(f"Loaded {len(tickers)} tickers from {performance_ticker}")

        # --- Get returns data ---
        returns_df, price_data = fetch_returns(tickers, performance_ticker)
        merged = pd.merge(returns_df, holdings_df, on="Ticker", how="left").dropna(subset=['Weight'])

        # --- Treemap Visualization ---
        st.subheader(f"{performance_ticker} Treemap - {selected_period} Return")

        plot_df = merged[['Ticker', selected_period, 'Weight']].dropna()
        labels = plot_df['Ticker']
        parents = [""] * len(plot_df)
        values = plot_df['Weight']
        colors = plot_df[selected_period]

        hovertext = [
            f"<b>{label}</b><br>Weight: {w:.2f}%<br>{selected_period}: {r:.2f}%"
            for label, w, r in zip(labels, values, colors)
        ]

        fig = go.Figure(go.Treemap(
            labels=labels,
            parents=parents,
            values=values,
            marker=dict(
                colors=colors,
                colorscale='RdYlGn',
                colorbar=dict(title=f"{selected_period} Return (%)"),
                cmid=0
            ),
            hoverinfo="text",
            hovertext=hovertext,
            textinfo="label+value",
            branchvalues="total"
        ))

        fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)

        # --- Performance Table ---
        st.subheader("Performance Table")
        st.dataframe(returns_df, use_container_width=True)

        # --- Top N Line Chart ---
        top_n = st.slider("Number of top performers to display:", 3, 20, 5)
        show_relative = st.toggle("Show relative performance chart (vs ETF)", True)

        leaders = returns_df[returns_df['Ticker'] != performance_ticker].sort_values(by='1D', ascending=False).head(top_n)['Ticker']
        rel_prices = price_data[leaders.tolist() + [performance_ticker]]

        st.subheader(f"Top {top_n} Performers {'(Relative)' if show_relative else ''}")
        fig2, ax = plt.subplots(figsize=(12, 6))
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
        st.pyplot(fig2)

        # --- SMA overlays ---
        st.subheader("% of Constituents Above Key SMAs")
        sma_stats = calculate_sma_percentages(price_data, start_date="2024-09-11")
        fig3, ax2 = plt.subplots(figsize=(12, 6))
        sma_stats.plot(ax=ax2)
        ax2.axhline(80, color='red', linestyle='--', alpha=0.5)
        ax2.axhline(20, color='green', linestyle='--', alpha=0.5)
        ax2.set_title("% of Constituents Above 20D / 50D / 200D SMAs")
        ax2.set_ylabel("Percentage")
        st.pyplot(fig3)

    except Exception as e:
        st.error(f"Error loading data for {performance_ticker.upper()}: {e}")
