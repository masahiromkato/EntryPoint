import pandas as pd


def simulate(prices: pd.Series, signals: pd.Series, periodic_invest: float, signal_bonus: float) -> pd.DataFrame:
    """
    Pure calculation engine for investment simulation.
    Takes price and signal Series, returns a DataFrame with simulation results.
    """
    valid = prices.notna()
    close = prices.loc[valid]
    sig   = signals.loc[valid]

    inv_dca = pd.Series(periodic_invest, index=close.index).cumsum()
    u_dca   = (periodic_invest / close).cumsum()
    extra   = sig.astype(float) * signal_bonus
    inv_sig = (periodic_invest + extra).cumsum()
    u_sig   = ((periodic_invest + extra) / close).cumsum()

    results = pd.DataFrame(index=prices.index)
    results.loc[valid, "DCA_Val"] = u_dca * close
    results.loc[valid, "Sig_Val"] = u_sig * close
    results.loc[valid, "DCA_Inv"] = inv_dca
    results.loc[valid, "Sig_Inv"] = inv_sig
    results.loc[valid, "DCA_ROI"] = (results.loc[valid, "DCA_Val"] / inv_dca - 1) * 100
    results.loc[valid, "Sig_ROI"] = (results.loc[valid, "Sig_Val"] / inv_sig - 1) * 100
    
    return results
