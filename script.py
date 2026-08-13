import logging
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas

load_dotenv()

LOG_DIR = Path(__file__).parent / 'logs'
LOG_FILE = Path(os.getenv('LOG_FILE', LOG_DIR / 'stock_job.log'))

logger = logging.getLogger(__name__)


def configure_logging():
    root = logging.getLogger()
    if root.handlers:
        return

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


MASSIVE_API_KEY = os.getenv('MASSIVE_API_KEY')
MASSIVE_TICKERS_URL = 'https://api.massive.com/v3/reference/tickers'
LIMIT = 1000
# Massive API strictly limits to 5 requests per minute
REQUEST_LIMIT = 5
REQUEST_LIMIT_TIME = 60

SNOWFLAKE_USER = os.getenv('SNOWFLAKE_USER')
SNOWFLAKE_PASSWORD = os.getenv('SNOWFLAKE_PASSWORD')
SNOWFLAKE_ACCOUNT = os.getenv('SNOWFLAKE_ACCOUNT')
SNOWFLAKE_WAREHOUSE = os.getenv('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH')
SNOWFLAKE_DATABASE = os.getenv('SNOWFLAKE_DATABASE', 'NBELL')
SNOWFLAKE_SCHEMA = os.getenv('SNOWFLAKE_SCHEMA', 'PUBLIC')
SNOWFLAKE_TABLE = os.getenv('SNOWFLAKE_TABLE', 'STOCK_TICKERS')

TICKER_FIELDS = [
    'ticker',
    'name',
    'market',
    'locale',
    'primary_exchange',
    'type',
    'active',
    'currency_name',
    'cik',
    'composite_figi',
    'share_class_figi',
    'last_updated_utc',
    'ds',
]


def normalize_ticker(ticker, ds):
    row = {field: ticker.get(field) for field in TICKER_FIELDS}
    row['ds'] = ds
    return row


def with_api_key(url):
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}apiKey={MASSIVE_API_KEY}'


def fetch_tickers_page(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def throttle_if_needed(request_count):
    """Stay under the Massive API request limit; reset the counter after waiting."""
    if request_count <= REQUEST_LIMIT:
        return request_count

    logger.info('Request limit reached, waiting 1 minute...')
    time.sleep(REQUEST_LIMIT_TIME)
    return 1


def fetch_all_tickers():
    ds = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    url = with_api_key(
        f'{MASSIVE_TICKERS_URL}'
        f'?market=stocks&active=true&order=asc&limit={LIMIT}&sort=ticker'
    )
    tickers = []
    request_count = 0

    while url:
        request_count = throttle_if_needed(request_count + 1)
        logger.info('Request %s: fetching page...', request_count)

        data = fetch_tickers_page(url)
        page = [normalize_ticker(ticker, ds) for ticker in data.get('results', [])]
        tickers.extend(page)
        logger.info('Fetched %s tickers so far', len(tickers))

        next_url = data.get('next_url')
        url = with_api_key(next_url) if next_url else None

    return tickers


def load_tickers_to_snowflake(tickers):
    df = pd.DataFrame(tickers)
    df.columns = [column.upper() for column in df.columns]

    conn = snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
    )
    try:
        success, nchunks, nrows, _ = write_pandas(
            conn,
            df,
            table_name=SNOWFLAKE_TABLE,
            auto_create_table=True,
            overwrite=True,
            quote_identifiers=False,
        )
        if not success:
            raise RuntimeError('Failed to load tickers into Snowflake')
        logger.info(
            'Wrote %s tickers to %s.%s.%s (%s chunk(s))',
            nrows,
            SNOWFLAKE_DATABASE,
            SNOWFLAKE_SCHEMA,
            SNOWFLAKE_TABLE,
            nchunks,
        )
    finally:
        conn.close()


def run_stock_job():
    configure_logging()
    logger.info('Starting stock job')
    tickers = fetch_all_tickers()
    logger.info('Total tickers: %s', len(tickers))
    load_tickers_to_snowflake(tickers)
    logger.info('Stock job completed')


if __name__ == '__main__':
    run_stock_job()
