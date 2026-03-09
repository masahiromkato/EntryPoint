import datetime
import pandas as pd
from modules.data import fetch_data, fetch_fx_rate, apply_fx_conversion
from modules.indicators import calc_indicators, gen_signals
from modules.simulation import simulate

def run_analysis_pipeline(
    ticker: str,
    interval_yf: str,
    ma_period: int,
    start_date: datetime.date,
    end_date: datetime.date,
    display_currency: str,
    is_native_jpy: bool,
    dev_thr: float, use_ma: bool,
    rsi_thr: float, use_rsi: bool,
    chg_thr: float, use_chg: bool,
    cond_mode: str,
    periodic_invest: float,
    signal_bonus: float
):
    """
    Consolidated analysis pipeline. Fetches data, calculates indicators, 
    generates signals, and runs simulation. Returns (df, metrics).
    """
    
    # 1. Fetch Price Data
    # Calculate buffer for MA
    buffer_days = (
        ma_period * 31 if interval_yf == "1mo"
        else ma_period * 7 + 30 if interval_yf == "1wk"
        else int(ma_period * 1.5 + 30)
    )
    fetch_start = start_date - datetime.timedelta(days=buffer_days)
    
    df = fetch_data(ticker, start_date=fetch_start, end_date=end_date, interval=interval_yf)
    
    # 2. Handle FX if needed
    if display_currency == "JPY" and not is_native_jpy:
        fx_series = fetch_fx_rate(start_date=fetch_start, end_date=end_date, interval=interval_yf)
        df = apply_fx_conversion(df, fx_series)
    
    # 3. Calculate Indicators
    df = calc_indicators(df, ma_period)
    
    # 4. Generate Signals
    df = gen_signals(df, chg_thr, rsi_thr, dev_thr, use_chg, use_rsi, use_ma, cond_mode)
    
    # 5. Run Simulation
    df = simulate(df, periodic_invest, signal_bonus)
    
    # 6. Extract Metrics
    metrics = {
        "latest":  float(df["Close"].iloc[-1]),
        "ma_last": float(df["MA_VAL"].iloc[-1]) if not pd.isna(df["MA_VAL"].iloc[-1]) else None,
        "dev_last": float(df["DEV"].iloc[-1]) if not pd.isna(df["DEV"].iloc[-1]) else None,
        "rsi_last": float(df["RSI"].iloc[-1]) if not pd.isna(df["RSI"].iloc[-1]) else None,
        "chg_last": float(df["PRICE_CHG"].iloc[-1]) if not pd.isna(df["PRICE_CHG"].iloc[-1]) else None,
        "sig_count": int(df["Signal"].sum()),
        "is_signal": bool(df["Signal"].iloc[-1]),
        "actual_start": df.index[0].date(),
    }
    
    return df, metrics
