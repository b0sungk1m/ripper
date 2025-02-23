from src.alert_service.backend.database.db import SessionLocal
from src.alert_service.backend.database.operations import get_entry_by_symbol, add_new_entry, update_entry
from src.alert_service.backend.alerts.refresh import refresh_entry
from termcolor import cprint
from src.alert_service.backend.alerts.alert_models import Alert

def process_alert(alert: Alert):
    """
    Process a new alert by checking if the entry exists in the database.
    If it exists, update it; otherwise, create a new entry.
    Afterward, refresh the entry's additional data.
    
    :param alert: A dict or Pydantic model with keys: symbol, price, sm_buy_count, etc.
    """
    db = SessionLocal()
    try:
        # Assume 'alert' has attribute 'symbol'. Adjust according to your model.
        existing_entry = get_entry_by_symbol(db, alert.info.symbol)
        if existing_entry:
            # Update the existing entry (this updates alert count, last alert time, price, alert count)
            updated_entry = update_entry(db, existing_entry, alert.lastPrice.price, alert.strategyAlertCount)
            entry = updated_entry
            cprint(f"Updated entry for {alert.info.symbol} with price {alert.lastPrice.price} and alert count {alert.strategyAlertCount}.", "green")
        else:
            # Create a new entry with the provided data
            entry = add_new_entry(db, alert.info.symbol, alert.lastPrice.price, alert.strategyAlertCount, alert.address)
            cprint(f"Created new entry for {alert.info.symbol} with price {alert.lastPrice.price} and alert count {alert.strategyAlertCount}.", "green")
        # After updating/adding the entry, refresh additional data synchronously.
        refreshed_entry = refresh_entry(db, entry)
        return refreshed_entry
    finally:
        db.close()

def validate_alert(alert: Alert) -> None:
    """
    Validates that the given alert contains all the expected fields.
    Raises ValueError with an appropriate message if any required field is missing or invalid.
    """
    # Check required primitive fields
    if not alert.address:
        raise ValueError("Missing 'address' in alert.")
    if alert.price is None:
        raise ValueError("Missing 'price' in alert.")
    if alert.lastTouched is None:
        raise ValueError("Missing 'lastTouched' in alert.")
    if alert.strategyAlertCount is None:
        raise ValueError("Missing 'strategyAlertCount' in alert.")

    # Validate TokenInfo if provided
    if alert.info is not None:
        # Check that name, symbol, description and websites are present
        if not alert.info.name:
            raise ValueError("Missing 'name' in alert info.")
        if not alert.info.symbol:
            raise ValueError("Missing 'symbol' in alert info.")

    # Validate PriceInfo if provided
    if alert.lastPrice is not None:
        if not alert.lastPrice.price:
            raise ValueError("Missing 'price' in alert lastPrice.")
        if not alert.lastPrice.fdv:
            raise ValueError("Missing 'fdv' in alert lastPrice.")