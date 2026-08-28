from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.services import viral_clips, viral_insights  # noqa: E402


class ViralClipEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "object": "transcription",
            "language": "pt",
            "duration_seconds": 180.0,
            "segments": [
                {"start": 0.0, "end": 35.0, "text": "A verdade que ninguém te conta sobre vendas?", "words": []},
                {"start": 35.0, "end": 70.0, "text": "O maior erro é ignorar os dados e repetir o mesmo anúncio.", "words": []},
                {"start": 70.0, "end": 105.0, "text": "No resultado do teste, as vendas aumentaram 200% em sete dias.", "words": []},
                {"start": 105.0, "end": 140.0, "text": "Mas existe uma virada: o criativo simples venceu o bonito.", "words": []},
                {"start": 140.0, "end": 175.0, "text": "A prova está nos dados e no resultado do cliente.", "words": []},
            ],
        }

    def test_insights_return_ranked_explainable_windows(self) -> None:
        result = viral_insights.analyze_json_verbose(self.payload, max_clips=3)
        self.assertEqual(result["object"], "viral_insights")
        self.assertEqual(result["engine"], "heuristic-v1")
        self.assertGreaterEqual(result["count"], 1)
        self.assertLessEqual(result["count"], 3)
        for clip in result["clips"]:
            self.assertGreaterEqual(clip["retention_score"], 0)
            self.assertLessEqual(clip["retention_score"], 100)
            self.assertGreaterEqual(clip["duration_seconds"], 30)
            self.assertLessEqual(clip["duration_seconds"], 90)
            self.assertTrue(clip["suggested_title"])
            self.assertTrue(clip["initial_hook"])
            self.assertTrue(clip["summary"])
            self.assertTrue(clip["reasons"])
            self.assertIn("hook_strength", clip["signals"])
        scores = [clip["retention_score"] for clip in result["clips"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_empty_or_short_transcription_returns_no_clip(self) -> None:
        self.assertEqual(viral_insights.detect_viral_clips({"duration_seconds": 20, "segments": []}), [])
        self.assertEqual(viral_insights.detect_viral_clips({"duration_seconds": 20, "segments": [{"start": 0, "end": 20, "text": "curto"}]}), [])

    def test_window_validation_rejects_out_of_bounds_and_long_clips(self) -> None:
        with self.assertRaises(viral_clips.ClipValidationError):
            viral_clips.validate_window(-1, 20, 100)
        with self.assertRaises(viral_clips.ClipValidationError):
            viral_clips.validate_window(0, 91, 100)
        with self.assertRaises(viral_clips.ClipValidationError):
            viral_clips.validate_window(80, 110, 100)
        self.assertEqual(viral_clips.validate_window(10.1234, 40.5678, 100), (10.123, 40.568, 100.0))

    def test_relative_segments_recalibrate_clip_to_zero(self) -> None:
        segments = [
            {
                "start": 5.0,
                "end": 12.0,
                "text": "primeiro trecho",
                "words": [
                    {"start": 5.5, "end": 6.0, "text": "primeiro"},
                    {"start": 10.0, "end": 11.0, "text": "trecho"},
                ],
            },
            {"start": 13.0, "end": 20.0, "text": "fora do clipe", "words": []},
        ]
        relative = viral_clips.relative_segments(segments, 8.0, 16.0)
        self.assertEqual(len(relative), 2)
        self.assertEqual(relative[0]["start"], 0.0)
        self.assertEqual(relative[0]["end"], 4.0)
        self.assertEqual(relative[0]["words"][0]["start"], 2.0)
        self.assertEqual(relative[0]["words"][0]["end"], 3.0)
        self.assertEqual(relative[1]["start"], 5.0)

    def test_clip_payload_and_caption_timestamps_are_relative(self) -> None:
        clip = viral_clips.clip_payload(self.payload, 35.0, 95.0)
        self.assertEqual(clip["source_start_seconds"], 35.0)
        self.assertEqual(clip["duration_seconds"], 60.0)
        self.assertEqual(clip["segments"][0]["start"], 0.0)
        srt = viral_clips.render_captions(clip, "srt")
        vtt = viral_clips.render_captions(clip, "vtt")
        self.assertIn("1\n00:00:00,000 -->", srt)
        self.assertIn("00:00:00.000 -->", vtt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
