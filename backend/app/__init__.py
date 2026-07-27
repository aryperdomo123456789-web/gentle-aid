"""Factory da aplicação Flask do Ecossistema Viral."""

from __future__ import annotations

import os

from flask import Flask, jsonify, send_from_directory

from .config import Config
from .blueprints.apis import bp as apis_bp
from .blueprints.canva_cleaner import bp as canva_bp
from .blueprints.jobs import bp as jobs_bp
from .blueprints.legendar import bp as legendar_bp
from .blueprints.radar import bp as radar_bp
from .blueprints.tiktok import bp as tiktok_bp
from .blueprints.voice import bp as voice_bp
from .blueprints.youtube import bp as youtube_bp


def create_app(config: Config | None = None) -> Flask:
    cfg = config or Config.from_env()

    app = Flask(
        __name__,
        static_folder=str(cfg.frontend_dir),
        static_url_path="/assets_spa",
    )
    app.config.from_object(cfg)
    app.config["MAX_CONTENT_LENGTH"] = cfg.max_upload_bytes

    cfg.ensure_dirs()

    # O autofill completo pode varrer árvores grandes e atrasar o boot.
    # Ele fica disponível como fluxo explícito na Central de APIs e, se o
    # operador quiser, pode ser habilitado no boot via variável de ambiente.
    from .services import api_keys

    api_keys.autofill_once()

    for bp in (youtube_bp, tiktok_bp, legendar_bp, voice_bp, canva_bp, jobs_bp, apis_bp, radar_bp):
        app.register_blueprint(bp)

    @app.get("/api/health")
    def health():
        return jsonify(
            status="ok",
            ffmpeg=cfg.ffmpeg_bin,
            storage=str(cfg.storage_dir),
        )

    @app.get("/downloads/<path:filename>")
    def downloads(filename: str):
        """Serve arquivos finais. Em produção o Nginx intercepta essa rota."""
        return send_from_directory(cfg.storage_dir, filename, as_attachment=True)

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
