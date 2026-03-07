import streamlit as st
import pandas as pd
import yfinance as yf
import datetime


def _safe_download(ticker: str, start: datetime.date, end: datetime.date, interval: str) -> pd.DataFrame:
    """yfinance でデータ取得。MultiIndex対応・空チェック付き。"""
    try:
        raw = yf.download(
            ticker,
            start=start,
            end=end + datetime.timedelta(days=1),
            interval=interval,
            auto_adjust=True,
            progress=False,
        )
    except Exception:
        return pd.DataFrame()

    if raw is None or raw.empty:
        return pd.DataFrame()

    # MultiIndex 対策
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw.droplevel(axis=1, level=1)
        raw.columns.name = None

    # 重複インデックス除去
    if raw.index.duplicated().any():
        raw = raw.loc[~raw.index.duplicated(keep="first")]

    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
    df = raw[cols].copy()
    df.dropna(subset=["Close"], inplace=True)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    return df


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_data(ticker: str, start_date: datetime.date, end_date: datetime.date, interval: str) -> pd.DataFrame:
    return _safe_download(ticker, start_date, end_date, interval)


@st.cache_data(ttl=86400 * 7, show_spinner=False)
def fetch_ticker_name(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ""
    except Exception:
        return ""


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_fx_rate(start_date: datetime.date, end_date: datetime.date, interval: str) -> pd.Series:
    """USD/JPY レートを取得してSeriesで返す。失敗時は空Series。"""
    df = _safe_download("JPY=X", start_date, end_date, interval)
    if df.empty or "Close" not in df.columns:
        return pd.Series(dtype=float)
    return df["Close"].rename("USDJPY")


def apply_fx_conversion(df: pd.DataFrame, fx_series: pd.Series) -> pd.DataFrame:
    """OHLC各列に USD/JPY レートを乗算して円建てに変換する。欠損はffill/bfill。"""
    if fx_series.empty:
        return df

    df_conv = df.copy()
    # インデックスを日付のみ（tz-naive日付）に揃えて結合
    df_conv.index = pd.to_datetime(df_conv.index).normalize()
    fx_idx = pd.to_datetime(fx_series.index).normalize()
    fx_aligned = fx_series.copy()
    fx_aligned.index = fx_idx

    df_conv = df_conv.join(fx_aligned, how="left")
    df_conv["USDJPY"] = df_conv["USDJPY"].ffill().bfill()

    for col in ["Open", "High", "Low", "Close"]:
        if col in df_conv.columns:
            df_conv[col] = df_conv[col] * df_conv["USDJPY"]

    df_conv.drop(columns=["USDJPY"], inplace=True)
    return df_conv
