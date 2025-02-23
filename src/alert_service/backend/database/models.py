from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class AlertEntry(Base):
    __tablename__ = "alert_entries"
    
    address = Column(String, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    first_alert_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    ath_multiplier = Column(Float, nullable=True) # ATH multiplier from first alert price
    token_age = Column(Float, nullable=True)
    first_alert_time = Column(DateTime, default=func.now())
    alert_count = Column(Integer, nullable=False)
    last_alert_time = Column(DateTime, default=func.now())
    last_update_time = Column(DateTime, default=func.now(), onupdate=func.now())
    dexscreener_link = Column(String, nullable=True)
    twitter_sentiment = Column(String, nullable=True)
    rug_bundle_check = Column(String, nullable=True)
    macd_line = Column(String, nullable=True)
    macd_short = Column(String, nullable=True)
    macd_long = Column(String, nullable=True)
    volume_5min = Column(Float, nullable=True)
    volume_1hr = Column(Float, nullable=True)
    active_watchlist = Column(Boolean, default=True, nullable=False)
    sm_buy_count = Column(Integer, nullable=True)
    summary = Column(String, nullable=True)
    twitter = Column(String, nullable=True)
    website = Column(String, nullable=True)
    channel_HighConviction = Column(Boolean, default=False, nullable=False)
    channel_EarlyAlpha = Column(Boolean, default=False, nullable=False)
    channel_5xSMWallet = Column(Boolean, default=False, nullable=False)
    channel_SmartFollowers = Column(Boolean, default=False, nullable=False)
    channel_KimchiTest = Column(Boolean, default=False, nullable=False)
