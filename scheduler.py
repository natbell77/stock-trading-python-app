import schedule
import time
import threading
from script import run_stock_job

from datetime import datetime

_stock_job_lock = threading.Lock()
_stock_job_running = False


def basic_job():
    global _stock_job_running

    print(f"Basic job running at {datetime.now()}")

    with _stock_job_lock:
        if _stock_job_running:
            print("run_stock_job already running, skipping")
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
