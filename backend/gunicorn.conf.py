"""Configuração do Gunicorn — jobs de FFmpeg rodam em threads, não em processos."""

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "8"))
worker_class = "gthread"
timeout = 3600
graceful_timeout = 60
keepalive = 15
# Jobs de voz/dublagem podem durar muitos minutos. Se o worker recicla por
# contagem de requests, o interpretador entra em shutdown e quebra tarefas em
# andamento. Desligamos o recycle automático para não matar jobs longos.
max_requests = 0
max_requests_jitter = 0
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
