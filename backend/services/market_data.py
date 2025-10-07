"""Market data utilities relying on AkShare and the local database."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Tuple

import akshare as ak
import pandas as pd
from sqlalchemy import func, select

from ..database import session_scope
from ..models import Candle
from ..utils.indicators import enrich_indicators

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_date(date_str: str) -> datetime:
    """Parse a date string that may include time information."""

    for fmt in (DATETIME_FORMAT, DATE_FORMAT):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {date_str}")


def fetch_candles(symbol: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    """Fetch futures K-line data from AkShare."""

    start_dt = _parse_date(start)
    end_dt = _parse_date(end)

    if interval == "1d":
        raw = ak.futures_zh_daily_sina(symbol=symbol)
        raw.rename(
            columns={"date": "event_time", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"},
            inplace=True,
        )
        raw["event_time"] = pd.to_datetime(raw["event_time"])
    else:
        raw = ak.futures_zh_minute_sina(symbol=symbol, period=interval)
        raw.rename(
            columns={"datetime": "event_time", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"},
            inplace=True,
        )
        raw["event_time"] = pd.to_datetime(raw["event_time"])

    filtered = raw[(raw["event_time"] >= start_dt) & (raw["event_time"] <= end_dt)].copy()
    filtered.sort_values("event_time", inplace=True)

    if "turnover" not in filtered.columns:
        filtered["turnover"] = None

    filtered["interval"] = interval
    filtered["symbol"] = symbol

    return enrich_indicators(filtered)


def load_candles_from_db(
    symbol: str,
    *,
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Load candles from SQLite and attach indicators."""

    start_dt = _parse_date(start) if start else None
    end_dt = _parse_date(end) if end else None

    with session_scope() as session:
        query = select(Candle).where(Candle.symbol == symbol, Candle.interval == interval)
        if start_dt:
            query = query.where(Candle.event_time >= start_dt)
        if end_dt:
            query = query.where(Candle.event_time <= end_dt)
        query = query.order_by(Candle.event_time.asc())

        rows: List[Candle] = [row[0] for row in session.execute(query).all()]

    if not rows:
        return pd.DataFrame(
            columns=[
                "event_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "turnover",
            ]
        )

    frame = pd.DataFrame(
        [
            {
                "event_time": candle.event_time,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "turnover": candle.turnover,
            }
            for candle in rows
        ]
    )

    frame.sort_values("event_time", inplace=True)
    return enrich_indicators(frame)


def convert_to_models(frame: pd.DataFrame) -> Iterable[Candle]:
    """Transform a dataframe into Candle model instances."""

    records: Iterable[Tuple] = frame[[
        "symbol",
        "interval",
        "event_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover",
    ]].itertuples(index=False, name=None)

    for record in records:
        yield Candle(
            symbol=record[0],
            interval=record[1],
            event_time=record[2].to_pydatetime() if hasattr(record[2], "to_pydatetime") else record[2],
            open=record[3],
            high=record[4],
            low=record[5],
            close=record[6],
            volume=None if pd.isna(record[7]) else float(record[7]),
            turnover=None if pd.isna(record[8]) else float(record[8]),
        )


def list_available_contracts() -> list[dict[str, object]]:
    """Return imported contracts along with their available date ranges."""

    with session_scope() as session:
        results = session.execute(
            select(
                Candle.symbol,
                Candle.interval,
                func.min(Candle.event_time),
                func.max(Candle.event_time),
                func.count(),
            ).group_by(Candle.symbol, Candle.interval)
        ).all()

    payload = []
    for symbol, interval, start_dt, end_dt, count in results:
        payload.append(
            {
                "symbol": symbol,
                "interval": interval,
                "start_date": start_dt.isoformat() if start_dt else None,
                "end_date": end_dt.isoformat() if end_dt else None,
                "records": int(count or 0),
            }
        )

    return payload
