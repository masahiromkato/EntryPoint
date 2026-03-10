import datetime
import pandas as pd
from dataclasses import dataclass
from typing import Optional
from modules.data import fetch_data, fetch_fx_rate, apply_fx_conversion, StockData
from modules.indicators import calc_ma, calc_rsi, calc_deviation, calc_price_chg, gen_signals
from modules.simulation import simulate

@dataclass
class AnalysisMetrics:
    latest: float
    ma_last: Optional[float]
    dev_last: Optional[float]
    rsi_last: Optional[float]
    chg_last: Optional[float]
    sig_count: int
    is_signal: bool
    actual_start: datetime.date

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
) -> tuple[StockData, AnalysisMetrics]:
    """
    Consolidated analysis pipeline. Fetches data, calculates indicators, 
    generates signals, and runs simulation. Returns (stock_data, metrics).
    """
    
    # 1. Fetch Price Data
    # Calculate buffer for MA
    buffer_days = (
        ma_period * 31 if interval_yf == "1mo"
        else ma_period * 7 + 30 if interval_yf == "1wk"
        else int(ma_period * 1.5 + 30)
    )
    fetch_start = start_date - datetime.timedelta(days=buffer_days)
    
    df = fetch_data(ticker, start=fetch_start, end=end_date, interval=interval_yf, ma_period=ma_period)
    
    # 2. Handle FX if needed
    if display_currency == "JPY" and not is_native_jpy:
        fx_series = fetch_fx_rate(start_date=fetch_start, end_date=end_date, interval=interval_yf)
        df = apply_fx_conversion(df, fx_series)

    # Wrap in StockData early to use properties during calculation
    stock_data = StockData(
        df=df,
        ticker=ticker,
        currency=display_currency,
        interval=interval_yf
    )
    
    # 3. Calculate Indicators
    df["MA_VAL"]    = calc_ma(stock_data.close, ma_period)
    df["RSI"]       = calc_rsi(stock_data.close, 14)
    df["DEV"]       = calc_deviation(stock_data.close, stock_data.ma)
    df["PRICE_CHG"] = calc_price_chg(stock_data.close)
    
    # --- Filter to selected range for all downstream logic (signals, simulation, stats) ---
    stock_data = stock_data.slice_range(start_date, end_date)
    df = stock_data.df # Sync local df reference
    
    # 4. Generate Signals
    sig_df = gen_signals(
        prices=stock_data.close,
        ma=stock_data.ma,
        rsi=stock_data.rsi,
        dev=stock_data.dev,
        price_chg=stock_data.price_chg,
        dev_thr=dev_thr,   use_ma=use_ma,
        rsi_thr=rsi_thr,   use_rsi=use_rsi,
        chg_thr=chg_thr,   use_chg=use_chg,
        mode=cond_mode
    )
    stock_data.df = df.join(sig_df)
    
    # 5. Run Simulation
    sim_results = simulate(
        prices=stock_data.close, 
        signals=stock_data.signal, 
        periodic_invest=periodic_invest, 
        signal_bonus=signal_bonus
    )
    stock_data.df = stock_data.df.join(sim_results)
    
    # 6. Extract Metrics
    metrics = AnalysisMetrics(
        latest=float(stock_data.close.iloc[-1]),
        ma_last=float(stock_data.ma.iloc[-1]) if not pd.isna(stock_data.ma.iloc[-1]) else None,
        dev_last=float(stock_data.dev.iloc[-1]) if not pd.isna(stock_data.dev.iloc[-1]) else None,
        rsi_last=float(stock_data.rsi.iloc[-1]) if not pd.isna(stock_data.rsi.iloc[-1]) else None,
        chg_last=float(stock_data.price_chg.iloc[-1]) if not pd.isna(stock_data.price_chg.iloc[-1]) else None,
        sig_count=int(stock_data.signal.sum()),
        is_signal=bool(stock_data.signal.iloc[-1]),
        actual_start=stock_data.index[0].date(),
    )
    
    return stock_data, metrics
