# watchlist_tab.py

import panel as pn
import param
from watchlist import load_watchlist, save_watchlist, add_to_watchlist, remove_from_watchlist, update_watchlist_notes
from shared_data import get_local_df  # Returns the dashboard's local DataFrame

# ---------------------
# Utility: Get options for the Select widget.
def get_watchlist_options():
    """
    Returns a dictionary mapping from token symbol (display) to token address (value),
    based on the current watchlist JSON.
    """
    watchlist = load_watchlist()
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
# Create a MultiChoice widget for tag assignment.
tags_multichoice = pn.widgets.MultiChoice(
    name="Tags",
    options=["untagged", "current", "hawk", "slow"],
    value=["untagged"],
    disabled=True,
    sizing_mode="stretch_width"
)

# ---------------------
# Create an HTML pane to show the embedded chart.
embed_chart = pn.pane.HTML("", sizing_mode="stretch_width", height=400)

class WatchlistState(param.Parameterized):
    selected_address = param.String(default="")
    selected_notes = param.String(default="")
    selected_tags = param.List(default=["untagged"])
    watchlist_items = param.List(default=[])
    
    def update_selection(self, address):
        print(f"Updating selection to {address}")
        self.selected_address = address
        watchlist = load_watchlist()
        found = False
        for entry in watchlist:
            if entry.get("address") == address:
                self.selected_notes = entry.get("notes", "")
                self.selected_tags = entry.get("tags", ["untagged"])
                found = True
                break
        if not found:
            self.selected_notes = ""
            self.selected_tags = []
        # Update the MultiChoice widget manually so it doesn't override user changes.
        tags_multichoice.value = self.selected_tags
        tags_multichoice.disabled = (self.selected_address == "")
    
    def refresh_watchlist_items(self):
        self.watchlist_items = load_watchlist()

watchlist_state = WatchlistState()
watchlist_state.refresh_watchlist_items()

# ---------------------
# Reactive function to update the embedded chart.
@pn.depends(watchlist_state.param.selected_address, watch=False)
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
    return pn.pane.HTML(embed_html, sizing_mode="stretch_width", height=700)

@pn.depends(watchlist_state.param.selected_notes, watch=False)
def notes_pane(selected_notes):
    ta = pn.widgets.TextAreaInput(name="Notes", value=selected_notes, height=100)
    
    def on_change(event):
        if watchlist_state.selected_address:
            update_watchlist_notes(watchlist_state.selected_address, ta.value)
            print(f"Updated notes for token with address {watchlist_state.selected_address}.")
            watchlist_state.selected_notes = ta.value

    ta.param.watch(on_change, 'value')
    return ta

# ---------------------
# Callback for tags_multichoice widget changes.
def on_tags_change(event):
    if not watchlist_state.selected_address:
        return
    new_tags = event.new
    # If "untagged" is present along with other tags, remove it.
    if "untagged" in new_tags and len(new_tags) > 1:
        new_tags = [tag for tag in new_tags if tag != "untagged"]
        tags_multichoice.value = new_tags  # Update widget value accordingly.
    watchlist = load_watchlist()
    for entry in watchlist:
        if entry.get("address") == watchlist_state.selected_address:
            entry["tags"] = new_tags
            break
    save_watchlist(watchlist)
    watchlist_state.selected_tags = new_tags
    watchlist_state.refresh_watchlist_items()
    print(f"Updated tags for token {watchlist_state.selected_address} to {new_tags}")

tags_multichoice.param.watch(on_tags_change, "value")

# ---------------------
# Callback: Refresh the watchlist.
def refresh_watchlist(event=None):
    search_input.options = get_dashboard_symbols()
    watchlist_state.refresh_watchlist_items()
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

    matching = df[df["symbol"].str.lower() == query.lower()]
    if not matching.empty:
        address = matching.iloc[0]["address"]
        entry = {"address": address, "symbol": query, "notes": "", "tags": ["untagged"]}
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

    df = get_local_df()
    if df is None or "address" not in df.columns:
        print("Dashboard data unavailable.")
        return

    remove_from_watchlist(watchlist_state.selected_address)
    print(f"Removed token with address {watchlist_state.selected_address} from watchlist.")
    refresh_watchlist()
    embed_chart.object = ""
    watchlist_state.selected_address = ""
    watchlist_state.selected_notes = ""
    watchlist_state.selected_tags = []
    tags_multichoice.value = []
    tags_multichoice.disabled = True

add_button.on_click(add_token_callback)
remove_button.on_click(remove_token_callback)
refresh_button.on_click(refresh_watchlist)

# ---------------------
# Create a reactive function to generate buttons for each watchlist entry.
@pn.depends(watchlist_state.param.watchlist_items, watch=False)
def get_watchlist_buttons(watchlist_items):
    buttons = []
    for entry in watchlist_items:
        symbol = entry.get("symbol", entry.get("address"))
        address = entry.get("address")
        btn = pn.widgets.Button(name=symbol, width=200, height=30)
        btn.css_classes = ["watchlist-button"]
        btn.on_click(lambda event, address=address: watchlist_state.update_selection(address))
        buttons.append(btn)
    return buttons

# ---------------------/
# Build a tabs layout for the fixed tag categories.
@pn.depends(watchlist_state.param.watchlist_items, watch=False)
def get_watchlist_accordion(watchlist_items=None):
    # map string tags to emojis
    tag_emojis = {
        "untagged": "🆕",
        "current": "💰",
        "hawk": "🦅",
        "slow": "🐢"
    }
    categories = ["untagged", "current", "hawk", "slow"]
    tab_items = []
    for cat in categories:
        # Filter coins that have this tag.
        coins = [entry for entry in watchlist_state.watchlist_items if "tags" in entry and cat in entry["tags"]]
        if coins:
            buttons = []
            for coin in coins:
                symbol = coin.get("symbol", coin.get("address"))
                address = coin.get("address")
                # Add an extra css class based on the category.
                btn = pn.widgets.Button(
                    name=symbol,
                    width=200,
                    height=30,
                    css_classes=[f"watchlist-button-{cat}"]
                )
                btn.on_click(lambda event, address=address: watchlist_state.update_selection(address))
                buttons.append(btn)
            content = pn.Column(*buttons, sizing_mode="stretch_width")
        else:
            content = pn.pane.Markdown("No coins in this category.", sizing_mode="stretch_width")
        tab_items.append((tag_emojis[cat], content))
    return pn.Tabs(*tab_items, margin=7)

# ---------------------
# Construct the overall layout for the watchlist tab.
def get_watchlist_tab():
    # Arrange the control row including the new MultiChoice widget.
    watchlist_controls = pn.Row(
        search_input,
        add_button,
        remove_button,
        refresh_button,
        tags_multichoice,
        sizing_mode="stretch_width"
    )
    
    # Build the main layout with controls, embed chart, notes pane, and the watchlist tabs.
    watchlist_tab = pn.Column(
        watchlist_controls,
        pn.Spacer(height=10),
        update_embed_chart,
        pn.Spacer(height=30),
        notes_pane,
        sizing_mode="stretch_width"
    )
    
    refresh_watchlist()
    print("Getting watchlist tab.")
    return watchlist_tab

pn.extension(raw_css=[
    """
    .watchlist-button {
        border: 2px solid #90ee90;  
        border-radius: 4px;
        transition: background-color 0.3s, color 0.3s;
    }
    .watchlist-button:hover,
    .watchlist-button:active {
        background-color: white;    
        color: white;           
    }
    .watchlist-button-untagged {
        background-color: #d3d3d3;
        color: black;
    }
    .watchlist-button-current {
        background-color: green;
        color: white;
    }
    .watchlist-button-hawk {
        background-color: red;
        color: white;
    }
    .watchlist-button-slow {
        background-color: orange;
        color: black;
    }
    """
])

# Serve the tab if running in a Bokeh server context.
if __name__.startswith("bokeh"):
    get_watchlist_tab().servable(title="Watchlist")