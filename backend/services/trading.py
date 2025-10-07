"""Trading utilities and in-memory engine for the simulated environment."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Deque, Dict, Iterable, List, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Candle, SimulatedOrder, SimulatedTrade

DIRECTION_MULTIPLIER = {"buy": 1, "sell": -1}
DEFAULT_INITIAL_CASH = Decimal("1000000")
DEFAULT_CONTRACT_MULTIPLIER = Decimal("1")
DEFAULT_MARGIN_RATE = Decimal("0.1")


@dataclass
class Lot:
    """Represent a quantity opened at a specific price."""

    price: Decimal
    quantity: int


@dataclass
class Position:
    """Aggregated position after netting long/short lots."""

    symbol: str
    quantity: int = 0
    average_price: Decimal = Decimal("0")

    @property
    def direction(self) -> str:
        if self.quantity > 0:
            return "long"
        if self.quantity < 0:
            return "short"
        return "flat"


@dataclass
class PortfolioSummary:
    """Account-wide snapshot including margin and cash figures."""

    positions: Dict[str, Position]
    last_mark_prices: Dict[str, float]
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    cash: Decimal
    equity: Decimal
    margin_used: Decimal
    available_funds: Decimal


class PositionBook:
    """Maintain open lots for long与short方向，便于 FIFO 计算。"""

    def __init__(self) -> None:
        self.longs: Deque[Lot] = deque()
        self.shorts: Deque[Lot] = deque()

    def apply_trade(
        self,
        direction: str,
        price: Decimal,
        quantity: int,
        contract_multiplier: Decimal,
    ) -> Decimal:
        """Apply a trade to the lot book and return realized PnL."""

        realized = Decimal("0")

        if direction == "buy":
            realized_part, remaining = self._offset(
                self.shorts,
                price,
                quantity,
                lambda lot_price, fill_price: (lot_price - fill_price),
                contract_multiplier,
            )
            realized += realized_part
            if remaining > 0:
                self.longs.append(Lot(price=price, quantity=remaining))
        elif direction == "sell":
            realized_part, remaining = self._offset(
                self.longs,
                price,
                quantity,
                lambda lot_price, fill_price: (fill_price - lot_price),
                contract_multiplier,
            )
            realized += realized_part
            if remaining > 0:
                self.shorts.append(Lot(price=price, quantity=remaining))
        return realized

    @staticmethod
    def _offset(
        queue: Deque[Lot],
        fill_price: Decimal,
        quantity: int,
        per_unit_calc,
        contract_multiplier: Decimal,
    ) -> tuple[Decimal, int]:
        realized = Decimal("0")
        remaining = quantity
        while remaining > 0 and queue:
            lot = queue[0]
            matched = min(remaining, lot.quantity)
            realized += (
                per_unit_calc(lot.price, fill_price)
                * Decimal(matched)
                * contract_multiplier
            )
            lot.quantity -= matched
            remaining -= matched
            if lot.quantity == 0:
                queue.popleft()
        return realized, remaining

    def snapshot(self, symbol: str) -> Position | None:
        long_qty = sum(lot.quantity for lot in self.longs)
        short_qty = sum(lot.quantity for lot in self.shorts)
        if long_qty:
            total_value = sum(lot.price * lot.quantity for lot in self.longs)
            avg_price = total_value / Decimal(long_qty)
            return Position(symbol=symbol, quantity=long_qty, average_price=avg_price)
        if short_qty:
            total_value = sum(lot.price * lot.quantity for lot in self.shorts)
            avg_price = total_value / Decimal(short_qty)
            return Position(symbol=symbol, quantity=-short_qty, average_price=avg_price)
        return None


class TradingEngine:
    """In-memory controller orchestrating order placement and fills."""

    def __init__(
        self,
        *,
        initial_cash: Decimal = DEFAULT_INITIAL_CASH,
        contract_multiplier: Decimal = DEFAULT_CONTRACT_MULTIPLIER,
        margin_rate: Decimal = DEFAULT_MARGIN_RATE,
    ) -> None:
        self.initial_cash = initial_cash
        self.contract_multiplier = contract_multiplier
        self.margin_rate = margin_rate

    # ------------------------------------------------------------------
    # Order lifecycle
    # ------------------------------------------------------------------
    def place_order(
        self,
        session: Session,
        *,
        symbol: str,
        direction: str,
        quantity: int,
        order_type: str,
        price: float | None = None,
        note: str | None = None,
    ) -> tuple[SimulatedOrder, List[SimulatedTrade]]:
        """Persist an order and fill immediately when条件满足."""

        if direction not in DIRECTION_MULTIPLIER:
            raise ValueError("Direction must be 'buy' or 'sell'")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        order_type = order_type or "market"
        if order_type not in {"market", "limit"}:
            raise ValueError("Order type must be 'market' or 'limit'")

        normalized_symbol = symbol.strip().upper()
        dec_price = Decimal(str(price)) if price is not None else None

        last_price = self._latest_price(session, normalized_symbol)
        if order_type == "market" and dec_price is None and last_price is None:
            raise ValueError("Market orders require最新价或填写价格")
        if order_type == "limit" and dec_price is None:
            raise ValueError("Limit orders require a price")

        self._validate_margin(
            session,
            symbol=normalized_symbol,
            direction=direction,
            quantity=quantity,
            price=dec_price or last_price,
        )

        order = SimulatedOrder(
            symbol=normalized_symbol,
            direction=direction,
            order_type=order_type,
            price=dec_price,
            quantity=quantity,
            note=note,
        )
        session.add(order)
        session.flush()

        fills: List[SimulatedTrade] = []

        if order_type == "market":
            fill_price = dec_price or last_price
            trade = self._fill_order(
                session,
                order,
                fill_price,
                quantity,
                trade_time=datetime.utcnow(),
            )
            fills.append(trade)
        elif order_type == "limit":
            should_fill = False
            reference_price = last_price
            if reference_price is not None:
                if direction == "buy" and reference_price <= dec_price:
                    should_fill = True
                if direction == "sell" and reference_price >= dec_price:
                    should_fill = True
            if should_fill:
                trade = self._fill_order(
                    session,
                    order,
                    dec_price,
                    quantity,
                    trade_time=datetime.utcnow(),
                )
                fills.append(trade)
            else:
                order.status = "open"
        return order, fills

    def cancel_order(self, session: Session, order_id: int) -> SimulatedOrder:
        order = session.get(SimulatedOrder, order_id)
        if not order:
            raise ValueError("Order not found")
        if order.status != "open":
            raise ValueError("Only open orders can be cancelled")
        order.status = "cancelled"
        order.updated_at = datetime.utcnow()
        return order

    def process_candles(
        self,
        session: Session,
        symbol: str,
        candles: Sequence[dict[str, object]],
    ) -> List[SimulatedTrade]:
        """尝试用新行情撮合挂单，返回成交的交易记录。"""

        if not candles:
            return []
        open_orders = session.execute(
            select(SimulatedOrder)
            .where(
                SimulatedOrder.symbol == symbol.upper(),
                SimulatedOrder.status == "open",
            )
            .order_by(SimulatedOrder.created_at)
        ).scalars().all()
        if not open_orders:
            return []

        fills: List[SimulatedTrade] = []
        for order in open_orders:
            price = Decimal(str(order.price)) if order.price is not None else None
            for candle in candles:
                if order.order_type != "limit" or price is None:
                    break
                low = candle.get("low")
                high = candle.get("high")
                event_time = candle.get("event_time")
                trade_time = self._parse_event_time(event_time)
                if order.direction == "buy" and low is not None and low <= float(price):
                    trade = self._fill_order(
                        session,
                        order,
                        price,
                        order.quantity,
                        trade_time=trade_time,
                    )
                    fills.append(trade)
                    break
                if order.direction == "sell" and high is not None and high >= float(price):
                    trade = self._fill_order(
                        session,
                        order,
                        price,
                        order.quantity,
                        trade_time=trade_time,
                    )
                    fills.append(trade)
                    break
        return fills

    # ------------------------------------------------------------------
    # Account summary helpers
    # ------------------------------------------------------------------
    def summarize(
        self,
        trades: List[SimulatedTrade],
        candles: Dict[str, Candle],
    ) -> PortfolioSummary:
        return summarize_portfolio(
            trades,
            candles,
            initial_cash=self.initial_cash,
            contract_multiplier=self.contract_multiplier,
            margin_rate=self.margin_rate,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fill_order(
        self,
        session: Session,
        order: SimulatedOrder,
        price: Decimal | None,
        quantity: int,
        *,
        trade_time: datetime,
    ) -> SimulatedTrade:
        if price is None:
            raise ValueError("Cannot fill order without price")
        order.status = "filled"
        order.filled_quantity = quantity
        order.avg_fill_price = price
        order.updated_at = trade_time
        trade = SimulatedTrade(
            order_id=order.id,
            symbol=order.symbol,
            direction=order.direction,
            price=price,
            quantity=quantity,
            trade_time=trade_time,
            note=order.note,
        )
        session.add(trade)
        session.flush()
        return trade

    def _latest_price(self, session: Session, symbol: str) -> Decimal | None:
        candle = session.execute(
            select(Candle)
            .where(Candle.symbol == symbol)
            .order_by(Candle.event_time.desc())
            .limit(1)
        ).scalar_one_or_none()
        if not candle:
            return None
        return Decimal(str(candle.close))

    def _validate_margin(
        self,
        session: Session,
        *,
        symbol: str,
        direction: str,
        quantity: int,
        price: Decimal | None,
    ) -> None:
        if price is None:
            return
        trades = session.execute(
            select(SimulatedTrade).order_by(SimulatedTrade.trade_time)
        ).scalars().all()
        candles: Dict[str, Candle] = {}
        summary = summarize_portfolio(
            trades,
            candles,
            initial_cash=self.initial_cash,
            contract_multiplier=self.contract_multiplier,
            margin_rate=self.margin_rate,
        )
        current_pos = summary.positions.get(symbol)
        opening_qty = quantity
        if direction == "buy" and current_pos and current_pos.quantity < 0:
            closing = min(quantity, abs(current_pos.quantity))
            opening_qty = quantity - closing
        if direction == "sell" and current_pos and current_pos.quantity > 0:
            closing = min(quantity, current_pos.quantity)
            opening_qty = quantity - closing
        if opening_qty <= 0:
            return
        margin_needed = (
            price
            * Decimal(opening_qty)
            * self.contract_multiplier
            * self.margin_rate
        )
        if summary.available_funds < margin_needed:
            raise ValueError("Insufficient available funds for new position")

    @staticmethod
    def _parse_event_time(value: object) -> datetime:
        if isinstance(value, str):
            sanitized = value.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(sanitized)
                if parsed.tzinfo is not None:
                    return parsed.replace(tzinfo=None)
                return parsed
            except ValueError:
                return datetime.utcnow()
        if isinstance(value, datetime):
            return value
        return datetime.utcnow()


def summarize_portfolio(
    trades: Iterable[SimulatedTrade],
    candles: Dict[str, Candle],
    *,
    initial_cash: Decimal,
    contract_multiplier: Decimal,
    margin_rate: Decimal,
) -> PortfolioSummary:
    """Aggregate持仓、现金、盈亏指标。"""

    books: Dict[str, PositionBook] = defaultdict(PositionBook)
    realized_total = Decimal("0")
    cash = initial_cash

    for trade in trades:
        symbol = trade.symbol
        price = Decimal(str(trade.price))
        quantity = int(trade.quantity)
        direction = trade.direction
        notional = price * Decimal(quantity) * contract_multiplier
        if direction == "buy":
            cash -= notional
        else:
            cash += notional
        realized = books[symbol].apply_trade(direction, price, quantity, contract_multiplier)
        realized_total += realized

    positions: Dict[str, Position] = {}
    last_prices: Dict[str, float] = {}
    unrealized_total = Decimal("0")
    margin_used = Decimal("0")

    for symbol, book in books.items():
        position = book.snapshot(symbol)
        if not position:
            continue
        positions[symbol] = position
        candle = candles.get(symbol)
        if candle:
            mark_price = Decimal(str(candle.close))
            last_prices[symbol] = float(mark_price)
        else:
            mark_price = position.average_price
        qty = position.quantity
        if qty > 0:
            unrealized = (mark_price - position.average_price) * Decimal(qty) * contract_multiplier
        else:
            unrealized = (position.average_price - mark_price) * Decimal(abs(qty)) * contract_multiplier
        unrealized_total += unrealized
        margin_used += (
            mark_price
            * Decimal(abs(qty))
            * contract_multiplier
            * margin_rate
        )

    equity = cash + unrealized_total
    available_funds = cash - margin_used

    return PortfolioSummary(
        positions=positions,
        last_mark_prices=last_prices,
        realized_pnl=realized_total,
        unrealized_pnl=unrealized_total,
        cash=cash,
        equity=equity,
        margin_used=margin_used,
        available_funds=available_funds,
    )
