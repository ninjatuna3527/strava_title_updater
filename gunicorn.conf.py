import os

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
