"""Simple in-memory playback manager for historical candles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable

import pandas as pd

from .market_data import load_candles_from_db


@dataclass
class PlaybackState:
    """Represent the current playback configuration and progress."""

    symbol: str
    interval: str
    start: datetime
    end: datetime
    frame: pd.DataFrame
    index: int = 0
    playing: bool = False

    def as_dict(self) -> Dict[str, object]:
        """Serialize the playback state for API responses."""

        total = len(self.frame)
        current_time = None
        if 0 <= self.index - 1 < total:
            current_time = self.frame.iloc[self.index - 1]["event_time"]
            if hasattr(current_time, "to_pydatetime"):
                current_time = current_time.to_pydatetime()

        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "total": total,
            "current_index": self.index,
            "playing": self.playing,
            "current_time": current_time.isoformat() if current_time is not None else None,
        }


class PlaybackManager:
    """Manage a single-user playback session stored in memory."""

    def __init__(self) -> None:
        self._state: PlaybackState | None = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def start(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> PlaybackState:
        """Start a playback session by loading candles into memory."""

        frame = load_candles_from_db(symbol, interval=interval, start=start_date, end=end_date)
        if frame.empty:
            raise ValueError("No candles available for the requested range")

        # Pandas uses Timestamp; convert to datetime for metadata while keeping Timestamp in frame.
        first_value = frame.iloc[0]["event_time"]
        last_value = frame.iloc[-1]["event_time"]
        start_at = first_value.to_pydatetime() if hasattr(first_value, "to_pydatetime") else first_value
        end_at = last_value.to_pydatetime() if hasattr(last_value, "to_pydatetime") else last_value

        state = PlaybackState(
            symbol=symbol,
            interval=interval,
            start=start_at,
            end=end_at,
            frame=frame.reset_index(drop=True),
            index=0,
            playing=True,
        )
        self._state = state
        return state

    def stop(self) -> None:
        """Terminate the current playback session."""

        self._state = None

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------
    def pause(self) -> PlaybackState:
        state = self._require_state()
        state.playing = False
        return state

    def resume(self) -> PlaybackState:
        state = self._require_state()
        state.playing = True
        return state

    def seek(self, timestamp: str) -> PlaybackState:
        state = self._require_state()
        target = pd.to_datetime(timestamp)

        matches = state.frame[state.frame["event_time"] >= target]
        if matches.empty:
            state.index = len(state.frame)
            state.playing = False
        else:
            state.index = int(matches.index[0])
        return state

    # ------------------------------------------------------------------
    # Data retrieval
    # ------------------------------------------------------------------
    def next(self, count: int = 1) -> tuple[Iterable[dict[str, object]], PlaybackState]:
        state = self._require_state()
        if count <= 0:
            return [], state

        start_idx = state.index
        end_idx = min(start_idx + count, len(state.frame))

        chunk = state.frame.iloc[start_idx:end_idx]
        state.index = end_idx

        if state.index >= len(state.frame):
            state.playing = False

        records = [
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
            for row in chunk.itertuples()
        ]

        return records, state

    def status(self) -> PlaybackState | None:
        return self._state

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _require_state(self) -> PlaybackState:
        if not self._state:
            raise ValueError("Playback has not been started")
        return self._state
