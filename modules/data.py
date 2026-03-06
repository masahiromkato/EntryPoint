import streamlit as st
import pandas as pd
import yfinance as yf
import datetime

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_data(ticker: str, start_date: datetime.date, end_date: datetime.date, interval: str) -> pd.DataFrame:
    try:
        raw = yf.download(ticker, start=start_date, end=end_date + datetime.timedelta(days=1), interval=interval,
                          auto_adjust=True, progress=False)
    except Exception:
        return pd.DataFrame()
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    if raw.index.duplicated().any():
        raw = raw.loc[~raw.index.duplicated(keep="first"), :]
    cols = [c for c in ["Open","High","Low","Close","Volume"] if c in raw.columns]
    df   = raw[cols].copy()
    df.dropna(subset=["Close"], inplace=True)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    return df

@st.cache_data(ttl=86400*7, show_spinner=False)
def fetch_ticker_name(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info
        name = info.get('shortName') or info.get('longName') or ""
        return name
    except Exception:
        return ""
