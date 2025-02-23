from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from .models import AlertEntry
from termcolor import cprint

def get_entry_by_symbol(db: Session, symbol: str) -> AlertEntry:
    """
    Returns the first entry for a given symbol, or None if not found.
    """
    return db.query(AlertEntry).filter(AlertEntry.symbol == symbol).first()

def add_new_entry(db: Session, symbol: str, price: float, alert_count: int, 
                  address: str) -> AlertEntry:
    """
    Creates a new AlertEntry in the database.
    """
    new_entry = AlertEntry(
        symbol=symbol,
        price=price,
        dexscreener_link=f'https://dexscreener.com/solana/{address}',
        first_alert_time=datetime.now(timezone.utc),
        last_alert_time=datetime.now(timezone.utc),
        last_update_time=datetime.now(timezone.utc),
        alert_count=alert_count,
        active=True  # Default to active
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry

def update_entry(db: Session, entry: AlertEntry, price: float, alert_count: int) -> AlertEntry:
    """
    Updates an existing AlertEntry with a new alert. Increments the alert count and updates price and sm_buy_count.
    """
    entry.price = price
    entry.alert_count = alert_count
    entry.last_alert_time = datetime.now(timezone.utc)
    entry.last_update_time = datetime.now(timezone.utc)
    # Optionally update other fields if necessary
    db.commit()
    db.refresh(entry)
    return entry

def cleanup_old_entries(db: Session, older_than_days: int = 7):
    """
    Deletes entries older than a specified number of days.
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    deleted = db.query(AlertEntry).filter(AlertEntry.first_alert_time < cutoff_time).delete()
    db.commit()
    cprint(f"Deleted {deleted} entries older than {older_than_days} days.", "yellow")
    return deleted