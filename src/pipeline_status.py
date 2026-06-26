import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_OUTPUT_DIR = PROJECT_ROOT / "data" / "golden"


def build_pipeline_status(
    status: str,
    raw_price_records: int = 0,
    raw_news_records: int = 0,
    processed_price_records: int = 0,
    processed_news_records: int = 0,
    golden_records: int = 0,
    email_sent: bool = False,
    raw_price_file_path: Optional[Path] = None,
    raw_news_file_path: Optional[Path] = None,
    processed_price_file_path: Optional[Path] = None,
    processed_news_file_path: Optional[Path] = None,
    golden_summary_file_path: Optional[Path] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Builds a pipeline run status dictionary.

    This helps track:
    - Success/failure
    - Record counts
    - Output file paths
    - Email status
    - Error message if the pipeline fails
    """

    run_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    run_date = datetime.utcnow().strftime("%Y-%m-%d")

    status_payload = {
        "pipeline_name": "daily_stock_opening_price_movement_pipeline",
        "run_date": run_date,
        "run_timestamp": run_timestamp,
        "status": status,
        "record_counts": {
            "raw_price_records": raw_price_records,
            "raw_news_records": raw_news_records,
            "processed_price_records": processed_price_records,
            "processed_news_records": processed_news_records,
            "golden_records": golden_records,
        },
        "email_sent": email_sent,
        "output_files": {
            "raw_price_file_path": str(raw_price_file_path) if raw_price_file_path else None,
            "raw_news_file_path": str(raw_news_file_path) if raw_news_file_path else None,
            "processed_price_file_path": (
                str(processed_price_file_path) if processed_price_file_path else None
            ),
            "processed_news_file_path": (
                str(processed_news_file_path) if processed_news_file_path else None
            ),
            "golden_summary_file_path": (
                str(golden_summary_file_path) if golden_summary_file_path else None
            ),
        },
        "error_message": error_message,
    }

    return status_payload


def save_pipeline_status(status_payload: Dict[str, Any]) -> Path:
    """
    Saves pipeline status JSON into data/golden.
    """

    GOLDEN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    run_date = status_payload.get(
        "run_date",
        datetime.utcnow().strftime("%Y-%m-%d"),
    )

    output_path = GOLDEN_OUTPUT_DIR / f"pipeline_run_status_{run_date}.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(status_payload, file, indent=4)

    return output_path