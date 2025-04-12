import streamlit as st
import yfinance as yf
import pandas as pd
from inject_font import inject_custom_font, inject_sidebar_logo

st.set_page_config(layout="wide")
inject_custom_font()
inject_sidebar_logo()


st.title("📈 Top N Daily Market Moves: Context & Consequences")

# --- Download NASDAQ Composite Index (^IXIC) ---

# Toggle for best or worst day selection
mode = st.radio("📊 Market Move Focus", ["Biggest Gains", "Biggest Losses"], horizontal=True, help="Select whether to analyze the strongest gainers or worst losers in the dataset")
st.markdown("---")
st.markdown("### ⚙️ Data Configuration")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("Choose any stock or index ticker, like **^IXIC (NASDAQ)**, **SPY**, **AAPL**, etc.")
    ticker = st.text_input("Ticker Symbol", value="^IXIC", help="Enter a Yahoo Finance ticker symbol (e.g. ^IXIC, SPY, AAPL)")
with col2:
    start_date = st.date_input("Start Date", value=pd.to_datetime("1920-01-01"), help="The date to begin pulling historical data from")
with col3:
    end_date = st.date_input("End Date", value=pd.to_datetime("today"), help="The final date for historical data (defaults to today)")

@st.cache_data
def load_nasdaq_data(start, end):
    data = yf.download(ticker, start=start, end=end, auto_adjust=False)
    return data

data = load_nasdaq_data(start_date, end_date)

# Use adjusted close if available; fallback to close
nasdaq = data['Adj Close'] if 'Adj Close' in data.columns else data['Close']

# Calculate daily returns
daily_returns = nasdaq.pct_change().squeeze() * 100

# --- Top N selector ---
num_days = st.slider("Number of Days", 1, 20, 5, help="How many top gain/loss days should be analyzed")

# Get top N biggest up/down days based on toggle
if mode == "Biggest Gains":
    top_5 = daily_returns.sort_values(ascending=False).head(num_days)
else:
    top_5 = daily_returns.sort_values(ascending=True).head(num_days)
top_5_dates = top_5.index

# Compute return stats around those days
def compute_returns(date):
    row = {}
    t_idx = nasdaq.index.get_loc(date)
    if t_idx < 4:
        return None
    price_t = nasdaq.iloc[t_idx]
    price_t_1 = nasdaq.iloc[t_idx - 1]
    price_t_2 = nasdaq.iloc[t_idx - 2]
    price_t_4 = nasdaq.iloc[t_idx - 4]

    row['Date'] = date.date()
    row['-3D %'] = round(float(((price_t_1 - price_t_4) / price_t_4) * 100), 2)
    row['-1D %'] = round(float(((price_t_1 - price_t_2) / price_t_2) * 100), 2)
    row['Day %'] = round(float(top_5.loc[date].iloc[0]) if hasattr(top_5.loc[date], 'iloc') else float(top_5.loc[date]), 2)

    for label, offset in zip(['Next Day %', 'Next 3D %', 'Next Week %', 'Next Month %'], [1, 3, 5, 21]):
        future_idx = t_idx + offset
        if future_idx < len(nasdaq):
            future_price = nasdaq.iloc[future_idx]
            row[label] = round(float(((future_price - price_t) / price_t) * 100), 2)
        else:
            row[label] = None

    return row

results = [compute_returns(date) for date in top_5_dates]
df = pd.DataFrame([r for r in results if r is not None])

st.markdown("---")
st.subheader("📋 Forward Return Summary Table")
st.caption("For each selected day, this table shows the price movement before and after the event, helping you understand behavioral drift post-extreme move.")
st.dataframe(df.round(2), use_container_width=True)

# --- Chart section ---
st.markdown("---")
st.subheader("📊 Normalized Price Action Across Top N Events")
st.caption("Each line shows price action from 10 days before to 10 days after the selected event, all normalized to 100 at t−1.")
import plotly.graph_objects as go

fig = go.Figure()

for date in df['Date']:
    t = pd.to_datetime(date)
    if t not in nasdaq.index:
        continue
    t_idx = nasdaq.index.get_loc(t)
    window_start = max(0, t_idx - 10)
    window_end = min(len(nasdaq), t_idx + 11)
    window_data = nasdaq.iloc[window_start:window_end].copy()

    # Normalize x-axis to t = 0
    rel_day = list(range(-(t_idx - window_start), window_end - t_idx))

    # Normalize price so price at t-1 is 100
    if t_idx - 1 >= 0:
        price_base = nasdaq.iloc[t_idx - 1]
        window_data = (window_data / price_base) * 100
    else:
        continue

    fig.add_trace(go.Scatter(
        x=rel_day,
        y=window_data.values.flatten(),
        mode='lines',
        name=str(t.date())
    ))

fig.add_vline(x=-1, line=dict(color='red', dash='dash'), annotation_text='Normalization Baseline (t−1)', annotation_position="top")
fig.update_layout(title=f"{ticker.upper()} | Normalized ±10 Day Price Curves Across Top {num_days} Days", height=500)
st.plotly_chart(fig, use_container_width=True)

st.markdown("""
🔴 **Note**: The red dashed line marks **t−1**, the day before the event.
All price paths are normalized to 100 on this day so you can clearly see how the market behaved **after** the big move. This gives a consistent visual anchor for comparing forward paths.

This makes it easier to understand *relative* price action while keeping the visual scale consistent.
""")

st.markdown(f"""
This table highlights the **top 5 {'biggest up' if mode == 'Biggest Gains' else 'worst down'} days** in the selected ticker's history since your chosen start date, along with:
- Returns leading into the event (-3D, -1D)
- The big {'gain' if mode == 'Biggest Gains' else 'loss'} day
- Returns following the event (next day, 3D, week, month)
""")
