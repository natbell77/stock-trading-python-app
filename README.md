# Stock Trading Python App

Fetches active US stock tickers from the [Massive API](https://massive.com/) and writes them to a CSV file.

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

3. Add your API key to `.env`:

```
MASSIVE_API_KEY=your_api_key_here
```

## Usage

```bash
python script.py
```

The script paginates through all active stock tickers, respects the API rate limit (5 requests/minute), and writes the results to `tickers.csv`.

## Output

`tickers.csv` contains one row per ticker with these columns:

`ticker`, `name`, `market`, `locale`, `primary_exchange`, `type`, `active`, `currency_name`, `cik`, `composite_figi`, `share_class_figi`, `last_updated_utc`
