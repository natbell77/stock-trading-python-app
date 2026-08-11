import requests
import os
import csv
from dotenv import load_dotenv
import time

load_dotenv()

MASSIVE_API_KEY = os.getenv('MASSIVE_API_KEY')
LIMIT = 1000
# Massive API strictly limits to 5 requests per minute
REQUEST_LIMIT = 5
REQUEST_LIMIT_TIME = 60

def run_stock_job():
    URL = f'https://api.massive.com/v3/reference/tickers?market=stocks&active=true&order=asc&limit={LIMIT}&sort=ticker&apiKey={MASSIVE_API_KEY}'

    example_ticker = {
        'ticker': 'A',
        'name': 'Agilent Technologies Inc.',
        'market': 'stocks',
        'locale': 'us',
        'primary_exchange': 'XNYS',
        'type': 'CS',
        'active': True,
        'currency_name': 'usd',
        'cik': '0001090872',
        'composite_figi': 'BBG000C2V3D6',
        'share_class_figi': 'BBG001SCTQY4',
        'last_updated_utc': '2026-08-10T06:08:34.415664315Z',
    }
    TICKER_SCHEMA_KEYS = list(example_ticker.keys())
    OUTPUT_CSV = 'tickers.csv'


    def normalize_ticker(ticker):
        return {key: ticker.get(key) for key in TICKER_SCHEMA_KEYS}


    response = requests.get(URL)
    tickers = []
    request_count = 0

    data = response.json()
    print(data.keys())
    print(data['next_url'])

    for ticker in data['results']:
        tickers.append(normalize_ticker(ticker))
    request_count += 1

    while 'next_url' in data:
        request_count += 1
        if request_count > REQUEST_LIMIT:
            print('Request limit reached, waiting 1 minute...')
            time.sleep(REQUEST_LIMIT_TIME)
            request_count = 1
        print('Request count:', request_count)
        print('Fetching next page...', data['next_url'])
        response = requests.get(data['next_url'] + f'&apiKey={MASSIVE_API_KEY}')
        data = response.json()
        for ticker in data['results']:
            tickers.append(normalize_ticker(ticker))
        print('Fetched', len(tickers), 'tickers')

    print(len(tickers))

    # write to csv
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=TICKER_SCHEMA_KEYS)
        writer.writeheader()
        writer.writerows(tickers)

    print(f'Wrote {len(tickers)} tickers to {OUTPUT_CSV}')

if __name__ == '__main__':
    run_stock_job()