from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_INPUT_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"


def get_latest_raw_news_file(raw_dir: Path) -> Path:
    """
    Finds the latest raw stock news CSV file from data/raw.
    Expected file pattern:
    stock_news_raw_YYYY-MM-DD.csv
    """
    files = list(raw_dir.glob("stock_news_raw_*.csv"))

    if not files:
        raise FileNotFoundError(
            f"No raw stock news files found in {raw_dir}. "
            "Please run extract_news.py first."
        )

    latest_file = max(files, key=lambda file: file.stat().st_mtime)
    return latest_file


def read_raw_news(input_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Reads raw stock news data from CSV.
    If no input path is provided, it reads the latest raw news file.
    """
    if input_path is None:
        input_path = get_latest_raw_news_file(RAW_INPUT_DIR)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)

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
        raise ValueError(f"Missing required columns: {missing_columns}")

    return df


def clean_text(value) -> str:
    """
    Cleans text fields safely.
    """
    if pd.isna(value):
        return ""

    return str(value).strip().replace("\n", " ").replace("\r", " ")


def transform_news(raw_news_df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """
    Cleans and ranks news data for each stock.

    Ranking logic:
    1. Higher symbol relevance score
    2. Newer published date
    3. Records with sentiment score available
    """
    if raw_news_df.empty:
        print("Raw news dataframe is empty. Returning empty processed news dataframe.")
        return pd.DataFrame(
            columns=[
                "load_date",
                "symbol",
                "company_name",
                "headline",
                "news_source",
                "published_at",
                "url",
                "summary",
                "symbol_sentiment_score",
                "symbol_relevance_score",
                "symbol_sentiment_label",
                "news_rank",
                "created_at",
            ]
        )

    df = raw_news_df.copy()

    # Clean core text fields
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    df["company_name"] = df["company_name"].apply(clean_text)
    df["headline"] = df["headline"].apply(clean_text)
    df["news_source"] = df["news_source"].apply(clean_text)
    df["url"] = df["url"].apply(clean_text)
    df["summary"] = df["summary"].apply(clean_text)

    # Convert timestamp and numeric columns
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")

    df["symbol_sentiment_score"] = pd.to_numeric(
        df["symbol_sentiment_score"],
        errors="coerce",
    )

    df["symbol_relevance_score"] = pd.to_numeric(
        df["symbol_relevance_score"],
        errors="coerce",
    )

    # Remove rows without useful headline
    df = df[df["headline"] != ""].copy()

    if df.empty:
        print("No valid news headlines found after cleaning.")
        return pd.DataFrame()

    # Remove duplicate news articles
    # Same symbol + same headline is enough for this project
    df = df.drop_duplicates(
        subset=["symbol", "headline"],
        keep="first",
    ).copy()

    # Helper columns for ranking
    df["has_sentiment_score"] = df["symbol_sentiment_score"].notna().astype(int)
    df["symbol_relevance_score_rank_value"] = df["symbol_relevance_score"].fillna(0)

    # Sort before ranking
    df = df.sort_values(
        by=[
            "symbol",
            "symbol_relevance_score_rank_value",
            "has_sentiment_score",
            "published_at",
        ],
        ascending=[
            True,
            False,
            False,
            False,
        ],
    )

    # Rank news per symbol
    df["news_rank"] = df.groupby("symbol").cumcount() + 1

    # Keep top N news records per stock
    df = df[df["news_rank"] <= top_n].copy()

    load_date = datetime.utcnow().strftime("%Y-%m-%d")
    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    df["load_date"] = load_date
    df["created_at"] = created_at

    final_columns = [
        "load_date",
        "symbol",
        "company_name",
        "headline",
        "news_source",
        "published_at",
        "url",
        "summary",
        "symbol_sentiment_score",
        "symbol_relevance_score",
        "symbol_sentiment_label",
        "news_rank",
        "created_at",
    ]

    processed_df = df[final_columns].sort_values(
        by=["symbol", "news_rank"],
        ascending=[True, True],
    )

    return processed_df


def save_processed_news(df: pd.DataFrame) -> Path:
    """
    Saves transformed stock news data into data/processed.
    """
    PROCESSED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    load_date = datetime.utcnow().strftime("%Y-%m-%d")
    output_path = PROCESSED_OUTPUT_DIR / f"stock_news_cleaned_{load_date}.csv"

    df.to_csv(output_path, index=False)

    return output_path


if __name__ == "__main__":
    raw_news_df = read_raw_news()
    processed_news_df = transform_news(raw_news_df, top_n=5)
    saved_path = save_processed_news(processed_news_df)

    print("\nNews transformation completed.")
    print(f"Processed news data saved to: {saved_path}")

    if not processed_news_df.empty:
        print("\nProcessed news sample:")
        print(processed_news_df.head(15))
    else:
        print("\nNo processed news records created.")