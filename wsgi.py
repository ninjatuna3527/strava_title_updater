"""WSGI entrypoint for production servers.

This module exposes the Flask `app` as `app` so WSGI servers such as
`gunicorn` can import it using `wsgi:app`.
"""

from src.app import app
import os


if __name__ == '__main__':
    # allow running locally for quick debugging (not for production)
    ssl_cert = os.getenv('SSL_CERTFILE')
    ssl_key = os.getenv('SSL_KEYFILE')
    if ssl_cert and ssl_key:
        app.run(host='0.0.0.0', port=5000, ssl_context=(ssl_cert, ssl_key))
    else:
        app.run(host='0.0.0.0', port=5000)
