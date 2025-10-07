"""Indicator calculations for K-line series."""

from __future__ import annotations

import pandas as pd


def apply_bollinger_bands(
    frame: pd.DataFrame,
    window: int = 20,
    multiplier: float = 2.0,
) -> pd.DataFrame:
    """Calculate Bollinger Bands on the given dataframe."""

    rolling_mean = frame["close"].rolling(window=window, min_periods=window)
    mean = rolling_mean.mean()
    std = frame["close"].rolling(window=window, min_periods=window).std(ddof=0)

    frame["boll_mid"] = mean
    frame["boll_upper"] = mean + multiplier * std
    frame["boll_lower"] = mean - multiplier * std
    return frame


def apply_volume_indicators(frame: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """Attach moving averages for volume."""

    frame["volume_ma"] = frame["volume"].rolling(window=window, min_periods=1).mean()
    return frame


def enrich_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """Add default indicators used by the training UI."""

    frame = apply_bollinger_bands(frame)
    frame = apply_volume_indicators(frame)
    return frame
