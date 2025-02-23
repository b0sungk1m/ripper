from pydantic import BaseModel, Field
from datetime import datetime, timezone
# Define Pydantic models for the additional data

class TokenInfo(BaseModel):
    name: str
    symbol: str
    imageUrl: str | None = None
    twitterHandle: str | None = None
    telegramHandle: str | None = None
    discordUrl: str | None = None
    description: str | None = None
    websites: list[str]

class PriceInfo(BaseModel):
    price: str
    fdv: str

# Updated Alert model including the new fields.
class Alert(BaseModel):
    address: str
    price: float
    timestamp: datetime = None  # Optional; will be set to current time if not provided
    purchaseSize: float | None = None
    lastTouched: int
    info: TokenInfo | None = None
    lastPrice: PriceInfo | None = None
    strategyAlertCount: int | None = None