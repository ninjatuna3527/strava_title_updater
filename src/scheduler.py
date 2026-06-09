"""Simple long-running scheduler that periodically invokes the processor.

This module is purposely minimal: it performs environment debugging output on
startup and then runs an infinite loop calling `process_new_activities` with a
delay between iterations. The loop catches exceptions so transient failures do
not stop the scheduler.
"""

import time
import os
from dotenv import load_dotenv
from .processor import process_new_activities

# Load environment from common locations. In Docker the entrypoint writes a
# sanitized env file to `/app/.env`; locally `python -m src.app` can use a
# `.env` in the repo root. load_dotenv is idempotent if variables are already
# present in the process environment.
load_dotenv()  # load .env from cwd if present

def run_loop():
    """Run the processing loop until interrupted (KeyboardInterrupt).

    This function is suitable for containerized workers or systemd services.
    """
    POLL_INTERVAL = int(os.getenv('POLL_INTERVAL_SECONDS', '3600'))
    print(f"Starting scheduler: polling every {POLL_INTERVAL} seconds")
    try:
        while True:
            try:
                updated, skipped = process_new_activities()
                print(f"Processed activities, updated: {updated}, skipped: {skipped}")
            except Exception as e:
                print('Scheduler error:', e)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print('Scheduler stopped')


if __name__ == '__main__':
    run_loop()
