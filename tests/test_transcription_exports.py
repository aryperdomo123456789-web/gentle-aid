from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.services import transcription_exports, transcribe  # noqa: E402


class TranscriptionExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.segments = [
            transcribe.Segment(
                start=0.125,
                end=1.875,
                text="Olá, mundo!",
                words=[
                    transcribe.WordStamp(0.125, 0.5, "Olá,"),
                    transcribe.WordStamp(0.6, 1.875, "mundo!"),
                ],
            ),
            transcribe.Segment(start=600.25, end=601.0, text="Segundo bloco."),
        ]

    def test_srt_and_vtt_keep_precise_timestamps(self) -> None:
        srt = transcription_exports.render_segments(self.segments, "srt", language="pt")
        vtt = transcription_exports.render_segments(self.segments, "vtt", language="pt")
        self.assertIn("00:00:00,125 --> 00:00:01,875", srt)
        self.assertIn("00:10:00,250 --> 00:10:01,000", srt)
        self.assertIn("00:00:00.125 --> 00:00:01.875", vtt)
        self.assertTrue(vtt.startswith("WEBVTT\n"))
        self.assertNotIn(",", vtt.splitlines()[2])

    def test_json_verbose_contains_words_duration_and_text(self) -> None:
        rendered = transcription_exports.render_segments(
            self.segments,
            "json_verbose",
            language="pt",
            duration_seconds=601.2,
        )
        self.assertIn('"object": "transcription"', rendered)
        self.assertIn('"duration_seconds": 601.2', rendered)
        self.assertIn('"text": "Olá, mundo!"', rendered)
        self.assertIn('"text": "Olá,"', rendered)

    def test_legacy_json_remains_compact_contract(self) -> None:
        rendered = transcription_exports.render_segments(self.segments, "json", language="pt")
        self.assertIn('"language": "pt"', rendered)
        self.assertIn('"segments"', rendered)
        self.assertNotIn('"object": "transcription"', rendered)

    def test_vad_moves_cut_to_nearby_silence_and_keeps_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "long.mp3"
            source.write_bytes(b"x")
            with patch.object(transcribe, "_vad_silences", return_value=[(590.0, 610.0)]):
                chunks = transcribe._plan_chunks(source, 1200.0, job_id="test-vad")
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].start, 0.0)
        self.assertEqual(chunks[0].duration, 590.0)
        self.assertEqual(chunks[1].start, 590.0)
        self.assertEqual(chunks[1].duration, 610.0)
        self.assertEqual(chunks[0].reason, "vad")

    def test_size_limit_also_creates_multiple_chunks(self) -> None:
        fake_path = type(
            "FakePath",
            (),
            {"stat": lambda self: type("Stat", (), {"st_size": 26 * 1024 * 1024})()},
        )()
        with patch.object(transcribe, "_vad_silences", return_value=[]):
            chunks = transcribe._plan_chunks(fake_path, 60.0, job_id="test-size")
        self.assertEqual(len(chunks), 2)
        self.assertAlmostEqual(sum(chunk.duration for chunk in chunks), 60.0)

    def test_chunk_segment_offset_is_absolute(self) -> None:
        payload = {"segments": [{"start": 1.25, "end": 2.5, "text": "bloco"}]}
        segments = transcribe._segments_from(payload, 600.0)
        self.assertEqual(segments[0].start, 601.25)
        self.assertEqual(segments[0].end, 602.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
