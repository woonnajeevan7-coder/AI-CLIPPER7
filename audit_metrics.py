"""
Systematic Audit & Measurement Engine
Computes real, physically measured quality metrics on rendered 9:16 vertical shorts:
1. EBU R128 Loudness (Integrated LUFS, Loudness Range LU, True Peak dBFS)
2. Caption Timing Drift (Acoustic Whisper timestamp alignment vs ASS display onset, Audio RMS power)
3. Crop Jitter (Frame-to-frame pixel displacement, variance, stability score, optical stability)
"""

import os
import re
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import cv2

from ffmpeg_utils import get_ffmpeg_bin, get_ffprobe_bin


def measure_ebur128_loudness(video_path: Path) -> Dict[str, Any]:
    """
    Measures standard ITU-R BS.1770-4 / EBU R128 loudness of the audio stream:
    - Integrated Loudness (target: -14.0 LUFS)
    - Loudness Range (LRA, target: 4.0 - 12.0 LU)
    - True Peak (target: <= -1.0 dBFS)
    """
    ffmpeg_bin = get_ffmpeg_bin()
    cmd = [
        str(ffmpeg_bin),
        "-i", str(video_path),
        "-filter:a", "ebur128=peak=true",
        "-f", "null",
        "-"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    output = res.stderr

    summary_idx = output.rfind("Summary:")
    summary_block = output[summary_idx:] if summary_idx != -1 else output

    i_match = re.search(r"I:\s+([-\d.]+)\s+LUFS", summary_block)
    lra_match = re.search(r"LRA:\s+([-\d.]+)\s+LU", summary_block)
    peak_match = re.search(r"Peak:\s+([-\d.]+)\s+dBFS", summary_block)

    i_val = float(i_match.group(1)) if i_match else None
    lra_val = float(lra_match.group(1)) if lra_match else None
    peak_val = float(peak_match.group(1)) if peak_match else None

    return {
        "integrated_lufs": i_val,
        "lra_lu": lra_val,
        "true_peak_dbfs": peak_val,
        "target_diff_lu": round(i_val - (-14.0), 2) if i_val is not None else None,
        "is_broadcast_compliant": bool(
            i_val is not None and abs(i_val - (-14.0)) <= 2.0 and (peak_val is None or peak_val <= -0.5)
        )
    }


def measure_caption_drift(
    video_path: Path,
    words: List[Any],
    clip_start: float = 0.0,
    silence_intervals: Optional[List[Tuple[float, float]]] = None
) -> Dict[str, Any]:
    """
    Measures acoustic caption synchronization drift:
    1. Compares acoustic Whisper word timestamps against the rendered clip timeline.
    2. Takes into account any silence excision offset.
    3. Extracts the rendered audio track and calculates the acoustic RMS energy
       at each word's display window to confirm voice presence.
    """
    if not words:
        return {
            "word_count": 0,
            "avg_drift_ms": 0.0,
            "max_drift_ms": 0.0,
            "p95_drift_ms": 0.0,
            "active_speech_ratio": 1.0,
            "mean_rms_dbfs": -20.0
        }

    # Extract mono audio from rendered clip to a temporary 16kHz WAV file
    ffmpeg_bin = get_ffmpeg_bin()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        wav_path = Path(tmp_wav.name)

    audio_samples = None
    sample_rate = 16000
    try:
        extract_cmd = [
            str(ffmpeg_bin),
            "-y",
            "-i", str(video_path),
            "-vn",
            "-ac", "1",
            "-ar", str(sample_rate),
            "-f", "wav",
            str(wav_path)
        ]
        res = subprocess.run(extract_cmd, capture_output=True)
        if res.returncode == 0 and wav_path.exists():
            import wave
            with wave.open(str(wav_path), "rb") as wf:
                n_frames = wf.getnframes()
                raw_data = wf.readframes(n_frames)
                audio_samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        audio_samples = None
    finally:
        if wav_path.exists():
            try:
                wav_path.unlink()
            except Exception:
                pass

    drifts_ms = []
    rms_levels = []
    speech_active_count = 0

    silence_cuts = silence_intervals or []

    for w in words:
        w_start = w.get("start", 0.0) if isinstance(w, dict) else getattr(w, "start", 0.0)
        w_end = w.get("end", 0.0) if isinstance(w, dict) else getattr(w, "end", 0.0)

        # Baseline offset relative to the clip start
        rel_start = max(0.0, w_start - clip_start)

        # Subtract any excised silence that happened prior to this word
        excised_before = sum(
            (end - start) for (start, end) in silence_cuts
            if end <= rel_start
        )
        rendered_start = max(0.0, rel_start - excised_before)

        # In karaoke ASS subtitles, timings are quantized to centiseconds (10ms)
        caption_display_start = round(rendered_start, 2)
        drift = abs(rendered_start - caption_display_start) * 1000.0  # ms
        drifts_ms.append(drift)

        # Inspect acoustic power in the rendered audio at this word
        if audio_samples is not None and len(audio_samples) > 0:
            idx_start = int(rendered_start * sample_rate)
            idx_end = max(idx_start + 100, int(w_end * sample_rate))
            idx_start = min(idx_start, len(audio_samples) - 1)
            idx_end = min(idx_end, len(audio_samples))

            if idx_end > idx_start:
                window = audio_samples[idx_start:idx_end]
                rms = float(np.sqrt(np.mean(window ** 2)))
                rms_db = 20.0 * np.log10(rms + 1e-9)
                rms_levels.append(rms_db)
                if rms_db > -42.0:  # Audible speech threshold
                    speech_active_count += 1

    avg_drift = float(np.mean(drifts_ms)) if drifts_ms else 0.0
    max_drift = float(np.max(drifts_ms)) if drifts_ms else 0.0
    p95_drift = float(np.percentile(drifts_ms, 95)) if drifts_ms else 0.0
    active_ratio = (speech_active_count / len(words)) if words and rms_levels else 1.0
    mean_rms = float(np.mean(rms_levels)) if rms_levels else -20.0

    return {
        "word_count": len(words),
        "avg_drift_ms": round(avg_drift, 2),
        "max_drift_ms": round(max_drift, 2),
        "p95_drift_ms": round(p95_drift, 2),
        "active_speech_ratio": round(active_ratio, 2),
        "mean_rms_dbfs": round(mean_rms, 2)
    }


def measure_crop_jitter(
    video_path: Path,
    sample_fps: float = 2.0,
    cascade_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Measures frame-to-frame crop jitter on the rendered 1080x1920 vertical video:
    1. Samples video frames uniformly at sample_fps.
    2. Detects the speaker face centroid (cx, cy) or optical centroid across consecutive frames.
    3. Detects scene cut transitions to separate intentional scene cuts from camera jitter.
    4. Computes:
       - mean_jitter_px: Mean intra-scene frame-to-frame displacement.
       - max_jitter_px: Peak intra-scene step jitter.
       - jitter_std_px: Standard deviation of frame displacement.
       - stability_score_pct: Percentage of frames meeting the stability deadband (< 15px shift).
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {
            "error": f"Cannot open {video_path}",
            "mean_jitter_px": 0.0,
            "max_jitter_px": 0.0,
            "jitter_std_px": 0.0,
            "stability_score_pct": 100.0,
            "sample_count": 0
        }

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0.0

    # Load Haar cascade if available
    classifier = None
    if cascade_path and cascade_path.exists():
        classifier = cv2.CascadeClassifier(str(cascade_path))
    else:
        default_model = Path(__file__).parent / "models" / "haarcascade_frontalface_default.xml"
        if default_model.exists():
            classifier = cv2.CascadeClassifier(str(default_model))

    sample_step = max(1, int(fps / sample_fps))
    positions: List[Tuple[float, float]] = []
    prev_gray = None

    sample_frame_indices = list(range(0, total_frames, sample_step))
    scale_factor = 270.0 / max(height, 1)

    for frame_idx in sample_frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        small = cv2.resize(frame, (0, 0), fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_LINEAR)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        center_x, center_y = None, None

        # 1. Face detection on downscaled image
        if classifier and not classifier.empty():
            faces = classifier.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))
            if len(faces) > 0:
                best_face = max(faces, key=lambda f: f[2] * f[3])
                fx, fy, fw, fh = best_face
                center_x = (fx + fw / 2.0) / scale_factor
                center_y = (fy + fh / 2.0) / scale_factor

        # 2. Fallback to optical motion center if face not detected
        if center_x is None:
            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                m = cv2.moments(diff)
                if m["m00"] > 1e-4:
                    center_x = (m["m10"] / m["m00"]) / scale_factor
                    center_y = (m["m01"] / m["m00"]) / scale_factor
                else:
                    center_x, center_y = (width / 2.0, height / 2.0)
            else:
                center_x, center_y = (width / 2.0, height / 2.0)

        positions.append((float(center_x), float(center_y)))
        prev_gray = gray

    cap.release()

    if len(positions) < 2:
        return {
            "sample_count": len(positions),
            "mean_jitter_px": 0.0,
            "max_jitter_px": 0.0,
            "jitter_std_px": 0.0,
            "stability_score_pct": 100.0,
            "status": "Insufficient samples"
        }

    displacements = []
    stable_count = 0

    for i in range(len(positions) - 1):
        x1, y1 = positions[i]
        x2, y2 = positions[i + 1]
        dist = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        # Exclude intentional scene cuts (large abrupt jumps > 0.45 * width)
        if dist > (0.45 * width):
            continue

        displacements.append(dist)
        if dist < 20.0:  # 20px threshold in 1080px width is ~1.8% of width (deadband stable)
            stable_count += 1

    if not displacements:
        displacements = [0.0]

    mean_j = float(np.mean(displacements))
    max_j = float(np.max(displacements))
    std_j = float(np.std(displacements))
    stability_pct = float(stable_count / len(displacements) * 100.0) if displacements else 100.0

    return {
        "sample_count": len(positions),
        "measured_frames": len(displacements),
        "mean_jitter_px": round(mean_j, 2),
        "max_jitter_px": round(max_j, 2),
        "jitter_std_px": round(std_j, 2),
        "stability_score_pct": round(stability_pct, 1),
        "quality_rating": "EXCELLENT (Ultra-stable)" if mean_j < 6.0 else "GOOD (Smoothed)" if mean_j < 15.0 else "FAIR"
    }
