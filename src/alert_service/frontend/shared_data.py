# shared_data.py
import pandas as pd

# This global variable will hold the local DataFrame from your dashboard.
local_df = pd.DataFrame()

def set_local_df(df: pd.DataFrame):
    global local_df
    local_df = df.copy()

def get_local_symbols():
    """Return a list of unique symbols from the shared local_df."""
    if not local_df.empty and "symbol" in local_df.columns:
        return list(local_df["symbol"].unique())
    return []

def get_local_df():
    return local_df.copy()