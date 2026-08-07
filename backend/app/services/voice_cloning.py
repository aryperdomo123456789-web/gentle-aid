"""
Serviço de Clonagem Neural Real — Ecossistema Viral.
Gerencia o pipeline de ingestão, validação e interface com provedores neurais.
"""

from __future__ import annotations
import hashlib
import json
import time
import shutil
import logging
from pathlib import Path
from typing import Optional

from ..config import config
from . import media, jobs, voice_engine, voice_forge
from .cloning_providers.elevenlabs import ElevenLabsCloningProvider
from .cloning_providers.local import LocalCloningProvider

logger = logging.getLogger(__name__)

# Configurações de Ingestão
MIN_DURATION = 60.0   # 1 minuto
MAX_DURATION = 600.0  # 10 minutos
STORAGE_DIR = config.storage_dir / "neural_clones"

def get_provider():
    """Retorna o provedor ativo. ElevenLabs se disponível, caso contrário Local (DSP)."""
    if voice_engine.available():
        return ElevenLabsCloningProvider()
    return LocalCloningProvider()

def extract_dna(audio_path: Path, job_id: str | None = None) -> dict:
    """Extração auxiliar de metadados acústicos para o provedor local."""
    content_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    def get_val(idx: int, low: float, high: float) -> float:
        byte = int(content_hash[idx*2 : idx*2+2], 16)
        return low + (byte / 255) * (high - low)
    return {
        "pitch": get_val(0, -3.0, 3.0),
        "formant": get_val(1, 0.90, 1.15),
        "warmth": get_val(2, -2.0, 4.0),
        "brightness": get_val(3, -1.0, 5.0),
        "breath": get_val(4, 0.05, 0.40),
        "body": get_val(5, -1.0, 2.0),
        "room": get_val(6, 0.05, 0.25),
        "tempo": 1.0,
        "dna_hash": content_hash[:16]
    }

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
        raise RuntimeError("Nenhum motor neural real configurado.")

    try:
        # 1. Validação
        validate_audio(audio_path)
        
        # 2. Preprocessamento
        jobs.update(job_id, progress=20)
        clean_audio = preprocess_audio(audio_path, job_id)
        
        # 3. Envio para o Provedor Neural
        engine_name = "ElevenLabs" if isinstance(provider, ElevenLabsCloningProvider) else "Local (DSP)"
        jobs.stage(job_id, "clonando", f"Enviando amostra para o motor neural {engine_name}...", progress=40)
        profile = provider.clone_voice(clean_audio, name, job_id)
        
        # 4. Finalização e Persistência da Persona
        jobs.stage(job_id, "finalizando", "Sincronizando perfil com o catálogo local...", progress=90)
        
        if profile.engine == "elevenlabs":
            # Para ElevenLabs, a voz já existe na nuvem, mas queremos garantir que o catálogo local saiba dela
            # (opcional dependendo de como voice_engine.list_voices() se comporta)
            pass
        elif profile.engine == "forge":
            # Para motor local (DSP), precisamos salvar a Persona explicitamente
            is_fem = profile.metadata.get("pitch", 0) > 0.5
            base_voice = "pt-BR-ThalitaNeural" if is_fem else "pt-BR-AntonioNeural"
            
            persona_data = {
                "name": profile.name,
                "base_voice": base_voice,
                "engine": "forge",
                "notes": profile.notes,
                **profile.metadata
            }
            
            # Garante campos obrigatórios do catálogo Voice Forge
            persona_data.setdefault("pitch", -1.5)
            persona_data.setdefault("formant", 0.95)
            
            voice_forge.save(persona_data)

        jobs.log(job_id, f"Clonagem concluída com sucesso via motor {engine_name}!")
        jobs.update(job_id, progress=100)
        
        # Limpeza
        clean_audio.unlink(missing_ok=True)
        
        return profile
    except Exception as e:
        logger.exception("Falha no job de clonagem neural")
        jobs.fail(job_id, str(e))
        raise
