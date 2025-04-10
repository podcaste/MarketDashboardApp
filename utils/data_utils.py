import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import streamlit as st
import time

@st.cache_data
def fetch_holdings(seasonality_ticker):
    import pandas as pd

    url = f"https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-{seasonality_ticker.lower()}.xlsx"

    # Load raw Excel file
    raw = pd.read_excel(url, header=None)

    # Search for header row containing "Ticker" and "Weight"
    header_row_idx = None
    for i in range(len(raw)):
        row = raw.iloc[i].astype(str).str.strip().str.lower()
        if "ticker" in row.values and "weight" in row.values:
            header_row_idx = i
            break

    if header_row_idx is None:
        raise ValueError("Could not find header row with 'Ticker' and 'Weight'.")

    # Set headers and extract data
    headers = raw.iloc[header_row_idx].tolist()
    data = raw.iloc[header_row_idx + 1:].copy()
    data.columns = headers

    # Clean and filter
    if 'Ticker' not in data.columns or 'Weight' not in data.columns:
        raise ValueError(f"Expected 'Ticker' and 'Weight' columns. Got: {data.columns.tolist()}")

    df = data[['Ticker', 'Weight']].dropna()
    df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
    df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce')
    df = df[df['Ticker'].str.isalpha() & df['Weight'].notna()]

    return df

@st.cache_data
def fetch_returns(tickers, benchmark, days=365):
    periods = {
        "1D": 1,
        "3D": 3,
        "5D": 5,
        "30D": 30,
        "1Y": 365
    }

    tickers = list(set(tickers + [benchmark]))
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)

    price_data, _ = download_batched(
    tickers,
    start=start_date,
    end=end_date,
    auto_adjust=True)

    if isinstance(price_data.columns, pd.MultiIndex):
        close_prices = price_data.xs('Close', axis=1, level=1)
    else:
        close_prices = price_data

    close_prices = close_prices.dropna(axis=1)
    latest_date = close_prices.index[-1]

    returns_df = pd.DataFrame(index=close_prices.columns)
    for label, delta in periods.items():
        period_start = latest_date - timedelta(days=delta)
        period_data = close_prices[close_prices.index >= period_start]
        returns = (period_data.iloc[-1] - period_data.iloc[0]) / period_data.iloc[0] * 100
        returns_df[label] = returns.round(2)

    returns_df = returns_df.reset_index().rename(columns={"index": "Ticker"})
    etf_row = returns_df[returns_df['Ticker'] == benchmark.upper()]
    others = returns_df[returns_df['Ticker'] != benchmark.upper()].sort_values(by="1D", ascending=False)
    full_df = pd.concat([etf_row, others], ignore_index=True)
    return full_df, close_prices

def calculate_sma_percentages(price_data, start_date):
    price_data = price_data.loc[price_data.index >= pd.to_datetime(start_date)]
    results = {"20D": [], "50D": [], "200D": []}
    for current_date in price_data.index:
        window = price_data.loc[:current_date]
        results["20D"].append((window.iloc[-1] > window.rolling(20).mean().iloc[-1]).mean() * 100)
        results["50D"].append((window.iloc[-1] > window.rolling(50).mean().iloc[-1]).mean() * 100)
        results["200D"].append((window.iloc[-1] > window.rolling(200).mean().iloc[-1]).mean() * 100)
    sma_data = pd.DataFrame(results, index=price_data.index)
    sma_data.columns = ["% > 20D SMA", "% > 50D SMA", "% > 200D SMA"]
    return sma_data


import time
import yfinance as yf
import pandas as pd
import streamlit as st

@st.cache_data(show_spinner=False)
def download_batched(
    tickers,
    start=None,
    end=None,
    period=None,
    interval='1d',
    group_by='ticker',
    auto_adjust=True,
    max_retries=3,
    sleep_base=2
):
    """
    Download ticker data in batches of 50 from Yahoo Finance, with retries, backoff, and caching.
    Returns: combined DataFrame and list of failed tickers.
    """
    all_batches = []
    failed_tickers = []
    tickers = list(set(tickers))  # remove duplicates

    for i in range(0, len(tickers), 50):
        batch = tickers[i:i + 50]
        retry_count = 0
        success = False
        while not success and retry_count <= max_retries:
            try:
                data = yf.download(
                    tickers=batch,
                    start=start,
                    end=end,
                    period=period,
                    interval=interval,
                    group_by=group_by,
                    auto_adjust=auto_adjust,
                    progress=False,
                    threads=True
                )
                if not data.empty:
                    all_batches.append(data)
                else:
                    failed_tickers.extend(batch)
                success = True
            except Exception as e:
                retry_count += 1
                wait = sleep_base * (2 ** (retry_count - 1))
                print(f"[Retry {retry_count}] Batch {batch[:3]}... -> {e} | Waiting {wait}s")
                time.sleep(wait)
        time.sleep(1)  # gentle cooldown

    if all_batches:
        combined = pd.concat(all_batches, axis=1)
    else:
        combined = pd.DataFrame()

    return combined, failed_tickers