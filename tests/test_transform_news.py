from pathlib import Path
import sys

import pandas as pd


# Allows pytest to import files from the src folder
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from transform_news import transform_news


def build_news_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Creates a small dataframe matching the raw news input structure.
    """
    return pd.DataFrame(records)


def test_removes_duplicate_headlines():
    raw_df = build_news_dataframe(
        [
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc",
                "headline": "Apple shares rise after analyst upgrade",
                "news_source": "Reuters",
                "published_at": "2026-06-11 08:15:00",
                "url": "https://example.com/aapl-1",
                "summary": "Positive analyst outlook.",
                "overall_sentiment_score": 0.45,
                "overall_sentiment_label": "Bullish",
                "symbol_sentiment_score": 0.62,
                "symbol_relevance_score": 0.88,
                "symbol_sentiment_label": "Bullish",
                "api_source": "sample",
                "ingestion_timestamp": "2026-06-11 09:40:00",
            },
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc",
                "headline": "Apple shares rise after analyst upgrade",
                "news_source": "Reuters",
                "published_at": "2026-06-11 08:20:00",
                "url": "https://example.com/aapl-duplicate",
                "summary": "Duplicate article.",
                "overall_sentiment_score": 0.45,
                "overall_sentiment_label": "Bullish",
                "symbol_sentiment_score": 0.62,
                "symbol_relevance_score": 0.88,
                "symbol_sentiment_label": "Bullish",
                "api_source": "sample",
                "ingestion_timestamp": "2026-06-11 09:40:00",
            },
        ]
    )

    result_df = transform_news(raw_df, top_n=5)

    assert len(result_df) == 1
    assert result_df.iloc[0]["headline"] == "Apple shares rise after analyst upgrade"


def test_ranks_highest_relevance_news_first():
    raw_df = build_news_dataframe(
        [
            {
                "symbol": "NVDA",
                "company_name": "NVIDIA Corporation",
                "headline": "Lower relevance article",
                "news_source": "Source A",
                "published_at": "2026-06-11 08:30:00",
                "url": "https://example.com/nvda-1",
                "summary": "General market news.",
                "overall_sentiment_score": 0.20,
                "overall_sentiment_label": "Neutral",
                "symbol_sentiment_score": 0.10,
                "symbol_relevance_score": 0.45,
                "symbol_sentiment_label": "Neutral",
                "api_source": "sample",
                "ingestion_timestamp": "2026-06-11 09:40:00",
            },
            {
                "symbol": "NVDA",
                "company_name": "NVIDIA Corporation",
                "headline": "Highest relevance article",
                "news_source": "Source B",
                "published_at": "2026-06-11 08:10:00",
                "url": "https://example.com/nvda-2",
                "summary": "AI chip demand remains strong.",
                "overall_sentiment_score": 0.55,
                "overall_sentiment_label": "Bullish",
                "symbol_sentiment_score": 0.71,
                "symbol_relevance_score": 0.91,
                "symbol_sentiment_label": "Bullish",
                "api_source": "sample",
                "ingestion_timestamp": "2026-06-11 09:40:00",
            },
        ]
    )

    result_df = transform_news(raw_df, top_n=5)

    assert len(result_df) == 2
    assert result_df.iloc[0]["headline"] == "Highest relevance article"
    assert result_df.iloc[0]["news_rank"] == 1
    assert result_df.iloc[1]["news_rank"] == 2


def test_keeps_only_top_n_news_per_stock():
    raw_df = build_news_dataframe(
        [
            {
                "symbol": "MSFT",
                "company_name": "Microsoft Corporation",
                "headline": f"Microsoft article {index}",
                "news_source": "News Source",
                "published_at": f"2026-06-11 08:{10 + index}:00",
                "url": f"https://example.com/msft-{index}",
                "summary": "Microsoft related news.",
                "overall_sentiment_score": 0.10,
                "overall_sentiment_label": "Neutral",
                "symbol_sentiment_score": 0.10,
                "symbol_relevance_score": 0.90 - (index * 0.10),
                "symbol_sentiment_label": "Neutral",
                "api_source": "sample",
                "ingestion_timestamp": "2026-06-11 09:40:00",
            }
            for index in range(5)
        ]
    )

    result_df = transform_news(raw_df, top_n=3)

    assert len(result_df) == 3
    assert result_df["news_rank"].tolist() == [1, 2, 3]


def test_removes_blank_headlines():
    raw_df = build_news_dataframe(
        [
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc",
                "headline": "",
                "news_source": "Reuters",
                "published_at": "2026-06-11 08:15:00",
                "url": "https://example.com/blank",
                "summary": "No headline.",
                "overall_sentiment_score": 0.10,
                "overall_sentiment_label": "Neutral",
                "symbol_sentiment_score": 0.10,
                "symbol_relevance_score": 0.50,
                "symbol_sentiment_label": "Neutral",
                "api_source": "sample",
                "ingestion_timestamp": "2026-06-11 09:40:00",
            },
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc",
                "headline": "Apple announces AI updates",
                "news_source": "Nasdaq",
                "published_at": "2026-06-11 08:20:00",
                "url": "https://example.com/aapl-ai",
                "summary": "New AI-related features.",
                "overall_sentiment_score": 0.40,
                "overall_sentiment_label": "Bullish",
                "symbol_sentiment_score": 0.55,
                "symbol_relevance_score": 0.80,
                "symbol_sentiment_label": "Bullish",
                "api_source": "sample",
                "ingestion_timestamp": "2026-06-11 09:40:00",
            },
        ]
    )

    result_df = transform_news(raw_df, top_n=5)

    assert len(result_df) == 1
    assert result_df.iloc[0]["headline"] == "Apple announces AI updates"


def test_empty_news_dataframe_returns_empty_result():
    empty_df = pd.DataFrame(
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

    result_df = transform_news(empty_df, top_n=5)

    assert result_df.empty