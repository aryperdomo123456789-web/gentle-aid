"""Motor de transmissão ao vivo em loop (RTMP) — YouTube e TikTok.

Uma sessão de live é um processo FFmpeg persistente que:

* lê uma playlist (um ou vários arquivos) em loop infinito (`-stream_loop -1`);
* envia em tempo real (`-re`) para o endpoint RTMP da plataforma;
* recebe um overlay dinâmico opcional (relógio + contador de tempo no ar),
  que evita a classificação de "vídeo estático repetido";
* é supervisionado por um watchdog com backoff exponencial: quando a
  plataforma derruba a sessão, o motor reconecta sozinho.

O estado vive em disco (`fabrica_clips/_live/<platform>.json`) para sobreviver
à reciclagem de worker do Gunicorn: qualquer worker consegue ler o status e
qualquer worker consegue mandar parar (sinal em arquivo + `os.kill`).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import config

PLATFORMS: dict[str, dict[str, Any]] = {
    "youtube": {
        "label": "YouTube Live",
        "default_url": "rtmp://a.rtmp.youtube.com/live2",
        "env_url": "YOUTUBE_RTMP_URL",
        "env_key": "YOUTUBE_STREAM_KEY",
        "provider_id": "youtube_live",
        "note": "RTMP liberado para qualquer canal verificado. A chave fica em YouTube Studio → Transmitir ao vivo.",
    },
    "tiktok": {
        "label": "TikTok LIVE",
        "default_url": "",
        "env_url": "TIKTOK_RTMP_URL",
        "env_key": "TIKTOK_STREAM_KEY",
        "provider_id": "tiktok_live",
        "note": "A chave RTMP só aparece em contas com acesso a LIVE por software (normalmente 1.000+ seguidores).",
    },
}

PRESETS: dict[str, dict[str, Any]] = {
    "720p30": {"label": "720p · 30 fps", "width": 1280, "height": 720, "fps": 30, "bitrate": 2500},
    "1080p30": {"label": "1080p · 30 fps", "width": 1920, "height": 1080, "fps": 30, "bitrate": 4500},
    "1080p60": {"label": "1080p · 60 fps", "width": 1920, "height": 1080, "fps": 60, "bitrate": 6000},
    "vertical720p30": {
        "label": "Vertical 720x1280 · 30 fps",
        "width": 720,
        "height": 1280,
        "fps": 30,
        "bitrate": 2500,
    },
    "vertical1080p30": {
        "label": "Vertical 1080x1920 · 30 fps",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "bitrate": 4500,
    },
}

DEFAULT_PRESET = {"youtube": "1080p30", "tiktok": "vertical720p30"}

MAX_LOG_LINES = 400
RECONNECT_BASE_SECONDS = 5
RECONNECT_MAX_SECONDS = 120

_lock = threading.Lock()
_threads: dict[str, threading.Thread] = {}

_STATS_RE = re.compile(
    r"frame=\s*(?P<frame>\d+).*?fps=\s*(?P<fps>[\d.]+).*?"
    r"(?:size|Lsize)=\s*(?P<size>\S+).*?time=\s*(?P<time>[\d:.]+).*?"
    r"bitrate=\s*(?P<bitrate>\S+)",
    re.S,
)
_DROP_RE = re.compile(r"drop=\s*(\d+)")
_SPEED_RE = re.compile(r"speed=\s*([\d.]+)x")


class StreamerError(RuntimeError):
    """Erro de configuração/operação da estação de live."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- Persistência ------------------------------------------------------------


def _live_dir() -> Path:
    path = config.storage_dir / "_live"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_file(platform: str) -> Path:
    return _live_dir() / f"{platform}.json"


def _stop_file(platform: str) -> Path:
    return _live_dir() / f"{platform}.stop"


def _playlist_file(platform: str) -> Path:
    return _live_dir() / f"{platform}.playlist.txt"


def _read_state(platform: str) -> dict[str, Any] | None:
    file = _state_file(platform)
    if not file.exists():
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _write_state(state: dict[str, Any]) -> None:
    try:
        _state_file(state["platform"]).write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except (OSError, KeyError):
        return


def _pid_alive(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
    except (TypeError, ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _log(state: dict[str, Any], line: str, level: str = "info") -> None:
    entry = f"[{_now()[11:19]}] {level.upper():<7} {line}"
    lines = list(state.get("log") or [])
    lines.append(entry)
    state["log"] = lines[-MAX_LOG_LINES:]
    state["updated_at"] = _now()
    _write_state(state)


# --- Construção do comando (puro — testado no laboratório) -------------------


def escape_drawtext(value: str) -> str:
    """Escapa texto para o filtro `drawtext` do FFmpeg."""
    out = value.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
    return out.replace("%", r"\%").replace(",", r"\,").replace("[", r"\[").replace("]", r"\]")


def write_playlist(paths: list[Path], destination: Path) -> Path:
    """Gera o arquivo do demuxer `concat` com os vídeos da fila."""
    lines = []
    for path in paths:
        safe = str(path.resolve()).replace("'", r"'\''")
        lines.append(f"file '{safe}'")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def build_overlay(options: dict[str, Any], preset: dict[str, Any]) -> str | None:
    """Monta a cadeia de `drawtext` do overlay dinâmico."""
    parts: list[str] = []
    font_size = max(16, int(preset["height"] * 0.028))
    box = "box=1:boxcolor=black@0.45:boxborderw=12"

    if options.get("clock"):
        parts.append(
            f"drawtext=text='%{{localtime\\:%H\\\\:%M\\\\:%S}}':fontcolor=white:fontsize={font_size}:"
            f"{box}:x=w-tw-40:y=40"
        )
    if options.get("counter"):
        parts.append(
            f"drawtext=text='NO AR %{{pts\\:hms}}':fontcolor=white:fontsize={font_size}:"
            f"{box}:x=40:y=40"
        )
    text = str(options.get("text") or "").strip()
    if text:
        parts.append(
            f"drawtext=text='{escape_drawtext(text[:120])}':fontcolor=white:fontsize={font_size}:"
            f"{box}:x=(w-tw)/2:y=h-th-60"
        )
    return ",".join(parts) if parts else None


def build_command(
    *,
    playlist: Path,
    rtmp_target: str,
    preset: dict[str, Any],
    overlay: str | None,
    ffmpeg_bin: str | None = None,
) -> list[str]:
    """Comando FFmpeg completo da transmissão em loop."""
    fps = int(preset["fps"])
    bitrate = int(preset["bitrate"])
    scale = (
        f"scale={preset['width']}:{preset['height']}:force_original_aspect_ratio=decrease,"
        f"pad={preset['width']}:{preset['height']}:(ow-iw)/2:(oh-ih)/2:black,"
        f"fps={fps},format=yuv420p"
    )
    vf = f"{scale},{overlay}" if overlay else scale

    return [
        ffmpeg_bin or config.ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-stats",
        "-nostdin",
        # Loop infinito da playlist inteira, em ritmo de tempo real.
        "-stream_loop",
        "-1",
        "-re",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(playlist),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-profile:v",
        "main",
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        f"{bitrate}k",
        "-maxrate",
        f"{bitrate}k",
        "-bufsize",
        f"{bitrate * 2}k",
        # GOP fixo de 2 s: exigência de YouTube e TikTok para RTMP estável.
        "-g",
        str(fps * 2),
        "-keyint_min",
        str(fps * 2),
        "-sc_threshold",
        "0",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-af",
        "aresample=async=1:first_pts=0",
        "-f",
        "flv",
        "-flvflags",
        "no_duration_filesize",
        rtmp_target,
    ]


def parse_stats(line: str) -> dict[str, Any] | None:
    """Extrai fps/bitrate/frames/drop da linha de progresso do FFmpeg."""
    match = _STATS_RE.search(line)
    if not match:
        return None
    stats: dict[str, Any] = {
        "frames": int(match.group("frame")),
        "fps": float(match.group("fps")),
        "time": match.group("time"),
        "bitrate": match.group("bitrate"),
    }
    drop = _DROP_RE.search(line)
    if drop:
        stats["dropped"] = int(drop.group(1))
    speed = _SPEED_RE.search(line)
    if speed:
        stats["speed"] = float(speed.group(1))
    return stats


def resolve_target(platform: str, url: str, key: str) -> str:
    """Junta URL base e stream key, respeitando cofre de chaves e env."""
    spec = PLATFORMS[platform]
    base = (url or "").strip()
    stream_key = (key or "").strip()

    if not base:
        base = (os.environ.get(spec["env_url"]) or spec["default_url"] or "").strip()
    if not stream_key:
        stream_key = (os.environ.get(spec["env_key"]) or "").strip()
    if not base:
        raise StreamerError("Informe a URL RTMP da plataforma.")
    if not base.startswith(("rtmp://", "rtmps://")):
        raise StreamerError("A URL precisa começar com rtmp:// ou rtmps://.")
    if not stream_key:
        raise StreamerError("Informe a stream key da plataforma.")
    if "/" in stream_key or " " in stream_key:
        raise StreamerError("Stream key inválida.")
    return f"{base.rstrip('/')}/{stream_key}"


# --- Ciclo de vida da sessão -------------------------------------------------


def status(platform: str) -> dict[str, Any]:
    state = _read_state(platform)
    if not state:
        return {"platform": platform, "status": "idle", "log": [], "metrics": {}}
    if state.get("status") in {"starting", "live", "reconnecting"}:
        owner = state.get("owner_pid")
        if owner and not _pid_alive(owner) and not _pid_alive(state.get("ffmpeg_pid")):
            state["status"] = "error"
            state["error"] = "Transmissão interrompida: o processo supervisor foi encerrado."
            state["stopped_at"] = state.get("stopped_at") or _now()
            _write_state(state)
    if state.get("started_at") and state.get("status") in {"live", "reconnecting", "starting"}:
        started = datetime.fromisoformat(state["started_at"])
        state["uptime_seconds"] = int((datetime.now(timezone.utc) - started).total_seconds())
    return state


def sessions() -> list[dict[str, Any]]:
    return [status(platform) for platform in PLATFORMS]


def is_running(platform: str) -> bool:
    return status(platform).get("status") in {"starting", "live", "reconnecting"}


def start(
    platform: str,
    sources: list[Path],
    *,
    rtmp_url: str = "",
    stream_key: str = "",
    preset_id: str = "",
    overlay: dict[str, Any] | None = None,
    max_retries: int = 0,
) -> dict[str, Any]:
    if platform not in PLATFORMS:
        raise StreamerError("Plataforma inválida.")
    if is_running(platform):
        raise StreamerError("Já existe uma transmissão ativa nesta plataforma. Pare antes de iniciar outra.")
    if not sources:
        raise StreamerError("Selecione pelo menos um vídeo para a playlist.")
    for path in sources:
        if not path.exists():
            raise StreamerError(f"Arquivo não encontrado: {path.name}")

    preset_id = preset_id or DEFAULT_PRESET[platform]
    if preset_id not in PRESETS:
        raise StreamerError("Preset de qualidade inválido.")

    target = resolve_target(platform, rtmp_url, stream_key)
    playlist = write_playlist(sources, _playlist_file(platform))
    _stop_file(platform).unlink(missing_ok=True)

    state: dict[str, Any] = {
        "session_id": f"live-{platform}-{uuid.uuid4().hex[:10]}",
        "platform": platform,
        "platform_label": PLATFORMS[platform]["label"],
        "status": "starting",
        "preset": preset_id,
        "preset_label": PRESETS[preset_id]["label"],
        "sources": [p.name for p in sources],
        "overlay": overlay or {},
        "rtmp_host": target.split("/")[2] if "//" in target else "",
        "max_retries": max(0, int(max_retries)),
        "attempts": 0,
        "reconnects": 0,
        "created_at": _now(),
        "started_at": _now(),
        "updated_at": _now(),
        "stopped_at": None,
        "error": None,
        "metrics": {},
        "owner_pid": os.getpid(),
        "ffmpeg_pid": None,
        "log": [],
    }
    _write_state(state)
    _log(state, f"Sessão criada · {len(sources)} vídeo(s) · preset {PRESETS[preset_id]['label']}.")

    thread = threading.Thread(
        target=_supervise,
        args=(platform, playlist, target, preset_id, overlay or {}),
        name=f"live-{platform}",
        daemon=True,
    )
    with _lock:
        _threads[platform] = thread
    thread.start()
    return status(platform)


def stop(platform: str) -> dict[str, Any]:
    if platform not in PLATFORMS:
        raise StreamerError("Plataforma inválida.")
    state = _read_state(platform)
    if not state:
        raise StreamerError("Nenhuma transmissão registrada nesta plataforma.")

    # Sinal em disco: funciona mesmo quando o pedido cai em outro worker.
    try:
        _stop_file(platform).write_text(_now(), encoding="utf-8")
    except OSError:
        pass

    pid = state.get("ffmpeg_pid")
    if pid and _pid_alive(pid):
        try:
            os.kill(int(pid), signal.SIGTERM)
        except (OSError, ValueError):
            pass

    if state.get("owner_pid") != os.getpid():
        # O supervisor está em outro worker: ele lê o sinal e finaliza sozinho.
        state["status"] = "stopping"
        state["updated_at"] = _now()
        _write_state(state)
    return status(platform)


def _stop_requested(platform: str) -> bool:
    return _stop_file(platform).exists()


def _supervise(
    platform: str,
    playlist: Path,
    target: str,
    preset_id: str,
    overlay_options: dict[str, Any],
) -> None:
    preset = PRESETS[preset_id]
    overlay = build_overlay(overlay_options, preset)
    cmd = build_command(playlist=playlist, rtmp_target=target, preset=preset, overlay=overlay)
    delay = RECONNECT_BASE_SECONDS
    attempt = 0

    state = _read_state(platform) or {"platform": platform}
    redacted = " ".join(shlex.quote(c) for c in cmd[:-1]) + " rtmp://***"
    _log(state, f"Comando: {redacted}")

    while not _stop_requested(platform):
        attempt += 1
        state = _read_state(platform) or state
        state["attempts"] = attempt
        state["status"] = "live" if attempt == 1 else "reconnecting"
        state["owner_pid"] = os.getpid()
        state["error"] = None
        _write_state(state)
        _log(state, f"Conectando ao RTMP (tentativa {attempt}).")

        try:
            proc = subprocess.Popen(  # noqa: S603 - argumentos construídos internamente
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
            )
        except FileNotFoundError:
            state = _read_state(platform) or state
            state["status"] = "error"
            state["error"] = f"Binário não encontrado: {cmd[0]}"
            state["stopped_at"] = _now()
            _write_state(state)
            return

        state = _read_state(platform) or state
        state["ffmpeg_pid"] = proc.pid
        state["status"] = "live"
        _write_state(state)
        _log(state, f"FFmpeg no ar (pid {proc.pid}).")

        started = time.monotonic()
        _pump(platform, proc)
        code = proc.poll()
        alive_for = int(time.monotonic() - started)

        if _stop_requested(platform):
            break
        if code == 0:
            _log(_read_state(platform) or state, f"FFmpeg encerrou normalmente após {alive_for}s.")
        else:
            _log(
                _read_state(platform) or state,
                f"Conexão caiu (código {code}) após {alive_for}s.",
                level="warn",
            )

        state = _read_state(platform) or state
        state["reconnects"] = int(state.get("reconnects") or 0) + 1
        max_retries = int(state.get("max_retries") or 0)
        if max_retries and state["reconnects"] > max_retries:
            state["status"] = "error"
            state["error"] = f"Limite de {max_retries} reconexões atingido."
            state["stopped_at"] = _now()
            _write_state(state)
            return

        # Se aguentou bastante tempo no ar, a queda foi pontual: reinicia rápido.
        delay = RECONNECT_BASE_SECONDS if alive_for > 120 else min(delay * 2, RECONNECT_MAX_SECONDS)
        state["status"] = "reconnecting"
        _write_state(state)
        _log(state, f"Reconectando em {delay}s (backoff).", level="warn")

        waited = 0.0
        while waited < delay and not _stop_requested(platform):
            time.sleep(0.5)
            waited += 0.5

    state = _read_state(platform) or state
    state["status"] = "stopped"
    state["stopped_at"] = _now()
    state["ffmpeg_pid"] = None
    _write_state(state)
    _log(state, "Transmissão encerrada pelo operador.")
    _stop_file(platform).unlink(missing_ok=True)


def iter_output(stream) -> "Any":
    """Itera linhas do FFmpeg tratando '\\r' — o progresso (-stats) não usa '\\n'."""
    buffer = ""
    while True:
        try:
            raw = os.read(stream.fileno(), 4096)
        except OSError:
            raw = b""
        chunk = raw.decode("utf-8", "replace")
        if not chunk:
            if buffer.strip():
                yield buffer.strip()
            return
        buffer += chunk
        while True:
            index = min(
                (i for i in (buffer.find("\r"), buffer.find("\n")) if i >= 0),
                default=-1,
            )
            if index < 0:
                break
            line, buffer = buffer[:index].strip(), buffer[index + 1 :]
            if line:
                yield line


def _pump(platform: str, proc: subprocess.Popen) -> None:
    """Lê a saída do FFmpeg, alimenta métricas e obedece ao pedido de parada."""
    stream = proc.stdout
    stop_watch = threading.Thread(target=_kill_on_stop, args=(platform, proc), daemon=True)
    stop_watch.start()

    last_metric = 0.0
    if stream is not None:
        for line in iter_output(stream):
            stats = parse_stats(line)
            now = time.monotonic()
            if stats:
                if now - last_metric >= 5:
                    last_metric = now
                    state = _read_state(platform)
                    if state:
                        state["metrics"] = stats
                        state["updated_at"] = _now()
                        _write_state(state)
                continue
            state = _read_state(platform)
            if state:
                level = "error" if "error" in line.lower() or "failed" in line.lower() else "info"
                _log(state, line[:300], level=level)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    if stream is not None:
        stream.close()


def _kill_on_stop(platform: str, proc: subprocess.Popen) -> None:
    while proc.poll() is None:
        if _stop_requested(platform):
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    proc.kill()
                except OSError:
                    pass
            return
        time.sleep(0.5)


def reconcile() -> int:
    """No boot: fecha sessões que ficaram 'no ar' após restart do serviço."""
    healed = 0
    for platform in PLATFORMS:
        state = _read_state(platform)
        if not state or state.get("status") not in {"starting", "live", "reconnecting", "stopping"}:
            continue
        if _pid_alive(state.get("ffmpeg_pid")):
            continue
        state["status"] = "error"
        state["error"] = "Transmissão interrompida por reinício do serviço. Inicie novamente."
        state["stopped_at"] = _now()
        state["ffmpeg_pid"] = None
        _write_state(state)
        healed += 1
    return healed
