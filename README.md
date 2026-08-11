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

## Usage

Run the job once:

```bash
python script.py
```

Or run it on a schedule (every minute). If a previous run is still in progress, the next tick is skipped:

```bash
python scheduler.py
```

## Behavior

- Paginates through all active stock tickers from Massive
- Respects the API rate limit (5 requests/minute)
- Stamps each row with a `ds` run timestamp (`YYYY-MM-DD HH:MM:SS`)
- Creates or overwrites the Snowflake table on each successful run

## Output

Rows are written to `{SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.{SNOWFLAKE_TABLE}` (default: `NBELL.PUBLIC.STOCK_TICKERS`) with these columns:

`TICKER`, `NAME`, `MARKET`, `LOCALE`, `PRIMARY_EXCHANGE`, `TYPE`, `ACTIVE`, `CURRENCY_NAME`, `CIK`, `COMPOSITE_FIGI`, `SHARE_CLASS_FIGI`, `LAST_UPDATED_UTC`, `DS`
