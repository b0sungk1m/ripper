import panel as pn
import pandas as pd
import numpy as np
import requests
import os
import signal
import sys
import asyncio
from bokeh.models.widgets.tables import NumberFormatter, BooleanFormatter
from src.alert_service.frontend.websocket_client import set_update_callback, run_ws_client_in_background, websocket_shutdown
from watchlist import load_watchlist, add_to_watchlist, remove_from_watchlist, update_watchlist_notes
from watchlist_tab import get_watchlist_tab, get_watchlist_accordion, refresh_watchlist
from shared_data import set_local_df
from token_crawler import TokenCrawler
from concurrent.futures import ThreadPoolExecutor

NO_HEADER_RAW_CSS = """
nav#header {
    display: none;
}
"""

MAXIMIZE_FIRST_PANEL = """
.bk-root {
    height: calc(100vh - 50px) !important;
}
"""

pn.extension('tabulator', sizing_mode="stretch_height", raw_css=[NO_HEADER_RAW_CSS, MAXIMIZE_FIRST_PANEL])

REST_ALERTS_URL = os.environ.get("ALERTS_URL", "http://172.184.170.40:3000/alerts")
token_crawler = TokenCrawler(headless=True)

def load_data():
    try:
        response = requests.get(REST_ALERTS_URL)
        response.raise_for_status()
        data = response.json()
        print(f"Data loaded with {len(data)} alerts")
        df = pd.DataFrame(data)
    except Exception as e:
        print("Error fetching alerts from REST endpoint:", e)
        df = pd.DataFrame()
    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    for col in timestamp_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors='coerce')
    df = alter_data(df)
    col_order = [
        "favorited",
        "alert_count",
        "symbol",
        "first_alert_time_ago",
        "last_alert_time_ago",
        "first_alert_price",
        "current_price",
        "ath_multiplier",
        "curr_multiplier",
        "avg_purchase_size",
        "last_update_time_ago",
        "chain"
    ]
    df = reorder_and_rename_df(df, col_order)
    print(f"Data loaded with {len(df)} alerts")
    return df

def reorder_and_rename_df(df, first_columns, rename_map=None):
    remaining_columns = [col for col in df.columns if col not in first_columns]
    new_order = first_columns + remaining_columns
    df = df[new_order]
    if rename_map:
        df = df.rename(columns=rename_map)
    return df

def alter_data(df):
    # Add dexscreener link column
    if 'address' in df.columns:
        df['dexscreener_link'] = df.apply(
            lambda row: f"https://dexscreener.com/{'avalanche' if row['address'].startswith('0x') else row['chain']}/{row['address']}",
            axis=1
        )
    
    # Initialize favorited column
    watchlist = load_watchlist()
    watchlist_addresses = {entry.get("address") for entry in watchlist}
    df['favorited'] = df['address'].apply(lambda addr: addr in watchlist_addresses)

    # Add time ago columns
    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    for col in timestamp_cols:
        if col in df.columns:
            df[f'{col}_ago'] = df[col].apply(format_timedelta)

    # Calculate avg_purchase_size
    df['avg_purchase_size'] = np.where(df['alert_count'] == 0, 0, df['purchase_size'] / df['alert_count'])
    return df

def format_timedelta(dt_val):
    if pd.isnull(dt_val):
        return None
    now = pd.Timestamp.now(tz='UTC')
    diff = now - dt_val
    total_minutes = int(diff.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"

def refresh_data(event):
    global local_df
    local_df = load_data()
    data_table.value = local_df.copy()
    set_local_df(local_df)
    print("Data refreshed.")

def filter_data(event=None):
    global local_df
    local_df = alter_data(local_df)
    data_table.value = local_df
    set_local_df(local_df)

def timestamp_update():
    global local_df
    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    for col in timestamp_cols:
        if col in local_df.columns:
            local_df[f'{col}_ago'] = local_df[col].apply(format_timedelta)

def timestamp_callback(event=None):
    timestamp_update()

def format_timestamp_from_seconds(seconds):
    return pd.to_datetime(seconds, unit='s', utc=True)

def update_callback(payload):
    timestampcols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    global local_df
    address = payload.get("address")
    if not address:
        return
    matches = local_df.index[local_df['address'] == address].tolist()
    if not matches:
        print(f"Address {address} not in local_df; performing full refresh.")
        local_df = load_data()
    else:
        idx = matches[0]
        for key, val in payload.items():
            if key != "address" and key in local_df.columns:
                if key in timestampcols:
                    val = format_timestamp_from_seconds(val)
                print(f"Updating {key} for address {address} with value {val}")
                local_df.at[idx, key] = val
            else:
                print(f"Skipping {key} for address {address} with value {val}")
    timestamp_update()
    data_table.value = local_df.copy()
    set_local_df(local_df)
    print(f"Updated row for address {address} with delta: {payload}")

def shutdown_handler(signum, frame):
    print("Shutting down dashboard gracefully...")
    loop = asyncio.get_event_loop()
    loop.create_task(websocket_shutdown())
    token_crawler.cleanup()
    sys.exit(0)

def row_click_callback(event):
    if event.column == "favorited":
        return
    row_index = event.row
    row_data = local_df.iloc[row_index]
    if row_data is None or "address" not in row_data:
        return
    address = row_data["address"]
    chain = row_data["chain"]
    if chain is None:
        if address.startswith("0x"):
            chain = "avalanche"
        else:
            chain = "solana"

    token_pane.object = """
    <div id="loading-screen" style="display: flex; justify-content: center; align-items: center; height: 100%;">
        <h2>Loading...</h2>
    </div>
    """
    print(f"Embed updating for address: {address}")
    embed_html = f"""
    <style>
      #dexscreener-embed {{
        position: relative;
        width: 100%;
        height: 550px;
      }}
      @media (max-width: 1400px) {{
        #dexscreener-embed {{
            height: 550px;
        }}
      }}
      #dexscreener-embed iframe {{
        position: absolute;
        width: 100%;
        height: 100%;
        top: 0;
        left: 0;
        border: 0;
      }}
    </style>
    <div id="dexscreener-embed">
      <iframe src="https://dexscreener.com/{chain}/{address}?embed=1&loadChartSettings=1&trades=0&chartLeftToolbar=0&chartTheme=dark&theme=dark&chartStyle=1&chartType=usd&interval=5"></iframe>
    </div>
    """
    embed_pane.object = embed_html
    if address.startswith("0x"):
        return
    token_pane.object = token_crawler.get_pane_data(address)

def toggle_favorite_callback(event):
    row_index = event.row
    address = local_df.iloc[row_index]["address"]
    current_value = local_df.iloc[row_index]["favorited"]
    new_value = not current_value
    local_df.at[row_index, "favorited"] = new_value
    if new_value:
        entry = {"address": address, "symbol": local_df.iloc[row_index]["symbol"], "notes": ""}
        add_to_watchlist(entry)
    else:
        remove_from_watchlist(address)
    data_table.value = local_df.copy()
    set_local_df(local_df)
    refresh_watchlist()

def cell_click_callback(event):
    if event.column == "favorited":
        toggle_favorite_callback(event)
    else:
        row_click_callback(event)

local_df = load_data()
print(f"Setting local_df on dashboard startup")
set_local_df(local_df)

bokeh_formatters = {
    'favorited': {'type': 'tickCross'},
    'symbol': {
         'type': 'link',
         'target': '_blank',
         'labelField': 'symbol',
         'urlField': 'dexscreener_link'
    },
    'ath_multiplier': NumberFormatter(format="0.0"),
    'curr_multiplier': NumberFormatter(format="0.0"),
    'avg_purchase_size': NumberFormatter(format="0.0")
}

data_table = pn.widgets.Tabulator(
    local_df, 
    pagination='local', 
    page_size=50,
    layout='fit_columns',
    text_align='center',
    show_index=False,
    disabled=True,
    hidden_columns=[
        'address', 'dexscreener_link', 'channel_HighConviction', 'channel_EarlyAlpha', 
        'channel_5xSMWallet', 'channel_SmartFollowers', 'channel_KimchiTest',
        'isMoni', 'isNansen', 'first_alert_time', 'last_alert_time', 'last_update_time',
        'token_age', 'twitter_sentiment', 'rug_bundle_check', 'macd_line', 'macd_short', 'macd_long',
        'sm_buy_count', 'purchase_size', 'notes', 'website', 'twitter', 'summary', 'active_watchlist', 'volume_5min', 'volume_1hr'
    ],
    titles={
        "alert_count": "Count",
        "symbol": "Symbol",
        "first_alert_time_ago": "First Alert",
        "last_alert_time_ago": "Last Alert",
        "first_alert_price": "First Price",
        "current_price": "Current Price",
        "ath_multiplier": "ATH",
        "curr_multiplier": "CURR",
        "avg_purchase_size": "Buy Size",
        "last_update_time_ago": "Last Update",
        "favorited": "Fav"
    },
    formatters=bokeh_formatters,
    height=400,
)

symbol_filter = pn.widgets.TextInput(placeholder="Enter symbol", width=225)
refresh_button = pn.widgets.Button(name="↻", button_type="primary", width=35, height=35)
refresh_button.on_click(refresh_data)

embed_pane = pn.pane.HTML("", sizing_mode="stretch_both", height=410)
styles = {
    'background-color': 'black', 'border': '2px solid green',
    'border-radius': '5px', 'padding': '10px'
}
token_pane = pn.pane.HTML("", styles=styles, height=350, width=250)

data_table.on_click(cell_click_callback)

symbol_filter.param.watch(filter_data, 'value')

pn.state.add_periodic_callback(filter_data, period=10000)
pn.state.add_periodic_callback(timestamp_callback, period=60000)

table_container = pn.Row(
    data_table,
    token_pane
)

controls = pn.Row(
    symbol_filter,
    pn.layout.HSpacer(width=550),
    refresh_button,
    sizing_mode="stretch_width"
)

alerts_tab = pn.Column(
    controls,
    embed_pane,
    pn.Spacer(height=10),
    table_container,
    sizing_mode="stretch_both"
)

dashboard_tabs = pn.Tabs(
    ("Alerts", alerts_tab),
    ("Watchlist", get_watchlist_tab()),
    sizing_mode="stretch_both",
    min_width=1200
)

template = pn.template.FastGridTemplate(
    theme="dark",
    accent="#90ee90"
)

# Use the new accordion watchlist in the left panel.
watchlist_panel_container = pn.panel(get_watchlist_accordion, sizing_mode="stretch_both")

template.main[:7, :2] = watchlist_panel_container
template.main[:7, 2:] = dashboard_tabs
template.servable(title="Ripper")

def shutdown_handler(signum, frame):
    print("Shutting down dashboard gracefully...")
    loop = asyncio.get_event_loop()
    loop.create_task(websocket_shutdown())
    sys.exit(0)

import signal
signal.signal(signal.SIGINT, shutdown_handler)

from src.alert_service.frontend.websocket_client import set_update_callback, run_ws_client_in_background
set_update_callback(update_callback)
run_ws_client_in_background()