from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass

@dataclass
class VoiceProfile:
    id: str
    name: str
    engine: str
    created_at: float
    notes: str = ""
    metadata: dict = None

class VoiceCloningProvider(ABC):
    @abstractmethod
    def clone_voice(self, audio_path: Path, name: str, job_id: str) -> VoiceProfile:
        pass

    @abstractmethod
    def delete_voice(self, voice_id: str):
        pass

    @abstractmethod
    def list_voices(self) -> list[VoiceProfile]:
        pass
