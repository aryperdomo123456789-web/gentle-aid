"""Laboratório local — prova que os motores aguentam de 10 s a 3 h.

Roda fora do aaPanel, sem rede e sem chave de IA: valida só a espinha dorsal
de mídia (probe, corte, esterilização, planos de chunk e montagem em lote),
que é onde os jobs longos costumavam quebrar.

Uso:

    cd backend && python3 lab/long_media_check.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("VIRAL_ROOT", tempfile.mkdtemp(prefix="viral_lab_"))

from app.services import beatsync, media, transcribe, voice_engine  # noqa: E402
from app.services.recap import CONCAT_BATCH  # noqa: E402

DURATIONS = [10, 60, 15 * 60, 3 * 60 * 60]
FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "OK " if ok else "FALHA"
    print(f"[{mark}] {label} {detail}".rstrip())
    if not ok:
        FAILURES.append(label)


def make_audio(path: Path, seconds: int) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
         "-c:a", "aac", "-b:a", "96k", str(path)],
        check=True,
    )


def make_video(path: Path, seconds: int) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"testsrc=size=640x360:rate=24:duration={seconds}",
         "-f", "lavfi", "-i", f"sine=frequency=330:duration={seconds}",
         "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", str(path)],
        check=True,
    )


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="viral_lab_media_"))
    print(f"laboratório em {work}\n")

    for seconds in DURATIONS:
        audio = work / f"a_{seconds}.m4a"
        started = time.monotonic()
        make_audio(audio, seconds)
        probed = media.probe_duration(audio)
        elapsed = time.monotonic() - started
        check(
            f"áudio {seconds}s · probe",
            abs(probed - seconds) < 2.0,
            f"→ {probed:.1f}s em {elapsed:.1f}s de geração",
        )

        # Plano de narração: nenhum bloco pode passar do teto do motor.
        plan = voice_engine.plan_chunks(probed) if hasattr(voice_engine, "plan_chunks") else None
        if plan is not None:
            worst = max((end - start) for start, end in plan)
            check(
                f"áudio {seconds}s · plano de voz",
                worst <= voice_engine.CHUNK_MAX + 1,
                f"{len(plan)} blocos, maior {worst:.0f}s",
            )

        # Plano de transcrição: blocos de CHUNK_SECONDS cobrindo tudo.
        blocks = max(1, int((probed + transcribe.CHUNK_SECONDS - 1) // transcribe.CHUNK_SECONDS))
        check(
            f"áudio {seconds}s · plano de transcrição",
            blocks * transcribe.CHUNK_SECONDS >= probed,
            f"{blocks} blocos de {transcribe.CHUNK_SECONDS}s",
        )

        # Análise de batida: precisa devolver amostras mesmo em arquivo longo.
        started = time.monotonic()
        samples = beatsync._decode_pcm(audio)
        check(
            f"áudio {seconds}s · beatsync",
            len(samples) > 0,
            f"{len(samples)} amostras em {time.monotonic() - started:.1f}s",
        )

    # Vídeo: probe + esterilização em arquivo curto e em arquivo médio.
    for seconds in (10, 300):
        video = work / f"v_{seconds}.mp4"
        make_video(video, seconds)
        dst = work / f"v_{seconds}_clean.mp4"
        started = time.monotonic()
        report = media.sterilize(video, dst, job_id=None, level="media")
        elapsed = time.monotonic() - started
        check(
            f"vídeo {seconds}s · esterilização",
            dst.exists() and dst.stat().st_size > 0 and bool(report),
            f"{dst.stat().st_size / 1_048_576:.1f} MB em {elapsed:.1f}s",
        )

    # Montagem em lote: simula um recap de 3 h partido em centenas de blocos.
    parts_dir = work / "parts"
    parts_dir.mkdir()
    total_parts = CONCAT_BATCH * 2 + 5
    parts = []
    for index in range(total_parts):
        part = parts_dir / f"p{index:03d}.mp4"
        make_video(part, 1)
        parts.append(part)
    from app.services.recap import _concat_batched

    started = time.monotonic()
    final = work / "recap_final.mp4"
    _concat_batched(parts, final, parts_dir, "lab")
    duration = media.probe_duration(final)
    check(
        "recap · concat em lote",
        final.exists() and duration >= total_parts * 0.8,
        f"{total_parts} blocos → {duration:.1f}s em {time.monotonic() - started:.1f}s",
    )

    print()
    if FAILURES:
        print("FALHAS:", ", ".join(FAILURES))
        return 1
    print("Todos os motores passaram no teste de 10 s a 3 h.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
