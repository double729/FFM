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

_COLUMN_MAPPING = {
    "date": "event_time",
    "datetime": "event_time",
    "time": "event_time",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "vol": "volume",
    "成交量": "volume",
    "amount": "turnover",
    "turnover": "turnover",
    "成交额": "turnover",
}


def _parse_date(date_str: str) -> datetime:
    """Parse a date string that may include time information."""

    for fmt in (DATETIME_FORMAT, DATE_FORMAT):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {date_str}")


def _normalize_symbol(symbol: str) -> str:
    """Normalize symbol strings for consistent storage and lookup."""

    cleaned = (symbol or "").strip().upper()
    if not cleaned:
        raise ValueError("symbol is required")
    return cleaned


def _normalize_interval(interval: str | int | None) -> str:
    """Normalize interval representation used across API and storage."""

    if interval is None:
        return "1d"

    value = str(interval).strip().lower()
    if value in {"1d", "day", "daily"}:
        return "1d"
    if value.endswith("m"):
        value = value[:-1]
    return value or "1d"


def fetch_candles(symbol: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    """Fetch futures K-line data from AkShare."""

    normalized_symbol = _normalize_symbol(symbol)
    normalized_interval = _normalize_interval(interval)

    start_dt = _parse_date(start)
    end_dt = _parse_date(end)
    if start_dt > end_dt:
        raise ValueError("start date must not be after end date")

    raw = None
    last_error: Exception | None = None
    candidate_symbols: list[str] = []
    original_symbol = (symbol or "").strip()
    for candidate in (normalized_symbol, original_symbol, original_symbol.upper(), original_symbol.lower()):
        if candidate and candidate not in candidate_symbols:
            candidate_symbols.append(candidate)

    for candidate in candidate_symbols:
        try:
            if normalized_interval == "1d":
                raw = ak.futures_zh_daily(symbol=candidate)
            else:
                period = normalized_interval or "1"
                raw = ak.futures_zh_minute_sina(symbol=candidate, period=period)
        except Exception as exc:  # pragma: no cover - AkShare runtime specific
            last_error = exc
            raw = None
            continue

        if raw is not None and not raw.empty:
            break

    if raw is None or raw.empty:
        if last_error:
            raise ValueError(f"AkShare 获取数据失败: {last_error}") from last_error
        raise ValueError("AkShare 未返回任何数据，请确认合约代码与日期区间")

    frame = raw.rename(columns=_COLUMN_MAPPING).copy()

    if "event_time" not in frame.columns:
        raise ValueError("AkShare 响应缺少时间字段，无法解析")

    frame["event_time"] = pd.to_datetime(frame["event_time"], errors="coerce")
    frame = frame.dropna(subset=["event_time"])

    for col in ("open", "high", "low", "close", "volume", "turnover"):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

    filtered = frame[(frame["event_time"] >= start_dt) & (frame["event_time"] <= end_dt)].copy()
    filtered.sort_values("event_time", inplace=True)

    if filtered.empty:
        raise ValueError("指定日期区间内没有可用的行情数据")

    if "volume" not in filtered.columns:
        filtered["volume"] = pd.NA
    if "turnover" not in filtered.columns:
        filtered["turnover"] = pd.NA

    filtered["interval"] = normalized_interval
    filtered["symbol"] = normalized_symbol

    return enrich_indicators(filtered)


def load_candles_from_db(
    symbol: str,
    *,
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Load candles from SQLite and attach indicators."""

    normalized_symbol = _normalize_symbol(symbol)
    normalized_interval = _normalize_interval(interval)

    start_dt = _parse_date(start) if start else None
    end_dt = _parse_date(end) if end else None

    with session_scope() as session:
        query = select(Candle).where(
            Candle.symbol == normalized_symbol, Candle.interval == normalized_interval
        )
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
