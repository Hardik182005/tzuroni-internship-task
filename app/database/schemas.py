import datetime
from typing import List
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Market(Base):
    __tablename__ = "markets"

    id = Column(String, primary_key=True)  # condition_id or custom generated ID
    slug = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    city = Column(String, nullable=False)
    metric = Column(String, nullable=False)  # "rain", "temperature", "wind", "aqi", etc.
    target_value = Column(Float, nullable=True)  # e.g., 0.1 (inches), 25.0 (C)
    operator = Column(String, default=">")  # ">", "<", ">=", "<=", "=="
    yes_price = Column(Float, default=0.5)  # price of YES contract (0 to 1)
    no_price = Column(Float, default=0.5)   # price of NO contract (0 to 1)
    volume_24h = Column(Float, default=0.0)
    liquidity = Column(Float, default=0.0)
    expiration_date = Column(DateTime, nullable=False)
    source = Column(String, default="live")  # "live" or "simulated"
    resolved = Column(Boolean, default=False)
    resolution_result = Column(String, nullable=True)  # "YES", "NO"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    predictions = relationship("Prediction", back_populates="market", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="market", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="market", cascade="all, delete-orphan")

class WeatherForecast(Base):
    __tablename__ = "weather_forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String, nullable=False)
    source = Column(String, nullable=False)  # "open-meteo", "noaa", "imd", "met-office", "bom", "jma"
    forecast_date = Column(DateTime, nullable=False)
    temperature_max = Column(Float, nullable=True)
    temperature_min = Column(Float, nullable=True)
    rain_probability = Column(Float, nullable=True)  # 0 to 1
    precipitation = Column(Float, nullable=True)  # mm or inches
    wind_speed = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    extreme_alerts = Column(Text, nullable=True)
    fetched_at = Column(DateTime, default=datetime.datetime.utcnow)

class NewsResearch(Base):
    __tablename__ = "news_research"

    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    sentiment_score = Column(Float, default=0.0)  # -1 (very negative) to 1 (very positive)
    confidence_score = Column(Float, default=0.5)  # 0 to 1
    sources = Column(Text, nullable=True)  # comma separated list of urls/sources
    fetched_at = Column(DateTime, default=datetime.datetime.utcnow)

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String, ForeignKey("markets.id"), nullable=False)
    model_probability = Column(Float, nullable=False)  # 0 to 1
    fair_odds = Column(Float, nullable=False)  # 1 / model_probability
    confidence = Column(Float, default=0.5)
    expected_value = Column(Float, nullable=False)
    edge = Column(Float, nullable=False)  # model_prob - market_prob
    decision = Column(String, nullable=False)  # "BUY YES", "BUY NO", "NO TRADE"
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    market = relationship("Market", back_populates="predictions")

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)  # client_order_id or server generated uuid
    market_id = Column(String, ForeignKey("markets.id"), nullable=False)
    side = Column(String, nullable=False)  # "YES", "NO"
    type = Column(String, default="MARKET")  # "LIMIT", "MARKET"
    price = Column(Float, nullable=False)  # price per share (0 to 1)
    quantity = Column(Float, nullable=False)  # number of shares
    filled_quantity = Column(Float, default=0.0)
    status = Column(String, default="PENDING")  # "PENDING", "FILLED", "PARTIALLY_FILLED", "CANCELLED"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    market = relationship("Market", back_populates="orders")
    trades = relationship("Trade", back_populates="order", cascade="all, delete-orphan")

class Trade(Base):
    __tablename__ = "trades"

    id = Column(String, primary_key=True)  # transaction hash or uuid
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    market_id = Column(String, ForeignKey("markets.id"), nullable=False)
    side = Column(String, nullable=False)  # "YES", "NO"
    execution_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    slippage_bps = Column(Float, default=0.0)
    executed_at = Column(DateTime, default=datetime.datetime.utcnow)

    market = relationship("Market", back_populates="trades")
    order = relationship("Order", back_populates="trades")

class PortfolioState(Base):
    __tablename__ = "portfolio_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    cash_balance = Column(Float, nullable=False)
    equity = Column(Float, nullable=False)
    open_positions_value = Column(Float, default=0.0)
    daily_return = Column(Float, default=0.0)
    weekly_return = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    loss_rate = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    sortino_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    profit_factor = Column(Float, default=1.0)
    exposure_pct = Column(Float, default=0.0)

class HedgingState(Base):
    __tablename__ = "hedging_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    primary_trade_id = Column(String, nullable=False)
    hedge_market_id = Column(String, nullable=False)
    hedge_side = Column(String, nullable=False)  # "YES", "NO"
    hedge_quantity = Column(Float, nullable=False)
    hedge_price = Column(Float, nullable=False)
    hedge_reason = Column(String, nullable=False)  # "correlation", "cross-city", "capital-protection"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
