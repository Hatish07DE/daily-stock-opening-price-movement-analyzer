from typing import List

import pandas as pd


class DataQualityError(Exception):
    """
    Raised when a data-quality validation fails.
    """


def validate_required_columns(
    df: pd.DataFrame,
    required_columns: List[str],
    dataset_name: str,
) -> None:
    """
    Confirms all expected columns exist in a dataframe.
    """
    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise DataQualityError(
            f"{dataset_name} is missing required columns: {missing_columns}"
        )


def validate_price_data(raw_prices_df: pd.DataFrame) -> None:
    """
    Validates raw stock-price data before transformation.
    """

    required_columns = [
        "symbol",
        "price_date",
        "open_price",
    ]

    validate_required_columns(
        df=raw_prices_df,
        required_columns=required_columns,
        dataset_name="Raw stock price data",
    )

    if raw_prices_df.empty:
        raise DataQualityError("Raw stock price data is empty.")

    duplicate_records = raw_prices_df.duplicated(
        subset=["symbol", "price_date"],
        keep=False,
    )

    if duplicate_records.any():
        duplicate_rows = raw_prices_df.loc[
            duplicate_records,
            ["symbol", "price_date"],
        ]

        raise DataQualityError(
            "Duplicate stock price records found for symbol and price_date: "
            f"{duplicate_rows.to_dict(orient='records')}"
        )

    missing_open_prices = raw_prices_df["open_price"].isna().sum()

    if missing_open_prices > 0:
        raise DataQualityError(
            f"Raw stock price data contains {missing_open_prices} missing open_price values."
        )

    invalid_open_prices = (raw_prices_df["open_price"] <= 0).sum()

    if invalid_open_prices > 0:
        raise DataQualityError(
            f"Raw stock price data contains {invalid_open_prices} invalid open_price values."
        )


def validate_news_data(raw_news_df: pd.DataFrame) -> None:
    """
    Validates raw stock-news data before transformation.
    """

    required_columns = [
        "symbol",
        "headline",
        "published_at",
    ]

    validate_required_columns(
        df=raw_news_df,
        required_columns=required_columns,
        dataset_name="Raw stock news data",
    )

    if raw_news_df.empty:
        raise DataQualityError("Raw stock news data is empty.")

    blank_headlines = (
        raw_news_df["headline"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    if blank_headlines > 0:
        raise DataQualityError(
            f"Raw stock news data contains {blank_headlines} blank headlines."
        )

    blank_symbols = (
        raw_news_df["symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    if blank_symbols > 0:
        raise DataQualityError(
            f"Raw stock news data contains {blank_symbols} blank symbols."
        )


def validate_price_movement_data(price_movement_df: pd.DataFrame) -> None:
    """
    Validates transformed stock opening-price movement data.
    """

    required_columns = [
        "symbol",
        "previous_open_price",
        "current_open_price",
        "open_price_change",
        "open_price_change_pct",
        "movement_direction",
    ]

    validate_required_columns(
        df=price_movement_df,
        required_columns=required_columns,
        dataset_name="Processed stock price movement data",
    )

    if price_movement_df.empty:
        raise DataQualityError("Processed stock price movement data is empty.")

    duplicate_symbols = price_movement_df.duplicated(
        subset=["symbol"],
        keep=False,
    )

    if duplicate_symbols.any():
        duplicates = price_movement_df.loc[
            duplicate_symbols,
            ["symbol"],
        ].to_dict(orient="records")

        raise DataQualityError(
            f"Processed price movement contains duplicate stock symbols: {duplicates}"
        )

    allowed_directions = {"UP", "DOWN", "FLAT"}

    invalid_directions = price_movement_df.loc[
        ~price_movement_df["movement_direction"].isin(allowed_directions),
        "movement_direction",
    ]

    if not invalid_directions.empty:
        raise DataQualityError(
            "Invalid movement_direction values found: "
            f"{invalid_directions.tolist()}"
        )

    invalid_prices = (
        (price_movement_df["previous_open_price"] <= 0)
        | (price_movement_df["current_open_price"] <= 0)
    ).sum()

    if invalid_prices > 0:
        raise DataQualityError(
            f"Processed price movement contains {invalid_prices} invalid open-price records."
        )


def validate_processed_news_data(processed_news_df: pd.DataFrame) -> None:
    """
    Validates cleaned and ranked stock-news data.
    """

    required_columns = [
        "symbol",
        "headline",
        "news_rank",
    ]

    validate_required_columns(
        df=processed_news_df,
        required_columns=required_columns,
        dataset_name="Processed stock news data",
    )

    if processed_news_df.empty:
        raise DataQualityError("Processed stock news data is empty.")

    duplicate_headlines = processed_news_df.duplicated(
        subset=["symbol", "headline"],
        keep=False,
    )

    if duplicate_headlines.any():
        duplicates = processed_news_df.loc[
            duplicate_headlines,
            ["symbol", "headline"],
        ].to_dict(orient="records")

        raise DataQualityError(
            f"Duplicate processed news headlines found: {duplicates}"
        )

    invalid_ranks = (processed_news_df["news_rank"] <= 0).sum()

    if invalid_ranks > 0:
        raise DataQualityError(
            f"Processed stock news contains {invalid_ranks} invalid news_rank values."
        )


def validate_golden_summary(
    golden_summary_df: pd.DataFrame,
    price_movement_df: pd.DataFrame,
) -> None:
    """
    Validates final golden output before it is emailed or published.
    """

    required_columns = [
        "symbol",
        "movement_direction",
        "summary_comment",
        "confidence_level",
    ]

    validate_required_columns(
        df=golden_summary_df,
        required_columns=required_columns,
        dataset_name="Golden stock summary",
    )

    if golden_summary_df.empty:
        raise DataQualityError("Golden stock summary is empty.")

    if len(golden_summary_df) != len(price_movement_df):
        raise DataQualityError(
            "Golden summary record count does not match price movement record count. "
            f"Golden records: {len(golden_summary_df)}, "
            f"Price movement records: {len(price_movement_df)}"
        )

    missing_summaries = (
        golden_summary_df["summary_comment"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    if missing_summaries > 0:
        raise DataQualityError(
            f"Golden summary contains {missing_summaries} blank summary comments."
        )