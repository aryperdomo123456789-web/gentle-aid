"""Factory da aplicação Flask do Ecossistema Viral."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from .config import Config
from .blueprints.auth import bp as auth_bp
from .blueprints.api_v1 import bp as api_v1_bp
from .blueprints.apis import bp as apis_bp
from .blueprints.canva_cleaner import bp as canva_bp
from .blueprints.discover import bp as discover_bp
from .blueprints.jobs import bp as jobs_bp
from .blueprints.legendar import bp as legendar_bp
from .blueprints.live import bp as live_bp
from .blueprints.release_keys import bp as release_keys_bp
from .blueprints.transcribe_video import bp as transcribe_bp
from .blueprints.radar import bp as radar_bp
from .blueprints.recap import bp as recap_bp
from .blueprints.studio import bp as studio_bp
from .blueprints.tiktok import bp as tiktok_bp
from .blueprints.voice import bp as voice_bp
from .blueprints.youtube import bp as youtube_bp


def _git_revision(root: Path) -> str:
    env_version = os.environ.get("VIRAL_BUILD_VERSION") or os.environ.get("GIT_COMMIT")
    if env_version:
        return env_version.strip()

    try:
        result = subprocess.run(
            ["git", "-c", f"safe.directory={root}", "rev-parse", "--short", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def create_app(config: Config | None = None) -> Flask:
    cfg = config or Config.from_env()

    app = Flask(
        __name__,
        static_folder=str(cfg.frontend_dir),
        static_url_path="/assets_spa",
    )
    app.config.from_object(cfg)
    app.config["MAX_CONTENT_LENGTH"] = cfg.max_upload_bytes
    app.config["AUTH_DB_PATH"] = str(cfg.auth_db_path)
    app.config["AUTH_COOKIE_SECURE"] = os.environ.get("AUTH_COOKIE_SECURE", "1")
    app.secret_key = cfg.secret_key

    cfg.ensure_dirs()

    # O autofill completo pode varrer árvores grandes e atrasar o boot.
    # Ele fica disponível como fluxo explícito na Central de APIs e, se o
    # operador quiser, pode ser habilitado no boot via variável de ambiente.
    from .services import api_keys, jobs as jobs_service, release_keys as release_keys_service

    with app.app_context():
        api_keys.autofill_once()
        release_keys_service.migrate()

        # Jobs longos: qualquer tarefa que ficou presa em "processando" porque o
        # processo anterior morreu (deploy, restart, crash, reciclagem do Gunicorn)
        # é fechada como falha explícita no boot, em vez de mentir para a Central
        # de Jobs e travar o polling do frontend.
        orphans = jobs_service.reconcile_orphans()
        if orphans:
            app.logger.warning("Jobs interrompidos por reinício reconciliados: %s", orphans)

        # Lives que ficaram marcadas como "no ar" após restart do serviço.
        from .services import streamer as streamer_service

        lives = streamer_service.reconcile()
        if lives:
            app.logger.warning("Sessões de live reconciliadas após reinício: %s", lives)

        for signal_name in ("SIGTERM", "SIGINT"):
            try:
                import signal as _signal

                sig = getattr(_signal, signal_name, None)
                if sig is not None:
                    previous = _signal.getsignal(sig)

                    def _handler(signum, frame, _previous=previous):
                        jobs_service.shutdown()
                        if callable(_previous):
                            _previous(signum, frame)

                    _signal.signal(sig, _handler)
            except (ValueError, OSError, RuntimeError):
                # Threads secundárias não podem registrar sinal — segue sem o hook.
                pass

    for bp in (
        auth_bp,
        api_v1_bp,
        youtube_bp,
        tiktok_bp,
        legendar_bp,
        voice_bp,
        canva_bp,
        jobs_bp,
        apis_bp,
        release_keys_bp,
        radar_bp,
        studio_bp,
        discover_bp,
        recap_bp,
        transcribe_bp,
        live_bp,
    ):
        app.register_blueprint(bp)

    @app.get("/api/health")
    def health():
        return jsonify(
            status="ok",
            ffmpeg=cfg.ffmpeg_bin,
            storage=str(cfg.storage_dir),
        )

    @app.get("/api/version")
    def version():
        return jsonify(
            status="ok",
            version=_git_revision(cfg.app_root),
            root=str(cfg.app_root),
        )

    @app.get("/api/openapi.json")
    def openapi_json():
        """Serve a especificação versionada, sem consultar o storage de produção."""
        spec_path = cfg.app_root / "docs" / "public-api" / "api-public-v1.openapi.json"
        try:
            payload = json.loads(spec_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return jsonify(error="Especificação OpenAPI ainda não publicada."), 503
        response = jsonify(payload)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/docs")
    def api_docs():
        """Página pública de referência; o schema é servido pela própria aplicação."""
        response = app.response_class(
            """<!doctype html>
<html lang=\"pt-BR\">
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>Mago API — documentação</title>
    <style>body{margin:0;background:#0b1020;color:#e8eefc;font-family:system-ui,sans-serif}main{max-width:56rem;margin:8rem auto;padding:2rem}a{color:#67e8f9}</style>
  </head>
  <body><main><h1>Mago API</h1><p>A referência interativa será publicada quando a API v1 passar pelo gate de lançamento.</p><p><a href=\"/api/openapi.json\">Baixar OpenAPI JSON</a></p></main></body>
</html>""",
            mimetype="text/html",
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/downloads/<path:filename>")
    def downloads(filename: str):
        """Downloads diretos ficam desativados; resultados usam rota autenticada."""
        return jsonify(error="Downloads públicos desativados; use uma rota autenticada."), 404

    @app.errorhandler(413)
    def too_large(_err):
        return jsonify(error="Arquivo maior que o limite permitido."), 413

    @app.errorhandler(404)
    def not_found(err):
        # API responde JSON; qualquer outra rota cai no SPA.
        from flask import request

        if request.path.startswith("/api/"):
            return jsonify(error="Rota não encontrada."), 404
        return _spa(cfg)

    @app.errorhandler(500)
    def server_error(err):  # pragma: no cover
        app.logger.exception("Erro interno: %s", err)
        return jsonify(error="Erro interno no servidor."), 500

    @app.get("/")
    def index():
        return _spa(cfg)

    return app


def _spa(cfg: Config):
    index_file = cfg.frontend_dir / "index.html"
    if index_file.exists():
        return send_from_directory(cfg.frontend_dir, "index.html")
    return jsonify(error="Frontend ainda não foi buildado (rode npm run build)."), 404
