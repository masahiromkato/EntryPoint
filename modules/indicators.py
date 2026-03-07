import pandas as pd
import numpy as np

try:
    import pandas_ta as ta
    PANDAS_TA_AVAILABLE = True
except ImportError:
    PANDAS_TA_AVAILABLE = False


def _rsi_wilder(series: pd.Series, length: int = 14) -> pd.Series:
    d  = series.diff()
    g  = d.clip(lower=0)
    l  = (-d).clip(lower=0)
    ag = g.ewm(alpha=1.0/length, min_periods=length, adjust=False).mean()
    al = l.ewm(alpha=1.0/length, min_periods=length, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    if PANDAS_TA_AVAILABLE:
        try:
            r = ta.rsi(series, length=length)
            if r is not None and not r.isna().all():
                return r
        except Exception:
            pass
    return _rsi_wilder(series, length)


def calc_indicators(df: pd.DataFrame, ma_period: int = 50) -> pd.DataFrame:
    df        = df.copy()
    close     = df["Close"]
    df["MA_VAL"]    = close.rolling(window=ma_period, min_periods=ma_period).mean()
    df["DEV"]       = (close - df["MA_VAL"]) / df["MA_VAL"] * 100
    df["RSI"]       = calc_rsi(close, 14)
    df["PRICE_CHG"] = close.pct_change() * 100
    return df


def gen_signals(
    df: pd.DataFrame,
    dev_thr: float,   use_ma:  bool,
    rsi_thr: float,   use_rsi: bool,
    chg_thr: float,   use_chg: bool,
    mode: str,
) -> pd.DataFrame:
    df    = df.copy()
    c_ma  = df["DEV"]       <= dev_thr if use_ma  else pd.Series(False, index=df.index)
    c_rsi = df["RSI"]       <= rsi_thr if use_rsi else pd.Series(False, index=df.index)
    c_chg = df["PRICE_CHG"] <= chg_thr if use_chg else pd.Series(False, index=df.index)

    active = [c for flag, c in [(use_ma, c_ma), (use_rsi, c_rsi), (use_chg, c_chg)] if flag]

    if not active:
        df["Signal"] = False
    elif mode == "AND":
        sig = active[0]
        for c in active[1:]:
            sig = sig & c
        df["Signal"] = sig
    else:
        sig = active[0]
        for c in active[1:]:
            sig = sig | c
        df["Signal"] = sig

    df["Sig_MA"]  = c_ma
    df["Sig_RSI"] = c_rsi
    df["Sig_CHG"] = c_chg
    return df
