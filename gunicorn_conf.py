# Gunicorn — Cloudtype 24h (https://cloudtypeinc.mintlify.app/en/developers/flask)
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
threads = int(os.environ.get("GTHREADS", "4"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "3600"))
keepalive = 65
preload_app = True


def when_ready(server):
    from cloud_background import start_cloud_services
    start_cloud_services()
