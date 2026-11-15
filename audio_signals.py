"""
Multimodal Audio Signal Analyzer
Extracts vocal energy spikes, laughter bursts, and speech-rate dynamics
using librosa with resilient numpy/scipy fallback.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from schema import AudioSignals, WordTimestamp


class AudioSignalAnalyzer:
    """Extracts acoustic emotion, energy, and rhythm signals to augment viral curation."""

    @staticmethod
    def analyze_audio(
        audio_path: Optional[Path] = None,
        words: Optional[List[WordTimestamp]] = None,
        sample_rate: int = 16000
    ) -> AudioSignals:
        energy_peaks: List[float] = []
        laughter_spikes: List[float] = []
        speech_rate_wps = 2.5

        # 1. Analyze word-level speech rate spikes if words provided
        if words and len(words) > 5:
            durations = [w.end - w.start for w in words if (w.end - w.start) > 0.05]
            if durations:
                speech_rate_wps = round(float(np.mean([1.0 / d for d in durations[:50]])), 2)

        # 2. Extract acoustic features from audio file if present
        if audio_path and Path(audio_path).exists():
            try:
                # Try librosa first
                import librosa
                y, sr = librosa.load(str(audio_path), sr=sample_rate, mono=True)
                
                # RMS energy
                hop_length = int(sr * 0.25)  # 250ms hops
                rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
                times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
                
                # Threshold for energy peaks (> 85th percentile)
                if len(rms) > 10:
                    threshold = np.percentile(rms, 85)
                    peak_indices = np.where(rms >= threshold)[0]
                    # Sample top energy peaks spaced at least 3 seconds apart
                    last_time = -10.0
                    for idx in peak_indices:
                        t = float(times[idx])
                        if t - last_time >= 3.0:
                            energy_peaks.append(round(t, 2))
                            last_time = t

                # High-frequency spectral centroid burst detection (proxy for laughter/excitement)
                centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
                if len(centroid) > 10:
                    c_threshold = np.percentile(centroid, 90)
                    laughter_indices = np.where(centroid >= c_threshold)[0]
                    last_l_time = -10.0
                    for l_idx in laughter_indices:
                        lt = float(times[l_idx])
                        if lt - last_l_time >= 4.0:
                            laughter_spikes.append(round(lt, 2))
                            last_l_time = lt

            except Exception:
                # Fallback to scipy if librosa is not yet loaded
                try:
                    from scipy.io import wavfile
                    # If it's a wav file or can be read
                    sr, data = wavfile.read(str(audio_path))
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    step = int(sr * 0.5)
                    if len(data) > step * 5:
                        energies = [np.sqrt(np.mean(data[i:i+step].astype(np.float32)**2)) for i in range(0, len(data), step)]
                        top_idx = np.argsort(energies)[-5:]
                        energy_peaks = sorted([round(float(idx * 0.5), 2) for idx in top_idx])
                except Exception:
                    pass

        # Build prompt summary text
        summary_lines = []
        if energy_peaks:
            summary_lines.append(f"- High Vocal Energy / Emotion Spikes detected at seconds: {energy_peaks[:6]}")
        if laughter_spikes:
            summary_lines.append(f"- Laughter / Crowd Reactions detected at seconds: {laughter_spikes[:5]}")
        summary_lines.append(f"- Average Speech Velocity: {speech_rate_wps} words/sec")

        summary_text = "\n".join(summary_lines)

        return AudioSignals(
            energy_peaks=energy_peaks,
            laughter_spikes=laughter_spikes,
            avg_speech_rate_wps=speech_rate_wps,
            summary_text=summary_text
        )
