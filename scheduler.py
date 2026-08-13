import logging
import schedule
import time
import threading
from datetime import datetime

from script import configure_logging, run_stock_job

configure_logging()
logger = logging.getLogger(__name__)

_stock_job_lock = threading.Lock()
_stock_job_running = False


def basic_job():
    global _stock_job_running

    logger.info('Basic job running at %s', datetime.now())

    with _stock_job_lock:
        if _stock_job_running:
            logger.info('run_stock_job already running, skipping')
            return
        _stock_job_running = True

    def _run():
        global _stock_job_running
        try:
            run_stock_job()
        finally:
            with _stock_job_lock:
                _stock_job_running = False

    threading.Thread(target=_run, daemon=True).start()


# run every minute
schedule.every(1).minutes.do(basic_job)

while True:
    schedule.run_pending()
    time.sleep(1)
