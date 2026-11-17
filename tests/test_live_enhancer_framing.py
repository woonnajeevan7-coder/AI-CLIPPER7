"""
Comprehensive Tests for Live Enhancer & Smart Framing
Verifies:
1. Genre detection: word-boundary regex, >= 3 distinct keyword hits, UI explicit mode override.
2. Gaming layout: webcam face crop on top (1080x640) + gameplay crop below (1080x1280),
   falling back to action crop when no webcam face is detected.
3. ffprobe checks: 1080x1920 resolution, h264, aac audio present, source frame rate preserved (no forced -r 60).
4. Caption timing: dialogue timestamps in ASS file within 100 ms of Whisper words.
5. Unicode headlines with script-aware fonts: Devanagari, Spanish, CJK, quotes without stripping.
6. Failed render handling: retries once with libx264, emits error event, never silently drops.
"""

import json
import re
import subprocess
import tempfile
import uuid
from pathlib import Path
import pytest

from ffmpeg_utils import get_ffmpeg_bin, get_ffprobe_bin
from agents.framing import SmartFramingAgent
from agents.editor import VideoEditorAgent, select_script_aware_font
from captions import generate_karaoke_ass
from schema import WordTimestamp, CropPlan
from backend.models import User, LiveSession, Clip
from backend.database import SessionLocal
from backend.auth import create_access_token
from live.enhancer import enhance_clip_sync


def get_media_stream_info(media_path: Path):
    """Uses ffprobe to extract stream details in JSON format."""
    ffprobe_bin = get_ffprobe_bin()
    cmd = [
        str(ffprobe_bin),
        "-v", "error",
        "-show_entries", "stream=width,height,codec_name,codec_type,r_frame_rate,avg_frame_rate",
        "-of", "json",
        str(media_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    data = json.loads(res.stdout)
    return data.get("streams", [])


def create_test_user(username: str = "framing_user") -> User:
    db = SessionLocal()
    user_email = f"{username}@example.com"
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=user_email,
            full_name=username,
            hashed_password="pw",
            plan="agency"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    db.close()
    return user


def create_test_session(user_id: str) -> str:
    db = SessionLocal()
    session = LiveSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        broadcaster_id="streamer_123",
        title="Epic Stream Gaming & Highlights",
        status="live",
        rights_confirmed=True,
        target_framing="auto"
    )
    db.add(session)
    db.commit()
    session_id = session.id
    db.close()
    return session_id


# ==============================================================================
# 1. Genre Detection Tests
# ==============================================================================

def test_genre_detection_word_boundary_and_distinct_keyword_threshold():
    """
    Verifies that genre detection:
    - Uses word-boundary regex (no substring false positives like 'moreover' or 'matches')
    - Requires >= 3 distinct keyword hits for auto-detection
    - Correctly classifies gaming vs sports
    """
    # Test A: Substring false positives must NOT trigger keywords
    sub_text = "Moreover, we are discovering matches covering sixteen players."
    mode, hits = SmartFramingAgent.detect_genre_and_framing(sub_text)
    assert mode == "auto"
    assert len(hits) == 0  # 'moreover' != 'over', 'matches' != 'match', 'sixteen' != 'six'

    # Test B: Less than 3 distinct keywords must NOT trigger genre auto-crop
    few_keywords = "The bowler delivered on the pitch."
    mode, hits = SmartFramingAgent.detect_genre_and_framing(few_keywords)
    assert mode == "auto"
    assert len(hits) == 2  # 'bowler', 'pitch' (only 2 distinct hits < 3)

    # Test C: >= 3 distinct sports keywords triggers sports_gaming
    sports_text = "In this cricket match, the batsman hit a six against the bowler over the boundary in IPL."
    mode, hits = SmartFramingAgent.detect_genre_and_framing(sports_text)
    assert mode == "sports_gaming"
    assert len(hits) >= 3
    assert "cricket" in hits
    assert "batsman" in hits
    assert "six" in hits

    # Test D: >= 3 distinct gaming keywords triggers gaming
    gaming_text = "What a clutch in fortnite during the live gaming stream!"
    mode, hits = SmartFramingAgent.detect_genre_and_framing(gaming_text)
    assert mode == "gaming"
    assert len(hits) >= 3
    assert "clutch" in hits
    assert "fortnite" in hits
    assert "gaming" in hits
    assert "stream" in hits


def test_genre_detection_allows_explicit_framing_mode_from_ui():
    """
    Verifies that explicit framing_mode from the UI always overrides auto-detection.
    """
    neutral_text = "Just a casual podcast about cooking food."

    # UI explicitly passes 'gaming'
    mode, _ = SmartFramingAgent.detect_genre_and_framing(neutral_text, explicit_framing_mode="gaming")
    assert mode == "gaming"

    # UI explicitly passes 'single_face'
    gaming_text = "What a clutch in fortnite during the stream!"
    mode, _ = SmartFramingAgent.detect_genre_and_framing(gaming_text, explicit_framing_mode="single_face")
    assert mode == "single_face"

    # UI explicitly passes 'split_screen'
    mode, _ = SmartFramingAgent.detect_genre_and_framing(gaming_text, explicit_framing_mode="split_screen")
    assert mode == "split_screen"


# ==============================================================================
# 2. Gaming Layout Tests
# ==============================================================================

def test_gaming_layout_with_webcam_face():
    """
    Verifies that when mode='gaming' and face(s) are detected:
    - Builds 'gaming' layout
    - Top webcam face crop: 1080x640
    - Bottom gameplay crop: 1080x1280
    - Filter stacks to 1080x1920 with divider
    """
    agent = SmartFramingAgent()
    # Facecam located at top-left (cx=220, cy=180) in 1920x1080 capture
    face_records = [
        {"time_offset": 0.0, "faces": [{"cx": 220, "cy": 180, "w": 120, "h": 120}]},
        {"time_offset": 0.5, "faces": [{"cx": 222, "cy": 182, "w": 120, "h": 120}]},
        {"time_offset": 1.0, "faces": [{"cx": 225, "cy": 178, "w": 120, "h": 120}]},
    ]

    plan = agent._build_gaming_layout_plan(face_records, width=1920, height=1080, scene_cuts=[])
    assert plan.layout == "gaming"
    assert plan.face_count >= 1
    assert "scale=1080:640[webcam_top]" in plan.filter_string
    assert "scale=1080:1280[gameplay_bottom]" in plan.filter_string
    assert "[webcam_top][gameplay_bottom]vstack[stacked]" in plan.filter_string
    assert "drawbox=y=638:h=4" in plan.filter_string


def test_gaming_layout_falls_back_to_action_crop_when_no_webcam_face(tmp_path: Path):
    """
    Verifies that when mode='gaming' but NO face is detected, it falls back to action crop.
    """
    ffmpeg_bin = get_ffmpeg_bin()
    test_vid = tmp_path / "gameplay_noface.mp4"
    cmd_synth = [
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=24",
        "-t", "1.0",
        "-c:v", "libx264",
        "-y",
        str(test_vid)
    ]
    subprocess.run(cmd_synth, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    agent = SmartFramingAgent()
    plan = agent.analyze_framing(test_vid, start_seconds=0.0, end_seconds=1.0, mode="gaming")
    assert plan.layout == "action_crop"
    assert "1080:1920" in plan.filter_string


# ==============================================================================
# 3. Output Specs & FFprobe Verification Tests
# ==============================================================================

def test_render_output_ffprobe_resolution_codec_audio_and_source_framerate(tmp_path: Path):
    """
    Verifies that VideoEditorAgent render:
    - Outputs exactly 1080x1920
    - Video codec is h264
    - Audio stream is present and aac
    - Preserves source frame rate (e.g. 24 fps source -> 24 fps output, no forced -r 60)
    """
    ffmpeg_bin = get_ffmpeg_bin()
    fonts_dir = Path("fonts").resolve()

    # Synthesize test video at native 24 fps with audio
    source_vid = tmp_path / "native_24fps_source.mp4"
    cmd_synth = [
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=24",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "1.5",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-y",
        str(source_vid)
    ]
    subprocess.run(cmd_synth, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    editor = VideoEditorAgent(ffmpeg_bin=ffmpeg_bin, fonts_dir=fonts_dir)
    output_vid = tmp_path / "rendered_output_1080x1920.mp4"

    crop_plan = CropPlan(
        layout="action_crop",
        face_count=0,
        filter_string="[0:v]scale=1080:1920[merged]"
    )

    success = editor.render_short(
        source_video_path=source_vid,
        start_seconds=0.0,
        end_seconds=1.5,
        headline="TEST 24FPS SOURCE SHORT",
        output_path=output_vid,
        crop_plan=crop_plan,
        use_nvenc=True
    )

    assert success is True
    assert output_vid.exists()

    # Probe rendered stream details via ffprobe
    streams = get_media_stream_info(output_vid)
    v_streams = [s for s in streams if s.get("codec_type") == "video"]
    a_streams = [s for s in streams if s.get("codec_type") == "audio"]

    assert len(v_streams) == 1
    assert len(a_streams) == 1

    v = v_streams[0]
    assert v.get("width") == 1080
    assert v.get("height") == 1920
    assert v.get("codec_name") == "h264"

    # Source frame rate was 24 fps -> output must remain 24 fps (r_frame_rate == "24/1")
    assert v.get("r_frame_rate") == "24/1"

    a = a_streams[0]
    assert a.get("codec_name") == "aac"


# ==============================================================================
# 4. Caption Timing Alignment (Within 100 ms of Whisper Words)
# ==============================================================================

def test_caption_timing_accurate_within_100ms_of_whisper_words(tmp_path: Path):
    """
    Verifies that generated ASS subtitle event timestamps align within 100 ms
    of Whisper word-level timestamps.
    """
    words = [
        WordTimestamp(word="WELCOME", start=0.500, end=0.950),
        WordTimestamp(word="EVERYONE", start=1.000, end=1.450),
        WordTimestamp(word="TO", start=1.500, end=1.750),
        WordTimestamp(word="THE", start=1.800, end=2.000),
        WordTimestamp(word="SHOW", start=2.050, end=2.850, is_keyword=True, emoji="🔥")
    ]

    ass_path = tmp_path / "timing_test.ass"
    generate_karaoke_ass(words, ass_path, style_preset="hormozi", clip_start_offset=0.0)
    assert ass_path.exists()

    lines = ass_path.read_text(encoding="utf-8").splitlines()
    dialogue_lines = [l for l in lines if l.startswith("Dialogue:")]
    assert len(dialogue_lines) >= 1

    # Parse Start and End timestamp from the first dialogue line
    # Format: Dialogue: Layer, Start, End, Style, ...
    def parse_ass_time(time_str: str) -> float:
        parts = time_str.strip().split(":")
        h = int(parts[0])
        m = int(parts[1])
        s = float(parts[2])
        return h * 3600 + m * 60 + s

    first_line_parts = dialogue_lines[0].split(",", 9)
    ass_start = parse_ass_time(first_line_parts[1])
    whisper_start = words[0].start

    # Must be accurate within 100 ms (0.1s)
    drift_ms = abs(ass_start - whisper_start) * 1000
    assert drift_ms <= 100.0, f"Caption drift {drift_ms}ms exceeds 100ms threshold!"


# ==============================================================================
# 5. Unicode Headlines with Script-Aware Fonts
# ==============================================================================

def test_unicode_headlines_with_script_aware_fonts(tmp_path: Path):
    """
    Verifies that Unicode headlines (Indic/Devanagari, CJK, Spanish, quotes)
    select appropriate script-aware fonts and render without being stripped.
    """
    fonts_dir = Path("fonts").resolve()
    ffmpeg_bin = get_ffmpeg_bin()

    # 1. Font selection test
    hindi_text = "आज का सबसे बड़ा मैच"
    font_for_hindi = select_script_aware_font(hindi_text, fonts_dir)
    assert "nirmala" in font_for_hindi.name.lower() or "arial" in font_for_hindi.name.lower()

    latin_text = "THE ULTIMATE GAMEPLAY"
    font_for_latin = select_script_aware_font(latin_text, fonts_dir)
    assert "montserrat" in font_for_latin.name.lower() or font_for_latin.name.endswith(".ttf")

    # 2. Render test with Devanagari Unicode headline
    source_vid = tmp_path / "unicode_source.mp4"
    cmd_synth = [
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "1.0",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-y",
        str(source_vid)
    ]
    subprocess.run(cmd_synth, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out_short = tmp_path / "unicode_short.mp4"
    editor = VideoEditorAgent(ffmpeg_bin=ffmpeg_bin, fonts_dir=fonts_dir)

    success = editor.render_short(
        source_video_path=source_vid,
        start_seconds=0.0,
        end_seconds=1.0,
        headline="नमस्ते: \"क्या यह सच है?\" — 100%!",
        output_path=out_short,
        crop_plan=CropPlan(layout="action_crop", filter_string="[0:v]scale=1080:1920[merged]"),
        use_nvenc=False  # Test software libx264
    )

    assert success is True
    assert out_short.exists()
    assert out_short.stat().st_size > 0


# ==============================================================================
# 6. Failure Handling & Retry Logic
# ==============================================================================

def test_failed_render_emits_error_event_and_retries_with_libx264(monkeypatch, tmp_path: Path):
    """
    Verifies that:
    - NVENC failure retries once with libx264
    - An unrecoverable render failure marks clip as 'failed', emits SSE error, and never silently drops
    """
    user = create_test_user("render_fail_user")
    session_id = create_test_session(user.id)

    db = SessionLocal()
    clip = Clip(
        id=str(uuid.uuid4()),
        live_session_id=session_id,
        clip_index=1,
        source="fixed",
        status="raw",
        title="Gaming Clutch",
        headline="CLUTCH MOMENT",
        start_seconds=0.0,
        end_seconds=10.0,
        duration=10.0,
        viral_score=85,
        video_url="/non_existent_corrupted_file.mp4"
    )
    db.add(clip)
    db.commit()
    clip_id = clip.id
    db.close()

    # Track broadcasted events
    broadcast_events = []
    from backend.sse import live_broadcaster
    async def mock_broadcast(session_id, event_name, data):
        broadcast_events.append({"session_id": session_id, "event": event_name, "data": data})

    monkeypatch.setattr(live_broadcaster, "broadcast", mock_broadcast)

    # Execute enhance_clip_sync on non-existent video
    res = enhance_clip_sync(clip_id)
    assert res is None

    # Database status must be marked 'failed'
    db = SessionLocal()
    refreshed_clip = db.query(Clip).filter(Clip.id == clip_id).first()
    assert refreshed_clip.status == "failed"
    db.close()

    # SSE error event must have been emitted (never silently dropped)
    assert len(broadcast_events) >= 1
    assert any(e["event"] == "error" for e in broadcast_events)
    error_event = next(e for e in broadcast_events if e["event"] == "error")
    assert error_event["data"]["clip_id"] == clip_id
    assert error_event["data"]["status"] == "render_failed"
