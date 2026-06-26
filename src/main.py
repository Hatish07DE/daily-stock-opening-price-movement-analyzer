from data_quality import (
    validate_price_data,
    validate_news_data,
    validate_price_movement_data,
    validate_processed_news_data,
    validate_golden_summary,
)

from extract_prices import extract_prices, save_raw_prices
from transform_prices import (
    read_raw_prices,
    calculate_open_price_movement,
    save_processed_prices,
)

from extract_news import extract_news, save_raw_news
from transform_news import (
    read_raw_news,
    transform_news,
    save_processed_news,
)

from generate_summary import (
    build_golden_summary,
    save_golden_summary,
)

from send_email_report import (
    read_golden_summary,
    build_email_subject,
    build_email_body,
    send_email,
)

from logger_config import setup_logger
from pipeline_status import build_pipeline_status, save_pipeline_status


logger = setup_logger(__name__)


def run_pipeline(send_report: bool = True) -> None:
    """
    Runs the full local batch stock opening-price movement pipeline.

    Layers:
    - Ingestion: extract stock price and news data
    - Transformation: calculate price movement and clean news
    - Data Quality: validate records before publishing
    - Golden: generate final business summary
    - Notification: email final report
    - Observability: logs and run-status JSON
    """

    logger.info("Starting Daily Stock Opening Price Movement Pipeline...")

    raw_price_df = None
    raw_news_df = None
    price_movement_df = None
    processed_news_df = None
    golden_summary_df = None

    raw_price_file_path = None
    raw_news_file_path = None
    processed_price_file_path = None
    processed_news_file_path = None
    golden_summary_file_path = None

    email_sent = False

    try:
        # --------------------------------------------------
        # Layer 1: Ingestion - Prices
        # --------------------------------------------------
        logger.info("[Ingestion] Extracting raw stock prices...")

        raw_price_df = extract_prices()

        validate_price_data(raw_price_df)
        logger.info("Raw stock price data-quality validation passed.")

        raw_price_file_path = save_raw_prices(raw_price_df)

        logger.info("Raw stock price data saved to: %s", raw_price_file_path)
        logger.info("Raw stock price records extracted: %s", len(raw_price_df))

        # --------------------------------------------------
        # Layer 1: Ingestion - News
        # --------------------------------------------------
        logger.info("[Ingestion] Extracting raw stock news...")

        raw_news_df = extract_news()

        validate_news_data(raw_news_df)
        logger.info("Raw stock news data-quality validation passed.")

        raw_news_file_path = save_raw_news(raw_news_df)

        logger.info("Raw stock news data saved to: %s", raw_news_file_path)
        logger.info("Raw stock news records extracted: %s", len(raw_news_df))

        # --------------------------------------------------
        # Layer 2: Transformation - Prices
        # --------------------------------------------------
        logger.info("[Transformation] Calculating open price movement...")

        raw_prices_df = read_raw_prices(input_path=raw_price_file_path)

        price_movement_df = calculate_open_price_movement(raw_prices_df)

        validate_price_movement_data(price_movement_df)
        logger.info("Processed price movement data-quality validation passed.")

        processed_price_file_path = save_processed_prices(price_movement_df)

        logger.info(
            "Processed price movement data saved to: %s",
            processed_price_file_path,
        )
        logger.info(
            "Processed price movement records created: %s",
            len(price_movement_df),
        )

        # --------------------------------------------------
        # Layer 2: Transformation - News
        # --------------------------------------------------
        logger.info("[Transformation] Cleaning and ranking stock news...")

        raw_news_df = read_raw_news(input_path=raw_news_file_path)

        processed_news_df = transform_news(
            raw_news_df=raw_news_df,
            top_n=5,
        )

        validate_processed_news_data(processed_news_df)
        logger.info("Processed news data-quality validation passed.")

        processed_news_file_path = save_processed_news(processed_news_df)

        logger.info(
            "Processed news data saved to: %s",
            processed_news_file_path,
        )
        logger.info(
            "Processed news records created: %s",
            len(processed_news_df),
        )

        # --------------------------------------------------
        # Layer 3: Golden
        # --------------------------------------------------
        logger.info("[Golden] Building final stock movement summary...")

        golden_summary_df = build_golden_summary(
            price_movement_df=price_movement_df,
            clean_news_df=processed_news_df,
        )

        validate_golden_summary(
            golden_summary_df=golden_summary_df,
            price_movement_df=price_movement_df,
        )
        logger.info("Golden summary data-quality validation passed.")

        golden_summary_file_path = save_golden_summary(golden_summary_df)

        logger.info("Golden summary saved to: %s", golden_summary_file_path)
        logger.info(
            "Golden summary records created: %s",
            len(golden_summary_df),
        )

        # --------------------------------------------------
        # Notification - Email Report
        # --------------------------------------------------
        if send_report:
            logger.info("[Notification] Sending email report...")

            email_summary_df = read_golden_summary(
                input_path=golden_summary_file_path
            )

            subject = build_email_subject(email_summary_df)
            body = build_email_body(email_summary_df)

            send_email(
                subject=subject,
                body=body,
                attachment_path=golden_summary_file_path,
            )

            email_sent = True
            logger.info("Email report sent successfully.")

        # --------------------------------------------------
        # Pipeline Status - Success
        # --------------------------------------------------
        success_payload = build_pipeline_status(
            status="SUCCESS",
            raw_price_records=len(raw_price_df),
            raw_news_records=len(raw_news_df),
            processed_price_records=len(price_movement_df),
            processed_news_records=len(processed_news_df),
            golden_records=len(golden_summary_df),
            email_sent=email_sent,
            raw_price_file_path=raw_price_file_path,
            raw_news_file_path=raw_news_file_path,
            processed_price_file_path=processed_price_file_path,
            processed_news_file_path=processed_news_file_path,
            golden_summary_file_path=golden_summary_file_path,
            error_message=None,
        )

        status_file_path = save_pipeline_status(success_payload)

        logger.info("Pipeline status saved to: %s", status_file_path)
        logger.info("Pipeline completed successfully.")

        logger.info("Final Golden Output:")
        logger.info(
            "\n%s",
            golden_summary_df[
                [
                    "symbol",
                    "previous_open_price",
                    "current_open_price",
                    "open_price_change_pct",
                    "movement_direction",
                    "confidence_level",
                    "summary_comment",
                ]
            ].to_string(index=False),
        )

    except Exception as error:
        failure_payload = build_pipeline_status(
            status="FAILED",
            raw_price_records=len(raw_price_df) if raw_price_df is not None else 0,
            raw_news_records=len(raw_news_df) if raw_news_df is not None else 0,
            processed_price_records=(
                len(price_movement_df)
                if price_movement_df is not None
                else 0
            ),
            processed_news_records=(
                len(processed_news_df)
                if processed_news_df is not None
                else 0
            ),
            golden_records=(
                len(golden_summary_df)
                if golden_summary_df is not None
                else 0
            ),
            email_sent=email_sent,
            raw_price_file_path=raw_price_file_path,
            raw_news_file_path=raw_news_file_path,
            processed_price_file_path=processed_price_file_path,
            processed_news_file_path=processed_news_file_path,
            golden_summary_file_path=golden_summary_file_path,
            error_message=str(error),
        )

        status_file_path = save_pipeline_status(failure_payload)

        logger.error("Pipeline failed. Status saved to: %s", status_file_path)
        logger.error("Pipeline failed.", exc_info=True)

        raise


if __name__ == "__main__":
    run_pipeline(send_report=True)