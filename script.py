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
SNOWFLAKE_PRIMARY_KEY = os.getenv('SNOWFLAKE_PRIMARY_KEY', 'TICKER,DS')
STAGING_TABLE_SUFFIX = '_STAGING'

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
    ds = datetime.now().replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
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


def parse_primary_key_columns():
    columns = [
        column.strip().upper()
        for column in SNOWFLAKE_PRIMARY_KEY.split(',')
        if column.strip()
    ]
    if not columns:
        raise ValueError('SNOWFLAKE_PRIMARY_KEY must include at least one column')
    return columns


def qualified_table(table_name):
    return f'{SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.{table_name}'


def build_merge_sql(target_table, staging_table, columns, primary_key_columns):
    on_clause = ' AND '.join(
        f'target.{column} = staging.{column}' for column in primary_key_columns
    )
    update_columns = [column for column in columns if column not in primary_key_columns]
    when_matched = ''
    if update_columns:
        update_clause = ', '.join(
            f'target.{column} = staging.{column}' for column in update_columns
        )
        when_matched = f'WHEN MATCHED THEN UPDATE SET {update_clause}'

    insert_columns = ', '.join(columns)
    insert_values = ', '.join(f'staging.{column}' for column in columns)

    return f"""
        MERGE INTO {target_table} AS target
        USING {staging_table} AS staging
        ON {on_clause}
        {when_matched}
        WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})
    """


def load_tickers_to_snowflake(tickers):
    df = pd.DataFrame(tickers)
    df.columns = [column.upper() for column in df.columns]
    primary_key_columns = parse_primary_key_columns()

    missing_primary_key_columns = set(primary_key_columns) - set(df.columns)
    if missing_primary_key_columns:
        raise ValueError(
            'Primary key columns missing from ticker data: '
            f'{", ".join(sorted(missing_primary_key_columns))}'
        )

    target_table = qualified_table(SNOWFLAKE_TABLE)
    staging_table = qualified_table(f'{SNOWFLAKE_TABLE}{STAGING_TABLE_SUFFIX}')

    conn = snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
    )
    try:
        cursor = conn.cursor()

        success, _, nrows, _ = write_pandas(
            conn,
            df,
            table_name=f'{SNOWFLAKE_TABLE}{STAGING_TABLE_SUFFIX}',
            auto_create_table=True,
            overwrite=True,
            quote_identifiers=False,
        )
        if not success:
            raise RuntimeError('Failed to load tickers into Snowflake staging table')

        cursor.execute(
            f'CREATE TABLE IF NOT EXISTS {target_table} AS '
            f'SELECT * FROM {staging_table} WHERE 1 = 0'
        )

        merge_sql = build_merge_sql(
            target_table,
            staging_table,
            list(df.columns),
            primary_key_columns,
        )
        logger.info('Executing Snowflake merge query:\n%s', merge_sql.strip())
        cursor.execute(merge_sql)
        cursor.execute('SELECT * FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))')
        merge_stats = cursor.fetchone()

        logger.info(
            'Upserted %s tickers into %s using primary key (%s); '
            'merge stats: %s',
            nrows,
            target_table,
            ', '.join(primary_key_columns),
            merge_stats,
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
