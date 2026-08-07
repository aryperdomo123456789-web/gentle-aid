
import os
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

# Adiciona o diretório do backend ao path
sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

# Mock de dependências pesadas antes de importar os serviços
sys.modules['voice_engine'] = MagicMock()
sys.modules['media'] = MagicMock()
sys.modules['jobs'] = MagicMock()

from app.services import voice_cloning, voice_forge
from app.services.cloning_providers.base import VoiceProfile

class TestVoiceCloningNeural(unittest.TestCase):
    def setUp(self):
        self.audio_path = Path("/tmp/test_audio.wav")
        self.audio_path.write_bytes(b"fake audio data" * 100)
        self.job_id = "test-job-123"

    def tearDown(self):
        if self.audio_path.exists():
            self.audio_path.unlink()

    @patch("app.services.media.probe")
    def test_validate_audio_duration_ok(self, mock_probe):
        # 2 minutos (OK)
        mock_probe.return_value = MagicMock(has_audio=True, duration=120.0, sample_rate=44100, channels=1)
        info = voice_cloning.validate_audio(self.audio_path)
        self.assertEqual(info["duration"], 120.0)

    @patch("app.services.media.probe")
    def test_validate_audio_duration_too_short(self, mock_probe):
        # 30 segundos (Curto demais)
        mock_probe.return_value = MagicMock(has_audio=True, duration=30.0, sample_rate=44100, channels=1)
        with self.assertRaisesRegex(ValueError, "Áudio insuficiente"):
            voice_cloning.validate_audio(self.audio_path)

    @patch("app.services.media.probe")
    def test_validate_audio_duration_too_long(self, mock_probe):
        # 15 minutos (Longo demais)
        mock_probe.return_value = MagicMock(has_audio=True, duration=900.0, sample_rate=44100, channels=1)
        with self.assertRaisesRegex(ValueError, "Áudio muito longo"):
            voice_cloning.validate_audio(self.audio_path)

    @patch("app.services.voice_cloning.get_provider")
    @patch("app.services.voice_cloning.validate_audio")
    @patch("app.services.voice_cloning.preprocess_audio")
    @patch("app.services.voice_forge.save")
    def test_full_cloning_flow(self, mock_save, mock_preprocess, mock_validate, mock_get_provider):
        # Setup mocks
        mock_provider = MagicMock()
        mock_profile = VoiceProfile(
            id="voice_123", 
            name="Test Voice", 
            engine="elevenlabs", 
            created_at=123456789,
            notes="Clone neural real",
            metadata={"test": True}
        )
        mock_provider.clone_voice.return_value = mock_profile
        mock_get_provider.return_value = mock_provider
        
        mock_validate.return_value = {"duration": 120.0, "sample_rate": 44100, "channels": 1}
        mock_preprocess.return_value = self.audio_path

        # Execute
        voice_cloning.start_cloning_job(self.audio_path, "Test Voice", True, self.job_id)

        # Verify
        mock_provider.clone_voice.assert_called_once()
        mock_save.assert_called_once()
        args, _ = mock_save.call_args
        persona_dict = args[0]
        
        self.assertEqual(persona_dict["id"], "voice_123")
        self.assertEqual(persona_dict["type"], "neural_clone")
        self.assertEqual(persona_dict["engine"], "elevenlabs")

if __name__ == "__main__":
    unittest.main()
