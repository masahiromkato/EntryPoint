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


def calc_ma(prices: pd.Series, period: int) -> pd.Series:
    """移動平均の計算"""
    return prices.rolling(window=period, min_periods=period).mean()


def calc_deviation(prices: pd.Series, ma: pd.Series) -> pd.Series:
    """乖離率の計算"""
    return (prices - ma) / ma * 100


def calc_price_chg(prices: pd.Series) -> pd.Series:
    """騰落率の計算"""
    return (prices.pct_change() * 100).fillna(0.0).astype(float)


def gen_signals(
    prices: pd.Series,
    ma: pd.Series,
    rsi: pd.Series,
    dev: pd.Series,
    price_chg: pd.Series,
    dev_thr: float,   use_ma:  bool,
    rsi_thr: float,   use_rsi: bool,
    chg_thr: float,   use_chg: bool,
    mode: str,
) -> pd.DataFrame:
    """
    Pure signal generation. Returns a DataFrame with Signal and sub-signals.
    """
    c_ma  = dev       <= dev_thr if use_ma  else pd.Series(False, index=prices.index)
    c_rsi = rsi       <= rsi_thr if use_rsi else pd.Series(False, index=prices.index)
    c_chg = price_chg <= chg_thr if use_chg else pd.Series(False, index=prices.index)

    active = [c for flag, c in [(use_ma, c_ma), (use_rsi, c_rsi), (use_chg, c_chg)] if flag]

    if not active:
        sig = pd.Series(False, index=prices.index)
    elif mode == "AND":
        sig = active[0]
        for c in active[1:]:
            sig = sig & c
    else:
        sig = active[0]
        for c in active[1:]:
            sig = sig | c

    return pd.DataFrame({
        "Signal":  sig,
        "Sig_MA":  c_ma,
        "Sig_RSI": c_rsi,
        "Sig_CHG": c_chg
    }, index=prices.index)
