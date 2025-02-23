import json
import pytest
from fastapi.testclient import TestClient
from src.alert_service.backend.app import app
from src.alert_service.backend.database.db import SessionLocal
from src.alert_service.backend.database.models import AlertEntry

client = TestClient(app)

def test_end_to_end_alert_flow():
    # Simulate sending an alert to the REST endpoint.
    data = {
        "address": "0xABC123",
        "price": 0.25,
        "smBuyCount": 5
    }
    response = client.post("/alert", json=data)
    assert response.status_code == 201
    json_response = response.json()
    assert json_response["status"] == "success"
    
    # Verify that the database has been updated with the alert.
    session = SessionLocal()
    try:
        entry = session.query(AlertEntry).filter(AlertEntry.symbol == "0xABC123").first()
        assert entry is not None
        assert entry.price == 0.25
        assert entry.sm_buy_count == 5
        # Optionally, check additional fields updated by refresh_entry.
    finally:
        session.close()