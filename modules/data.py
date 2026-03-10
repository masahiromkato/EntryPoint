import pandas as pd
import yfinance as yf
import datetime
from dataclasses import dataclass


@dataclass
class StockData:
    """分析データとメタデータを保持するデータモデル。"""
    df: pd.DataFrame
    ticker: str
    currency: str
    interval: str

    @property
    def index(self) -> pd.Index: return self.df.index
    @property
    def close(self) -> pd.Series: return self.df["Close"]
    @property
    def open(self) -> pd.Series: return self.df["Open"] if "Open" in self.df.columns else None
    @property
    def high(self) -> pd.Series: return self.df["High"] if "High" in self.df.columns else None
    @property
    def low(self) -> pd.Series: return self.df["Low"] if "Low" in self.df.columns else None
    
    # 指標系
    @property
    def ma(self) -> pd.Series: return self.df.get("MA_VAL")
    @property
    def rsi(self) -> pd.Series: return self.df.get("RSI")
    @property
    def dev(self) -> pd.Series: return self.df.get("DEV")
    @property
    def price_chg(self) -> pd.Series: return self.df.get("PRICE_CHG")
    
    # シグナル系
    @property
    def signal(self) -> pd.Series: return self.df.get("Signal")
    @property
    def sig_ma(self) -> pd.Series: return self.df.get("Sig_MA")
    @property
    def sig_rsi(self) -> pd.Series: return self.df.get("Sig_RSI")
    @property
    def sig_chg(self) -> pd.Series: return self.df.get("Sig_CHG")
    
    # シミュレーション系
    @property
    def dca_val(self) -> pd.Series: return self.df.get("DCA_Val")
    @property
    def sig_val(self) -> pd.Series: return self.df.get("Sig_Val")

    def copy(self) -> 'StockData':
        return StockData(df=self.df.copy(), ticker=self.ticker, currency=self.currency, interval=self.interval)

    def slice_range(self, start_date: datetime.date, end_date: datetime.date) -> 'StockData':
        mask = (self.df.index.date >= start_date) & (self.df.index.date <= end_date)
        return StockData(
            df=self.df[mask].copy(),
            ticker=self.ticker,
            currency=self.currency,
            interval=self.interval
        )


class DataFetchError(Exception):
    """Exception raised when data fetching fails."""
    pass


def _safe_download(ticker: str, start: datetime.date, end: datetime.date, interval: str, min_len: int = 0) -> pd.DataFrame:
    """yfinance でデータ取得。MultiIndex対応・空チェック・最小件数チェック付き。"""
    try:
        raw = yf.download(
            ticker,
            start=start,
            end=end + datetime.timedelta(days=1),
            interval=interval,
            auto_adjust=True,
            progress=False,
        )
    except Exception as e:
        raise DataFetchError(f"通信エラー: {ticker} のデータの取得に失敗しました。({str(e)})")

    if raw is None or raw.empty:
        raise DataFetchError(f"銘柄 {ticker} のデータが見つからないか、指定期間内に存在しません。")

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

    # 最小件数チェック
    if len(df) < min_len:
        raise DataFetchError(
            f"データ件数が不足しています（取得: {len(df)}件 / 必要: {min_len}件）。"
            "分析期間を長くするか、移動平均期間（MA）を短くしてください。"
        )

    return df


def fetch_data(ticker: str, start: datetime.date, end: datetime.date, interval: str, ma_period: int = 0) -> pd.DataFrame:
    """
    外部（logic.py）向けのインターフェース。
    MA期間を考慮した最小データ件数（MA + 10日）を自動的に検証します。
    """
    min_len = ma_period + 10 if ma_period > 0 else 0
    return _safe_download(ticker, start, end, interval, min_len=min_len)


def fetch_ticker_name(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ""
    except Exception:
        return ""


def fetch_fx_rate(start: datetime.date, end: datetime.date, interval: str) -> pd.Series:
    """USD/JPY レートを取得。失敗時は DataFetchError。"""
    try:
        # 為替データは最小件数チェックを緩める（計算不能回避のため空でなければOKとする）
        df = _safe_download("JPY=X", start, end, interval, min_len=1)
    except DataFetchError as e:
        raise DataFetchError(f"為替レート（JPY=X）の取得に失敗しました: {str(e)}")

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
