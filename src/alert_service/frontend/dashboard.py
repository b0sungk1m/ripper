# dashboard.py
import panel as pn
import pandas as pd
import numpy as np
import requests
import os
from src.alert_service.frontend.websocket_client import set_update_callback, run_ws_client_in_background, websocket_shutdown
import signal
import sys
import asyncio

def load_data():
    """
    Fetch all alerts from the REST API endpoint on the VM and return a DataFrame.
    """
    try:
        response = requests.get(REST_ALERTS_URL)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
    except Exception as e:
        print("Error fetching alerts from REST endpoint:", e)
        df = pd.DataFrame()
    
    # Convert timestamp columns (stored as strings) to datetime and then compute the HH:MM difference.
    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    for col in timestamp_cols:
        if col in df.columns:
            # Convert the column to datetime in UTC.
            df[col] = pd.to_datetime(df[col], utc=True, errors='coerce')

    df = alter_data(df)
    # reorder and rename columns
    col_order = ["alert_count",
                 "symbol",
                 "first_alert_time_ago",
                 "last_alert_time_ago",
                 "first_alert_price",
                 "current_price",
                 "ath_multiplier",
                 "curr_multiplier",
                 "avg_purchase_size",
                 "last_update_time_ago"
    ]
    df = reorder_and_rename_df(df, col_order)
    return df

def refresh_data(event):
    global local_df
    local_df = load_data()          # Reload full data from REST
    data_table.value = local_df.copy()  # Update the table with a fresh copy
    print("Data refreshed.")

def reorder_and_rename_df(df, first_columns, rename_map=None):
    """
    Reorder the DataFrame so that the columns in `first_columns` appear first in the specified order,
    and all other columns follow in their original order.
    
    Optionally, rename columns using rename_map, a dict mapping original column names to new names.
    
    Parameters:
      df: the original DataFrame.
      first_columns: list of column names that should come first.
      rename_map: dictionary mapping column names to new names (optional).
    
    Returns:
      A new DataFrame with reordered (and optionally renamed) columns.
    """
    # Get the rest of the columns in their original order.
    remaining_columns = [col for col in df.columns if col not in first_columns]
    # New order is the desired columns first, then the remaining.
    new_order = first_columns + remaining_columns
    df = df[new_order]
    if rename_map:
        df = df.rename(columns=rename_map)
    return df

def alter_data(df):
    if 'address' in df.columns:
        df['dexscreener_link'] = df['address'].apply(
            lambda addr: f"https://dexscreener.com/solana/{addr}"
        )
    # Define the timestamp columns that should be converted.
    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    for col in timestamp_cols:
        if col in df.columns:
            # Create a new column with the relative "ago" value.
            df[f'{col}_ago'] = df[col].apply(format_timedelta)
    
    df['avg_purchase_size'] = np.where(df['alert_count'] == 0, 0, df['purchase_size'] / df['alert_count'])
    return df


def filter_data(event=None):
    global local_df
    local_df = alter_data(local_df)
    if symbol_filter.value.strip():
        local_df = local_df[local_df['symbol'].str.contains(symbol_filter.value, case=False, na=False)]
    if active_filter.value:
        local_df = local_df[local_df['active_watchlist'] == True]
    local_df = local_df.copy()
    data_table.value = local_df

def timestamp_update():
    global local_df
    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    for col in timestamp_cols:
        if col in local_df.columns:
            # Create a new column with the relative "ago" value.
            local_df[f'{col}_ago'] = local_df[col].apply(format_timedelta)

def timestamp_callback(event=None):
    timestamp_update()

def update_callback(payload):
    """
    This callback is called when the WS client receives a delta update.
    It merges the delta into the local_df DataFrame and refreshes the data_table.
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
                    # Convert timestamps to datetime objects for easier comparison.
                    val = format_timestamp_from_seconds(val)
                print(f"Updating {key} for address {address} with value {val}")
                local_df.at[idx, key] = val
            else:
                print(f"Skipping {key} for address {address} with value {val}")
    # Assign a fresh copy so Panel detects the change.
    timestamp_update()
    data_table.value = local_df.copy()
    print(f"Updated row for address {address} with delta: {payload}")

def format_timestamp_from_seconds(seconds):
    """
    Assumes seconds is a pandas datetime second past epoch in UTC.
    """
    # Convert Unix timestamp in seconds to a UTC datetime string "YYYY-MM-DD HH:MM:SS"
    dt_obj = pd.to_datetime(seconds, unit='s', utc=True)
    return dt_obj

def format_timedelta(dt_val):
    """
    Calculate the difference between now (UTC) and the datetime value (dt_val)
    and return a string in "HH:MM" format.
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

def shutdown_handler(signum, frame):
    print("Shutting down dashboard gracefully...")
    loop = asyncio.get_event_loop()
    loop.create_task(websocket_shutdown())
    sys.exit(0)

def row_click_callback(event):
    # Use the row index provided by the event:
    row_index = event.row
    # Get the row data from the global DataFrame:
    row_data = local_df.iloc[row_index]
    if row_data is None or "address" not in row_data:
        return
    address = row_data["address"]
    embed_html = f"""
    <style>
      #dexscreener-embed {{
        position: relative;
        width: 100%;
        padding-bottom: 125%;
      }}
      @media(min-width:1400px) {{
        #dexscreener-embed {{
          padding-bottom: 65%;
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

pn.extension('tabulator', sizing_mode="stretch_width")
# REST endpoint URL for full data fetch; replace <YOUR_VM_PUBLIC_IP> with the actual IP.
REST_ALERTS_URL = os.environ.get("ALERTS_URL", "http://172.184.170.40:3000/alerts")
# Initial full data load.
local_df = load_data()

bokeh_formatters = {
    'active_watchlist': {'type': 'tickCross'},
    # Use the link formatter for the "symbol" column:
    'symbol': {
         'type': 'link',
         'target': '_blank',
         'labelField': 'symbol',       # Display the symbol text.
         'urlField': 'dexscreener_link'  # Use the URL from the dexscreener_link column.
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
    hidden_columns=['address', 'dexscreener_link', 'channel_HighConviction', 'channel_EarlyAlpha', 'channel_5xSMWallet', 'channel_SmartFollowers', 'channel_KimchiTest',
                    'isMoni', 'isNansen', 'first_alert_time', 'last_alert_time', 'last_update_time'],
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
        "active_watchlist": "Active"
    },
    formatters=bokeh_formatters
)

symbol_filter = pn.widgets.TextInput(name="Symbol Filter", placeholder="Enter symbol substring")
active_filter = pn.widgets.Checkbox(name="Active Only", value=True)
embed_pane = pn.pane.HTML("", sizing_mode="stretch_width", height=400)
data_table.on_click(row_click_callback)

symbol_filter.param.watch(filter_data, 'value')
active_filter.param.watch(filter_data, 'value')

# callback to filter data but we dont need this right now
pn.state.add_periodic_callback(filter_data, period=10000)
pn.state.add_periodic_callback(timestamp_callback, period=60000)

template = pn.template.FastListTemplate(
    title="Ripper",
    header_background="#808000",
    theme="dark",
    accent="#90ee90",
    main_max_width="1200px",
    sidebar=[]
)

header = pn.pane.HTML("<h1 style='text-align: center; margin: 20px 0;'>Alert Dashboard</h1>", sizing_mode="stretch_width")
# Use an HSpacer to push the button to the right.
refresh_button = pn.widgets.Button(name="Refresh Data", button_type="primary")
refresh_button.on_click(refresh_data)
controls = pn.Row(
    symbol_filter,
    active_filter,
    pn.layout.HSpacer(),  # This spacer will expand and push the refresh button to the right.
    refresh_button,
    sizing_mode="stretch_width"
)
layout = pn.Column(
    header,
    controls,
    data_table,
    pn.Spacer(height=20),
    embed_pane,
    sizing_mode="stretch_both"
)
template.main.append(layout)
template.servable(title="Ripper")
# Register the shutdown handler for SIGINT (Ctrl+C)
signal.signal(signal.SIGINT, shutdown_handler)


# Register the update callback with the WebSocket client.
set_update_callback(update_callback)

# Start the WS client in the background.
run_ws_client_in_background()