from src.alert_service.backend.alerts.alert_handler import process_alert

# Create a dummy alert class for testing
class DummyAlert:
    def __init__(self, symbol, price, sm_buy_count):
        self.symbol = symbol
        self.price = price
        self.sm_buy_count = sm_buy_count

def test_process_new_alert():
    alert = DummyAlert("BTC", 0.25, 5)
    # Process the alert and get the created entry
    entry = process_alert(alert)
    assert entry.symbol == "BTC"
    assert entry.alert_count == 1

def test_process_existing_alert():
    alert = DummyAlert("ETH", 1.0, 3)
    # Process the alert once to create the entry
    entry = process_alert(alert)
    # Process the same alert again; should update the existing entry.
    updated_entry = process_alert(alert)
    assert updated_entry.alert_count == 2