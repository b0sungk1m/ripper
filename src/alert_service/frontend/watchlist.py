import json
import os

# Path to the watchlist JSON file.
# You can configure this via an environment variable or hard-code a default.
WATCHLIST_PATH = os.environ.get("WATCHLIST_PATH", "/Users/bosungkim/bosungkim/src/github/ripper/src/data/watchlist/watchlist.json")

def load_watchlist():
    """
    Loads the watchlist from a JSON file.
    
    Returns:
        A list of watchlist entries. Each entry can be a dict containing
        the token's address, symbol, notes, etc.
    If the file does not exist, returns an empty list.
    """
    if not os.path.exists(WATCHLIST_PATH):
        # Create an empty JSON file if it doesn't exist
        with open(WATCHLIST_PATH, "w") as f:
            json.dump([], f)
        return []
    try:
        with open(WATCHLIST_PATH, "r") as f:
            data = json.load(f)
            # Ensure the watchlist is a list.
            if isinstance(data, list):
                return data
            else:
                return []
    except Exception as e:
        print(f"Error loading watchlist: {e}")
        return []

def save_watchlist(watchlist):
    """
    Saves the watchlist to a JSON file.
    
    Parameters:
      watchlist (list): The list of watchlist entries to save.
    """
    try:
        with open(WATCHLIST_PATH, "w") as f:
            json.dump(watchlist, f, indent=4)
    except Exception as e:
        print(f"Error saving watchlist: {e}")

def add_to_watchlist(entry):
    """
    Adds an entry to the watchlist if it does not already exist.
    
    Parameters:
      entry (dict): A dictionary representing the token. For example:
          {
              "address": "0xABC...",
              "symbol": "TOKEN",
              "notes": ""
          }
    """
    watchlist = load_watchlist()
    # Check if the entry already exists by address.
    if any(item.get("address") == entry.get("address") for item in watchlist):
        print(f"Token {entry.get('address')} is already in the watchlist.")
        return
    watchlist.append(entry)
    save_watchlist(watchlist)
    print(f"Added token {entry.get('address')} to watchlist.")

def remove_from_watchlist(address):
    """
    Removes an entry from the watchlist by symbol.
    
    Parameters:
      address (str): The token's symbol to remove.
    """
    watchlist = load_watchlist()
    new_watchlist = [entry for entry in watchlist if entry.get("address", "").lower() != address.lower()]

    # find symbol of the address
    symbol = None
    for entry in watchlist:
        if entry.get("address", "").lower() == address.lower():
            symbol = entry.get("symbol")
            break
    save_watchlist(new_watchlist)
    print(f"Removed token {symbol} with address {address} from watchlist.")

def update_watchlist_notes(symbol, notes):
    """
    Updates the notes for a token in the watchlist.
    
    Parameters:
      address (str): The token's symbol.
      notes (str): The updated notes.
    """
    watchlist = load_watchlist()
    for entry in watchlist:
        if entry.get("address").lower() == symbol.lower():
            entry["notes"] = notes
            break
    save_watchlist(watchlist)
    print(f"Updated notes for token {symbol}.")