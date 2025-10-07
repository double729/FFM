"""Flask application entrypoint for the futures training platform."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import and_, select

from .database import init_db, session_scope
from .models import Candle, SimulatedTrade
from .services.market_data import convert_to_models, fetch_candles, list_available_contracts, load_candles_from_db
from .services.playback import PlaybackManager
from .services.trading import DIRECTION_MULTIPLIER, summarize_portfolio

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
init_db()


playback_manager = PlaybackManager()


@app.route("/api/health", methods=["GET"])
def health() -> tuple[Dict[str, str], int]:
    """Simple health check endpoint."""

    return {"status": "ok"}, 200


@app.route("/api/import", methods=["POST"])
def import_data() -> tuple[Dict[str, str], int]:
    """Fetch data from AkShare and load into SQLite."""

    payload = request.get_json(force=True)
    symbol = payload.get("symbol")
    start = payload.get("start_date")
    end = payload.get("end_date")
    interval = payload.get("interval", "1d")

    if not symbol or not start or not end:
        return {"message": "symbol, start_date, and end_date are required"}, 400

    try:
        frame = fetch_candles(symbol=symbol, start=start, end=end, interval=interval)
    except Exception as exc:  # pragma: no cover - AkShare/runtime specific
        return {"message": f"failed to fetch data: {exc}"}, 500

    imported = 0
    with session_scope() as session:
        for candle in convert_to_models(frame):
            existing = session.execute(
                select(Candle).where(
                    and_(
                        Candle.symbol == candle.symbol,
                        Candle.interval == candle.interval,
                        Candle.event_time == candle.event_time,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                # update existing record
                existing.open = candle.open
                existing.high = candle.high
                existing.low = candle.low
                existing.close = candle.close
                existing.volume = candle.volume
                existing.turnover = candle.turnover
            else:
                session.add(candle)
                imported += 1

    return {"imported": imported}, 201


@app.route("/api/contracts", methods=["GET"])
def contracts():
    """Return imported contract metadata."""

    return jsonify({"items": list_available_contracts()})


@app.route("/api/candles", methods=["GET"])
def list_candles():
    """Return candles with indicators for the chart."""

    symbol = request.args.get("symbol")
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    interval = request.args.get("interval", "1d")

    if not symbol:
        return {"message": "symbol is required"}, 400

    frame = load_candles_from_db(symbol, interval=interval, start=start, end=end)

    if frame.empty:
        return {"items": []}, 200

    response = [
        {
            "event_time": (
                row.event_time.to_pydatetime().isoformat()
                if hasattr(row.event_time, "to_pydatetime")
                else row.event_time.isoformat()
            ),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": None if pd.isna(row.volume) else float(row.volume),
            "turnover": None if pd.isna(row.turnover) else float(row.turnover),
            "boll_mid": None if pd.isna(row.boll_mid) else float(row.boll_mid),
            "boll_upper": None if pd.isna(row.boll_upper) else float(row.boll_upper),
            "boll_lower": None if pd.isna(row.boll_lower) else float(row.boll_lower),
            "volume_ma": None if pd.isna(row.volume_ma) else float(row.volume_ma),
        }
        for row in frame.itertuples()
    ]

    return jsonify({"items": response})


@app.route("/api/playback/start", methods=["POST"])
def playback_start():
    payload = request.get_json(force=True)
    symbol = payload.get("symbol")
    interval = payload.get("interval", "1d")
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")

    if not symbol:
        return {"message": "symbol is required"}, 400

    try:
        state = playback_manager.start(
            symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        return {"message": str(exc)}, 400

    return jsonify({"status": state.as_dict()})


@app.route("/api/playback/pause", methods=["POST"])
def playback_pause():
    try:
        state = playback_manager.pause()
    except ValueError as exc:
        return {"message": str(exc)}, 400
    return jsonify({"status": state.as_dict()})


@app.route("/api/playback/resume", methods=["POST"])
def playback_resume():
    try:
        state = playback_manager.resume()
    except ValueError as exc:
        return {"message": str(exc)}, 400
    return jsonify({"status": state.as_dict()})


@app.route("/api/playback/seek", methods=["POST"])
def playback_seek():
    payload = request.get_json(force=True)
    timestamp = payload.get("timestamp")
    if not timestamp:
        return {"message": "timestamp is required"}, 400
    try:
        state = playback_manager.seek(timestamp)
    except ValueError as exc:
        return {"message": str(exc)}, 400
    return jsonify({"status": state.as_dict()})


@app.route("/api/playback/status", methods=["GET"])
def playback_status():
    state = playback_manager.status()
    if not state:
        return jsonify({"status": None})
    return jsonify({"status": state.as_dict()})


@app.route("/api/playback/next", methods=["GET"])
def playback_next():
    count = request.args.get("count", default=1, type=int)
    try:
        items, state = playback_manager.next(count)
    except ValueError as exc:
        return {"message": str(exc)}, 400

    return jsonify({"items": list(items), "status": state.as_dict(), "has_more": state.index < state.frame.shape[0]})


@app.route("/api/trades", methods=["GET"])
def get_trades():
    """List stored simulated trades."""

    with session_scope() as session:
        trades = session.execute(select(SimulatedTrade).order_by(SimulatedTrade.trade_time)).scalars().all()

    payload = [
        {
            "id": trade.id,
            "symbol": trade.symbol,
            "direction": trade.direction,
            "price": float(trade.price),
            "quantity": trade.quantity,
            "trade_time": trade.trade_time.isoformat(),
            "note": trade.note,
        }
        for trade in trades
    ]

    return jsonify({"items": payload})


@app.route("/api/trades", methods=["POST"])
def create_trade():
    """Create a new simulated trade."""

    payload = request.get_json(force=True)
    symbol = payload.get("symbol")
    direction = payload.get("direction")
    price = payload.get("price")
    quantity = payload.get("quantity", 1)
    note = payload.get("note")

    if not symbol or direction not in DIRECTION_MULTIPLIER:
        return {"message": "symbol and direction (buy/sell) are required"}, 400
    if price is None:
        return {"message": "price is required"}, 400
    if quantity <= 0:
        return {"message": "quantity must be positive"}, 400

    trade = SimulatedTrade(
        symbol=symbol,
        direction=direction,
        price=Decimal(str(price)),
        quantity=int(quantity),
        note=note,
    )

    with session_scope() as session:
        session.add(trade)
        session.flush()
        trade_id = trade.id

    return {"id": trade_id}, 201


@app.route("/api/trades/<int:trade_id>", methods=["DELETE"])
def delete_trade(trade_id: int):
    """Delete a simulated trade by identifier."""

    with session_scope() as session:
        trade = session.get(SimulatedTrade, trade_id)
        if not trade:
            return {"message": "trade not found"}, 404
        session.delete(trade)

    return {"status": "deleted"}, 200


@app.route("/api/portfolio", methods=["GET"])
def portfolio_summary():
    """Return aggregated portfolio metrics."""

    with session_scope() as session:
        trades = session.execute(select(SimulatedTrade).order_by(SimulatedTrade.trade_time)).scalars().all()
        latest_candles: Dict[str, Candle] = {}
        for trade in trades:
            candle = session.execute(
                select(Candle)
                .where(Candle.symbol == trade.symbol)
                .order_by(Candle.event_time.desc())
                .limit(1)
            ).scalar_one_or_none()
            if candle:
                latest_candles[trade.symbol] = candle

    summary = summarize_portfolio(trades, latest_candles)

    return jsonify(
        {
            "positions": {
                symbol: {
                    "quantity": position.quantity,
                    "average_price": float(position.average_price),
                    "last_price": summary.last_mark_prices.get(symbol),
                }
                for symbol, position in summary.positions.items()
            },
            "realized_pnl": float(summary.realized_pnl),
            "unrealized_pnl": float(summary.unrealized_pnl),
        }
    )


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=8000, debug=True)
