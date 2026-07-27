"""Configuração central da aplicação."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Sem VIRAL_ROOT definido, usa a raiz do repositório (dois níveis acima deste arquivo).
_DEFAULT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = Path(os.environ.get("VIRAL_ROOT", str(_DEFAULT_ROOT))).resolve()


def _tool_bin(env_key: str, default_name: str) -> str:
    value = os.environ.get(env_key)
    if value:
        return value
    candidate = APP_ROOT / ".venv" / "bin" / default_name
    if candidate.exists():
        return str(candidate)
    return default_name


def _recommended_worker_count() -> int:
    cpu = os.cpu_count() or 4
    # Mantém margem para o sistema e ainda escala bem em máquinas de 30+ núcleos.
    return max(2, min(6, max(2, cpu // 5)))


@dataclass
class Config:
    app_root: Path = APP_ROOT
    storage_dir: Path = field(default_factory=lambda: APP_ROOT / "fabrica_clips")
    ffmpeg_bin: str = _tool_bin("FFMPEG_BIN", "ffmpeg")
    ffprobe_bin: str = _tool_bin("FFPROBE_BIN", "ffprobe")
    ytdlp_bin: str = _tool_bin("YTDLP_BIN", "yt-dlp")
    max_upload_bytes: int = int(os.environ.get("MAX_UPLOAD_MB", "500")) * 1024 * 1024
    max_workers: int = int(os.environ.get("VIRAL_WORKERS", str(_recommended_worker_count())))
    secret_key: str = os.environ.get("SECRET_KEY", "change-me-in-env")

    @classmethod
    def from_env(cls) -> "Config":
        root = Path(os.environ.get("VIRAL_ROOT", str(APP_ROOT))).resolve()
        return cls(
            app_root=root,
            storage_dir=Path(os.environ.get("VIRAL_STORAGE", str(root / "fabrica_clips"))),
        )

    # --- Diretórios por ferramenta -------------------------------------
    @property
    def frontend_dir(self) -> Path:
        return Path(os.environ.get("VIRAL_FRONTEND", str(self.app_root / "frontend_dist")))

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "_uploads"

    @property
    def jobs_dir(self) -> Path:
        return self.storage_dir / "_jobs"

    def tool_dir(self, tool: str) -> Path:
        mapping = {
            "youtube": "_youtube_jobs",
            "tiktok": "_tiktok_jobs",
            "legendar": "_legenda_jobs",
            "voice": "_voice_jobs",
            "canva": "_canva_jobs",
        }
        return self.storage_dir / mapping.get(tool, "_misc_jobs")

    def ensure_dirs(self) -> None:
        dirs = [self.storage_dir, self.uploads_dir, self.jobs_dir]
        dirs += [self.tool_dir(t) for t in ("youtube", "tiktok", "legendar", "voice", "canva")]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


config = Config.from_env()
