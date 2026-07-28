"""Configuração do Gunicorn — jobs de FFmpeg/voz rodam em threads, não em processos.

Regras que protegem jobs longos (dublagem, recap, legendas, estúdio):

* `max_requests = 0`: nada de reciclar worker por contagem de requisições. Era
  isso que matava o job no meio e produzia
  `cannot schedule new futures after interpreter shutdown`.
* `timeout` alto: o worker é gthread e o job roda em thread própria, mas
  requisições de upload pesado não podem ser mortas por timeout curto.
* `graceful_timeout` generoso: no deploy o worker tem tempo de marcar os jobs
  em andamento antes de sair, e o boot seguinte reconcilia o que sobrou.
* `preload_app = False`: cada worker tem seu próprio pool de jobs; com preload
  as threads não sobrevivem ao fork.
"""

import os

bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "8"))
worker_class = "gthread"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "3600"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "120"))
keepalive = 15
preload_app = False
max_requests = 0
max_requests_jitter = 0
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")


def worker_int(worker):  # pragma: no cover - hook do Gunicorn
    _stop_jobs(worker)


def worker_exit(server, worker):  # pragma: no cover - hook do Gunicorn
    _stop_jobs(worker)


def _stop_jobs(worker) -> None:
    """Avisa o registro de jobs que este processo está saindo."""
    try:
        from app.services import jobs

        jobs.shutdown()
    except Exception as exc:  # noqa: BLE001
        try:
            worker.log.warning("Falha ao sinalizar shutdown de jobs: %s", exc)
        except Exception:  # noqa: BLE001
            pass
