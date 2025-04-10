import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from io import BytesIO
from inject_font import inject_custom_font, inject_sidebar_logo

st.set_page_config(page_title="Correlation Overlay", layout="wide")
inject_custom_font()
inject_sidebar_logo()
st.title("🔍 Correlation Overlay Visualizer")

st.markdown("""
Use this tool to compare historical windows of price behavior to the most recent window and identify similar periods based on **rolling correlation**.

ℹ️ Example tickers:
- `^GSPC` for S&P 500 (SPX)
- `^IXIC` for Nasdaq Composite (NDX)
- `AAPL`, `TSLA`, `BTC-USD` also work.
""")

# --- User Inputs ---
ticker_input = st.text_input("Enter a Ticker:", value="^GSPC", help="You can enter index, stock, or crypto tickers.").upper()
correlation_threshold = st.slider("Correlation Threshold", min_value=0.1, max_value=0.99, value=0.5, step=0.01, help="Minimum correlation required to include a historical window")
window_size = st.slider("Rolling Window Size (Days)", min_value=30, max_value=500, value=151, step=1, help="Window size used to compute correlation")

reference_size = window_size
start_date = "1940-01-01"
end_date = pd.Timestamp.now() + pd.Timedelta(days=1)

if ticker_input:
    try:
        data = yf.download(ticker_input, start=start_date, end=end_date, auto_adjust=False)
        if data.empty:
            st.error(f"No data found for {ticker_input}")
        else:
            daily_close = data[['Close']].rename(columns={'Close': 'Daily_Close'}).dropna()
            reference_df = daily_close.tail(reference_size).copy()

            if len(reference_df) < reference_size:
                st.warning("Not enough data in recent history for reference period.")
            else:
                correlation_data = []

                for i in range(len(daily_close) - window_size + 1):
                    window = daily_close.iloc[i:i + window_size].copy()
                    if len(window) == len(reference_df):
                        aligned = pd.concat([
                            window.reset_index(drop=True),
                            reference_df.reset_index(drop=True)
                        ], axis=1).dropna()

                        if len(aligned) > 1:
                            correlation = np.corrcoef(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1]
                            if correlation > correlation_threshold:
                                correlation_data.append({
                                    'Start_Date': window.index[0],
                                    'End_Date': window.index[-1],
                                    'Correlation_Value': correlation
                                })

                correlation_df = pd.DataFrame(correlation_data)

                if not correlation_df.empty:
                    correlation_df['Year'] = correlation_df['Start_Date'].dt.year
                    correlation_df = correlation_df.groupby('Year').apply(lambda x: x.loc[x['Correlation_Value'].idxmax()]).reset_index(drop=True)
                    correlation_df = correlation_df[:-1]
                    correlation_df = correlation_df.sort_values(by='Correlation_Value', ascending=False).head(7)

                    corr_min = correlation_threshold
                    corr_max = correlation_df['Correlation_Value'].max()
                    correlation_df['Normalized_Correlation'] = 0.5 + 0.5 * (correlation_df['Correlation_Value'] - corr_min) / (corr_max - corr_min)
                    correlation_df['LineWidth'] = 1 + 2 * (correlation_df['Correlation_Value'] - corr_min) / (corr_max - corr_min)

                    fetched_data = {}
                    unique_date_ranges = correlation_df[['Start_Date', 'End_Date']].drop_duplicates()

                    for _, row in unique_date_ranges.iterrows():
                        adjusted_end = row['End_Date'] + pd.Timedelta(days=window_size + reference_size - 1)
                        key = (row['Start_Date'], adjusted_end)
                        if key not in fetched_data:
                            series = yf.download(ticker_input, start=row['Start_Date'], end=adjusted_end)['Close']
                            if not series.empty:
                                fetched_data[key] = series / series.iloc[0] * 100

                    fig, ax = plt.subplots(figsize=(14, 7))
                    ax.set_facecolor('white')
                    ax.grid(color='gray', linestyle='--', linewidth=0.5)

                    for _, row in correlation_df.iterrows():
                        key = (row['Start_Date'], row['End_Date'] + pd.Timedelta(days=window_size + reference_size - 1))
                        series = fetched_data.get(key)
                        if series is not None:
                            label = f"{row['Start_Date'].date()} to {row['End_Date'].date()} (Corr: {row['Correlation_Value']:.4f})"
                            ax.plot(np.arange(len(series)), series, label=label,
                                    alpha=row['Normalized_Correlation'], linewidth=row['LineWidth'])

                    indexed_reference = reference_df['Daily_Close'] / reference_df['Daily_Close'].iloc[0] * 100
                    ref_start = reference_df.index[0].strftime('%Y-%m-%d')
                    ref_end = reference_df.index[-1].strftime('%Y-%m-%d')
                    ax.plot(np.arange(len(indexed_reference)), indexed_reference,
                            label=f"Reference: {ref_start} to {ref_end}", linewidth=2, color='black')

                    ax.set_title(f"{ticker_input} Correlation Overlay — {pd.Timestamp.now().strftime('%Y-%m-%d')}",
                                 fontsize=16, fontweight='bold')
                    ax.set_xlabel("Trading Days", fontsize=14, fontweight='bold')
                    ax.set_ylabel("Indexed Value", fontsize=14, fontweight='bold')
                    ax.xaxis.set_major_locator(ticker.MultipleLocator(10))
                    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: int(x) if x % 50 == 0 else ''))
                    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=10))
                    ax.annotate(f"# of Days Tracked: {window_size}", (1.02, 0.2), xycoords='axes fraction', fontsize=10, va='top', ha='left')
                    ax.annotate(f"Correlation cutoff: {correlation_threshold:.2f}", (1.02, 0.15), xycoords='axes fraction', fontsize=10, va='top', ha='left')
                    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize=10)

                    st.pyplot(fig)

                    st.markdown("### 📥 Export Options")

                    csv_bytes = correlation_df.to_csv(index=False).encode('utf-8')
                    st.download_button("Download Correlation Table (CSV)", data=csv_bytes,
                                       file_name=f"{ticker_input}_correlation_table.csv", mime="text/csv")

                    img_buffer = BytesIO()
                    fig.savefig(img_buffer, format='png', bbox_inches='tight')
                    img_buffer.seek(0)
                    st.download_button("Download Plot (PNG)", data=img_buffer,
                                       file_name=f"{ticker_input}_correlation_plot.png", mime="image/png")

                else:
                    st.warning("No historical periods found with correlation above the cutoff.")

    except Exception as e:
        st.error(f"Error processing {ticker_input}: {e}")
