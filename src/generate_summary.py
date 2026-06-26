from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_INPUT_DIR = PROJECT_ROOT / "data" / "processed"
GOLDEN_OUTPUT_DIR = PROJECT_ROOT / "data" / "golden"


def get_latest_file(input_dir: Path, file_pattern: str) -> Path:
    """
    Finds the latest file matching a given pattern.
    """
    files = list(input_dir.glob(file_pattern))

    if not files:
        raise FileNotFoundError(
            f"No files found in {input_dir} matching pattern: {file_pattern}"
        )

    latest_file = max(files, key=lambda file: file.stat().st_mtime)
    return latest_file


def read_price_movement(input_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Reads processed stock open price movement data.
    """
    if input_path is None:
        input_path = get_latest_file(
            PROCESSED_INPUT_DIR,
            "stock_open_price_movement_*.csv",
        )

    if not input_path.exists():
        raise FileNotFoundError(f"Price movement file not found: {input_path}")

    df = pd.read_csv(input_path)

    required_columns = [
        "load_date",
        "symbol",
        "company_name",
        "previous_trading_date",
        "current_trading_date",
        "previous_open_price",
        "current_open_price",
        "open_price_change",
        "open_price_change_pct",
        "movement_direction",
        "created_at",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            f"Missing required columns in price movement file: {missing_columns}"
        )

    return df


def read_clean_news(input_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Reads processed cleaned stock news data.
    """
    if input_path is None:
        input_path = get_latest_file(
            PROCESSED_INPUT_DIR,
            "stock_news_cleaned_*.csv",
        )

    if not input_path.exists():
        raise FileNotFoundError(f"Clean news file not found: {input_path}")

    df = pd.read_csv(input_path)

    required_columns = [
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

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            f"Missing required columns in clean news file: {missing_columns}"
        )

    return df


def prepare_news_context(news_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates top ranked news into one row per stock.
    """
    if news_df.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "top_news_headlines",
                "top_news_sources",
                "avg_sentiment_score",
                "primary_sentiment_label",
            ]
        )

    df = news_df.copy()

    df["headline"] = df["headline"].fillna("").astype(str)
    df["news_source"] = df["news_source"].fillna("").astype(str)
    df["symbol_sentiment_score"] = pd.to_numeric(
        df["symbol_sentiment_score"],
        errors="coerce",
    )

    # Keep only top 3 news items per stock for golden output
    df = df[df["news_rank"] <= 3].copy()

    news_context = (
        df.groupby("symbol")
        .agg(
            top_news_headlines=(
                "headline",
                lambda values: " | ".join([v for v in values if v.strip() != ""]),
            ),
            top_news_sources=(
                "news_source",
                lambda values: " | ".join(
                    sorted(set([v for v in values if v.strip() != ""]))
                ),
            ),
            avg_sentiment_score=("symbol_sentiment_score", "mean"),
            primary_sentiment_label=(
                "symbol_sentiment_label",
                lambda values: values.dropna().iloc[0]
                if len(values.dropna()) > 0
                else "Neutral",
            ),
        )
        .reset_index()
    )

    return news_context


def generate_rule_based_comment(row: pd.Series) -> str:
    """
    Creates a business-friendly summary comment using price movement and news context.

    This is version 1.
    Later, we can replace this with Amazon Bedrock/OpenAI.
    """
    symbol = row["symbol"]
    company_name = row.get("company_name", "")
    movement_direction = row["movement_direction"]
    change_pct = row["open_price_change_pct"]

    top_news_headlines = row.get("top_news_headlines", "")
    primary_sentiment_label = row.get("primary_sentiment_label", "Neutral")

    company_display = company_name if pd.notna(company_name) and company_name != "" else symbol

    if movement_direction == "UP":
        base_comment = (
            f"{symbol} opened higher compared to the previous trading day, "
            f"with an opening price increase of {change_pct:.2f}%."
        )
    elif movement_direction == "DOWN":
        base_comment = (
            f"{symbol} opened lower compared to the previous trading day, "
            f"with an opening price decrease of {abs(change_pct):.2f}%."
        )
    else:
        base_comment = (
            f"{symbol} opened nearly flat compared to the previous trading day."
        )

    if pd.notna(top_news_headlines) and str(top_news_headlines).strip() != "":
        news_comment = (
            f" Recent news sentiment for {company_display} appears "
            f"{str(primary_sentiment_label).lower()}, and the movement may be related "
            f"to the latest headlines: {top_news_headlines}."
        )
    else:
        news_comment = (
            f" No major company-specific news was found in the selected news window, "
            f"so the movement may be related to broader market conditions or normal trading activity."
        )

    return base_comment + news_comment


def assign_confidence_level(row: pd.Series) -> str:
    """
    Assigns confidence level based on news availability and relevance/sentiment.
    """
    top_news_headlines = row.get("top_news_headlines", "")
    avg_sentiment_score = row.get("avg_sentiment_score", None)

    has_news = pd.notna(top_news_headlines) and str(top_news_headlines).strip() != ""
    has_sentiment = pd.notna(avg_sentiment_score)

    if has_news and has_sentiment:
        return "MEDIUM"

    if has_news:
        return "LOW"

    return "LOW"


def build_golden_summary(
    price_movement_df: pd.DataFrame,
    clean_news_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Builds final golden summary by joining price movement with news context.
    """
    if price_movement_df.empty:
        raise ValueError("Price movement dataframe is empty.")

    news_context_df = prepare_news_context(clean_news_df)

    golden_df = price_movement_df.merge(
        news_context_df,
        on="symbol",
        how="left",
    )

    golden_df["top_news_headlines"] = golden_df["top_news_headlines"].fillna("")
    golden_df["top_news_sources"] = golden_df["top_news_sources"].fillna("")
    golden_df["primary_sentiment_label"] = golden_df[
        "primary_sentiment_label"
    ].fillna("Neutral")

    golden_df["avg_sentiment_score"] = pd.to_numeric(
        golden_df["avg_sentiment_score"],
        errors="coerce",
    )

    golden_df["summary_comment"] = golden_df.apply(
        generate_rule_based_comment,
        axis=1,
    )

    golden_df["confidence_level"] = golden_df.apply(
        assign_confidence_level,
        axis=1,
    )

    golden_df["report_date"] = datetime.utcnow().strftime("%Y-%m-%d")
    golden_df["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    final_columns = [
        "report_date",
        "symbol",
        "company_name",
        "previous_trading_date",
        "current_trading_date",
        "previous_open_price",
        "current_open_price",
        "open_price_change",
        "open_price_change_pct",
        "movement_direction",
        "top_news_headlines",
        "top_news_sources",
        "avg_sentiment_score",
        "primary_sentiment_label",
        "summary_comment",
        "confidence_level",
        "created_at",
    ]

    golden_df = golden_df[final_columns]

    golden_df = golden_df.sort_values(
        by="open_price_change_pct",
        ascending=False,
        na_position="last",
    )

    return golden_df


def save_golden_summary(df: pd.DataFrame) -> Path:
    """
    Saves final golden output into data/golden.
    """
    GOLDEN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report_date = datetime.utcnow().strftime("%Y-%m-%d")

    output_path = (
        GOLDEN_OUTPUT_DIR
        / f"daily_stock_open_movement_summary_{report_date}.csv"
    )

    df.to_csv(output_path, index=False)

    return output_path


if __name__ == "__main__":
    price_movement_df = read_price_movement()
    clean_news_df = read_clean_news()

    golden_summary_df = build_golden_summary(
        price_movement_df=price_movement_df,
        clean_news_df=clean_news_df,
    )

    saved_path = save_golden_summary(golden_summary_df)

    print("\nGolden summary generation completed.")
    print(f"Golden summary saved to: {saved_path}")

    print("\nGolden summary sample:")
    print(
        golden_summary_df[
            [
                "symbol",
                "previous_open_price",
                "current_open_price",
                "open_price_change_pct",
                "movement_direction",
                "summary_comment",
            ]
        ]
    )