import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

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
    tickers = [t.replace('/', '-').strip().upper() for t in tickers if isinstance(t, str) and t.isalnum() and t.upper() not in ['TICKER', '-', 'NONE', ''] and len(t) <= 5]
    return sorted(list(set(tickers)))

sector_etfs = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY", "XBI", "XRT", "KRE", "ITB", "IBB"]

@st.cache_data
def download_price_data(tickers, start, end):
    return yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)["Close"].dropna(axis=1, how='all')

if submitted:
    try:
        end_date = datetime.today()
        start_date = end_date - timedelta(days=lookback_days + correlation_window)
        universe = get_spy_constituents() + sector_etfs
        universe = list(set(universe) - {target_ticker})
        tickers_to_fetch = [target_ticker] + universe + ["^GSPC"]

        price_data = download_price_data(tickers_to_fetch, start_date, end_date)
        common_dates = price_data.dropna().index

        rolling_corrs = {}
        for symbol in universe:
            pair_df = price_data[[target_ticker, symbol]].dropna()
            if len(pair_df) < correlation_window:
                continue
            rolling_corr = pair_df[target_ticker].rolling(correlation_window).corr(pair_df[symbol])
            rolling_corrs[symbol] = rolling_corr.dropna()

        corr_df = pd.DataFrame({k: v for k, v in rolling_corrs.items() if not v.empty})
        latest_corrs = corr_df.tail(1).T
        latest_corrs.columns = ["Rolling Correlation"]
        latest_corrs = latest_corrs.sort_values("Rolling Correlation", ascending=False)
        latest_corrs["Type"] = latest_corrs.index.map(lambda x: "Sector ETF" if x in sector_etfs else "SPY Stock")

        beta_df = pd.DataFrame(index=price_data.index)
        market_returns = price_data['^GSPC'].pct_change()
        for symbol in universe:
            if symbol not in price_data.columns:
                continue
            asset_returns = price_data[symbol].pct_change()
            rolling_cov = asset_returns.rolling(correlation_window).cov(market_returns)
            rolling_var = market_returns.rolling(correlation_window).var()
            beta_df[symbol] = rolling_cov / rolling_var

        st.subheader(f"Top Matches for {target_ticker}")
        st.dataframe(latest_corrs.head(20), use_container_width=True)

        st.subheader("Correlation Heatmap")
        fig = px.bar(
            latest_corrs.reset_index().rename(columns={"index": "Symbol"}),
            x="Symbol", y="Rolling Correlation", color="Type",
            color_discrete_map={"SPY Stock": "#1f77b4", "Sector ETF": "#ff7f0e"},
            title=f"Correlation to {target_ticker}", height=400
        )
        fig.update_layout(xaxis_tickangle=-45, yaxis_range=[-1, 1])
        st.plotly_chart(fig, use_container_width=True)
        st.download_button("Download CSV", latest_corrs.to_csv().encode("utf-8"), file_name=f"{target_ticker}_similarity.csv")

        st.subheader("Correlation Fingerprint Over Time")
        st.caption("This chart shows how each selected ticker's rolling correlation to the target ticker changes over time.")

        available_symbols = list(set(latest_corrs.index) & set(beta_df.columns))
        default_selection = list(set(latest_corrs.head(10).index) & set(available_symbols))
        selected_symbols = st.multiselect("Select Symbols to Display", options=available_symbols, default=default_selection, key="symbol_selector")

        selected_symbols = [s for s in selected_symbols if s in latest_corrs.index and s in beta_df.columns]
        if not selected_symbols:
            st.warning("No valid tickers available for correlation and beta calculation.")
            st.stop()

        fingerprint_df = corr_df[selected_symbols]
        fig_fp = px.line(
            fingerprint_df, x=fingerprint_df.index, y=fingerprint_df.columns,
            labels={"value": "Correlation", "variable": "Symbol"},
            title=f"Rolling Correlation Over Time to {target_ticker}"
        )
        fig_fp.update_layout(legend_title="Symbol", yaxis_range=[-1, 1])
        st.plotly_chart(fig_fp, use_container_width=True)
        st.download_button("Download Fingerprint CSV", fingerprint_df.to_csv().encode("utf-8"), file_name=f"{target_ticker}_fingerprint.csv")

        st.subheader("Rolling Beta Over Time vs SPX")
        st.caption("This chart shows how the beta of each ticker evolves over time relative to the S&P 500 benchmark.")
        beta_display_df = beta_df[selected_symbols].copy()
        fig_beta = px.line(
            beta_display_df, x=beta_display_df.index, y=beta_display_df.columns,
            labels={"value": "Beta", "variable": "Symbol"}, title="Rolling Beta vs S&P 500"
        )
        fig_beta.update_layout(legend_title="Symbol")
        st.plotly_chart(fig_beta, use_container_width=True)
        st.download_button("Download Beta CSV", beta_display_df.to_csv().encode("utf-8"), file_name=f"{target_ticker}_beta.csv")

        st.subheader("Beta Stability vs Correlation")
        st.caption("This scatterplot compares the most recent correlation and beta volatility of each selected ticker.")

        beta_std = beta_df[selected_symbols].std()
        beta_mean = beta_df[selected_symbols].mean()

        safe_symbols = [s for s in selected_symbols if s in latest_corrs.index and s in beta_mean.index and s in beta_std.index]
        if not safe_symbols:
            st.warning("No reliable data found for selected tickers.")
            st.stop()

        summary_df = pd.DataFrame({
            "Mean Beta": beta_mean[safe_symbols],
            "Beta StdDev": beta_std[safe_symbols],
            "Latest Correlation": latest_corrs.loc[safe_symbols, "Rolling Correlation"]
        })

        fig_scatter = px.scatter(
            summary_df, x="Latest Correlation", y="Beta StdDev", text=summary_df.index, size="Mean Beta",
            color=summary_df["Latest Correlation"].apply(lambda x: "High" if x > 0.5 else "Low"),
            labels={"Latest Correlation": "Correlation", "Beta StdDev": "Beta Volatility"},
            title="Correlation vs Beta Stability"
        )
        fig_scatter.update_traces(textposition='top center')
        st.plotly_chart(fig_scatter, use_container_width=True)
        st.download_button("Download Beta Summary", summary_df.to_csv().encode("utf-8"), file_name=f"{target_ticker}_beta_summary.csv")

        st.subheader("Beta Stability Animation")
        st.caption("An animated scatterplot showing how rolling beta changes over time. Use the controls below to customize the animation.")
        summary_df_reset = summary_df.reset_index().rename(columns={"index": "Symbol"})

        max_days = len(beta_df)
        show_all_days = st.toggle("Show full history in animation", value=False)
        animation_days = st.slider("Number of days to animate", min_value=10, max_value=min(180, max_days), value=30, step=5)

        beta_filtered_df = beta_df[selected_symbols].dropna()
        if not show_all_days:
            beta_filtered_df = beta_filtered_df.iloc[-animation_days:]

        recent_beta_df = beta_filtered_df.reset_index().rename(columns={"index": "Date"})
        beta_melted = recent_beta_df.melt(id_vars="Date", var_name="Symbol", value_name="Beta")
        beta_melted = beta_melted.merge(summary_df_reset, on="Symbol", how="left")

        fig_anim = px.scatter(
            beta_melted, x="Latest Correlation", y="Beta",
            animation_frame=beta_melted["Date"].astype(str),
            color="Symbol", size="Mean Beta",
            labels={"Beta": "Rolling Beta", "Latest Correlation": "Correlation"},
            title="Rolling Beta Over Time vs Correlation"
        )
        fig_anim.update_layout(showlegend=False)
        st.plotly_chart(fig_anim, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
