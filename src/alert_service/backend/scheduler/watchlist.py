from datetime import datetime, timezone
from src.alert_service.backend.database.db import SessionLocal
from src.alert_service.backend.database.operations import get_entry_by_symbol  # If needed for lookup or similar
from src.alert_service.backend.database.models import AlertEntry
from termcolor import cprint

def filter_watchlist():
    """
    This function iterates through the watchlist and marks entries as active/inactive
    based on a filter criteria (e.g., market cap > 40k). For now, we'll assume the market cap
    is represented by the `price` field or a dummy field. You can adjust this logic as needed.
    """
    print(f"[{datetime.now(timezone.utc)}] Running watchlist filter...")
    db = SessionLocal()
    try:
        # Retrieve all entries (for a production system, you might only want active ones)
        entries = db.query(AlertEntry).all()
        for entry in entries:
            # For demonstration, we use a dummy filter: mark active if price > 0.05, otherwise inactive.
            # Replace this with your actual filter logic (e.g., market cap > 40k).
            if entry.price > 0.05:
                entry.active = True
            else:
                entry.active = False
            # You could also update other fields or log information if necessary.

        db.commit()
        cprint(f"[{datetime.now(timezone.utc)}] Watchlist filter completed.", "green")
    except Exception as e:
        cprint(f"Error during watchlist filtering: {e}", "red")
        db.rollback()
    finally:
        db.close()