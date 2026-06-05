import time
import os
from .processor import process_new_activities

POLL_INTERVAL = int(os.getenv('POLL_INTERVAL_SECONDS', '3600'))

def _debug_env():
    cid = os.getenv('STRAVA_CLIENT_ID')
    csecret = os.getenv('STRAVA_CLIENT_SECRET')
    print('Scheduler env: STRAVA_CLIENT_ID=', 'SET' if cid else 'MISSING')
    if csecret:
        masked = csecret[:4] + '...' + str(len(csecret))
        print('Scheduler env: STRAVA_CLIENT_SECRET=', masked)
    else:
        print('Scheduler env: STRAVA_CLIENT_SECRET= MISSING')
    # show beginning of /app/.env if present
    try:
        if os.path.exists('/app/.env'):
            print('--- /app/.env preview ---')
            with open('/app/.env','r') as f:
                for i, ln in enumerate(f):
                    if i>9: break
                    print(ln.rstrip())
            print('--- end preview ---')
    except Exception as e:
        print('Failed to read /app/.env:', e)

def run_loop():
    _debug_env()
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
