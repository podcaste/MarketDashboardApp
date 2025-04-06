import streamlit as st
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime
import feedparser
from textblob import TextBlob
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="📰 News Sentiment Analyzer", layout="wide")
st.title("📰 News-Driven Sentiment Analysis")

st.markdown("""
This tool pulls recent headlines from multiple free sources (Yahoo Finance, Finviz, and Seeking Alpha) and scores them using TextBlob for sentiment.

**Features:**
- 📈 Sentiment timeline from headline polarity
- ☁️ Word cloud of headline content
- 🗞️ Most extreme headlines sorted by sentiment

*Free, real-time, and no API key required.*
""")

# --- User Inputs ---
ticker = st.text_input("Enter a Ticker (e.g., AAPL, TSLA, SPY):", value="AAPL").upper()

if ticker:
    all_articles = []

    st.info("🔍 Fetching headlines for: " + ticker)

    # --- Yahoo Finance RSS ---
    feed_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    st.write(f"✅ Yahoo RSS Feed: {feed_url}")
    feed = feedparser.parse(feed_url)
    st.write(f"🔹 Found {len(feed.entries)} Yahoo headlines")
    for entry in feed.entries:
        title = entry.title
        published = entry.published if "published" in entry else ""
        sentiment = TextBlob(title).sentiment.polarity
        all_articles.append({"source": "Yahoo", "title": title, "published": published, "sentiment": sentiment})

    # --- Finviz Scraper ---
    try:
        url = f"https://finviz.com/quote.ashx?t={ticker}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        news_table = soup.find(id="news-table")
        rows = news_table.find_all("tr") if news_table else []
        st.write(f"🔹 Found {len(rows)} Finviz headlines")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) == 2:
                raw_time = cols[0].text.strip()
                title = cols[1].text.strip()
                sentiment = TextBlob(title).sentiment.polarity
                all_articles.append({"source": "Finviz", "title": title, "published": raw_time, "sentiment": sentiment})
    except Exception as e:
        st.warning(f"Finviz scrape failed: {e}")

    # --- Seeking Alpha Scraper (Improved DOM Parsing) ---
    try:
        sa_url = f"https://seekingalpha.com/symbol/{ticker}/news"
        st.write(f"✅ Seeking Alpha URL: {sa_url}")
        r = requests.get(sa_url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        count = 0
        for post in soup.find_all("div", class_="flex min-w-0 grow self-center"):
            title_tag = post.find("a", {"data-test-id": "post-list-item-title"})
            time_tag = post.find_next("span", {"data-test-id": "post-list-date"})

            if title_tag and title_tag.text.strip():
                title = title_tag.text.strip()
                timestamp = time_tag.text.strip() if time_tag else ""

                # Clean up timestamp
                timestamp_clean = re.sub(r'[^0-9:AMPamp\s,]', '', timestamp).strip()
                sentiment = TextBlob(title).sentiment.polarity

                all_articles.append({
                    "source": "Seeking Alpha",
                    "title": title,
                    "published": timestamp_clean,
                    "sentiment": sentiment
                })
                count += 1

        st.write(f"🔹 Found {count} Seeking Alpha headlines")

    except Exception as e:
        st.warning(f"Seeking Alpha scrape failed: {e}")

    if not all_articles:
        st.warning("No headlines found from any source.")
    else:
        df = pd.DataFrame(all_articles)
        df["published"] = pd.to_datetime(df["published"], errors="coerce")
        df.dropna(subset=["published"], inplace=True)
        df["day"] = df["published"].dt.date

        # --- Sentiment Timeline ---
        timeline = df.groupby("day")[["sentiment"]].mean().reset_index()
        fig1 = px.line(timeline, x="day", y="sentiment", title=f"🧠 Sentiment Timeline for {ticker}")
        st.plotly_chart(fig1, use_container_width=True)

        # --- Word Cloud ---
        st.subheader("🗣️ Word Cloud from Headlines")
        all_words = " ".join(df["title"].tolist())
        wordcloud = WordCloud(width=1000, height=400, background_color="white").generate(all_words)
        fig_wc, ax_wc = plt.subplots(figsize=(14, 5))
        ax_wc.imshow(wordcloud, interpolation='bilinear')
        ax_wc.axis("off")
        st.pyplot(fig_wc)

        # --- Most Sentiment-Extreme Headlines ---
        st.subheader("🔥 Most Extreme Headlines")
        st.dataframe(df.sort_values("sentiment", key=abs, ascending=False)[["published", "source", "title", "sentiment"]].head(10))

        # --- Export ---
        csv_buffer = BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        st.download_button("📥 Download CSV", data=csv_buffer, file_name=f"{ticker}_sentiment_merged.csv", mime="text/csv")
