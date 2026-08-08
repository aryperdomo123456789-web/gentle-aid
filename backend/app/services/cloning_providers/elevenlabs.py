import json
import time
from pathlib import Path
from .base import VoiceCloningProvider, VoiceProfile
from .. import voice_engine

class ElevenLabsCloningProvider(VoiceCloningProvider):
    def clone_voice(self, audio_path: Path, name: str, job_id: str) -> VoiceProfile:
        # ElevenLabs Add Voice API
        # Ref: https://elevenlabs.io/docs/api-reference/add-voice
        fields = {
            "name": name,
            "description": f"Clone neural criado via Ecossistema Viral em {time.ctime()}",
        }
        
        # A ElevenLabs exige multipart
        body, content_type = voice_engine._multipart(
            fields,
            "files",
            audio_path
        )
        
        raw_resp = voice_engine._request(
            "/voices/add",
            method="POST",
            data=body,
            headers={"Content-Type": content_type}
        )
        resp = json.loads(raw_resp.decode("utf-8"))
        voice_id = resp.get("voice_id")
        
        return VoiceProfile(
            id=voice_id,
            name=name,
            engine="elevenlabs",
            created_at=time.time(),
            notes=fields["description"],
            metadata={"source": "upload", "job_id": job_id}
        )

    def delete_voice(self, voice_id: str):
        voice_engine._request(f"/voices/{voice_id}", method="DELETE")

    def list_voices(self) -> list[VoiceProfile]:
        voices = voice_engine.list_voices()
        # Aqui poderíamos filtrar apenas as clonadas se a API desse essa info fácil, 
        # mas por hora retornamos o que o engine já traz formatado.
        return [
            VoiceProfile(id=v["id"], name=v["name"], engine="elevenlabs", created_at=0)
            for v in voices
        ]
