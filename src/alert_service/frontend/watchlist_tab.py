# watchlist_tab.py
import panel as pn
import json
import os
from watchlist import load_watchlist, save_watchlist, add_to_watchlist, remove_from_watchlist, update_watchlist_notes
from shared_data import get_local_df  # Returns the dashboard’s local DataFrame

# ---------------------
# Utility: Get options for the Select widget.
def get_watchlist_options():
    """
    Returns a dictionary mapping from token symbol (display) to token address (value),
    based on the current watchlist JSON.
    """
    watchlist = load_watchlist()
    # Map each entry’s symbol to its address.
    options = {
        entry.get("symbol", entry.get("address")): entry.get("address")
        for entry in watchlist if entry.get("symbol")
    }
    return options

# ---------------------
# Utility: Get dashboard symbols from the local DataFrame.
def get_dashboard_symbols():
    df = get_local_df()
    if df is not None and "symbol" in df.columns:
        print(f"Dashboard data loaded with {len(df)} rows.")
        return list(df["symbol"].unique())
    print("Dashboard data unavailable.")
    return []

# ---------------------
# Create an AutocompleteInput for token search.
search_input = pn.widgets.AutocompleteInput(
    name="Search Tokens",
    placeholder="Type symbol...",
    options=get_dashboard_symbols(),
    case_sensitive=False
)

# ---------------------
# Create a Select widget for displaying the watchlist.
# Here the widget displays the token symbol (as key) and its underlying value is the address.
watchlist_select = pn.widgets.Select(
    name="Your Watchlist",
    options=get_watchlist_options()
)

# ---------------------
# Create buttons for watchlist actions.
add_button = pn.widgets.Button(name="Add to Watchlist", button_type="primary")
remove_button = pn.widgets.Button(name="Remove from Watchlist", button_type="danger")
refresh_button = pn.widgets.Button(name="Refresh Watchlist", button_type="default")

# ---------------------
# Create a TextArea for token notes.
notes_area = pn.widgets.TextAreaInput(name="Notes", value="", height=100)

# ---------------------
# Create an HTML pane to show the embedded chart.
embed_chart = pn.pane.HTML("", sizing_mode="stretch_width", height=400)

# ---------------------
# Callback: Refresh the watchlist.
def refresh_watchlist(event=None):
    options = get_watchlist_options()
    watchlist_select.options = options
    # Also update the autocomplete options using the dashboard's data.
    search_input.options = get_dashboard_symbols()
    print("Watchlist refreshed.")

# Callback: Add a token to the watchlist.
def add_token_callback(event):
    query = search_input.value.strip()
    print(f"Searching for token with symbol '{query}'...")
    if not query:
        return

    df = get_local_df()
    if df is None or "symbol" not in df.columns:
        print("Dashboard data unavailable.")
        return

    # Case-insensitive search for the token symbol.
    matching = df[df["symbol"].str.lower() == query.lower()]
    if not matching.empty:
        # Use the first match.
        address = matching.iloc[0]["address"]
        entry = {"address": address, "symbol": query, "notes": ""}
        add_to_watchlist(entry)
        print(f"Added token {query} (address: {address}) to watchlist.")
        refresh_watchlist()
    else:
        print(f"Token with symbol '{query}' not found in dashboard data.")

# Callback: Remove a token from the watchlist.
def remove_token_callback(event):
    selected_address = watchlist_select.value
    if not selected_address:
        print("No token selected to remove.")
        return
    remove_from_watchlist(selected_address)
    print(f"Removed token with address {selected_address} from watchlist.")
    refresh_watchlist()
    # Clear embed chart and notes if the removed token was selected.
    embed_chart.object = ""
    notes_area.value = ""

# Callback: When a token is selected in the watchlist, update the embed chart and notes.
def watchlist_select_callback(event):
    selected_address = watchlist_select.value
    if not selected_address:
        return
    print(f"Selected token with address {selected_address}.")
    embed_html = f"""
    <style>
      #dexscreener-embed {{
        position: relative;
        width: 100%;
        height: 100%;
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
      <iframe src="https://dexscreener.com/solana/{selected_address}?embed=1&loadChartSettings=1&trades=0&chartLeftToolbar=0&chartTheme=dark&theme=dark&chartStyle=1&chartType=usd&interval=15"></iframe>
    </div>
    """
    embed_chart.object = embed_html
    # Load the notes for the selected token.
    watchlist = load_watchlist()
    for entry in watchlist:
        if entry.get("address") == selected_address:
            notes_area.value = entry.get("notes", "")
            break

# Callback: Update the watchlist JSON when notes are modified.
def notes_callback(event):
    selected_address = watchlist_select.value
    if not selected_address:
        return
    update_watchlist_notes(selected_address, notes_area.value)
    print(f"Updated notes for token with address {selected_address}.")

# ---------------------
# Register widget callbacks.
add_button.on_click(add_token_callback)
remove_button.on_click(remove_token_callback)
refresh_button.on_click(refresh_watchlist)
watchlist_select.param.watch(watchlist_select_callback, "value")
notes_area.param.watch(notes_callback, "value")

# ---------------------
# Construct the layout for the watchlist tab.
def get_watchlist_tab():
    # Arrange the control row.
    watchlist_controls = pn.Row(
        search_input,
        add_button,
        remove_button,
        refresh_button,
        sizing_mode="stretch_width"
    )
    
    # Create the overall layout.
    watchlist_tab = pn.Column(
        watchlist_controls,
        watchlist_select,
        pn.Spacer(height=10),
        embed_chart,
        pn.Spacer(height=10),
        notes_area,
        sizing_mode="stretch_both"
    )
    
    # Refresh the watchlist on initial load.
    refresh_watchlist()
    print("Getting watchlist tab.")
    return watchlist_tab

pn.extension(raw_css=[
    """
    .watchlist-button {
        background-color: #1e1e1e;     
        color: #90ee90;                
        border: 2px solid #90ee90;  
        border-radius: 4px;
        transition: background-color 0.3s, color 0.3s;
    }
    .watchlist-button:hover,
    .watchlist-button:active {
        background-color: white;    
        color: white;           
    }
    """
])

def get_watchlist_panel():
    # Load the current watchlist.
    watchlist = load_watchlist()

    # Create a list of buttons—one per watchlist entry.
    buttons = []
    for entry in watchlist:
        symbol = entry.get("symbol", entry.get("address"))
        address = entry.get("address")
        # Create a button for each entry. Notice button_type is not set.
        btn = pn.widgets.Button(name=symbol, width=200, height=30)
        btn.css_classes = ["watchlist-button"]

        def on_click(event, address=address):
            watchlist_select.value = address

        btn.on_click(on_click)
        buttons.append(btn)
    watchlist_title = pn.pane.Markdown("## Moon list", sizing_mode="stretch_width")
    return pn.Column(watchlist_title, *buttons, sizing_mode="stretch_width")

# If running in a Bokeh server context, serve the tab.
if __name__.startswith("bokeh"):
    get_watchlist_tab().servable(title="Watchlist")