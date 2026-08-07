import time
import hashlib
from pathlib import Path
from .base import VoiceCloningProvider, VoiceProfile

class LocalCloningProvider(VoiceCloningProvider):
    """
    Provedor de fallback que mantém a lógica de DNA acústico.
    Útil para desenvolvimento ou quando não há chaves externas.
    """
    def clone_voice(self, audio_path: Path, name: str, job_id: str) -> VoiceProfile:
        from .. import voice_cloning
        # Reusa a lógica de DNA para preencher metadados iniciais
        dna = voice_cloning.extract_dna(audio_path, job_id)
        
        return VoiceProfile(
            id=f"local_{int(time.time())}",
            name=name,
            engine="forge",
            created_at=time.time(),
            notes=f"Clone local (DSP). DNA: {dna['dna_hash']}",
            metadata=dna
        )

    def delete_voice(self, voice_id: str):
        pass

    def list_voices(self) -> list[VoiceProfile]:
        return []
