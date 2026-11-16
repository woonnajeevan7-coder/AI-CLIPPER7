"""
Phase 1 Verification Tests: Captions & Audio Polish
Tests word-level ASS generation, karaoke tags, safe area, and FFmpeg output properties.
"""

import subprocess
import json
from pathlib import Path
import pytest

from schema import WordTimestamp
from captions import format_ass_timestamp, group_words_into_chunks, generate_karaoke_ass, STYLE_PRESETS
from agents.editor import VideoEditorAgent


def test_format_ass_timestamp():
    assert format_ass_timestamp(0.0) == "0:00:00.00"
    assert format_ass_timestamp(65.45) == "0:01:05.45"
    assert format_ass_timestamp(3661.12) == "1:01:01.12"


def test_group_words_into_chunks():
    words = [
        WordTimestamp(word="This", start=0.0, end=0.3),
        WordTimestamp(word="is", start=0.3, end=0.5),
        WordTimestamp(word="a", start=0.5, end=0.7),
        WordTimestamp(word="viral", start=0.7, end=1.0),
        WordTimestamp(word="moment", start=1.1, end=1.5),  # 5th word -> new chunk
    ]
    chunks = group_words_into_chunks(words, max_words_per_chunk=4)
    assert len(chunks) == 2
    assert len(chunks[0]) == 4
    assert len(chunks[1]) == 1
    assert chunks[1][0].word == "moment"


def test_generate_karaoke_ass(tmp_path: Path):
    words = [
        WordTimestamp(word="WELCOME", start=10.0, end=10.4),
        WordTimestamp(word="TO", start=10.4, end=10.6),
        WordTimestamp(word="THE", start=10.6, end=10.8),
        WordTimestamp(word="FUTURE", start=10.8, end=11.5),
    ]
    ass_path = tmp_path / "test_captions.ass"
    out = generate_karaoke_ass(
        words=words,
        output_ass_path=ass_path,
        style_preset="hormozi",
        clip_start_offset=10.0
    )
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "MarginV, Encoding" in content
    assert "460" in content  # safe-area vertical margin
    assert "Dialogue:" in content
    assert "WELCOME" in content
    assert r"{\c" in content  # karaoke color swap tag


def test_render_short_ffmpeg_pipeline(tmp_path: Path):
    ffmpeg_bin = Path("ffmpeg.exe").resolve()
    fonts_dir = Path("fonts").resolve()
    assert ffmpeg_bin.exists()

    # 1. Synthesize a 2-second test source video with audio
    source_vid = tmp_path / "raw_input.mp4"
    cmd_synth = [
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "2",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-y",
        str(source_vid)
    ]
    subprocess.run(cmd_synth, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert source_vid.exists()

    # 2. Generate karaoke ASS
    words = [
        WordTimestamp(word="AI", start=0.2, end=0.6),
        WordTimestamp(word="CLIPPER", start=0.6, end=1.2),
        WordTimestamp(word="PRO", start=1.2, end=1.8),
    ]
    ass_file = tmp_path / "karaoke.ass"
    generate_karaoke_ass(words, ass_file, style_preset="cyber_cyan")

    # 3. Render short via VideoEditorAgent
    editor = VideoEditorAgent(ffmpeg_bin=ffmpeg_bin, fonts_dir=fonts_dir)
    output_mp4 = tmp_path / "rendered_short.mp4"

    success = editor.render_short(
        source_video_path=source_vid,
        start_seconds=0.0,
        end_seconds=2.0,
        headline="AI CLIPPER TEST",
        output_path=output_mp4,
        ass_subtitle_path=ass_file,
        use_nvenc=True
    )
    assert success is True
    assert output_mp4.exists()

    # 4. Probe output video properties via ffprobe/ffmpeg
    cmd_probe = [
        str(ffmpeg_bin),
        "-i", str(output_mp4)
    ]
    res = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    probe_output = res.stderr

    # Check 1080x1920
    assert "1080x1920" in probe_output
    # Check yuv420p
    assert "yuv420p" in probe_output
    # Check 60 FPS output
    assert "60 fps" in probe_output or "60 tbr" in probe_output
    # Check AAC audio stream
    assert "Audio: aac" in probe_output


def test_video_editor_nvenc_check_and_probe():
    ffmpeg_bin = Path("ffmpeg.exe").resolve()
    fonts_dir = Path("fonts").resolve()
    editor = VideoEditorAgent(ffmpeg_bin=ffmpeg_bin, fonts_dir=fonts_dir)
    nvenc_ok = editor.check_nvenc_available()
    assert isinstance(nvenc_ok, bool)
    assert nvenc_ok is True


def test_transcriber_chunking_offset_accumulation(monkeypatch, tmp_path: Path):
    from agents.transcriber import TranscriberAgent
    agent = TranscriberAgent(ffmpeg_bin=Path("ffmpeg.exe"), temp_dir=tmp_path)

    big_audio = tmp_path / "big_audio.mp3"
    with open(big_audio, "wb") as f:
        f.seek(26 * 1024 * 1024)
        f.write(b"\0")

    assert big_audio.stat().st_size > 25 * 1024 * 1024

    chunk0 = tmp_path / "big_audio_chunk_000.mp3"
    chunk1 = tmp_path / "big_audio_chunk_001.mp3"
    chunk0.write_bytes(b"dummy audio 0")
    chunk1.write_bytes(b"dummy audio 1")

    def mock_subprocess_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    def mock_transcribe_single(audio_file, api_key, client):
        return [
            WordTimestamp(word="hello", start=1.0, end=2.0),
            WordTimestamp(word="world", start=2.5, end=3.5)
        ]

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
    monkeypatch.setattr(agent, "_transcribe_single_audio_file", mock_transcribe_single)

    words = agent.transcribe_with_groq_whisper(big_audio, api_key="dummy_key")
    assert len(words) == 4
    # Chunk 0: t_offset = 0.0s
    assert words[0].word == "hello" and words[0].start == 1.0 and words[0].end == 2.0
    assert words[1].word == "world" and words[1].start == 2.5 and words[1].end == 3.5
    # Chunk 1: t_offset = 600.0s
    assert words[2].word == "hello" and words[2].start == 601.0 and words[2].end == 602.0
    assert words[3].word == "world" and words[3].start == 602.5 and words[3].end == 603.5
