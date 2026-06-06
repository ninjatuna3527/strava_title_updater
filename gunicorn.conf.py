import os

from dotenv import load_dotenv, find_dotenv
import logging, os

logging.basicConfig(level=logging.INFO)

path = find_dotenv()
loaded = load_dotenv(path)

logging.info("dotenv path=%s loaded=%s cwd=%s", path, loaded, os.getcwd())
# Gunicorn configuration file. Values can be tuned via environment variables.

# Number of worker processes. Default 4.
workers = int(os.getenv('GUNICORN_WORKERS', '4'))

# Worker timeout (seconds)
timeout = int(os.getenv('GUNICORN_TIMEOUT', '30'))

# Keep-alive for clients
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '2'))

# Log to stdout/stderr so container logs capture Gunicorn output
accesslog = '-'  # stdout
errorlog = '-'   # stderr
loglevel = os.getenv('GUNICORN_LOGLEVEL', 'info')

# TLS termination is expected to be handled by a reverse proxy (e.g., Nginx).
# Do not configure Gunicorn to serve HTTPS directly in this deployment.
