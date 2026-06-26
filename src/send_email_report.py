import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv


load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GOLDEN_INPUT_DIR = PROJECT_ROOT / "data" / "golden"


def get_latest_golden_file(input_dir: Path) -> Path:
    """
    Finds the latest golden summary CSV file.
    Expected file pattern:
    daily_stock_open_movement_summary_YYYY-MM-DD.csv
    """
    files = list(input_dir.glob("daily_stock_open_movement_summary_*.csv"))

    if not files:
        raise FileNotFoundError(
            f"No golden summary files found in {input_dir}. "
            "Please run generate_summary.py or main.py first."
        )

    latest_file = max(files, key=lambda file: file.stat().st_mtime)
    return latest_file


def read_golden_summary(input_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Reads the latest golden summary file.
    """
    if input_path is None:
        input_path = get_latest_golden_file(GOLDEN_INPUT_DIR)

    if not input_path.exists():
        raise FileNotFoundError(f"Golden summary file not found: {input_path}")

    df = pd.read_csv(input_path)

    required_columns = [
        "report_date",
        "symbol",
        "company_name",
        "previous_open_price",
        "current_open_price",
        "open_price_change",
        "open_price_change_pct",
        "movement_direction",
        "summary_comment",
        "confidence_level",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns in golden summary: {missing_columns}")

    return df


def format_currency(value) -> str:
    """
    Formats numeric price values.
    """
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def format_percentage(value) -> str:
    """
    Formats percentage values.
    """
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def build_email_body(summary_df: pd.DataFrame) -> str:
    """
    Builds plain-text email body from golden summary dataframe.
    """
    if summary_df.empty:
        return "No stock movement records were available for today."

    report_date = summary_df["report_date"].iloc[0]

    lines = []
    lines.append(f"Daily Stock Opening Price Movement Summary - {report_date}")
    lines.append("")
    lines.append("This report compares the current trading day open price against the previous trading day open price.")
    lines.append("")

    for _, row in summary_df.iterrows():
        symbol = row["symbol"]
        company_name = row.get("company_name", "")
        direction = row["movement_direction"]
        change_pct = format_percentage(row["open_price_change_pct"])
        previous_open = format_currency(row["previous_open_price"])
        current_open = format_currency(row["current_open_price"])
        confidence = row.get("confidence_level", "LOW")
        summary_comment = row.get("summary_comment", "")

        company_display = f"{symbol} - {company_name}" if company_name else symbol

        lines.append("=" * 80)
        lines.append(f"{company_display}")
        lines.append(f"Movement Direction: {direction}")
        lines.append(f"Change Percentage: {change_pct}")
        lines.append(f"Previous Open Price: {previous_open}")
        lines.append(f"Current Open Price: {current_open}")
        lines.append(f"Confidence Level: {confidence}")
        lines.append("")
        lines.append("Summary:")
        lines.append(str(summary_comment))
        lines.append("")

    lines.append("=" * 80)
    lines.append("")
    lines.append("Note: Summary comments are based on available price movement and recent news context.")
    lines.append("They should be treated as directional insights, not financial advice.")

    return "\n".join(lines)


def build_email_subject(summary_df: pd.DataFrame) -> str:
    """
    Builds email subject line.
    """
    if summary_df.empty:
        report_date = datetime.utcnow().strftime("%Y-%m-%d")
    else:
        report_date = summary_df["report_date"].iloc[0]

    return f"Daily Stock Opening Price Movement Summary - {report_date}"


def send_email(subject: str, body: str, attachment_path: Optional[Path] = None) -> None:
    """
    Sends email using SMTP.
    """
    email_sender = os.getenv("EMAIL_SENDER")
    email_password = os.getenv("EMAIL_PASSWORD")
    email_receiver = os.getenv("EMAIL_RECEIVER")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    if not email_sender:
        raise EnvironmentError("Missing EMAIL_SENDER in .env file.")

    if not email_password:
        raise EnvironmentError("Missing EMAIL_PASSWORD in .env file.")

    if not email_receiver:
        raise EnvironmentError("Missing EMAIL_RECEIVER in .env file.")

    message = EmailMessage()
    message["From"] = email_sender
    message["To"] = email_receiver
    message["Subject"] = subject
    message.set_content(body)

    if attachment_path is not None and attachment_path.exists():
        with open(attachment_path, "rb") as file:
            file_data = file.read()
            file_name = attachment_path.name

        message.add_attachment(
            file_data,
            maintype="application",
            subtype="octet-stream",
            filename=file_name,
        )

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(email_sender, email_password)
        smtp.send_message(message)


def send_latest_stock_report() -> None:
    """
    Reads latest golden summary and sends email report.
    """
    golden_file_path = get_latest_golden_file(GOLDEN_INPUT_DIR)

    summary_df = read_golden_summary(golden_file_path)

    subject = build_email_subject(summary_df)
    body = build_email_body(summary_df)

    send_email(
        subject=subject,
        body=body,
        attachment_path=golden_file_path,
    )

    print("\nEmail report sent successfully.")
    print(f"Attached file: {golden_file_path}")


if __name__ == "__main__":
    send_latest_stock_report()