import panel as pn
import pandas as pd
from sqlalchemy import create_engine
from src.alert_service.backend.database.db import DATABASE_URL
from bokeh.models.widgets.tables import NumberFormatter, BooleanFormatter

# Enable Panel extensions with Tabulator support
pn.extension('tabulator', sizing_mode="stretch_width")

# Create a SQLAlchemy engine for the SQLite database.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def format_relative(dt_val):
    """Return a string like 'X min' or 'X hr Y min' for the difference between now and dt_val."""
    if pd.isnull(dt_val):
        return None
    # Get current time as a tz-aware UTC timestamp
    now = pd.Timestamp.now(tz='UTC')
    
    # Ensure dt_val is tz-aware in UTC
    if dt_val.tzinfo is None:
        dt_val = dt_val.tz_localize('UTC')
    else:
        dt_val = dt_val.tz_convert('UTC')
    
    diff = now - dt_val
    seconds = diff.total_seconds()
    if seconds < 3600:
        minutes = int(round(seconds / 60))
        return f"{minutes} min"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours} hr {minutes} min"

def load_data():
    """
    Query the SQLite database and return a DataFrame with alert entries.
    Converts datetime columns into a relative string format.
    """
    query = """
    SELECT 
      address,
      symbol,
      first_alert_price,
      current_price,
      purchase_size,
      alert_count,
      last_alert_time,
      last_update_time,
      first_alert_time,
      active_watchlist,
      sm_buy_count,
      dexscreener_link,
      twitter_sentiment,
      rug_bundle_check,
      macd_line,
      macd_short,
      macd_long,
      volume_5min,
      volume_1hr,
      summary,
      twitter,
      website,
      channel_HighConviction,
      channel_EarlyAlpha,
      channel_5xSMWallet,
      channel_SmartFollowers,
      channel_KimchiTest
    FROM alert_entries
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    
    # Process datetime columns: convert to datetime and then format as relative differences.
    datetime_cols = ['last_alert_time', 'last_update_time', 'first_alert_time']
    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').apply(format_relative)
    return df

# Load initial data
df = load_data()

# Create interactive filter widgets
symbol_filter = pn.widgets.TextInput(name="Symbol Filter", placeholder="Enter symbol substring")
active_filter = pn.widgets.Checkbox(name="Active Only", value=True)

# Create a Tabulator widget to display the DataFrame.
# Remove the top-level "editable" argument to avoid the error,
# and rely on table_options (if supported) or default read-only behavior.


bokeh_formatters = {
    'active': {'type': 'tickCross'},
    'dexscreener_link': {'type': 'link', 'target': '_blank', 'label': 'link'},
}

data_table = pn.widgets.Tabulator(
    df, 
    pagination='local', 
    page_size=20,
    sizing_mode="stretch_width",
    show_index=False,
    formatters=bokeh_formatters,
    disabled=True,
)

def filter_data(event=None):
    """
    Reload data, apply interactive filters, and update the table.
    """
    df = load_data()
    if symbol_filter.value:
        df = df[df['symbol'].str.contains(symbol_filter.value, case=False, na=False)]
    if active_filter.value:
        df = df[df['active'] == True]
    data_table.value = df

# Set up widget watchers for interactive filtering
symbol_filter.param.watch(filter_data, 'value')
active_filter.param.watch(filter_data, 'value')

# Refresh data periodically (every 10 seconds)
pn.state.add_periodic_callback(filter_data, period=10000)

# Use a Panel template for a polished layout.
template = pn.template.FastListTemplate(
    title="Ripper",
    header_background="#808000",  # Olive green header
    theme="dark",
    accent="#90ee90",             # Bright green accent
    main_max_width="1200px",
    sidebar=[]
)

# Create a header using an HTML pane for inline styling
header = pn.pane.HTML(
    "<h1 style='text-align: center; margin: 20px 0;'>Alert Dashboard</h1>",
    sizing_mode="stretch_width"
)

# Compose the layout
layout = pn.Column(
    header,
    pn.Row(symbol_filter, active_filter, sizing_mode="stretch_width", margin=10),
    data_table,
    sizing_mode="stretch_both"
)

# Add the layout to the template and serve it
template.main.append(layout)
template.servable(title="Ripper")