# watchlist_tab.py
import panel as pn
import param
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
# Create buttons for watchlist actions.
add_button = pn.widgets.Button(name="Add to Watchlist", button_type="primary")
remove_button = pn.widgets.Button(name="Remove from Watchlist", button_type="danger")
refresh_button = pn.widgets.Button(name="Refresh Watchlist", button_type="default")

# ---------------------
# Create an HTML pane to show the embedded chart.
embed_chart = pn.pane.HTML("", sizing_mode="stretch_width", height=400)

class WatchlistState(param.Parameterized):
    selected_address = param.String(default="")
    selected_notes = param.String(default="")

    def update_selection(self, address):
        self.selected_address = address
        watchlist = load_watchlist()
        for entry in watchlist:
            if entry.get("address") == address:
                self.selected_notes = entry.get("notes", "")
                break
            else:
                self.selected_notes = ""

watchlist_state = WatchlistState()

# Function to watch the state of watchlist_state
@pn.depends(watchlist_state.param.selected_address, watch=True)
def update_embed_chart(selected_address):
    if not selected_address:
        return pn.pane.Markdown("Select a token to view its chart.", sizing_mode="stretch_width")
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
      <iframe src="https://dexscreener.com/solana/{selected_address}?embed=1&loadChartSettings=1&trades=1&chartLeftToolbar=0&chartTheme=dark&theme=dark&chartStyle=1&chartType=usd&interval=15"></iframe>
    </div>
    """
    return pn.pane.HTML(embed_html, sizing_mode="stretch_width", height=400)

@pn.depends(watchlist_state.param.selected_notes, watch=True)
def notes_pane(selected_notes):
    # Using a TextAreaInput allows user edits; you can add a callback to update JSON.
    ta = pn.widgets.TextAreaInput(name="Notes", value=selected_notes, height=100)
    
    # When the user changes the notes, update the JSON file.
    def on_change(event):
        if watchlist_state.selected_address:
            update_watchlist_notes(watchlist_state.selected_address, ta.value)
            print(f"Updated notes for token with address {watchlist_state.selected_address}.")
            # Also update the state so the reactive function stays in sync.
            watchlist_state.selected_notes = ta.value

    ta.param.watch(on_change, 'value')
    return ta
# ---------------------
# Callback: Refresh the watchlist.
def refresh_watchlist(event=None):
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
    if not watchlist_state.selected_address:
        print("No token selected to remove.")
        return
    remove_from_watchlist(watchlist_state.selected_address)
    print(f"Removed token with address {watchlist_state.selected_address} from watchlist.")
    refresh_watchlist()
    # Clear embed chart and notes if the removed token was selected.
    embed_chart.object = ""
    watchlist_state.selected_address = ""
    watchlist_state.selected_notes = ""

# ---------------------
# Register widget callbacks.
add_button.on_click(add_token_callback)
remove_button.on_click(remove_token_callback)
refresh_button.on_click(refresh_watchlist)

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
        pn.Spacer(height=10),
        update_embed_chart,
        pn.Spacer(height=10),
        notes_pane,
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
        btn.on_click(lambda event, address=address: watchlist_state.update_selection(address))
        buttons.append(btn)
    watchlist_title = pn.pane.Markdown("## Moon list", sizing_mode="stretch_width")
    return pn.Column(watchlist_title, *buttons, sizing_mode="stretch_width")

# If running in a Bokeh server context, serve the tab.
if __name__.startswith("bokeh"):
    get_watchlist_tab().servable(title="Watchlist")