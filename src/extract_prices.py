import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd
import requests
from dotenv import load_dotenv


# Load environment variables from .env
load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WATCHLIST_PATH = PROJECT_ROOT / "config" / "stock_watchlist.json"
RAW_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"
SAMPLE_INPUT_DIR = PROJECT_ROOT / "data" / "sample"
SAMPLE_STOCK_PRICES_PATH = SAMPLE_INPUT_DIR / "sample_stock_prices.csv"

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


def read_watchlist(file_path: Path) -> List[Dict[str, str]]:
    """
    Reads selected stock symbols from config/stock_watchlist.json.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Watchlist file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as file:
        watchlist = json.load(file)

    if not isinstance(watchlist, list) or len(watchlist) == 0:
        raise ValueError("Watchlist must be a non-empty list.")

    for stock in watchlist:
        if "symbol" not in stock:
            raise ValueError("Each watchlist item must contain a 'symbol' field.")

    return watchlist


def fetch_daily_prices(symbol: str, api_key: str) -> Dict[str, Any]:
    """
    Calls Alpha Vantage TIME_SERIES_DAILY API for one stock symbol.
    This returns daily OHLCV data.
    """
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": api_key,
    }

    response = requests.get(
        ALPHA_VANTAGE_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()
    data = response.json()

    # Alpha Vantage returns these keys for errors / limits
    if "Error Message" in data:
        raise ValueError(f"API error for {symbol}: {data['Error Message']}")

    if "Note" in data:
        raise RuntimeError(
            f"API rate limit reached for {symbol}. "
            "Please wait and try again later, reduce stock count, or use another data source."
        )

    if "Information" in data:
        raise RuntimeError(
            f"API information message for {symbol}. "
            "This is usually caused by API rate limits, invalid API key, or request frequency limits."
        )

    if "Time Series (Daily)" not in data:
        safe_keys = list(data.keys())
        raise ValueError(
            f"Unexpected API response for {symbol}. Response keys: {safe_keys}"
        )

    return data


def parse_daily_prices(symbol: str, company_name: str, api_response: Dict[str, Any]) -> pd.DataFrame:
    """
    Converts Alpha Vantage JSON response into a normalized DataFrame.
    """
    time_series = api_response["Time Series (Daily)"]
    ingestion_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    records = []

    for price_date, values in time_series.items():
        records.append(
            {
                "symbol": symbol,
                "company_name": company_name,
                "price_date": price_date,
                "open_price": float(values["1. open"]),
                "high_price": float(values["2. high"]),
                "low_price": float(values["3. low"]),
                "close_price": float(values["4. close"]),
                "volume": int(values["5. volume"]),
                "api_source": "alpha_vantage",
                "ingestion_timestamp": ingestion_timestamp,
            }
        )

    df = pd.DataFrame(records)

    if df.empty:
        raise ValueError(f"No price records found for {symbol}")

    df["price_date"] = pd.to_datetime(df["price_date"]).dt.date

    df = df.sort_values(
        by=["symbol", "price_date"],
        ascending=[True, False],
    )

    return df

def load_sample_prices() -> pd.DataFrame:
    """
    Loads sample stock price data when USE_SAMPLE_DATA=true.
    This is useful for local testing when external API limits are reached.
    """
    if not SAMPLE_STOCK_PRICES_PATH.exists():
        raise FileNotFoundError(
            f"Sample stock price file not found: {SAMPLE_STOCK_PRICES_PATH}"
        )

    df = pd.read_csv(SAMPLE_STOCK_PRICES_PATH)

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
        raise ValueError(f"Missing required columns in sample price file: {missing_columns}")

    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    df["price_date"] = pd.to_datetime(df["price_date"]).dt.date

    numeric_columns = [
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["api_source"] = "sample"

    return df


def extract_prices() -> pd.DataFrame:
    """
    Main extraction function.

    If USE_SAMPLE_DATA=true:
        Reads sample stock price data from data/sample/sample_stock_prices.csv

    Else:
        Reads stock watchlist, extracts daily price data from Alpha Vantage,
        and returns a combined DataFrame.
    """
    use_sample_data = os.getenv("USE_SAMPLE_DATA", "false").lower() == "true"

    if use_sample_data:
        print("USE_SAMPLE_DATA=true. Loading sample stock price data...")
        sample_df = load_sample_prices()
        print(f"Successfully loaded {len(sample_df)} sample stock price records.")
        return sample_df

    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    if not api_key:
        raise EnvironmentError(
            "Missing ALPHA_VANTAGE_API_KEY. Please add it to your .env file."
        )

    watchlist = read_watchlist(WATCHLIST_PATH)

    all_price_data = []

    for stock in watchlist:
        symbol = stock["symbol"].upper().strip()
        company_name = stock.get("company_name", "")

        print(f"Extracting daily prices for {symbol}...")

        try:
            api_response = fetch_daily_prices(symbol=symbol, api_key=api_key)
            stock_df = parse_daily_prices(
                symbol=symbol,
                company_name=company_name,
                api_response=api_response,
            )

            all_price_data.append(stock_df)

            print(f"Successfully extracted {len(stock_df)} records for {symbol}")

            time.sleep(12)

        except Exception as error:
            print(f"Failed to extract prices for {symbol}: {error}")

    if not all_price_data:
        raise RuntimeError("No stock price data was extracted.")

    final_df = pd.concat(all_price_data, ignore_index=True)

    return final_df


def save_raw_prices(df: pd.DataFrame) -> Path:
    """
    Saves extracted raw stock price data into data/raw.
    """
    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    load_date = datetime.utcnow().strftime("%Y-%m-%d")

    output_path = RAW_OUTPUT_DIR / f"stock_prices_raw_{load_date}.csv"

    df.to_csv(output_path, index=False)

    return output_path


if __name__ == "__main__":
    price_df = extract_prices()
    saved_path = save_raw_prices(price_df)

    print("\nPrice extraction completed.")
    print(f"Raw price data saved to: {saved_path}")
    print("\nSample records:")
    print(price_df.head(10))