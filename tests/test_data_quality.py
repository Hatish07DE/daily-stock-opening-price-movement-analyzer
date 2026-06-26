from pathlib import Path
import sys

import pandas as pd
import pytest


# Allow pytest to import modules from src/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from data_quality import (
    DataQualityError,
    validate_golden_summary,
    validate_news_data,
    validate_price_data,
    validate_price_movement_data,
)


def test_duplicate_symbol_and_price_date_should_fail():
    """
    Duplicate stock records for the same symbol and trading date
    should not be allowed.
    """
    raw_prices_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "price_date": "2026-06-10",
                "open_price": 198.20,
            },
            {
                "symbol": "AAPL",
                "price_date": "2026-06-10",
                "open_price": 198.20,
            },
        ]
    )

    with pytest.raises(
        DataQualityError,
        match="Duplicate stock price records found",
    ):
        validate_price_data(raw_prices_df)


def test_missing_open_price_should_fail():
    """
    Missing opening price should fail validation.
    """
    raw_prices_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "price_date": "2026-06-10",
                "open_price": None,
            }
        ]
    )

    with pytest.raises(
        DataQualityError,
        match="missing open_price values",
    ):
        validate_price_data(raw_prices_df)


def test_zero_or_negative_open_price_should_fail():
    """
    Zero and negative opening prices are invalid.
    """
    raw_prices_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "price_date": "2026-06-10",
                "open_price": 0,
            }
        ]
    )

    with pytest.raises(
        DataQualityError,
        match="invalid open_price values",
    ):
        validate_price_data(raw_prices_df)


def test_blank_news_headline_should_fail():
    """
    Raw news records must contain a usable headline.
    """
    raw_news_df = pd.DataFrame(
        [
            {
                "symbol": "MSFT",
                "headline": "   ",
                "published_at": "2026-06-11 08:15:00",
            }
        ]
    )

    with pytest.raises(
        DataQualityError,
        match="blank headlines",
    ):
        validate_news_data(raw_news_df)


def test_duplicate_symbol_in_price_movement_should_fail():
    """
    Processed price movement must have only one record per stock.
    """
    price_movement_df = pd.DataFrame(
        [
            {
                "symbol": "NVDA",
                "previous_open_price": 890.00,
                "current_open_price": 917.59,
                "open_price_change": 27.59,
                "open_price_change_pct": 3.10,
                "movement_direction": "UP",
            },
            {
                "symbol": "NVDA",
                "previous_open_price": 917.59,
                "current_open_price": 920.00,
                "open_price_change": 2.41,
                "open_price_change_pct": 0.26,
                "movement_direction": "UP",
            },
        ]
    )

    with pytest.raises(
        DataQualityError,
        match="duplicate stock symbols",
    ):
        validate_price_movement_data(price_movement_df)


def test_invalid_movement_direction_should_fail():
    """
    Only UP, DOWN, and FLAT are valid movement directions.
    """
    price_movement_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "previous_open_price": 198.20,
                "current_open_price": 203.10,
                "open_price_change": 4.90,
                "open_price_change_pct": 2.47,
                "movement_direction": "RISING",
            }
        ]
    )

    with pytest.raises(
        DataQualityError,
        match="Invalid movement_direction values",
    ):
        validate_price_movement_data(price_movement_df)


def test_golden_record_count_mismatch_should_fail():
    """
    Golden output should contain one summary record for every
    processed stock price movement record.
    """
    price_movement_df = pd.DataFrame(
        [
            {"symbol": "AAPL"},
            {"symbol": "MSFT"},
            {"symbol": "NVDA"},
        ]
    )

    golden_summary_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "movement_direction": "UP",
                "summary_comment": "AAPL opened higher.",
                "confidence_level": "MEDIUM",
            },
            {
                "symbol": "MSFT",
                "movement_direction": "DOWN",
                "summary_comment": "MSFT opened lower.",
                "confidence_level": "MEDIUM",
            },
        ]
    )

    with pytest.raises(
        DataQualityError,
        match="record count does not match",
    ):
        validate_golden_summary(
            golden_summary_df=golden_summary_df,
            price_movement_df=price_movement_df,
        )


def test_valid_price_data_should_pass():
    """
    Valid raw price records should pass without raising an error.
    """
    raw_prices_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "price_date": "2026-06-10",
                "open_price": 198.20,
            },
            {
                "symbol": "AAPL",
                "price_date": "2026-06-11",
                "open_price": 203.10,
            },
        ]
    )

    validate_price_data(raw_prices_df)