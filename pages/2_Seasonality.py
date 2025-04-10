import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from datetime import datetime
from scipy.stats import ttest_1samp
import numpy as np
from inject_font import inject_custom_font, inject_sidebar_logo

st.set_page_config(page_title="Seasonality", layout="wide")
inject_custom_font()
inject_sidebar_logo()
st.title("📅 Seasonality Analysis")

# --- Ticker input ---
st.markdown("### 🧮 Choose a Ticker")
seasonality_ticker = st.text_input("Enter the ticker to check seasonality:", "XBI", help="Example: SPY, AAPL, XLK, etc.").upper()

if seasonality_ticker:
    try:
        df = yf.download(seasonality_ticker, start='1990-01-01', auto_adjust=True)
        if df.empty:
            st.warning(f"No data found for ticker {seasonality_ticker}.")
        else:
            df['Returns'] = df['Close'].pct_change()
            df['TradingDayOfYear'] = df.index.to_series().groupby(df.index.year).cumcount() + 1
            avg_returns = df.groupby('TradingDayOfYear')['Returns'].mean()
            std_deviation = df.groupby('TradingDayOfYear')['Returns'].std()
            seasonality = (avg_returns + 1).cumprod() - 1
            upper_band = seasonality + std_deviation
            lower_band = seasonality - std_deviation

            current_year = datetime.now().year
            current_year_data = df[df.index.year == current_year].copy()
            if not current_year_data.empty:
                current_year_data['CumulativeReturns'] = (current_year_data['Returns'] + 1).cumprod() - 1

            # --- X-Axis Logic ---
            month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            trading_days_per_month = [21, 19, 21, 21, 21, 21, 21, 22, 21, 21, 21, 21]
            cumulative_days = np.cumsum(trading_days_per_month)
            midpoints = [c - d / 2 for c, d in zip(cumulative_days, trading_days_per_month)]

            # --- Seasonality Plot ---
            st.markdown("---")
            st.subheader("📈 Seasonality Chart")
            st.caption("Shows cumulative average return through the year with ±1 SD bands. Overlays current year if data is available.")

            fig, ax = plt.subplots(figsize=(14, 7))
            ax.plot(seasonality.index, seasonality.values * 100, label='Historical Seasonality')
            ax.fill_between(seasonality.index, (lower_band * 100), (upper_band * 100), color='gray', alpha=0.3)

            if not current_year_data.empty:
                ax.plot(current_year_data['TradingDayOfYear'], current_year_data['CumulativeReturns'] * 100,
                        label=f'{current_year} Returns')

            ax.set_xticks(midpoints)
            ax.set_xticklabels(month_labels)
            for day in cumulative_days:
                ax.axvline(day, linestyle='--', color='lightgray', linewidth=1)

            ax.set_xlim(0, 252)
            ax.yaxis.set_major_formatter(ticker.PercentFormatter())
            ax.set_xlabel("Month")
            ax.set_ylabel("Cumulative Returns (%)")
            ax.set_title(f"{seasonality_ticker.upper()} Seasonality & {current_year} Overlay")
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.legend()
            st.pyplot(fig)

            # --- Half-Month Violin Plot ---
            st.markdown("---")
            st.subheader("🎻 Half-Month Return Distribution (Violin Plot)")
            st.caption("Each half-month is colored based on t-test significance (Bonferroni adjusted). Blue = p < 0.05")

            chronological_half_months = ['Jan1H', 'Jan2H', 'Feb1H', 'Feb2H', 'Mar1H', 'Mar2H', 'Apr1H', 'Apr2H',
                                         'May1H', 'May2H', 'Jun1H', 'Jun2H', 'Jul1H', 'Jul2H', 'Aug1H', 'Aug2H',
                                         'Sep1H', 'Sep2H', 'Oct1H', 'Oct2H', 'Nov1H', 'Nov2H', 'Dec1H', 'Dec2H']

            df['MonthHalf'] = df.index.strftime('%b') + df.index.map(lambda x: '1H' if x.day <= 15 else '2H')
            df['MonthHalf'] = pd.Categorical(df['MonthHalf'], categories=chronological_half_months, ordered=True)
            df = df.sort_values(by='MonthHalf')

            significance_levels = {
                mh: ttest_1samp(df[df['MonthHalf'] == mh]['Returns'].dropna(), 0)[1]
                for mh in chronological_half_months
            }
            adjusted_significance_levels = {k: v * len(chronological_half_months) for k, v in significance_levels.items()}

            fig2, ax2 = plt.subplots(figsize=(18, 8))
            violin = ax2.violinplot(
                dataset=[df[df['MonthHalf'] == mh]['Returns'].dropna() * 100 for mh in chronological_half_months],
                showmeans=False, showmedians=True
            )
            for pc, mh in zip(violin['bodies'], chronological_half_months):
                mean = df[df['MonthHalf'] == mh]['Returns'].mean()
                color = 'blue' if adjusted_significance_levels[mh] < 0.05 else ('green' if mean >= 0 else 'red')
                pc.set_facecolor(color)
                pc.set_edgecolor('black')
                pc.set_alpha(0.7)

            ax2.set_title(f"{seasonality_ticker.upper()} Half-Monthly Return Distribution")
            ax2.set_xlabel("Half-Month")
            ax2.set_ylabel("Returns (%)")
            ax2.set_xticks(range(1, len(chronological_half_months) + 1))
            ax2.set_xticklabels(chronological_half_months, rotation=45)
            ax2.grid(True, linestyle='--', alpha=0.5)
            st.pyplot(fig2)

            # --- Sorted Bar Plot ---
            st.markdown("---")
            st.subheader("📊 Mean Return by Half-Month (Sorted Bar Chart)")
            st.caption("Bars are blue if statistically significant vs zero (p < 0.05 after Bonferroni correction).")

            mean_returns = df.groupby('MonthHalf')['Returns'].mean()
            sorted_returns = mean_returns.sort_values(ascending=False)

            fig3, ax3 = plt.subplots(figsize=(18, 8))
            bars = ax3.bar(sorted_returns.index, sorted_returns.values * 100,
                           color=['green' if x >= 0 else 'red' for x in sorted_returns])

            for bar, mh in zip(bars, sorted_returns.index):
                if adjusted_significance_levels[mh] < 0.05:
                    bar.set_color('blue')
                    bar.set_edgecolor('black')
                    ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), '*', ha='center', va='bottom')

            ax3.set_title(f"{seasonality_ticker.upper()} Half-Monthly Mean Returns (Sorted)")
            ax3.set_xlabel("Half-Month")
            ax3.set_ylabel("Mean Returns (%)")
            ax3.set_xticks(range(len(sorted_returns.index)))
            ax3.set_xticklabels(sorted_returns.index, rotation=45)
            ax3.grid(True, linestyle='--', alpha=0.5)
            st.pyplot(fig3)

    except Exception as e:
        st.error(f"Error generating seasonality view for {seasonality_ticker}: {e}")
