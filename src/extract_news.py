import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests
from dotenv import load_dotenv


load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WATCHLIST_PATH = PROJECT_ROOT / "config" / "stock_watchlist.json"
RAW_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"

SAMPLE_INPUT_DIR = PROJECT_ROOT / "data" / "sample"
SAMPLE_STOCK_NEWS_PATH = SAMPLE_INPUT_DIR / "sample_stock_news.csv"

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


def build_alpha_vantage_time(value: datetime) -> str:
    """
    Alpha Vantage news API expects time format as YYYYMMDDTHHMM.
    Example: 20260611T0930
    """
    return value.strftime("%Y%m%dT%H%M")


def load_sample_news() -> pd.DataFrame:
    """
    Loads sample stock news data when USE_SAMPLE_NEWS=true.
    This is useful for local testing when external API limits are reached.
    """
    if not SAMPLE_STOCK_NEWS_PATH.exists():
        raise FileNotFoundError(
            f"Sample stock news file not found: {SAMPLE_STOCK_NEWS_PATH}"
        )

    df = pd.read_csv(SAMPLE_STOCK_NEWS_PATH)

    required_columns = [
        "symbol",
        "company_name",
        "headline",
        "news_source",
        "published_at",
        "url",
        "summary",
        "overall_sentiment_score",
        "overall_sentiment_label",
        "symbol_sentiment_score",
        "symbol_relevance_score",
        "symbol_sentiment_label",
        "api_source",
        "ingestion_timestamp",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            f"Missing required columns in sample news file: {missing_columns}"
        )

    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")

    numeric_columns = [
        "overall_sentiment_score",
        "symbol_sentiment_score",
        "symbol_relevance_score",
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["api_source"] = "sample"

    return df


def fetch_stock_news(
    symbol: str,
    api_key: str,
    lookback_hours: int = 48,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Calls Alpha Vantage NEWS_SENTIMENT API for one stock symbol.
    Pulls recent news for the given lookback window.
    """
    current_time = datetime.utcnow()
    from_time = current_time - timedelta(hours=lookback_hours)

    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": symbol,
        "time_from": build_alpha_vantage_time(from_time),
        "time_to": build_alpha_vantage_time(current_time),
        "limit": limit,
        "sort": "LATEST",
        "apikey": api_key,
    }

    response = requests.get(
        ALPHA_VANTAGE_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()
    data = response.json()

    if "Error Message" in data:
        raise ValueError(f"API error for {symbol}: {data['Error Message']}")

    if "Note" in data:
        raise RuntimeError(
            f"API rate limit reached for {symbol}. "
            "Please wait and try again later, reduce stock count, or use sample mode."
        )

    if "Information" in data:
        raise RuntimeError(
            f"API information message for {symbol}. "
            "This is usually caused by API limits, invalid API key, or request frequency limits."
        )

    if "feed" not in data:
        safe_keys = list(data.keys())
        raise ValueError(
            f"Unexpected news API response for {symbol}. Response keys: {safe_keys}"
        )

    return data


def parse_stock_news(
    symbol: str,
    company_name: str,
    api_response: Dict[str, Any],
) -> pd.DataFrame:
    """
    Converts Alpha Vantage news JSON response into a normalized DataFrame.
    """
    news_items = api_response.get("feed", [])
    ingestion_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    records = []

    for item in news_items:
        ticker_sentiment = item.get("ticker_sentiment", [])

        symbol_sentiment_score = None
        symbol_relevance_score = None
        symbol_sentiment_label = None

        for ticker_info in ticker_sentiment:
            if ticker_info.get("ticker") == symbol:
                symbol_sentiment_score = ticker_info.get("ticker_sentiment_score")
                symbol_relevance_score = ticker_info.get("relevance_score")
                symbol_sentiment_label = ticker_info.get("ticker_sentiment_label")
                break

        records.append(
            {
                "symbol": symbol,
                "company_name": company_name,
                "headline": item.get("title"),
                "news_source": item.get("source"),
                "published_at": item.get("time_published"),
                "url": item.get("url"),
                "summary": item.get("summary"),
                "overall_sentiment_score": item.get("overall_sentiment_score"),
                "overall_sentiment_label": item.get("overall_sentiment_label"),
                "symbol_sentiment_score": symbol_sentiment_score,
                "symbol_relevance_score": symbol_relevance_score,
                "symbol_sentiment_label": symbol_sentiment_label,
                "api_source": "alpha_vantage_news_sentiment",
                "ingestion_timestamp": ingestion_timestamp,
            }
        )

    df = pd.DataFrame(records)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "company_name",
                "headline",
                "news_source",
                "published_at",
                "url",
                "summary",
                "overall_sentiment_score",
                "overall_sentiment_label",
                "symbol_sentiment_score",
                "symbol_relevance_score",
                "symbol_sentiment_label",
                "api_source",
                "ingestion_timestamp",
            ]
        )

    df["published_at"] = pd.to_datetime(
        df["published_at"],
        format="%Y%m%dT%H%M%S",
        errors="coerce",
    )

    df["overall_sentiment_score"] = pd.to_numeric(
        df["overall_sentiment_score"],
        errors="coerce",
    )

    df["symbol_sentiment_score"] = pd.to_numeric(
        df["symbol_sentiment_score"],
        errors="coerce",
    )

    df["symbol_relevance_score"] = pd.to_numeric(
        df["symbol_relevance_score"],
        errors="coerce",
    )

    df = df.sort_values(
        by=["symbol", "published_at"],
        ascending=[True, False],
    )

    return df


def extract_news() -> pd.DataFrame:
    """
    Main news extraction function.

    If USE_SAMPLE_NEWS=true:
        Reads sample stock news data from data/sample/sample_stock_news.csv

    Else:
        Reads stock watchlist, extracts recent news from Alpha Vantage,
        and returns a combined DataFrame.
    """
    use_sample_news = os.getenv("USE_SAMPLE_NEWS", "false").lower() == "true"

    if use_sample_news:
        print("USE_SAMPLE_NEWS=true. Loading sample stock news data...")
        sample_df = load_sample_news()
        print(f"Successfully loaded {len(sample_df)} sample stock news records.")
        return sample_df

    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    if not api_key:
        raise EnvironmentError(
            "Missing ALPHA_VANTAGE_API_KEY. Please add it to your .env file."
        )

    watchlist = read_watchlist(WATCHLIST_PATH)

    all_news_data = []

    for stock in watchlist:
        symbol = stock["symbol"].upper().strip()
        company_name = stock.get("company_name", "")

        print(f"Extracting recent news for {symbol}...")

        try:
            api_response = fetch_stock_news(
                symbol=symbol,
                api_key=api_key,
                lookback_hours=48,
                limit=20,
            )

            stock_news_df = parse_stock_news(
                symbol=symbol,
                company_name=company_name,
                api_response=api_response,
            )

            if stock_news_df.empty:
                print(f"No recent news found for {symbol}")
            else:
                print(f"Successfully extracted {len(stock_news_df)} news records for {symbol}")

            all_news_data.append(stock_news_df)

            time.sleep(12)

        except Exception as error:
            print(f"Failed to extract news for {symbol}: {error}")

    if not all_news_data:
        raise RuntimeError("No stock news data was extracted.")

    final_df = pd.concat(all_news_data, ignore_index=True)

    return final_df


def save_raw_news(df: pd.DataFrame) -> Path:
    """
    Saves extracted raw stock news data into data/raw.
    """
    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    load_date = datetime.utcnow().strftime("%Y-%m-%d")

    output_path = RAW_OUTPUT_DIR / f"stock_news_raw_{load_date}.csv"

    df.to_csv(output_path, index=False)

    return output_path


if __name__ == "__main__":
    news_df = extract_news()
    saved_path = save_raw_news(news_df)

    print("\nNews extraction completed.")
    print(f"Raw news data saved to: {saved_path}")

    if not news_df.empty:
        print("\nSample news records:")
        print(news_df.head(10))
    else:
        print("\nNo news records found for selected stocks.")