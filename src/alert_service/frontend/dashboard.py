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
from watchlist_tab import get_watchlist_tab, get_watchlist_panel
from shared_data import set_local_df
# Enable Panel extensions with Tabulator support.
pn.extension('tabulator', sizing_mode="stretch_width")

# REST endpoint URL for full data fetch.
REST_ALERTS_URL = os.environ.get("ALERTS_URL", "http://172.184.170.40:3000/alerts")

# --------------------- Data Functions ---------------------
def load_data():
    """
    Fetch all alerts from the REST API endpoint and return a DataFrame.
    Timestamps are parsed as UTC and then processed.
    """
    try:
        response = requests.get(REST_ALERTS_URL)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
    except Exception as e:
        print("Error fetching alerts from REST endpoint:", e)
        df = pd.DataFrame()
    
    # Convert timestamp columns to UTC datetime.
    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    for col in timestamp_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors='coerce')
    
    df = alter_data(df)
    
    # Reorder columns: desired ones first.
    col_order = [
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
        "favorited"
    ]
    df = reorder_and_rename_df(df, col_order)
    return df

def reorder_and_rename_df(df, first_columns, rename_map=None):
    remaining_columns = [col for col in df.columns if col not in first_columns]
    new_order = first_columns + remaining_columns
    df = df[new_order]
    if rename_map:
        df = df.rename(columns=rename_map)
    return df

def alter_data(df):
    # Create a dexscreener link from the address.
    if 'address' in df.columns:
        df['dexscreener_link'] = df['address'].apply(
            lambda addr: f"https://dexscreener.com/solana/{addr}"
        )
    # Load your watchlist and mark tokens as favorited.
    watchlist = load_watchlist()
    watchlist_addresses = {entry.get("address") for entry in watchlist}
    df['favorited'] = df['address'].apply(lambda addr: addr in watchlist_addresses)
    
    # Create "ago" columns for timestamps.
    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    for col in timestamp_cols:
        if col in df.columns:
            df[f'{col}_ago'] = df[col].apply(format_timedelta)
    
    df['avg_purchase_size'] = np.where(df['alert_count'] == 0, 0, df['purchase_size'] / df['alert_count'])
    return df

def format_timedelta(dt_val):
    """
    Return a string representing the time difference between now (UTC) and dt_val in "HH:MM" format.
    Assumes dt_val is a pandas datetime object in UTC.
    """
    if pd.isnull(dt_val):
        return None
    now = pd.Timestamp.now(tz='UTC')
    diff = now - dt_val
    total_minutes = int(diff.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"

# --------------------- Callbacks ---------------------
def refresh_data(event):
    global local_df
    local_df = load_data()
    data_table.value = local_df.copy()
    set_local_df(local_df)
    
    print("Data refreshed.")

def filter_data(event=None):
    global local_df
    local_df = alter_data(local_df)
    if symbol_filter.value.strip():
        local_df = local_df[local_df['symbol'].str.contains(symbol_filter.value, case=False, na=False)]
    if active_filter.value:
        local_df = local_df[local_df['active_watchlist'] == True]
    local_df = local_df.copy()
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
    """
    Update callback for WebSocket delta updates.
    """
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
    sys.exit(0)

# --------------------- Row Click & Toggle Callback ---------------------
def row_click_callback(event):
    """
    Row click callback to update the embed chart when a row (other than favorite) is clicked.
    """
    # If the clicked column is "favorited", we skip here.
    if event.column == "favorited":
        return
    row_index = event.row
    row_data = local_df.iloc[row_index]
    if row_data is None or "address" not in row_data:
        return
    address = row_data["address"]
    embed_html = f"""
    <style>
      #dexscreener-embed {{
        position: relative;
        width: 100%;
        height: 450px;
      }}
      @media (max-width: 1400px) {{
        #dexscreener-embed {{
            height: 500px;
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
      <iframe src="https://dexscreener.com/solana/{address}?embed=1&loadChartSettings=1&trades=0&chartLeftToolbar=0&chartTheme=dark&theme=dark&chartStyle=1&chartType=usd&interval=15"></iframe>
    </div>
    """
    embed_pane.object = embed_html
    print(f"Embed updated for address: {address}")

def toggle_favorite_callback(event):
    """
    Callback to toggle the "favorited" status when the user clicks on the "favorited" cell.
    """
    # Get the row index from the event.
    row_index = event.row
    address = local_df.iloc[row_index]["address"]
    current_value = local_df.iloc[row_index]["favorited"]
    new_value = not current_value
    local_df.at[row_index, "favorited"] = new_value
    if new_value:
        # Add token to watchlist.
        entry = {"address": address, "symbol": local_df.iloc[row_index]["symbol"], "notes": ""}
        add_to_watchlist(entry)
    else:
        remove_from_watchlist(address)
    data_table.value = local_df.copy()
    set_local_df(local_df)
    watchlist_panel_container.objects = get_watchlist_panel().objects

def cell_click_callback(event):
    """
    Combined callback: If the clicked cell is in the "favorited" column, toggle it.
    Otherwise, treat the click as a row selection to update the embed chart.
    """
    if event.column == "favorited":
        toggle_favorite_callback(event)
    else:
        row_click_callback(event)

# --------------------- Dashboard Layout ---------------------
# Initial full data load.
local_df = load_data()
print(f"Setting local_df on dashboard startup")
set_local_df(local_df)

bokeh_formatters = {
    'active_watchlist': {'type': 'tickCross'},
    'favorited': {'type': 'tickCross'},
    'symbol': {
         'type': 'link',
         'target': '_blank',
         'labelField': 'symbol',
         'urlField': 'dexscreener_link'
    },
    'alert_count': {
        'type': 'custom',
        'formatter': """
          function(cell, formatterParams, onRendered) {
              var value = cell.getValue();
              if (value === 0) {
                  return "🌱";
              } else {
                  return "🔁 (" + value + ")";
              }
          }
        """,
        'sorter': 'number'
    },
}

data_table = pn.widgets.Tabulator(
    local_df, 
    pagination='local', 
    page_size=20,
    layout='fit_data',
    text_align='center',
    show_index=False,
    disabled=True,
    hidden_columns=[
        'address', 'dexscreener_link', 'channel_HighConviction', 'channel_EarlyAlpha', 
        'channel_5xSMWallet', 'channel_SmartFollowers', 'channel_KimchiTest',
        'isMoni', 'isNansen', 'first_alert_time', 'last_alert_time', 'last_update_time'
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
        "active_watchlist": "Active",
        "favorited": "Fav"
    },
    formatters=bokeh_formatters
)

# Create control widgets.
symbol_filter = pn.widgets.TextInput(name="Symbol Filter", placeholder="Enter symbol substring")
active_filter = pn.widgets.Checkbox(name="Active Only", value=True)
refresh_button = pn.widgets.Button(name="Refresh Data", button_type="primary")
refresh_button.on_click(refresh_data)

# Embed pane for the chart.
embed_pane = pn.pane.HTML("", sizing_mode="stretch_width", height=400)

# Register the combined cell click callback.
data_table.on_click(cell_click_callback)

# Watch for filter changes.
symbol_filter.param.watch(filter_data, 'value')
active_filter.param.watch(filter_data, 'value')

pn.state.add_periodic_callback(filter_data, period=10000)
pn.state.add_periodic_callback(timestamp_callback, period=60000)

# Wrap the table in a container (with a fixed height for scrolling).
table_container = pn.Column(
    data_table,
    sizing_mode="stretch_both",
    height=600
)

controls = pn.Row(
    symbol_filter,
    active_filter,
    pn.layout.HSpacer(),
    refresh_button,
    sizing_mode="stretch_width"
)

# Build the Alerts tab layout.
alerts_tab = pn.Column(
    controls,
    embed_pane,      # Embed chart container at the top.
    pn.Spacer(height=10),
    table_container,
    sizing_mode="stretch_both"
)

# Combine the Alerts tab with the Watchlist tab imported from watchlist_tab.py.
dashboard_tabs = pn.Tabs(
    ("Alerts", alerts_tab),
    ("Watchlist", get_watchlist_tab()),
    sizing_mode="stretch_both",
    min_width=1200
)

template = pn.template.FastGridTemplate(
    title="Ripper",
    header_background="#808000",
    theme="dark",
    accent="#90ee90"
)
# Create a global watchlist container.
watchlist_panel_container = pn.Column(*get_watchlist_panel().objects, sizing_mode="stretch_both")

template.main[:5, :2] = watchlist_panel_container
template.main[:5, 2:] = dashboard_tabs
template.servable(title="Ripper")

# --------------------- Shutdown and WebSocket Setup ---------------------
def shutdown_handler(signum, frame):
    print("Shutting down dashboard gracefully...")
    loop = asyncio.get_event_loop()
    loop.create_task(websocket_shutdown())
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)

set_update_callback(update_callback)
run_ws_client_in_background()