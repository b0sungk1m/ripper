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
/* Add styling for selected row */
.tabulator-row.tabulator-selected {
    background-color: #444 !important; /* Darker gray for selection */
}

.panel-widget-tabulator > .tabulator {
    tabindex: 0 !important; /* Make it programmatically focusable and via Tab key */
    outline: none; /* Optional: remove the default blue focus outline if you don't like it */
}

"""

pn.extension('tabulator', sizing_mode="stretch_height", raw_css=[NO_HEADER_RAW_CSS, MAXIMIZE_FIRST_PANEL])

REST_ALERTS_URL = os.environ.get("ALERTS_URL", "http://172.184.170.40:3000/alerts")
token_crawler = TokenCrawler(headless=True)

# --- Data Loading and Processing Functions (mostly unchanged) ---
def load_data():
    try:
        response = requests.get(REST_ALERTS_URL)
        response.raise_for_status()
        data = response.json()
        print(f"Data loaded with {len(data)} alerts")
        df = pd.DataFrame(data)
    except Exception as e:
        print("Error fetching alerts from REST endpoint:", e)
        df = pd.DataFrame() # Start with empty if error

    if df.empty:
        print("Loaded empty DataFrame, returning early.")
        return df # Return empty df if fetch failed or returned no data

    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    for col in timestamp_cols:
        if col in df.columns:
            # Ensure conversion happens even if data is mixed type
            df[col] = pd.to_datetime(df[col], utc=True, errors='coerce')

    # Drop rows where essential columns might be NaN after coerce
    df.dropna(subset=['address', 'chain'], inplace=True) # Ensure address/chain exist

    df = alter_data(df)
    col_order = [
        "favorited",
        "symbol",
        "alert_count",
        "last_update_time_ago",
        "first_alert_time_ago",
        "ath_multiplier",
        "curr_multiplier",
        "first_alert_price",
        "current_price",
        "avg_purchase_size",
        "chain"
    ]
    # Ensure all columns in col_order actually exist before reordering
    existing_cols_in_order = [col for col in col_order if col in df.columns]
    df = reorder_and_rename_df(df, existing_cols_in_order)
    print(f"Data processed with {len(df)} alerts remaining")
    return df

def reorder_and_rename_df(df, first_columns, rename_map=None):
    # Defensive check for empty df
    if df.empty:
        return df
    # Ensure first_columns exist in df before using them
    valid_first_columns = [col for col in first_columns if col in df.columns]
    remaining_columns = [col for col in df.columns if col not in valid_first_columns]
    new_order = valid_first_columns + remaining_columns
    df = df[new_order]
    if rename_map:
        df = df.rename(columns=rename_map)
    return df

def alter_data(df):
    if df.empty:
        return df

    # Add dexscreener link column
    if 'address' in df.columns and 'chain' in df.columns:
         # Ensure chain is suitable for URL (e.g., lowercase) - adjust if needed
        df['dexscreener_link'] = df.apply(
            lambda row: f"https://dexscreener.com/{str(row['chain']).lower()}/{row['address']}" if pd.notna(row['address']) and pd.notna(row['chain']) else None,
            axis=1
        )

    # Initialize favorited column
    watchlist = load_watchlist()
    watchlist_addresses = {entry.get("address") for entry in watchlist}
    if 'address' in df.columns:
        df['favorited'] = df['address'].apply(lambda addr: addr in watchlist_addresses if pd.notna(addr) else False)
    else:
        df['favorited'] = False # Add column even if address doesn't exist

    # Add time ago columns
    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    now = pd.Timestamp.now(tz='UTC') # Calculate 'now' once for efficiency
    for col in timestamp_cols:
        if col in df.columns:
            df[f'{col}_ago'] = df[col].apply(lambda dt: format_timedelta(dt, now))

    # Calculate avg_purchase_size
    if 'purchase_size' in df.columns and 'alert_count' in df.columns:
        df['avg_purchase_size'] = np.where(df['alert_count'] > 0, df['purchase_size'] / df['alert_count'], 0)
    else:
         df['avg_purchase_size'] = 0 # Add column even if source cols don't exist

    return df

def format_timedelta(dt_val, now): # Pass 'now' for efficiency
    if pd.isnull(dt_val):
        return "N/A" # Or None or ''
    # Ensure dt_val is timezone-aware (like now) or make now naive
    if dt_val.tzinfo is None:
        dt_val = dt_val.tz_localize('UTC') # Assume UTC if naive, adjust if needed

    diff = now - dt_val
    total_minutes = int(diff.total_seconds() // 60)
    if total_minutes < 0: # Handle potential clock skew or future dates
        return "Future?"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"

def refresh_data(event=None): # Added event=None for compatibility
    global local_df
    new_df = load_data()
    if not new_df.empty:
        local_df = new_df
        data_table.value = local_df.copy() # Update table value
        set_local_df(local_df) # Update shared data
        print("Data refreshed.")
        # Optionally, update chart if a row was previously selected
        # current_selection = data_table.selection
        # if current_selection:
        #     update_details_pane(current_selection[0])
    else:
        print("Refresh resulted in empty data. Table not updated.")

# Filter function needs refinement - currently just re-runs alter_data
# A proper filter would typically subset local_df based on filter input
def filter_data(event=None):
    global local_df
    # Example: Filter by symbol based on symbol_filter widget
    filter_value = symbol_filter.value_input.strip().lower() # Use value_input for TextInput
    if filter_value:
        # Make sure 'symbol' column exists and handle potential NaNs
        if 'symbol' in local_df.columns:
             filtered_df = local_df[local_df['symbol'].str.lower().str.contains(filter_value, na=False)]
        else:
            filtered_df = local_df.copy() # Or empty df if symbol essential
    else:
        filtered_df = local_df.copy() # Show all if filter is empty

    # Re-apply time formatting to the filtered view
    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    now = pd.Timestamp.now(tz='UTC')
    for col in timestamp_cols:
        if col in filtered_df.columns:
             filtered_df[f'{col}_ago'] = filtered_df[col].apply(lambda dt: format_timedelta(dt, now))

    # Update the table with the filtered data
    data_table.value = filtered_df
    # Do NOT update local_df here, local_df should hold the *full* dataset
    # set_local_df(local_df) # This line should maybe be removed from filter_data

def timestamp_update():
    global local_df
    if local_df.empty:
        return
    now = pd.Timestamp.now(tz='UTC')
    timestamp_cols = ['first_alert_time', 'last_alert_time', 'last_update_time']
    needs_update = False
    # Create a copy to modify, then assign back if needed
    df_copy = data_table.value.copy() # Update the *displayed* data
    if df_copy.empty: # If table is empty (e.g. after filtering everything)
        return

    for col in timestamp_cols:
        if col in local_df.columns: # Check against original df columns
            col_ago = f'{col}_ago'
            # Apply update to the table's current value (could be filtered)
            if col_ago in df_copy.columns and col in df_copy.columns:
                 df_copy[col_ago] = df_copy[col].apply(lambda dt: format_timedelta(dt, now))
                 needs_update = True

    if needs_update:
        # Update the table's value to refresh display
        data_table.value = df_copy

def timestamp_callback(event=None):
    timestamp_update()

def format_timestamp_from_seconds(seconds):
    try:
        # Attempt conversion, handle potential errors (non-numeric, etc.)
        return pd.to_datetime(seconds, unit='s', utc=True, errors='coerce')
    except (ValueError, TypeError):
        return pd.NaT # Return NaT on error

def update_callback(payload):
    global local_df
    address = payload.get("address")
    if not address or local_df.empty:
        return

    # Find index in the *master* DataFrame
    matches = local_df.index[local_df['address'] == address].tolist()

    if not matches:
        print(f"Address {address} not in local_df; performing full refresh.")
        # Consider if a full refresh is always desired here, or maybe just add the new row
        refresh_data() # This reloads and updates the table
    else:
        idx = matches[0] # Assuming unique addresses
        update_occurred = False
        timestampcols = ['first_alert_time', 'last_alert_time', 'last_update_time']

        for key, val in payload.items():
            if key != "address" and key in local_df.columns:
                original_value = local_df.at[idx, key]
                try:
                    if key in timestampcols:
                        new_val = format_timestamp_from_seconds(val)
                        # Check if conversion was successful before assigning
                        if pd.isna(new_val):
                             print(f"Skipping timestamp update for {key} due to conversion error for value: {val}")
                             continue # Skip this key
                    else:
                        # Try to cast to the column's type to avoid mixed types
                        col_type = local_df[key].dtype
                        try:
                             new_val = pd.Series([val]).astype(col_type)[0]
                        except Exception:
                             new_val = val # Assign as is if casting fails

                    # Only update if value actually changed
                    # Handle NaT/None comparison carefully
                    if pd.isna(original_value) and pd.isna(new_val):
                         changed = False
                    elif pd.isna(original_value) or pd.isna(new_val):
                         changed = True
                    else:
                         changed = original_value != new_val

                    if changed:
                        print(f"Updating {key} for address {address} from '{original_value}' to '{new_val}'")
                        local_df.at[idx, key] = new_val
                        update_occurred = True
                    # else:
                    #     print(f"Skipping update for {key} - value unchanged: {val}")

                except Exception as e:
                    print(f"Error processing update for key {key}, value {val}: {e}")
            # else:
                # print(f"Skipping key {key} (not in df or is address)")

        if update_occurred:
            # Re-apply dependent calculations like 'time_ago' and 'avg_purchase_size' for the updated row
            # This is complex to do efficiently in place. Re-running alter_data might be simpler if performance allows.
            # Quick fix: recalculate time_ago for the updated row
            now = pd.Timestamp.now(tz='UTC')
            for col in timestampcols:
                 if col in local_df.columns:
                    dt_val = local_df.at[idx, col]
                    local_df.at[idx, f'{col}_ago'] = format_timedelta(dt_val, now)

            if 'purchase_size' in local_df.columns and 'alert_count' in local_df.columns:
                 alert_count = local_df.at[idx, 'alert_count']
                 purchase_size = local_df.at[idx, 'purchase_size']
                 local_df.at[idx, 'avg_purchase_size'] = np.where(alert_count > 0, purchase_size / alert_count, 0)


            # Refresh the table *view* based on the current filter
            filter_data() # This will apply current filters to the updated local_df
            set_local_df(local_df) # Update shared data
            print(f"Updated row for address {address} via WS.")

            # Refresh watchlist if the favorited status might have changed (unlikely via WS?)
            # refresh_watchlist() # Uncomment if needed


def shutdown_handler(signum, frame):
    print("Shutting down dashboard gracefully...")
    if token_crawler:
        token_crawler.cleanup()
    # Ensure websocket shutdown is called, ideally awaiting it if possible
    # asyncio.run(websocket_shutdown()) # This might block, use loop if available
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(websocket_shutdown())
    else:
        asyncio.run(websocket_shutdown()) # Fallback if loop isn't running
    print("Shutdown complete.")
    sys.exit(0)

# --- NEW: Centralized function to update detail panes ---
def update_details_pane(row_index):
    """Updates the embed and token panes based on the selected row index."""
    global local_df # Use the global master dataframe
    # Use data_table.value as the source if filtering is active?
    # Let's stick to local_df for consistency, assuming index maps correctly.
    # If filtering *changes* indices, this needs care. Tabulator selection usually gives index *within the current view*.
    # We need the index in the *original* local_df.
    # Let's try getting the address from the *view* then finding it in local_df

    try:
        # Get data from the *currently displayed* table data
        current_table_df = data_table.value
        if row_index >= len(current_table_df):
            print(f"Error: Row index {row_index} out of bounds for current table view (len={len(current_table_df)}).")
            return

        row_data_view = current_table_df.iloc[row_index]
        address = row_data_view.get("address")

        if address is None:
             print(f"Error: Could not get address for view row index {row_index}.")
             return

        # Find the corresponding row in the master local_df using the address
        master_matches = local_df.index[local_df['address'] == address].tolist()
        if not master_matches:
            print(f"Error: Address {address} from view not found in master local_df.")
            # Fallback to using view data directly, though it might lack some columns
            row_data = row_data_view
        else:
            master_index = master_matches[0]
            row_data = local_df.loc[master_index] # Use .loc with the master index

    except IndexError:
        print(f"Error accessing row data at index {row_index}.")
        return
    except Exception as e:
        print(f"An unexpected error occurred in update_details_pane: {e}")
        return

    chain = row_data.get("chain", "solana") # Default to solana if chain missing
    # Simple heuristic if chain info is bad but address format is known
    if chain is None or pd.isna(chain):
         if isinstance(address, str) and address.startswith("0x"):
             chain = "avalanche" # Or ethereum? based on your data
         else:
             chain = "solana" # Default assumption

    print(f"Updating details for address: {address} on chain: {chain} (Row index in view: {row_index})")

    # Set loading message first
    embed_pane.object = """
    <div id="loading-screen" style="display: flex; justify-content: center; align-items: center; height: 100%;">
        <h4>Loading Dexscreener Chart...</h4>
    </div>
    """
    # Clear token pane or set loading state
    token_pane.object = """
    <div id="loading-screen-token" style="display: flex; justify-content: center; align-items: center; height: 100%;">
        <p>Loading token info...</p>
    </div>
    """


    # Use asyncio.create_task to load embed and token data concurrently
    # Check if loop is running before creating tasks
    try:
        loop = asyncio.get_running_loop()

        # Schedule the updates - they update the panes directly when done
        loop.create_task(load_embed_pane(chain, address))
        # Only load token pane if not an 0x address (assuming ETH/AVAX don't use it)
        if isinstance(address, str) and not address.startswith("0x"):
            loop.create_task(load_token_pane(address))
        else:
            token_pane.object = "<p>Token info not available for this chain/address.</p>" # Clear token pane if not applicable

    except RuntimeError: # No running event loop
         print("No running event loop found. Running updates sequentially.")
         # Fallback to sequential loading if no loop (e.g., script context)
         asyncio.run(load_embed_pane(chain, address))
         if isinstance(address, str) and not address.startswith("0x"):
              asyncio.run(load_token_pane(address))
         else:
              token_pane.object = "<p>Token info not available for this chain/address.</p>"


async def load_embed_pane(chain, address):
    """Loads the Dexscreener embed."""
    embed_html = f"""
    <style>
      #dexscreener-embed {{
        position: relative; width: 100%; height: 100%; /* Use 100% height */
        min-height: 500px; /* Ensure minimum height */
      }}
      #dexscreener-embed iframe {{
        position: absolute; width: 100%; height: 100%;
        top: 0; left: 0; border: 0;
      }}
    </style>
    <div id="dexscreener-embed">
      <iframe src="https://dexscreener.com/{chain}/{address}?embed=1&loadChartSettings=1&trades=0&chartLeftToolbar=0&chartTheme=dark&theme=dark&chartStyle=1&chartType=usd&interval=5"></iframe>
    </div>
    """
    embed_pane.object = embed_html
    print(f"Embed updated for: {address}")

async def load_token_pane(address):
    """Loads the token crawler data."""
    # This might still block if get_pane_data isn't async
    # Consider running token_crawler.get_pane_data in a thread pool executor
    # if it performs blocking I/O or computation
    try:
        # Example using ThreadPoolExecutor if get_pane_data is blocking
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
             token_data_html = await loop.run_in_executor(
                 pool, token_crawler.get_pane_data, address
             )
        token_pane.object = token_data_html
        print(f"Token pane updated for: {address}")
    except Exception as e:
        print(f"Error loading token pane for {address}: {e}")
        token_pane.object = f"<p>Error loading token info for {address}.</p>"


def toggle_favorite_callback(event):
    """Handles toggling the favorite status from cell click."""
    row_index = event.row # Index in the *current view*
    current_table_df = data_table.value

    try:
        if row_index >= len(current_table_df): return # Index out of bounds

        row_data_view = current_table_df.iloc[row_index]
        address = row_data_view.get("address")
        if not address: return # No address found

        # Find the index in the master local_df
        master_matches = local_df.index[local_df['address'] == address].tolist()
        if not master_matches:
             print(f"Cannot toggle favorite: Address {address} not found in master data.")
             return
        master_index = master_matches[0]

        current_value = local_df.loc[master_index, "favorited"]
        new_value = not current_value

        # Update the master DataFrame
        local_df.loc[master_index, "favorited"] = new_value

        # Update watchlist file
        symbol = local_df.loc[master_index, "symbol"]
        if new_value:
            entry = {"address": address, "symbol": symbol, "notes": ""} # Add other relevant fields if needed
            add_to_watchlist(entry)
            print(f"Added {symbol} ({address}) to watchlist.")
        else:
            remove_from_watchlist(address)
            print(f"Removed {symbol} ({address}) from watchlist.")

        # Update the displayed table data directly for immediate feedback
        # Need to get the index within the *current* table view again
        # This is tricky if sorting/filtering is active. Easiest is to refresh the table view.
        filter_data() # Re-applies filters/sorts to updated local_df

        # Update shared data and refresh the separate watchlist view
        set_local_df(local_df)
        refresh_watchlist()

    except Exception as e:
        print(f"Error in toggle_favorite_callback for row {row_index}: {e}")


# --- Callbacks for Table Interaction ---
def handle_selection_change(event):
    """Callback when table row selection changes (mouse or keyboard)."""
    selected_indices = event.new # List of selected row indices (in the view)
    if selected_indices:
        selected_row_index_in_view = selected_indices[0] # Get the first selected index
        print(f"Selection changed. New selected index in view: {selected_row_index_in_view}")
        update_details_pane(selected_row_index_in_view)
    else:
        print("Selection cleared.")
        # Optional: Clear detail panes when selection is cleared
        # embed_pane.object = "<div>Select a row to view details.</div>"
        # token_pane.object = ""


def handle_cell_click(event):
    """Callback for single clicks on any cell."""
    print(f"Cell clicked: Row {event.row}, Column {event.column}")
    if event.column == "favorited":
        toggle_favorite_callback(event)
    # else:
        # Selection change handles updating the panes now
        # You could add other single-click actions here if needed
        # update_details_pane(event.row) # This might be too sensitive on single click

def handle_double_click(event):
    """Callback for double clicks on a row."""
    print(f"Row double-clicked: Row {event.row}")
    # Double click implies intent to view details, like selection change
    update_details_pane(event.row)


# --- Load Initial Data ---
local_df = load_data()
print(f"Setting initial local_df on dashboard startup. Rows: {len(local_df)}")
set_local_df(local_df.copy() if not local_df.empty else pd.DataFrame()) # Pass copy or empty


# --- Define Table Formatters ---
# Using Panel's simplified formatter dict syntax
formatters = {
    'favorited': {'type': 'tickCross', 'hozAlign': 'center'}, # Center align the tick/cross
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

# --- Create Widgets and Panes ---
data_table = pn.widgets.Tabulator(
    local_df.copy() if not local_df.empty else pd.DataFrame(), # Start with data or empty DF
    pagination='local',
    page_size=30, # Adjust page size if needed
    layout='fit_columns',
    text_align='center',
    show_index=False,
    disabled=True,
    selectable=True,
    hidden_columns=[ # List columns to hide
        'address', 'dexscreener_link', 'channel_HighConviction', 'channel_EarlyAlpha',
        'channel_5xSMWallet', 'channel_SmartFollowers', 'channel_KimchiTest',
        'isMoni', 'isNansen', 'first_alert_time', 'last_alert_time', 'last_update_time',
        'token_age', 'twitter_sentiment', 'rug_bundle_check', 'macd_line', 'macd_short', 'macd_long',
        'sm_buy_count', 'purchase_size', 'notes', 'website', 'twitter', 'summary',
        'active_watchlist', 'volume_5min', 'volume_1hr',
        # Hide original timestamp columns if _ago versions are preferred
        # 'first_alert_time', 'last_alert_time', 'last_update_time'
    ],
    titles={ # Friendly column names
        "alert_count": "Count",
        "symbol": "Symbol",
        "first_alert_time_ago": "First Alert",
        "last_alert_time_ago": "Last Alert",
        "first_alert_price": "First Price",
        "current_price": "Current Price",
        "ath_multiplier": "ATH",
        "curr_multiplier": "CURR",
        "avg_purchase_size": "Avg Buy $",
        "last_update_time_ago": "Last Update",
        "favorited": "Fav",
        "chain": "Chain"
    },
    formatters=formatters,
    height=450,
    frozen_columns=['favorited'], # Freeze favorite column if desired
    sizing_mode="stretch_width" # Allow table to stretch
)

symbol_filter = pn.widgets.TextInput(placeholder="Filter Symbol (contains)...", width=150)
refresh_button = pn.widgets.Button(name="↻", button_type="primary", width=20, height=20)

# --- Embed and Token Panes ---
# Initial state for embed pane (Load first row's chart if data exists)
initial_embed_html = "<div>Select a row to view chart.</div>"
if not local_df.empty:
    try:
        first_row = local_df.iloc[0]
        address = first_row.get("address")
        chain = first_row.get("chain", "solana") # Default if missing
        if address and chain:
             # Generate initial iframe HTML directly
             initial_embed_html = f"""
                <style>
                #dexscreener-embed {{ position: relative; width: 100%; height: 100%; min-height: 500px; }}
                #dexscreener-embed iframe {{ position: absolute; width: 100%; height: 100%; top: 0; left: 0; border: 0; }}
                </style>
                <div id="dexscreener-embed">
                <iframe src="https://dexscreener.com/{chain}/{address}?embed=1&loadChartSettings=1&trades=0&chartLeftToolbar=0&chartTheme=dark&theme=dark&chartStyle=1&chartType=usd&interval=5"></iframe>
                </div>
             """
             print(f"Preloading chart for first row: {address}")
    except Exception as e:
        print(f"Could not preload first chart: {e}")


embed_pane = pn.pane.HTML(initial_embed_html, sizing_mode="stretch_both", min_height=530) # Ensure min height
styles = {
    'background-color': '#111', # Slightly lighter than pure black
    'border': '1px solid #333', # Subtle border
    'border-radius': '5px',
    'color': '#eee', # Light text color
    'font-size': '0.9em'
}
token_pane = pn.pane.HTML("Select a non-EVM token to view info.", styles=styles, height=350, width=250, sizing_mode="fixed") # Fixed size


# --- Connect Callbacks ---
refresh_button.on_click(refresh_data)

# Watch the 'value_input' for TextInput changes (debounced)
symbol_filter.param.watch(filter_data, 'value_input')

# Watch selection changes for updating panes
data_table.param.watch(handle_selection_change, 'selection')

# Handle specific cell clicks (like toggling favorite)
data_table.on_click(handle_cell_click)

# Periodic callbacks
# Consider increasing filter period if it causes performance issues
# pn.state.add_periodic_callback(filter_data, period=10000) # Filter might not need periodic trigger
pn.state.add_periodic_callback(timestamp_callback, period=30000) # Update timestamps every 30s


# --- Layout ---
table_container = pn.Row(
    data_table,
    token_pane
)

controls = pn.Row(
    symbol_filter,
    pn.layout.HSpacer(), # Push refresh button to the right
    refresh_button,
    sizing_mode="stretch_width",
)

alerts_tab = pn.Column(
    controls,
    embed_pane,
    pn.Row(table_container, margin=(-50, 0, 0, 0)),
    sizing_mode="stretch_both"
)

dashboard_tabs = pn.Tabs(
    ("Alerts", alerts_tab),
    ("Watchlist", get_watchlist_tab()), # Assuming this function returns a Panel layout
    sizing_mode="stretch_both",
    min_width=1200,
    dynamic=True
)

template = pn.template.FastGridTemplate(
    title="Ripper",
    theme="dark",
    accent_base_color="#90ee90",
    header_background="#1f1f1f",
)

# Use the new accordion watchlist in the left panel.
# Ensure get_watchlist_accordion returns a Panel object/layout
watchlist_panel_container = pn.panel(get_watchlist_accordion, sizing_mode="stretch_both")

# Adjust grid layout numbers if needed based on FastGridTemplate structure
template.main[0:7, 0:2] = watchlist_panel_container # Span rows 0-6, columns 0-1
template.main[0:7, 2:12] = dashboard_tabs # Span rows 0-6, columns 2-11 (adjust width as needed)


# --- Signal Handling and Background Tasks ---
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler) # Handle termination signal too

# Ensure update_callback is set before starting client
set_update_callback(update_callback)
run_ws_client_in_background()

# --- Serve the App ---
template.servable() # No need for explicit title here if set in Template constructor