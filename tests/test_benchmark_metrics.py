"""
TDD Tests for Audit & Quality Metrics:
Tests real measured loudness, caption drift, and crop jitter.
"""

import subprocess
import numpy as np
from pathlib import Path
import pytest

from ffmpeg_utils import get_ffmpeg_bin
from audit_metrics import measure_ebur128_loudness, measure_caption_drift, measure_crop_jitter


def test_measure_ebur128_loudness(tmp_path: Path):
    """Verifies real EBU R128 loudness measurement computes integrated LUFS, LRA, and True Peak."""
    ffmpeg_bin = get_ffmpeg_bin()
    test_video = tmp_path / "test_loudness.mp4"

    # Synthesize 2.0s audio-video file with known sine wave (ultrafast preset)
    subprocess.run([
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "color=c=blue:size=320x240:rate=10:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-y", str(test_video)
    ], check=True, capture_output=True)

    result = measure_ebur128_loudness(test_video)
    assert result is not None
    assert "integrated_lufs" in result
    assert "lra_lu" in result
    assert "true_peak_dbfs" in result
    assert isinstance(result["integrated_lufs"], float)
    assert result["integrated_lufs"] < 0.0  # Loudness in LUFS is negative
    assert isinstance(result["true_peak_dbfs"], float)


def test_measure_caption_drift(tmp_path: Path):
    """Verifies caption drift computes acoustic drift in milliseconds and measures audio RMS."""
    ffmpeg_bin = get_ffmpeg_bin()
    test_video = tmp_path / "test_caption_drift.mp4"

    # Synthesize video with 440Hz tone
    subprocess.run([
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "color=c=black:size=320x240:rate=10:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-y", str(test_video)
    ], check=True, capture_output=True)

    # Synthetic words with acoustic timestamps
    words = [
        {"word": "Hello", "start": 0.425, "end": 0.950},
        {"word": "World", "start": 1.108, "end": 1.842}
    ]

    drift_report = measure_caption_drift(test_video, words, clip_start=0.0)
    assert drift_report["word_count"] == 2
    assert "avg_drift_ms" in drift_report
    assert "max_drift_ms" in drift_report
    assert "p95_drift_ms" in drift_report
    assert "active_speech_ratio" in drift_report
    assert "mean_rms_dbfs" in drift_report

    # Sub-frame centisecond quantization drift is bounded below 10.0 ms
    assert drift_report["avg_drift_ms"] <= 10.0
    assert drift_report["max_drift_ms"] <= 10.0
    # Because tone is playing, speech energy is active
    assert drift_report["mean_rms_dbfs"] > -40.0


def test_measure_crop_jitter(tmp_path: Path):
    """Verifies crop jitter measures pixel displacements and stability scores across video frames."""
    ffmpeg_bin = get_ffmpeg_bin()
    test_video = tmp_path / "test_jitter.mp4"

    # Synthesize static solid color video (2.0s)
    subprocess.run([
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "color=c=black:size=320x240:rate=10:duration=2",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo:d=2",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-t", "2",
        "-y", str(test_video)
    ], check=True, capture_output=True)

    jitter_report = measure_crop_jitter(test_video, sample_fps=2.0)
    assert jitter_report["sample_count"] > 0
    assert "mean_jitter_px" in jitter_report
    assert "max_jitter_px" in jitter_report
    assert "jitter_std_px" in jitter_report
    assert "stability_score_pct" in jitter_report

    # In a completely static synthetic video, jitter is 0.0 px
    assert jitter_report["mean_jitter_px"] == 0.0
    assert jitter_report["stability_score_pct"] == 100.0
    assert "EXCELLENT" in jitter_report["quality_rating"]
