from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_INPUT_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"


def get_latest_raw_price_file(raw_dir: Path) -> Path:
    """
    Finds the latest raw stock price CSV file from data/raw.
    Expected file pattern:
    stock_prices_raw_YYYY-MM-DD.csv
    """
    files = list(raw_dir.glob("stock_prices_raw_*.csv"))

    if not files:
        raise FileNotFoundError(
            f"No raw stock price files found in {raw_dir}. "
            "Please run extract_prices.py first."
        )

    latest_file = max(files, key=lambda file: file.stat().st_mtime)

    return latest_file


def read_raw_prices(input_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Reads raw stock price data from CSV.
    If no input path is provided, it reads the latest raw price file.
    """
    if input_path is None:
        input_path = get_latest_raw_price_file(RAW_INPUT_DIR)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)

    required_columns = [
        "symbol",
        "company_name",
        "price_date",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
        "api_source",
        "ingestion_timestamp",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    df["price_date"] = pd.to_datetime(df["price_date"]).dt.date
    df["open_price"] = pd.to_numeric(df["open_price"], errors="coerce")

    return df


def calculate_open_price_movement(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each stock symbol:
    - Get the latest trading date
    - Get the previous trading date
    - Compare previous open price vs current open price
    """
    if raw_df.empty:
        raise ValueError("Raw price dataframe is empty.")

    # Remove records where open price is missing
    df = raw_df.dropna(subset=["open_price"]).copy()

    if df.empty:
        raise ValueError("No valid open price records found.")

    movement_records = []

    for symbol, stock_df in df.groupby("symbol"):
        stock_df = stock_df.sort_values("price_date", ascending=False)

        # Get unique trading dates in descending order
        trading_dates = stock_df["price_date"].drop_duplicates().tolist()

        if len(trading_dates) < 2:
            print(f"Skipping {symbol}: less than 2 trading dates available.")
            continue

        current_trading_date = trading_dates[0]
        previous_trading_date = trading_dates[1]

        current_row = stock_df[stock_df["price_date"] == current_trading_date].iloc[0]
        previous_row = stock_df[stock_df["price_date"] == previous_trading_date].iloc[0]

        current_open_price = float(current_row["open_price"])
        previous_open_price = float(previous_row["open_price"])

        open_price_change = current_open_price - previous_open_price

        if previous_open_price == 0:
            open_price_change_pct = None
        else:
            open_price_change_pct = (open_price_change / previous_open_price) * 100

        if open_price_change > 0:
            movement_direction = "UP"
        elif open_price_change < 0:
            movement_direction = "DOWN"
        else:
            movement_direction = "FLAT"

        movement_records.append(
            {
                "load_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "symbol": symbol,
                "company_name": current_row.get("company_name", ""),
                "previous_trading_date": previous_trading_date,
                "current_trading_date": current_trading_date,
                "previous_open_price": round(previous_open_price, 4),
                "current_open_price": round(current_open_price, 4),
                "open_price_change": round(open_price_change, 4),
                "open_price_change_pct": (
                    round(open_price_change_pct, 4)
                    if open_price_change_pct is not None
                    else None
                ),
                "movement_direction": movement_direction,
                "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    if not movement_records:
        raise RuntimeError("No price movement records were created.")

    movement_df = pd.DataFrame(movement_records)

    movement_df = movement_df.sort_values(
        by=["open_price_change_pct"],
        ascending=False,
        na_position="last",
    )

    return movement_df


def save_processed_prices(df: pd.DataFrame) -> Path:
    """
    Saves transformed stock movement data into data/processed.
    """
    PROCESSED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    load_date = datetime.utcnow().strftime("%Y-%m-%d")

    output_path = (
        PROCESSED_OUTPUT_DIR
        / f"stock_open_price_movement_{load_date}.csv"
    )

    df.to_csv(output_path, index=False)

    return output_path


if __name__ == "__main__":
    raw_prices_df = read_raw_prices()
    movement_df = calculate_open_price_movement(raw_prices_df)
    saved_path = save_processed_prices(movement_df)

    print("\nPrice transformation completed.")
    print(f"Processed price movement data saved to: {saved_path}")
    print("\nPrice movement sample:")
    print(movement_df)