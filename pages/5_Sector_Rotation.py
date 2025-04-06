import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="Sector Rotation Map", layout="wide")
st.title("🔁 Sector Rotation Map")

# --- Sector ETF Tickers ---
sector_etfs = {
    "XLB": "Materials",
    "XLC": "Comm Services",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLK": "Technology",
    "XLP": "Consumer Staples",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLV": "Health Care",
    "XLY": "Cons Discretionary",
    "XBI": "Biotech",
    "XRT": "Retail",
    "KRE": "Regional Banks",
    "ITB": "Homebuilders",
    "IBB": "Large Biotech"
}

benchmark = "SPY"
all_tickers = list(sector_etfs.keys()) + [benchmark]

# --- User Controls ---
st.sidebar.header("Settings")
momentum_days = st.sidebar.slider("Momentum Period (days)", 5, 30, 10)
strength_days = st.sidebar.slider("Relative Strength Period (days)", 10, 60, 30)
history_days = st.sidebar.slider("Animation Lookback (days)", 10, 90, 30)

# --- Fetch Data ---
@st.cache_data
def fetch_sector_data(tickers, days_back):
    end = datetime.today()
    start = end - timedelta(days=days_back + 60)
    df = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)["Close"]
    return df.dropna(how="all", axis=1)

try:
    price_data = fetch_sector_data(all_tickers, history_days + max(momentum_days, strength_days))

    frames = []
    for i in range(strength_days, len(price_data)):
        date = price_data.index[i]
        if i - momentum_days < 0:
            continue

        current = price_data.iloc[i]
        past_momentum = price_data.iloc[i - momentum_days]
        past_strength = price_data.iloc[i - strength_days]

        momentum = ((current - past_momentum) / past_momentum) * 100
        rel_strength = (((current - past_strength) / past_strength) - ((current[benchmark] - past_strength[benchmark]) / past_strength[benchmark])) * 100

        df_day = pd.DataFrame({
            "ETF": momentum.index,
            "Sector": [f"{sector_etfs.get(t, t)} (non-SPDR)" if t in ['ITB', 'IBB'] else sector_etfs.get(t, t) for t in momentum.index],
            "Momentum": momentum.values,
            "RelativeStrength": rel_strength.values,
            "Date": date
        }).dropna()

        df_day = df_day[df_day["ETF"] != benchmark]
        frames.append(df_day)

    animated_df = pd.concat(frames)
    animated_df["Date"] = animated_df["Date"].dt.strftime("%Y-%m-%d")

    fig = px.scatter(
        animated_df,
        x="Momentum",
        y="RelativeStrength",
        animation_frame="Date",
        animation_group="ETF",
        color="Sector",
        text="ETF",
        size_max=60,
        range_x=[animated_df["Momentum"].min() - 1, animated_df["Momentum"].max() + 1],
        range_y=[animated_df["RelativeStrength"].min() - 1, animated_df["RelativeStrength"].max() + 1],
        title=f"Animated Sector Rotation Map ({momentum_days}D Momentum vs {strength_days}D Relative Strength)"
    )

    # Add quadrant labels
    fig.add_annotation(text="Improving", x=-10, y=10, showarrow=False, font=dict(size=12, color="gray"))
    fig.add_annotation(text="Leading", x=10, y=10, showarrow=False, font=dict(size=12, color="gray"))
    fig.add_annotation(text="Lagging", x=-10, y=-10, showarrow=False, font=dict(size=12, color="gray"))
    fig.add_annotation(text="Weakening", x=10, y=-10, showarrow=False, font=dict(size=12, color="gray"))

    # Add quadrant lines
    fig.add_shape(type="line", x0=0, x1=0, y0=animated_df["RelativeStrength"].min(), y1=animated_df["RelativeStrength"].max(),
                  line=dict(color="gray", dash="dash"))
    fig.add_shape(type="line", x0=animated_df["Momentum"].min(), x1=animated_df["Momentum"].max(), y0=0, y1=0,
                  line=dict(color="gray", dash="dash"))

    fig.update_traces(textposition="top center")
    fig.update_layout(height=700, xaxis_title="Momentum (%)", yaxis_title="Relative Strength vs SPY (%)")

        # Highlight biggest movers each day
    latest_date = animated_df['Date'].max()
    latest_df = animated_df[animated_df['Date'] == latest_date].copy()
    latest_df['Distance'] = np.sqrt(latest_df['Momentum']**2 + latest_df['RelativeStrength']**2)
    top_mover = latest_df.loc[latest_df['Distance'].idxmax()]['ETF']
    fig.update_traces(marker=dict(line=dict(width=2, color="black")), selector=dict(name=top_mover))

    

    st.plotly_chart(fig, use_container_width=True)

    # Export option
    with st.expander("📤 Export Animation"):
        st.markdown("Plotly animations can't export GIF/MP4 directly in Streamlit. You can right-click and record, or use Plotly in Jupyter.")
        st.code("fig.write_html('sector_rotation.html')")

except Exception as e:
    st.error(f"Failed to load sector data: {e}")
