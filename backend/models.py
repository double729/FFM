"""SQLAlchemy models for the training platform backend."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Candle(Base):
    """Store futures K-line data along with volume."""

    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("symbol", "interval", "event_time", name="uq_candles_symbol_interval_time"),
    )

    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False, index=True)
    interval = Column(String(16), nullable=False, default="1d", index=True)
    event_time = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=True)
    turnover = Column(Float, nullable=True)


class SimulatedOrder(Base):
    """Store simulated orders before/after execution."""

    __tablename__ = "simulated_orders"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False, index=True)
    direction = Column(String(8), nullable=False)  # "buy" or "sell"
    order_type = Column(String(8), nullable=False, default="market")
    price = Column(Numeric(14, 4), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    filled_quantity = Column(Integer, nullable=False, default=0)
    avg_fill_price = Column(Numeric(14, 4), nullable=True)
    status = Column(String(16), nullable=False, default="open")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    note = Column(String(255), nullable=True)


class SimulatedTrade(Base):
    """Minimal trade record for the paper trading engine."""

    __tablename__ = "simulated_trades"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("simulated_orders.id"), nullable=True, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    trade_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    direction = Column(String(8), nullable=False)  # "buy" or "sell"
    price = Column(Numeric(14, 4), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    note = Column(String(255), nullable=True)


class PortfolioSnapshot(Base):
    """Optional end-of-day portfolio equity history."""

    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint("as_of", name="uq_portfolio_snapshot_time"),
    )

    id = Column(Integer, primary_key=True)
    as_of = Column(DateTime, nullable=False, index=True)
    equity = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    note = Column(String(255), nullable=True)
