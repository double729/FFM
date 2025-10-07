"""Market data utilities relying on AkShare."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Tuple

import akshare as ak
import pandas as pd

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
