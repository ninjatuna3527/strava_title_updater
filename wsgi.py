"""WSGI entrypoint for production servers.

This module exposes the Flask `app` as `app` so WSGI servers such as
`gunicorn` can import it using `wsgi:app`.
"""

from src.app import app


if __name__ == '__main__':
    # allow running locally for quick debugging (not for production)
    app.run(host='0.0.0.0', port=5000)
