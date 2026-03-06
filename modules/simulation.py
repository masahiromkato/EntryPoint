import pandas as pd

def simulate(df: pd.DataFrame, periodic_invest: float, signal_bonus: float) -> pd.DataFrame:
    df    = df.copy()
    valid = df["Close"].notna()
    close = df.loc[valid,"Close"]
    sig   = df.loc[valid,"Signal"]

    inv_dca = pd.Series(periodic_invest, index=close.index).cumsum()
    u_dca   = (periodic_invest / close).cumsum()
    extra   = sig.astype(float) * signal_bonus
    inv_sig = (periodic_invest + extra).cumsum()
    u_sig   = ((periodic_invest + extra) / close).cumsum()

    df.loc[valid,"DCA_Val"] = u_dca * close
    df.loc[valid,"Sig_Val"] = u_sig * close
    df.loc[valid,"DCA_Inv"] = inv_dca
    df.loc[valid,"Sig_Inv"] = inv_sig
    df.loc[valid,"DCA_ROI"] = (df.loc[valid,"DCA_Val"] / inv_dca - 1) * 100
    df.loc[valid,"Sig_ROI"] = (df.loc[valid,"Sig_Val"] / inv_sig - 1) * 100
    return df
