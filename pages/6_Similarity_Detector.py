import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from utils.data_utils import download_batched  # Corrected import

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

    st.subheader("Correlation Heatmap")
    st.caption("Shows top correlated, uncorrelated, and anti-correlated tickers.")

    if not corr_matrix.empty:
        corr_target = corr_matrix[target_ticker].drop(target_ticker)

        top_positive = corr_target.sort_values(ascending=False).head(10)
        top_negative = corr_target.sort_values().head(10)
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

        st.download_button("Download Correlation Matrix (CSV)", data=corr_matrix.to_csv().encode("utf-8"), file_name=f"{target_ticker}_correlation_matrix.csv", mime="text/csv")

    st.subheader("Top Correlated Tickers")
    st.caption("List of tickers most correlated with the target ticker over the lookback period.")

    corr_target = corr_matrix[target_ticker].drop(target_ticker).sort_values(ascending=False)
    corr_df = pd.DataFrame({"Ticker": corr_target.index, "Rolling Correlation": corr_target.values})
    corr_df["Type"] = corr_df["Ticker"].map(lambda x: "Sector ETF" if x in sector_etfs else "SPY Stock")
    st.dataframe(corr_df, use_container_width=True)

    fig_bar = px.bar(
        corr_df,
        x="Ticker", y="Rolling Correlation", color="Type",
        color_discrete_map={"SPY Stock": "#1f77b4", "Sector ETF": "#ff7f0e"},
        title=f"All Correlations with {target_ticker}"
    )
    fig_bar.update_layout(xaxis_tickangle=-45, yaxis_range=[-1, 1])
    st.plotly_chart(fig_bar, use_container_width=True)
    st.download_button("Download Correlation Rankings (CSV)", corr_df.to_csv(index=False).encode("utf-8"), file_name=f"{target_ticker}_top_corr.csv")


    st.subheader("Correlation Fingerprint Over Time")
    st.caption("This chart shows how each selected ticker's rolling correlation to the target ticker changes over time.")

    rolling_corrs = {}
    for symbol in universe:
        if symbol not in price_data.columns:
            continue
        pair_df = price_data[[target_ticker, symbol]].dropna()
        if len(pair_df) < correlation_window:
            continue
        rolling_corr = pair_df[target_ticker].rolling(correlation_window).corr(pair_df[symbol])
        rolling_corrs[symbol] = rolling_corr.dropna()

    corr_df_rolling = pd.DataFrame({k: v for k, v in rolling_corrs.items() if not v.empty})
    all_symbols = corr_df_rolling.columns.tolist()
    default_selection = all_symbols[:10]
    selected_symbols = st.multiselect("Select Symbols to Display", options=all_symbols, default=default_selection, key="symbol_selector")

    if selected_symbols:
        fingerprint_df = corr_df_rolling[selected_symbols]
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

        beta_df = pd.DataFrame(index=price_data.index)
        market_returns = price_data['^GSPC'].pct_change()
        for symbol in selected_symbols:
            if symbol not in price_data.columns:
                continue
            asset_returns = price_data[symbol].pct_change()
            rolling_cov = asset_returns.rolling(correlation_window).cov(market_returns)
            rolling_var = market_returns.rolling(correlation_window).var()
            beta_df[symbol] = rolling_cov / rolling_var

        fig_beta = px.line(
            beta_df[selected_symbols], x=beta_df.index, y=beta_df.columns,
            labels={"value": "Beta", "variable": "Symbol"}, title="Rolling Beta vs S&P 500"
        )
        fig_beta.update_layout(legend_title="Symbol")
        st.plotly_chart(fig_beta, use_container_width=True)
        st.download_button("Download Beta CSV", beta_df.to_csv().encode("utf-8"), file_name=f"{target_ticker}_beta.csv")

        st.subheader("Beta Stability vs Correlation")
        st.caption("This scatterplot compares the most recent correlation and beta volatility of each selected ticker.")

        beta_std = beta_df[selected_symbols].std()
        beta_mean = beta_df[selected_symbols].mean().clip(lower=0.01)  # Ensure non-negative for size
        latest_corr = corr_df.set_index("Ticker").loc[selected_symbols, "Rolling Correlation"]

        summary_df = pd.DataFrame({
            "Mean Beta": beta_mean,
            "Beta StdDev": beta_std,
            "Latest Correlation": latest_corr
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

        recent_beta_df = beta_filtered_df
        beta_melted = recent_beta_df.reset_index().melt(id_vars="Date", var_name="Symbol", value_name="Beta")
        beta_melted = beta_melted.merge(summary_df_reset, on="Symbol")

        fig_anim = px.scatter(
            beta_melted, x="Latest Correlation", y="Beta",
            animation_frame=beta_melted["Date"].astype(str),
            color="Symbol", size="Mean Beta",
            labels={"Beta": "Rolling Beta", "Latest Correlation": "Correlation"},
            title="Rolling Beta Over Time vs Correlation"
        )
        fig_anim.update_layout(showlegend=True)
        st.plotly_chart(fig_anim, use_container_width=True)
