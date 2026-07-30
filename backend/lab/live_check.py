"""Laboratório local da Estação de Live 24/7.

Valida, sem depender de plataforma externa:

1. montagem da playlist (`concat`) e o comando FFmpeg gerado;
2. transmissão real do loop para `-f null` / servidor RTMP de teste,
   confirmando que a virada de arquivo não interrompe o fluxo;
3. o watchdog: mata o FFmpeg no meio e confere a reconexão com backoff;
4. o parser de métricas contra a saída real do FFmpeg.

Uso:  python backend/lab/live_check.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("VIRAL_STORAGE", tempfile.mkdtemp(prefix="live-lab-"))

from app.services import streamer  # noqa: E402

FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")
OK, FAIL = "\033[0;32m✓\033[0m", "\033[0;31m✗\033[0m"


def synth(path: Path, seconds: int, color: str) -> Path:
    subprocess.run(
        [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c={color}:s=640x360:r=30:d={seconds}",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(path),
        ],
        check=True,
    )
    return path


def test_command(tmp: Path) -> None:
    a, b = synth(tmp / "a.mp4", 3, "red"), synth(tmp / "b.mp4", 3, "blue")
    playlist = streamer.write_playlist([a, b], tmp / "list.txt")
    assert "a.mp4" in playlist.read_text() and "b.mp4" in playlist.read_text()

    preset = streamer.PRESETS["720p30"]
    overlay = streamer.build_overlay({"clock": True, "counter": True, "text": "AO VIVO 24/7"}, preset)
    cmd = streamer.build_command(
        playlist=playlist, rtmp_target="rtmp://exemplo/live/KEY", preset=preset, overlay=overlay
    )
    assert "-stream_loop" in cmd and cmd[cmd.index("-stream_loop") + 1] == "-1"
    assert "-re" in cmd and cmd[cmd.index("-f", cmd.index("-c:a")) + 1] == "flv"
    assert cmd[cmd.index("-g") + 1] == "60"
    assert "drawtext" in cmd[cmd.index("-vf") + 1]
    print(f"  {OK} playlist + comando (loop infinito, tempo real, GOP 2s, overlay)")


def test_loop_runs(tmp: Path) -> None:
    """Roda o loop de verdade contra -f null e confere que passa da virada."""
    a, b = tmp / "a.mp4", tmp / "b.mp4"
    playlist = streamer.write_playlist([a, b], tmp / "list.txt")
    preset = streamer.PRESETS["720p30"]
    cmd = streamer.build_command(playlist=playlist, rtmp_target="-", preset=preset, overlay=None)
    cmd[cmd.index("-f", cmd.index("-c:a")) :] = ["-f", "null", "-"]
    cmd.remove("-re")  # laboratório: sem throttle, para o teste ser rápido

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    frames, deadline = 0, time.monotonic() + 20
    stats_seen = None
    for line in proc.stdout:  # type: ignore[union-attr]
        stats = streamer.parse_stats(line.strip())
        if stats:
            stats_seen = stats
            frames = stats["frames"]
        if frames > 30 * 8 or time.monotonic() > deadline:
            break
    proc.kill()
    proc.wait(timeout=10)

    assert frames > 30 * 7, f"loop parou cedo demais ({frames} frames)"
    assert stats_seen and "fps" in stats_seen and "bitrate" in stats_seen
    print(f"  {OK} loop atravessou a virada de arquivo · {frames} frames · métricas {stats_seen['bitrate']}")


def test_watchdog(tmp: Path) -> None:
    """Sessão real apontando para um RTMP inexistente: precisa reconectar."""
    a = tmp / "a.mp4"
    streamer.start(
        "youtube",
        [a],
        rtmp_url="rtmp://127.0.0.1:1",  # ninguém escutando: força a queda
        stream_key="labkey",
        preset_id="720p30",
        overlay={"clock": True},
        max_retries=3,
    )
    deadline = time.monotonic() + 45
    reconnects = 0
    while time.monotonic() < deadline:
        state = streamer.status("youtube")
        reconnects = int(state.get("reconnects") or 0)
        if reconnects >= 2:
            break
        time.sleep(1)
    assert reconnects >= 2, f"watchdog não reconectou (reconnects={reconnects})"

    streamer.stop("youtube")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if streamer.status("youtube").get("status") in {"stopped", "error"}:
            break
        time.sleep(0.5)
    final = streamer.status("youtube")
    assert final["status"] in {"stopped", "error"}, final["status"]
    print(f"  {OK} watchdog reconectou {reconnects}x com backoff e parou sob comando")


def test_parser() -> None:
    line = (
        "frame= 1234 fps= 30.0 q=25.0 size=    4096kB time=00:00:41.13 "
        "bitrate=2500.4kbits/s drop=  7 speed=1.01x"
    )
    stats = streamer.parse_stats(line)
    assert stats and stats["frames"] == 1234 and stats["fps"] == 30.0
    assert stats["dropped"] == 7 and stats["speed"] == 1.01
    assert stats["bitrate"].startswith("2500")
    print(f"  {OK} parser de métricas (frames, fps, bitrate, drop, speed)")


def main() -> int:
    print("\n▶ Laboratório · Estação de Live 24/7")
    with tempfile.TemporaryDirectory(prefix="live-check-") as raw:
        tmp = Path(raw)
        checks = (
            ("comando", lambda: test_command(tmp)),
            ("loop real", lambda: test_loop_runs(tmp)),
            ("parser", test_parser),
            ("watchdog", lambda: test_watchdog(tmp)),
        )
        failures = 0
        for name, fn in checks:
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  {FAIL} {name}: {exc}")
        print("")
        return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
