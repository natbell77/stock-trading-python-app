# Stock Trading Python App

Fetches active US stock tickers from the [Massive API](https://massive.com/) and loads them into a Snowflake table.

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv pythonenv
source pythonenv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your credentials:

```
MASSIVE_API_KEY=your_api_key_here

SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ACCOUNT=org-account
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=NBELL
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_TABLE=STOCK_TICKERS
```

`SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, and `SNOWFLAKE_TABLE` are optional and fall back to the defaults above.

`LOG_FILE` is also optional and defaults to `logs/stock_job.log`.

## Usage

Run the job once:

```bash
python script.py
```

Or run it on a schedule (every minute). If a previous run is still in progress, the next tick is skipped:

```bash
python scheduler.py
```

To follow job output in another terminal while a run is in progress:

```bash
tail -f logs/stock_job.log
```

## Behavior

- Paginates through all active stock tickers from Massive
- Respects the API rate limit (5 requests/minute)
- Stamps each row with a `ds` run timestamp (`YYYY-MM-DD HH:MM:SS`)
- Creates or overwrites the Snowflake table on each successful run
- Logs progress to `logs/stock_job.log` (and the console) with timestamps

## Logging

Both `script.py` and `scheduler.py` write structured log lines to `logs/stock_job.log` by default. Each line includes a timestamp, log level, and message:

```
2026-08-13 09:49:00 - INFO - Starting stock job
2026-08-13 09:49:01 - INFO - Request 1: fetching page...
2026-08-13 09:49:02 - INFO - Fetched 1000 tickers so far
```

Override the log file path with `LOG_FILE` in `.env`.

## Snowflake Output

Rows are written to `{SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.{SNOWFLAKE_TABLE}` (default: `NBELL.PUBLIC.STOCK_TICKERS`) with these columns:

`TICKER`, `NAME`, `MARKET`, `LOCALE`, `PRIMARY_EXCHANGE`, `TYPE`, `ACTIVE`, `CURRENCY_NAME`, `CIK`, `COMPOSITE_FIGI`, `SHARE_CLASS_FIGI`, `LAST_UPDATED_UTC`, `DS`
