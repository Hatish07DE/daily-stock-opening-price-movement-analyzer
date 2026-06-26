# Daily Stock Opening Price Movement Analyzer

A batch data engineering project that compares the opening price of selected stocks between the previous trading day and the current trading day, enriches the result with related company news, and sends a daily summary email.

The project follows a three-layer data pipeline design:

* **Ingestion Layer** — extracts stock price and news data
* **Transformation Layer** — cleans data, calculates price movement, and ranks relevant news
* **Golden Layer** — joins price movement with news and creates a business-ready daily summary

---

## Business Problem

Investors and business users often want a quick morning view of how selected stocks opened compared to the previous trading day.

This pipeline answers:

* Did the stock open higher, lower, or flat?
* What is the opening-price change amount and percentage?
* What recent news may be related to the movement?
* Can the result be delivered automatically by email?

> The news-based summary is directional context only. It does not prove causation and is not financial advice.

---

## Key Business Rule

The project compares:

```text
Previous trading day opening price
                vs
Current trading day opening price
```

It does **not** compare yesterday’s closing price with today’s opening price.

For example:

```text
Previous trading day open: $198.20
Current trading day open:  $203.10

Price change: $4.90
Percentage change: 2.47%
Direction: UP
```

The pipeline identifies the latest two available trading dates, which helps handle weekends and market holidays.

---

## Architecture

```text
                         Stock Watchlist
                                |
                                v
                        Local Batch Pipeline
                                |
        ------------------------------------------------
        |                                              |
        v                                              v
Stock Price Source                               News Source
        |                                              |
        v                                              v
              Ingestion Layer — Raw CSV Files
                                |
                                v
              Transformation Layer — Cleaned Data
                                |
                                v
            Golden Layer — Daily Stock Summary
                                |
                                v
             Email Report + CSV Attachment + Logs
                                |
                                v
                  Pipeline Status JSON File
```

---

## Data Pipeline Layers

### 1. Ingestion Layer

The ingestion layer reads selected stock symbols and collects:

* Daily stock OHLCV data
* Recent company/market news
* News sentiment and relevance scores

Current ingestion files:

```text
src/extract_prices.py
src/extract_news.py
```

Raw outputs:

```text
data/raw/stock_prices_raw_YYYY-MM-DD.csv
data/raw/stock_news_raw_YYYY-MM-DD.csv
```

For development and repeatable testing, the project supports sample-data mode:

```text
data/sample/sample_stock_prices.csv
data/sample/sample_stock_news.csv
```

---

### 2. Transformation Layer

The transformation layer:

* Validates required columns
* Cleans and standardizes price and news data
* Identifies the latest two available trading dates per stock
* Calculates opening-price movement
* Calculates percentage change
* Labels each stock as `UP`, `DOWN`, or `FLAT`
* Removes duplicate news headlines
* Ranks news by relevance, sentiment availability, and recency

Transformation files:

```text
src/transform_prices.py
src/transform_news.py
```

Processed outputs:

```text
data/processed/stock_open_price_movement_YYYY-MM-DD.csv
data/processed/stock_news_cleaned_YYYY-MM-DD.csv
```

---

### 3. Golden Layer

The golden layer joins opening-price movement with ranked news.

It produces:

* Previous trading day open price
* Current trading day open price
* Price change amount
* Price change percentage
* Movement direction
* Top related headlines
* Sentiment context
* Business-friendly summary comment
* Confidence level

Golden layer file:

```text
src/generate_summary.py
```

Golden output:

```text
data/golden/daily_stock_open_movement_summary_YYYY-MM-DD.csv
```

---

## Project Structure

```text
stock-market-movement-project/
│
├── config/
│   └── stock_watchlist.json
│
├── data/
│   ├── sample/
│   │   ├── sample_stock_prices.csv
│   │   └── sample_stock_news.csv
│   │
│   ├── raw/
│   ├── processed/
│   └── golden/
│
├── logs/
│
├── src/
│   ├── extract_prices.py
│   ├── extract_news.py
│   ├── transform_prices.py
│   ├── transform_news.py
│   ├── generate_summary.py
│   ├── send_email_report.py
│   ├── logger_config.py
│   ├── pipeline_status.py
│   └── main.py
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Technologies Used

| Area                | Tools                                                       |
| ------------------- | ----------------------------------------------------------- |
| Language            | Python                                                      |
| Data processing     | Pandas                                                      |
| External APIs       | Alpha Vantage                                               |
| Configuration       | python-dotenv                                               |
| Email notification  | Gmail SMTP                                                  |
| Logging             | Python logging                                              |
| File storage        | Local CSV files                                             |
| Data layers         | Raw, Processed, Golden                                      |
| Future cloud target | AWS S3, Glue, EventBridge, SES, CloudWatch, Secrets Manager |

---

## Sample Watchlist

The stock watchlist is maintained in:

```text
config/stock_watchlist.json
```

Example:

```json
[
  {
    "symbol": "AAPL",
    "company_name": "Apple Inc"
  },
  {
    "symbol": "MSFT",
    "company_name": "Microsoft Corporation"
  },
  {
    "symbol": "NVDA",
    "company_name": "NVIDIA Corporation"
  }
]
```

---

## How to Run Locally

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd stock-market-movement-project
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your `.env` file

Create a `.env` file in the project root.

For sample-data mode:

```env
USE_SAMPLE_DATA=true
USE_SAMPLE_NEWS=true

ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key

EMAIL_SENDER=your_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
EMAIL_RECEIVER=receiver_email@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

Use a Gmail App Password instead of your normal Gmail password.

### 5. Run the full pipeline

```bash
python src/main.py
```

---

## Expected Output

A successful run creates files similar to:

```text
data/raw/stock_prices_raw_YYYY-MM-DD.csv
data/raw/stock_news_raw_YYYY-MM-DD.csv

data/processed/stock_open_price_movement_YYYY-MM-DD.csv
data/processed/stock_news_cleaned_YYYY-MM-DD.csv

data/golden/daily_stock_open_movement_summary_YYYY-MM-DD.csv
data/golden/pipeline_run_status_YYYY-MM-DD.json
```

It also sends an email report with the golden CSV file attached.

Example result:

| Symbol | Previous Open | Current Open | Change % | Direction |
| ------ | ------------: | -----------: | -------: | --------- |
| NVDA   |        890.00 |       917.59 |    3.10% | UP        |
| AAPL   |        198.20 |       203.10 |    2.47% | UP        |
| MSFT   |        424.00 |       419.50 |   -1.06% | DOWN      |

---

## Logging and Observability

The project writes logs to:

```text
logs/pipeline_YYYY-MM-DD.log
```

It also creates a pipeline status file after each execution:

```text
data/golden/pipeline_run_status_YYYY-MM-DD.json
```

The status file includes:

* Pipeline status: `SUCCESS` or `FAILED`
* Record counts at each layer
* Generated output file paths
* Email delivery status
* Error message when the pipeline fails

Example:

```json
{
  "pipeline_name": "daily_stock_opening_price_movement_pipeline",
  "status": "SUCCESS",
  "record_counts": {
    "raw_price_records": 6,
    "raw_news_records": 6,
    "processed_price_records": 3,
    "processed_news_records": 6,
    "golden_records": 3
  },
  "email_sent": true,
  "error_message": null
}
```

---

## Error Handling

The project includes handling for:

* Missing API keys
* Missing input files
* API rate-limit responses
* Missing required columns
* Missing opening-price values
* Duplicate news headlines
* Missing news records
* Email configuration failures
* Pipeline failure status recording

Sample-data mode allows the pipeline to run even when external API rate limits are reached.

---

## Why Sample Data Mode Exists

Free market-data APIs can have request limits. Repeated testing should not depend on live API calls.

The project supports:

```env
USE_SAMPLE_DATA=true
USE_SAMPLE_NEWS=true
```

This allows local testing of ingestion, transformation, golden-layer logic, email delivery, logging, and pipeline status tracking without consuming API requests.

---

## Future AWS Architecture

The local project is designed to move to AWS.

```text
Amazon EventBridge Scheduler
            |
            v
AWS Step Functions
            |
            v
AWS Lambda / AWS Glue Job
            |
            v
Amazon S3 Raw Layer
            |
            v
Amazon S3 Processed Layer
            |
            v
Amazon S3 Golden Layer
            |
            v
Amazon SES Email Notification
            |
            v
Amazon CloudWatch Logs and Alarms
```

Future improvements:

* Store raw, processed, and golden outputs as Parquet in Amazon S3
* Use AWS Glue for scalable transformation jobs
* Use EventBridge Scheduler for market-day batch execution
* Store secrets in AWS Secrets Manager
* Use Amazon SES instead of Gmail SMTP
* Add Step Functions for orchestration and retry handling
* Add Amazon Bedrock for AI-generated news summaries
* Add unit tests and data-quality checks
* Add a dashboard using Power BI, QuickSight, or Streamlit

---

## Resume Bullet

> Built a Python-based batch data pipeline that compares selected stocks’ previous-trading-day opening prices with current opening prices, enriches movement results with ranked market news and sentiment context, and delivers automated email reports. Implemented raw, processed, and golden data layers; API-rate-limit fallback using sample data; logging; run-status tracking; failure handling; and business-ready summary generation.

---

## Disclaimer

This project is for educational and portfolio purposes only.

The stock movement summaries are generated from available price and news context and should not be interpreted as investment advice or as proof of why a stock price changed.
