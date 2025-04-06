import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from io import BytesIO
import statsmodels.api as sm

st.set_page_config(page_title="Factor Exposure Analyzer", layout="wide")
st.title("🧪 Factor Exposure & Tilt Analyzer")

st.markdown("""
This module helps you assess how your selected ticker moves relative to key factor ETFs:
- **📈 Momentum (MTUM)**
- **💼 Value (VLUE)**
- **🏢 Quality (QUAL)**
- **📉 Low Volatility (SPLV)**
- **🔬 Small Cap (IWM)**
- **💥 High Beta (SPHB)**
- **🌱 Growth (SPYG)**
- **⚖️ Equal Weight (RSP)**
- **🛡️ Minimum Volatility (USMV)**

You’ll see:
- Rolling **correlation and beta** to each factor
- A **radar chart** summarizing the average exposure across time
- Statistical summaries and the ability to compare two tickers side-by-side
- A **scatterplot** comparing correlation and beta per factor
- **Rolling beta volatility** showing factor stability
- **Rolling alpha**: how much return is left after accounting for beta exposure
- **Factor Sharpe Ratios**: performance per unit of volatility for each factor
- **Multi-factor regression summary and visual plot of coefficients**
""")

# --- User Input ---
ticker = st.text_input("Enter primary ticker (e.g., AAPL, MSFT, SPY):", value="AAPL").upper()
compare_ticker = st.text_input("Optional: Compare against another ticker:", value="").upper()
window = st.slider("Rolling Window (days)", min_value=10, max_value=180, value=60, step=5)
lookback = st.slider("Lookback Period (days)", min_value=90, max_value=1000, value=365)

factor_etfs = {
    "MTUM": "Momentum",
    "VLUE": "Value",
    "QUAL": "Quality",
    "SPLV": "Low Volatility",
    "IWM": "Small Cap",
    "SPHB": "High Beta",
    "SPYG": "Growth",
    "RSP": "Equal Weight",
    "USMV": "Min Volatility",
}

selected_factors = st.multiselect(
    "Select which factor ETFs to include:",
    options=list(factor_etfs.keys()),
    default=list(factor_etfs.keys()),
    format_func=lambda x: f"{x} ({factor_etfs[x]})"
)


if ticker:
    try:
        end = datetime.today()
        start = end - timedelta(days=lookback + window)

        tickers = [ticker] + list(factor_etfs.keys())
        if compare_ticker:
            tickers.append(compare_ticker)

        data = yf.download(tickers, start=start, end=end, auto_adjust=True)["Close"].dropna(how='all', axis=1)

        if isinstance(data.columns, pd.MultiIndex):
            data = data.droplevel(0, axis=1)

        available_factors = [f for f in factor_etfs if f in data.columns]
        factor_labels = {f: factor_etfs[f] for f in available_factors}

        if not available_factors:
            st.error("None of the factor ETFs loaded. Please try a different time window.")
        else:
            returns = data.pct_change().dropna()

            # --- Rolling Correlations ---
            st.subheader("📈 Rolling Correlation to Factors")
            st.caption("This shows how the selected ticker's correlation to each factor ETF changes over time.")
            rolling_corrs = pd.DataFrame(index=returns.index)
            for f in available_factors:
                rolling_corrs[factor_labels[f]] = returns[ticker].rolling(window).corr(returns[f])

            fig_corr = px.line(rolling_corrs, labels={"value": "Correlation", "index": "Date"})
            fig_corr.update_layout(legend_title="Factor")
            st.plotly_chart(fig_corr, use_container_width=True)

            # --- Rolling Betas ---
            st.subheader("🧮 Rolling Beta to Factors")
            st.caption("Beta estimates how sensitive the selected ticker is to each factor ETF's return.")
            beta_df = pd.DataFrame(index=returns.index)
            for f in available_factors:
                beta = returns[ticker].rolling(window).cov(returns[f]) / returns[f].rolling(window).var()
                beta_df[factor_labels[f]] = beta

            fig_beta = px.line(beta_df, labels={"value": "Beta", "index": "Date"})
            fig_beta.update_layout(legend_title="Factor")
            st.plotly_chart(fig_beta, use_container_width=True)

            # --- Radar Chart ---
            st.subheader("📊 Average Exposure Radar Chart")
            st.caption("This radar chart summarizes the average rolling beta to each factor across the time window.")
            radar = go.Figure()
            radar.add_trace(go.Scatterpolar(
                r=beta_df.mean().values,
                theta=beta_df.columns,
                fill='toself',
                name=ticker,
                line=dict(color="royalblue")
            ))

            if compare_ticker and compare_ticker in returns.columns:
                beta_df2 = pd.DataFrame(index=returns.index)
                for f in available_factors:
                    beta2 = returns[compare_ticker].rolling(window).cov(returns[f]) / returns[f].rolling(window).var()
                    beta_df2[factor_labels[f]] = beta2

                radar.add_trace(go.Scatterpolar(
                    r=beta_df2.mean().values,
                    theta=beta_df2.columns,
                    fill='toself',
                    name=compare_ticker,
                    line=dict(color="darkorange")
                ))
                radar.update_layout(showlegend=True)
            else:
                radar.update_layout(showlegend=False)

            radar.update_layout(polar=dict(radialaxis=dict(visible=True)))
            st.plotly_chart(radar, use_container_width=True)

            # --- Beta Scatter Plot ---
            st.subheader("📍 Correlation vs. Beta")
            st.caption("This scatterplot compares the average rolling beta and correlation for each factor.")
            scatter_data = pd.DataFrame({
                "Factor": beta_df.columns,
                "Mean Beta": beta_df.mean().values,
                "Mean Corr": rolling_corrs[beta_df.columns].mean().values
            })
            fig_scatter = px.scatter(scatter_data, x="Mean Corr", y="Mean Beta", text="Factor")
            fig_scatter.update_traces(textposition="top center")
            fig_scatter.update_layout(xaxis_title="Avg Correlation", yaxis_title="Avg Beta")
            st.plotly_chart(fig_scatter, use_container_width=True)

            # --- Beta StdDev Plot ---
            st.subheader("📉 Rolling Beta Volatility")
            st.caption("Tracks the standard deviation of beta for each factor — more stable beta may indicate more reliable exposure.")
            beta_vol = beta_df.rolling(window).std()
            fig_vol = px.line(beta_vol, labels={"value": "Beta StdDev", "index": "Date"})
            fig_vol.update_layout(legend_title="Factor")
            st.plotly_chart(fig_vol, use_container_width=True)

            # --- Rolling Alpha ---
            st.subheader("📈 Rolling Alpha")
            st.caption("Alpha represents return unexplained by beta exposure — the 'excess' performance.")
            X_beta = returns[list(factor_labels)].rename(columns=factor_labels)
            alpha_est = pd.Series(index=returns.index)
            for t in range(window, len(returns)):
                y = returns[ticker].iloc[t - window:t]
                X_win = X_beta.iloc[t - window:t]
                if len(y) == len(X_win):
                    model = sm.OLS(y, sm.add_constant(X_win)).fit()
                    alpha_est.iloc[t] = model.resid.mean()

            fig_alpha = px.line(alpha_est, labels={"value": "Alpha", "index": "Date"})
            fig_alpha.update_layout(title="Rolling Alpha (Residual Return)", showlegend=False)
            st.plotly_chart(fig_alpha, use_container_width=True)

            # --- Sharpe Ratios for Factors ---
            st.subheader("📊 Factor Sharpe Ratios")
            st.caption("Measures return per unit of risk (volatility) for each factor ETF.")
            sharpe = returns[list(factor_labels)].rename(columns=factor_labels).mean() / returns[list(factor_labels)].std()
            st.dataframe(sharpe.round(3).rename("Sharpe Ratio"))

            # --- OLS Regression Summary ---
            st.subheader("📘 Multi-Factor Regression")
            st.caption("Fit a linear regression model to estimate how much of the ticker's return is explained by factors.")
            X = returns[list(factor_labels)].rename(columns=factor_labels)
            X = sm.add_constant(X)
            model = sm.OLS(returns[ticker], X, missing='drop').fit()
            st.text(model.summary())

            # --- Regression Coefficient Plot ---
            st.subheader("📌 Regression Coefficients")
            st.caption("Estimated impact of each factor on the ticker's return, with confidence intervals.")
            coef_df = pd.DataFrame({
                "Factor": model.params.index,
                "Coefficient": model.params.values,
                "CI Lower": model.conf_int().iloc[:, 0].values,
                "CI Upper": model.conf_int().iloc[:, 1].values
            })
            coef_df = coef_df[coef_df["Factor"] != "const"]
            fig_coef = px.bar(coef_df, x="Factor", y="Coefficient",
                              error_y=coef_df["CI Upper"] - coef_df["Coefficient"],
                              error_y_minus=coef_df["Coefficient"] - coef_df["CI Lower"],
                              color="Coefficient",
                              color_continuous_scale="RdBu",
                              title="Factor Exposure Coefficients")
            st.plotly_chart(fig_coef, use_container_width=True)

            # --- Summary Table ---
            st.subheader("📋 Beta Summary Table")
            st.caption("Mean, standard deviation, and z-score of rolling beta for each factor.")
            summary = pd.DataFrame({
                "Mean": beta_df.mean(),
                "StdDev": beta_df.std(),
                "Z-Score": (beta_df.iloc[-1] - beta_df.mean()) / beta_df.std()
            }).round(3)
            st.dataframe(summary)

            # --- Download Buttons ---
            st.markdown("### 📥 Export Results")
            st.download_button("Download Beta Data (CSV)", data=beta_df.to_csv().encode('utf-8'), file_name=f"{ticker}_beta_data.csv", mime="text/csv")
            st.download_button("Download Correlation Data (CSV)", data=rolling_corrs.to_csv().encode('utf-8'), file_name=f"{ticker}_correlation_data.csv", mime="text/csv")

    except Exception as e:
        st.error(f"Error loading data: {e}")
