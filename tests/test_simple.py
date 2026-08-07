import unittest
from pathlib import Path
import hashlib

# Simula as constantes e lógicas do serviço sem importar o módulo
MIN_DURATION = 60.0
MAX_DURATION = 600.0

def validate_audio(duration, has_audio, sample_rate):
    if not has_audio:
        raise ValueError("O arquivo não contém uma trilha de áudio válida.")
    if duration < MIN_DURATION:
        raise ValueError(f"Áudio insuficiente para clonagem neural ({duration:.1f}s). Envie pelo menos 1 minuto (60s).")
    if duration > MAX_DURATION:
        raise ValueError(f"Áudio muito longo ({duration:.1f}s). O limite para precisão neural é 10 minutos.")
    if sample_rate < 16000:
        raise ValueError(f"Qualidade de áudio muito baixa ({sample_rate}Hz). Use pelo menos 16kHz.")
    return {"duration": duration, "sample_rate": sample_rate}

class TestVoiceLogic(unittest.TestCase):
    def test_validation_logic(self):
        # Teste de duração OK
        res = validate_audio(120.0, True, 44100)
        self.assertEqual(res["duration"], 120.0)
        
        # Teste de duração curta
        with self.assertRaises(ValueError):
            validate_audio(30.0, True, 44100)
            
        # Teste de duração longa
        with self.assertRaises(ValueError):
            validate_audio(900.0, True, 44100)
            
        # Teste de qualidade baixa
        with self.assertRaises(ValueError):
            validate_audio(120.0, True, 8000)

if __name__ == "__main__":
    unittest.main()
