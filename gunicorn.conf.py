"""Configuration gunicorn, réglable par variables d'environnement."""
import os

bind = "0.0.0.0:5000"
# Threads : une requête lente vers Nextcloud ne bloque plus tout un processus
worker_class = "gthread"
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
