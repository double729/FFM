"""Trading utilities for the simulated engine."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, Iterable, List

from ..models import Candle, SimulatedTrade


@dataclass
class Position:
    symbol: str
    quantity: int = 0
    average_price: Decimal = Decimal("0")


@dataclass
class PortfolioSummary:
    positions: Dict[str, Position]
    last_mark_prices: Dict[str, float]
    realized_pnl: Decimal
    unrealized_pnl: Decimal


DIRECTION_MULTIPLIER = {"buy": 1, "sell": -1}


def record_trade(
    trades: Iterable[SimulatedTrade],
    symbol: str,
    direction: str,
    price: float,
    quantity: int,
    note: str | None = None,
) -> SimulatedTrade:
    """Create a trade record ready for persistence."""

    if direction not in DIRECTION_MULTIPLIER:
        raise ValueError("Direction must be 'buy' or 'sell'")
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    return SimulatedTrade(
        symbol=symbol,
        direction=direction,
        price=Decimal(str(price)),
        quantity=quantity,
        note=note,
        trade_time=datetime.utcnow(),
    )


def build_positions(trades: Iterable[SimulatedTrade]) -> Dict[str, Position]:
    """Aggregate trades into net positions and average prices."""

    positions: Dict[str, Position] = defaultdict(lambda: Position(symbol=""))
    for trade in trades:
        multiplier = DIRECTION_MULTIPLIER.get(trade.direction, 0)
        if multiplier == 0:
            continue

        pos = positions[trade.symbol]
        if not pos.symbol:
            pos.symbol = trade.symbol

        trade_qty = multiplier * trade.quantity
        if pos.quantity + trade_qty == 0:
            pos.quantity = 0
            pos.average_price = Decimal("0")
            continue

        if pos.quantity == 0:
            pos.average_price = Decimal(trade.price)
        else:
            new_qty = pos.quantity + trade_qty
            total_value = pos.average_price * Decimal(pos.quantity) + Decimal(trade.price) * Decimal(trade_qty)
            pos.average_price = total_value / Decimal(new_qty)
        pos.quantity += trade_qty

    return {symbol: pos for symbol, pos in positions.items() if pos.quantity != 0}


def summarize_portfolio(
    trades: List[SimulatedTrade],
    candles: Dict[str, Candle],
) -> PortfolioSummary:
    """Compute PnL statistics for the provided trades."""

    positions = build_positions(trades)
    realized_pnl = Decimal("0")
    unrealized_pnl = Decimal("0")
    last_prices: Dict[str, float] = {}

    for symbol, pos in positions.items():
        candle = candles.get(symbol)
        if candle:
            last_price = float(candle.close)
            last_prices[symbol] = last_price
            unrealized_pnl += Decimal(last_price) * Decimal(pos.quantity) - pos.average_price * Decimal(pos.quantity)

    return PortfolioSummary(
        positions=positions,
        last_mark_prices=last_prices,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
    )
