"""
Serviço de Clonagem Neural Real — Ecossistema Viral.
Gerencia o pipeline de ingestão, validação e interface com provedores neurais.
"""

from __future__ import annotations
import time
import shutil
import logging
from pathlib import Path
from typing import Optional

from ..config import config
from . import media, jobs, voice_engine
from .cloning_providers.elevenlabs import ElevenLabsCloningProvider

logger = logging.getLogger(__name__)

# Configurações de Ingestão
MIN_DURATION = 60.0   # 1 minuto
MAX_DURATION = 600.0  # 10 minutos
STORAGE_DIR = config.storage_dir / "neural_clones"

def get_provider():
    """Retorna o provedor ativo. Por padrão, ElevenLabs se disponível."""
    if voice_engine.available():
        return ElevenLabsCloningProvider()
    return None

def validate_audio(path: Path) -> dict:
    """Valida se o áudio atende aos requisitos neurais."""
    info = media.probe(path)
    if not info.has_audio:
        raise ValueError("O arquivo não contém uma trilha de áudio válida.")
    
    if info.duration < MIN_DURATION:
        raise ValueError(f"Áudio muito curto ({info.duration:.1f}s). Envie pelo menos 1 minuto.")
    
    if info.duration > MAX_DURATION:
        raise ValueError(f"Áudio muito longo ({info.duration:.1f}s). O limite é 10 minutos.")
    
    return {
        "duration": info.duration,
        "sample_rate": info.sample_rate,
        "channels": info.channels
    }

def preprocess_audio(src: Path, job_id: str) -> Path:
    """Limpa e normaliza o áudio antes de enviar para o motor neural."""
    jobs.log(job_id, "Iniciando pré-processamento neural (normalização e redução de ruído)...")
    dst = src.parent / f"{src.stem}_clean.wav"
    
    # Normalização EBU R128 + Highpass para remover rumble + Gate para silêncios
    filters = [
        "highpass=f=80",
        "lowpass=f=12000",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        "silenceremove=start_periods=1:start_threshold=-50dB:stop_periods=1:stop_threshold=-50dB:stop_duration=0.5"
    ]
    
    media.run([
        config.ffmpeg_bin, "-y", "-i", str(src),
        "-af", ",".join(filters),
        "-ar", "44100", "-ac", "1", str(dst)
    ], job_id=job_id)
    
    return dst

def start_cloning_job(audio_path: Path, name: str, consent: bool, job_id: str):
    """Executa o fluxo completo de clonagem neural."""
    if not consent:
        raise ValueError("Consentimento obrigatório não fornecido.")
    
    provider = get_provider()
    if not provider:
        raise RuntimeError("Nenhum motor neural real configurado (Verifique a chave ElevenLabs em /apis).")

    try:
        # 1. Validação
        validate_audio(audio_path)
        
        # 2. Preprocessamento
        jobs.update(job_id, progress=20)
        clean_audio = preprocess_audio(audio_path, job_id)
        
        # 3. Envio para o Provedor Neural
        jobs.stage(job_id, "clonando", "Enviando amostra para o motor neural ElevenLabs...", progress=40)
        profile = provider.clone_voice(clean_audio, name, job_id)
        
        # 4. Finalização
        jobs.log(job_id, f"Clonagem concluída! ID da Voz: {profile.id}")
        jobs.update(job_id, progress=100)
        
        # Limpeza
        clean_audio.unlink(missing_ok=True)
        
        return profile
    except Exception as e:
        logger.exception("Falha no job de clonagem neural")
        jobs.fail(job_id, str(e))
        raise
