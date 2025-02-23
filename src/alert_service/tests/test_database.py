import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.alert_service.backend.database.models import Base, AlertEntry
from src.alert_service.backend.database.operations import add_new_entry, update_entry, cleanup_old_entries, get_entry_by_symbol

# Use an in-memory SQLite database for tests
@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()

def test_add_new_entry(db_session):
    entry = add_new_entry(db_session, "BTC", 0.25, 5)
    assert entry.symbol == "BTC"
    assert entry.price == 0.25
    assert entry.sm_buy_count == 5
    assert entry.alert_count == 1

def test_update_entry(db_session):
    entry = add_new_entry(db_session, "ETH", 1.0, 3)
    original_alert_count = entry.alert_count
    entry = update_entry(db_session, entry, 1.1, 4)
    assert entry.price == 1.1
    assert entry.sm_buy_count == 4
    assert entry.alert_count == original_alert_count + 1

def test_cleanup_old_entries(db_session):
    # Create an entry with a first_alert_time older than 7 days
    entry = add_new_entry(db_session, "DOGE", 0.05, 1)
    entry.first_alert_time = datetime.utcnow() - timedelta(days=8)
    db_session.commit()
    deleted_count = cleanup_old_entries(db_session, older_than_days=7)
    assert deleted_count == 1
    assert get_entry_by_symbol(db_session, "DOGE") is None