from pathlib import Path
import sys

import pandas as pd
import pytest


# Allows pytest to import files from the src folder
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from transform_prices import calculate_open_price_movement


def build_price_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Creates a small test dataframe that matches the fields required by
    calculate_open_price_movement().
    """
    return pd.DataFrame(records)


def test_open_price_movement_up():
    """
    Current open is higher than previous trading day open.
    """
    raw_df = build_price_dataframe(
        [
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc",
                "price_date": "2026-06-10",
                "open_price": 198.20,
            },
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc",
                "price_date": "2026-06-11",
                "open_price": 203.10,
            },
        ]
    )

    result_df = calculate_open_price_movement(raw_df)

    assert len(result_df) == 1

    result = result_df.iloc[0]

    assert result["symbol"] == "AAPL"
    assert result["previous_open_price"] == 198.20
    assert result["current_open_price"] == 203.10
    assert result["open_price_change"] == 4.90
    assert result["open_price_change_pct"] == pytest.approx(2.4723, abs=0.0001)
    assert result["movement_direction"] == "UP"


def test_open_price_movement_down():
    """
    Current open is lower than previous trading day open.
    """
    raw_df = build_price_dataframe(
        [
            {
                "symbol": "MSFT",
                "company_name": "Microsoft Corporation",
                "price_date": "2026-06-10",
                "open_price": 424.00,
            },
            {
                "symbol": "MSFT",
                "company_name": "Microsoft Corporation",
                "price_date": "2026-06-11",
                "open_price": 419.50,
            },
        ]
    )

    result_df = calculate_open_price_movement(raw_df)
    result = result_df.iloc[0]

    assert result["symbol"] == "MSFT"
    assert result["open_price_change"] == -4.50
    assert result["open_price_change_pct"] == pytest.approx(-1.0613, abs=0.0001)
    assert result["movement_direction"] == "DOWN"


def test_open_price_movement_flat():
    """
    Current open equals previous trading day open.
    """
    raw_df = build_price_dataframe(
        [
            {
                "symbol": "NVDA",
                "company_name": "NVIDIA Corporation",
                "price_date": "2026-06-10",
                "open_price": 890.00,
            },
            {
                "symbol": "NVDA",
                "company_name": "NVIDIA Corporation",
                "price_date": "2026-06-11",
                "open_price": 890.00,
            },
        ]
    )

    result_df = calculate_open_price_movement(raw_df)
    result = result_df.iloc[0]

    assert result["open_price_change"] == 0
    assert result["open_price_change_pct"] == 0
    assert result["movement_direction"] == "FLAT"


def test_uses_latest_two_available_trading_dates():
    """
    Confirms the function uses the two latest available dates,
    not simply the first two rows provided.
    """
    raw_df = build_price_dataframe(
        [
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc",
                "price_date": "2026-06-09",
                "open_price": 190.00,
            },
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc",
                "price_date": "2026-06-11",
                "open_price": 203.10,
            },
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc",
                "price_date": "2026-06-10",
                "open_price": 198.20,
            },
        ]
    )

    result_df = calculate_open_price_movement(raw_df)
    result = result_df.iloc[0]

    assert str(result["previous_trading_date"]) == "2026-06-10"
    assert str(result["current_trading_date"]) == "2026-06-11"
    assert result["previous_open_price"] == 198.20
    assert result["current_open_price"] == 203.10


def test_missing_open_price_does_not_create_movement_record():
    """
    A stock with only one valid opening price cannot be compared,
    so the transformation should fail clearly.
    """
    raw_df = build_price_dataframe(
        [
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc",
                "price_date": "2026-06-10",
                "open_price": 198.20,
            },
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc",
                "price_date": "2026-06-11",
                "open_price": None,
            },
        ]
    )

    with pytest.raises(RuntimeError, match="No price movement records were created"):
        calculate_open_price_movement(raw_df)