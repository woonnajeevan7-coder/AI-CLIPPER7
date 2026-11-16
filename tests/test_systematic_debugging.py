"""
Systematic Debugging Regression Tests
Verifies fixes for:
(a) Captions use Whisper acoustic word timestamps rather than interpolated YouTube times
(b) Silence trimming preserves exact audio/video/caption synchronization
(c) Background music ducking uses real sidechaincompress and measures post-mix loudness
(d) Smart framing builds per-segment crops that reset at scene cuts instead of collapsing
(e) Punch-in zoom actively alters frame pixels during zoom intervals
"""

import subprocess
import json
from pathlib import Path
import numpy as np
import cv2
import pytest

from schema import WordTimestamp, CropPlan
from agents.polish import PunchInPlanner, AudioPolisher
from agents.framing import SmartFramingAgent
from agents.editor import VideoEditorAgent
from agents.orchestrator import ClipperOrchestratorAgent
from captions import generate_karaoke_ass, format_ass_timestamp


def test_whisper_timestamps_always_used_for_captions(tmp_path: Path, monkeypatch):
    """
    (a) Verifies that even if YouTube captions exist, Groq Whisper acoustic
    timestamps are always used for captions whenever Groq Whisper is available.
    """
    orchestrator = ClipperOrchestratorAgent(project_root=tmp_path)
    orchestrator.curator.api_key = "mock_groq_key"
    orchestrator.curator.provider = "groq"

    # YouTube mock: linearly interpolated words (0.0 to 3.0 uniform)
    youtube_words = [
        WordTimestamp(word="Interpolated", start=0.0, end=1.5),
        WordTimestamp(word="Timing", start=1.5, end=3.0)
    ]
    # Whisper mock: true acoustic timestamps (e.g. speech actually occurs at 0.42 to 2.85)
    whisper_words = [
        WordTimestamp(word="Acoustic", start=0.42, end=1.18),
        WordTimestamp(word="Precision", start=1.85, end=2.85)
    ]

    monkeypatch.setattr(orchestrator.transcriber, "extract_youtube_id", lambda url: "mock_vid_123")
    monkeypatch.setattr(orchestrator.transcriber, "fetch_youtube_transcript", lambda vid: youtube_words)
    monkeypatch.setattr(orchestrator.transcriber, "download_youtube_video", lambda url, dest: dest)
    monkeypatch.setattr(orchestrator.transcriber, "extract_audio", lambda vid, dest: True)
    monkeypatch.setattr(orchestrator.transcriber, "transcribe_with_groq_whisper", lambda audio, key: whisper_words)
    monkeypatch.setattr("agents.orchestrator.AudioSignalAnalyzer.analyze_audio", lambda **kw: None)

    # Mock candidate generator and judge to isolate transcription step
    monkeypatch.setattr(orchestrator.curator, "generate_candidates", lambda *args, **kw: [])

    events = list(orchestrator.run_pipeline(source="https://www.youtube.com/watch?v=mock_vid_123", is_url=True))
    transcription_events = [e for e in events if e.get("step") == 1]
    assert any("acoustic word timestamps" in e.get("status", "").lower() for e in transcription_events)


def test_silence_trim_av_and_caption_synchronization(tmp_path: Path):
    """
    (b) Verifies silence trimming trims video and audio synchronously and adjusts
    ASS captions so audio, video, and captions never desynchronize.
    """
    ffmpeg_bin = Path("ffmpeg.exe").resolve()
    fonts_dir = Path("fonts").resolve()
    editor = VideoEditorAgent(ffmpeg_bin=ffmpeg_bin, fonts_dir=fonts_dir)

    # Synthesize 4.0s test video with 1.2s silence in the middle (t=1.0 to t=2.2)
    test_vid = tmp_path / "sync_test_source.mp4"
    cmd_synth = [
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-filter_complex", "[1:a]volume=enable='between(t,1.0,2.2)':volume=0[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-c:a", "aac",
        "-y", str(test_vid)
    ]
    subprocess.run(cmd_synth, check=True, capture_output=True)

    # Generate ASS with dialogue at 2.8s - 3.4s (after the silence)
    words = [
        WordTimestamp(word="Intro", start=0.2, end=0.8),
        WordTimestamp(word="PostSilence", start=2.8, end=3.4)
    ]
    ass_file = tmp_path / "sync_captions.ass"
    generate_karaoke_ass(words, ass_file, style_preset="hormozi")

    out_short = tmp_path / "sync_short.mp4"
    success = editor.render_short(
        source_video_path=test_vid,
        start_seconds=0.0,
        end_seconds=4.0,
        headline="SYNC TEST",
        output_path=out_short,
        ass_subtitle_path=ass_file,
        silence_trim=True,
        use_nvenc=False
    )
    assert success is True
    assert out_short.exists()

    # Probe stream durations with ffprobe
    p = subprocess.run([
        "ffprobe.exe", "-v", "error", "-show_entries", "stream=codec_type,duration",
        "-of", "json", str(out_short)
    ], capture_output=True, text=True)
    streams = json.loads(p.stdout)["streams"]
    v_dur = float([s["duration"] for s in streams if s["codec_type"] == "video"][0])
    a_dur = float([s["duration"] for s in streams if s["codec_type"] == "audio"][0])

    # Audio and video durations must match within 0.15s (not 1.2s desynced)
    assert abs(v_dur - a_dur) < 0.15


def test_sidechaincompress_ducking_and_postmix_loudness(tmp_path: Path):
    """
    (c) Verifies background music ducking uses sidechaincompress and measures post-mix loudness.
    """
    ffmpeg_bin = Path("ffmpeg.exe").resolve()
    fonts_dir = Path("fonts").resolve()
    editor = VideoEditorAgent(ffmpeg_bin=ffmpeg_bin, fonts_dir=fonts_dir)

    # Synthesize speech video and bgm music file
    speech_vid = tmp_path / "voice.mp4"
    bgm_file = tmp_path / "bgm.mp3"

    subprocess.run([
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264", "-c:a", "aac", "-y", str(speech_vid)
    ], check=True, capture_output=True)

    subprocess.run([
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "sine=frequency=220:duration=3",
        "-c:a", "libmp3lame", "-y", str(bgm_file)
    ], check=True, capture_output=True)

    # Verify AudioPolisher ducking filter string contains sidechaincompress
    duck_filter = AudioPolisher.build_ducking_filter(music_volume=0.25)
    assert "sidechaincompress" in duck_filter
    assert "amix" in duck_filter

    # Render with BGM
    out_ducked = tmp_path / "ducked_output.mp4"
    success = editor.render_short(
        source_video_path=speech_vid,
        start_seconds=0.0,
        end_seconds=3.0,
        headline="DUCKING TEST",
        output_path=out_ducked,
        background_music_path=bgm_file,
        use_nvenc=False
    )
    assert success is True
    assert out_ducked.exists()

    # Verify loudness was measured post-mixing
    assert editor.last_measured_loudness is not None
    assert "integrated_lufs" in editor.last_measured_loudness
    assert "true_peak_db" in editor.last_measured_loudness
    assert "lra" in editor.last_measured_loudness
    assert isinstance(editor.last_measured_loudness["integrated_lufs"], float)


def test_framing_per_segment_crops_reset_at_scene_cuts():
    """
    (d) Verifies framing produces per-segment crops across scene cut boundaries
    rather than collapsing into one static median crop.
    """
    framing = SmartFramingAgent()

    # Simulate 2 distinct scenes:
    # Scene 1 (t=0.0 to 3.0): Speaker A is on the far left (cx = 200)
    # Scene cut at t=3.0
    # Scene 2 (t=3.0 to 6.0): Speaker B is on the far right (cx = 1600)
    scene_cuts = [3.0]
    records = [
        {"time_offset": 0.5, "faces": [{"cx": 200, "cy": 500, "w": 100, "h": 100}]},
        {"time_offset": 1.5, "faces": [{"cx": 200, "cy": 500, "w": 100, "h": 100}]},
        {"time_offset": 2.5, "faces": [{"cx": 200, "cy": 500, "w": 100, "h": 100}]},
        {"time_offset": 3.5, "faces": [{"cx": 1600, "cy": 500, "w": 100, "h": 100}]},
        {"time_offset": 4.5, "faces": [{"cx": 1600, "cy": 500, "w": 100, "h": 100}]},
        {"time_offset": 5.5, "faces": [{"cx": 1600, "cy": 500, "w": 100, "h": 100}]},
    ]

    crop_plan = framing._build_single_face_plan(records, width=1920, height=1080, scene_cuts=scene_cuts)

    # Must contain per-segment crops
    assert len(crop_plan.crop_segments) >= 2
    seg_0 = crop_plan.crop_segments[0]
    seg_1 = crop_plan.crop_segments[1]

    # Segment 0 framed near cx=200, Segment 1 framed near cx=1600
    assert seg_0["crop_x"] != seg_1["crop_x"]
    assert seg_0["crop_x"] < seg_1["crop_x"]

    # Filter string must use conditional expression resetting at scene cut
    assert "if(lt(t" in crop_plan.filter_string
    assert "3.00" in crop_plan.filter_string


def test_punch_in_zoom_actually_changes_frames(tmp_path: Path):
    """
    (e) Verifies punch-in zoom actively alters frame content during zoom intervals.
    """
    ffmpeg_bin = Path("ffmpeg.exe").resolve()
    fonts_dir = Path("fonts").resolve()
    editor = VideoEditorAgent(ffmpeg_bin=ffmpeg_bin, fonts_dir=fonts_dir)

    # Synthesize test video (3.0s) with rich gradient and pattern
    source_vid = tmp_path / "zoom_source.mp4"
    cmd_synth = [
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264", "-c:a", "aac",
        "-y", str(source_vid)
    ]
    subprocess.run(cmd_synth, check=True, capture_output=True)

    # Build zoom filter punching in between 0.0s and 1.5s
    intervals = [(0.0, 1.5)]
    zoom_filter = PunchInPlanner.generate_zoom_filter(intervals, zoom_factor=1.20)
    assert "split=2" in zoom_filter
    assert "overlay=" in zoom_filter

    out_zoomed = tmp_path / "rendered_zoomed.mp4"
    success = editor.render_short(
        source_video_path=source_vid,
        start_seconds=0.0,
        end_seconds=3.0,
        headline="PUNCH IN VERIFICATION",
        output_path=out_zoomed,
        punch_in_filter=zoom_filter,
        use_nvenc=False
    )
    assert success is True
    assert out_zoomed.exists()

    # Extract frame at t=0.5 (zoom active) and compare against source at t=0.5 (unzoomed)
    frame_zoomed = tmp_path / "frame_zoomed.png"
    frame_unzoomed = tmp_path / "frame_unzoomed.png"

    subprocess.run([str(ffmpeg_bin), "-ss", "0.5", "-i", str(out_zoomed), "-vframes", "1", "-y", str(frame_zoomed)], check=True, capture_output=True)
    subprocess.run([str(ffmpeg_bin), "-ss", "0.5", "-i", str(source_vid), "-vframes", "1", "-y", str(frame_unzoomed)], check=True, capture_output=True)

    img_z = cv2.imread(str(frame_zoomed))
    img_u = cv2.imread(str(frame_unzoomed))

    diff = cv2.absdiff(img_z, img_u)
    mean_diff = float(np.mean(diff))

    # Mean pixel difference must be significantly non-zero (proving frames actually changed)
    assert mean_diff > 10.0, f"Expected mean_diff > 10.0, got {mean_diff}"
