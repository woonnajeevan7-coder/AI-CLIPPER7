"""
Phase 4 Verification Tests: Motion and Polish
Tests dynamic punch-in zooms, keyword/emoji tagging, silence trimming, and audio ducking.
"""

import subprocess
from pathlib import Path
import pytest

from schema import WordTimestamp
from agents.polish import KeywordEmojiTagger, PunchInPlanner, AudioPolisher
from captions import generate_karaoke_ass
from agents.editor import VideoEditorAgent
from ffmpeg_utils import get_ffmpeg_bin


def test_keyword_emoji_tagger():
    words = [
        WordTimestamp(word="This", start=0.0, end=0.4),
        WordTimestamp(word="secret", start=0.4, end=0.8),
        WordTimestamp(word="will", start=0.8, end=1.0),
        WordTimestamp(word="make", start=1.0, end=1.2),
        WordTimestamp(word="money", start=3.5, end=4.0),
    ]

    tagged = KeywordEmojiTagger.tag_words(words)
    assert len(tagged) == 5
    
    # "secret" should have emoji and is_keyword=True
    w_secret = tagged[1]
    assert w_secret.is_keyword is True
    assert w_secret.emoji == "💡"

    # "money" at 3.5s (>2.5s apart) should also have emoji
    w_money = tagged[4]
    assert w_money.is_keyword is True
    assert w_money.emoji in ["💰", "💵"]


def test_punch_in_planner_and_filter():
    words = [
        WordTimestamp(word="Hook", start=0.2, end=0.6, is_keyword=True),
        WordTimestamp(word="sentence", start=0.6, end=1.0),
        WordTimestamp(word="Big", start=5.0, end=5.4, is_keyword=True),
    ]
    intervals = PunchInPlanner.build_punch_in_intervals(words, clip_duration=10.0, zoom_duration=1.5, min_gap=2.5)
    assert len(intervals) >= 2
    # First interval must be opening hook
    assert intervals[0][0] == 0.0

    zoom_filter = PunchInPlanner.generate_zoom_filter(intervals, zoom_factor=1.14)
    assert "crop=" in zoom_filter
    assert "between(t" in zoom_filter
    assert "scale=1080:1920" in zoom_filter


def test_audio_polisher_filters():
    trim_filter = AudioPolisher.get_silence_trim_filter()
    assert "silenceremove" in trim_filter
    duck_filter = AudioPolisher.build_ducking_filter(music_volume=0.15)
    assert "volume=0.15" in duck_filter
    assert "amix" in duck_filter


def test_motion_polish_ffmpeg_render_pipeline(tmp_path: Path):
    ffmpeg_bin = get_ffmpeg_bin()
    fonts_dir = Path("fonts").resolve()

    # Synthesize test video (2.0s)
    test_vid = tmp_path / "raw_motion.mp4"
    cmd_synth = [
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "2.0",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-y",
        str(test_vid)
    ]
    subprocess.run(cmd_synth, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Words with keyword & emoji
    words = [
        WordTimestamp(word="UNLEASH", start=0.1, end=0.6, is_keyword=True, emoji="🔥"),
        WordTimestamp(word="THE", start=0.6, end=0.9),
        WordTimestamp(word="SECRET", start=0.9, end=1.6, is_keyword=True, emoji="💡"),
    ]
    ass_file = tmp_path / "motion_subs.ass"
    generate_karaoke_ass(words, ass_file, style_preset="hormozi")

    # Build punch-in zoom
    intervals = PunchInPlanner.build_punch_in_intervals(words, clip_duration=2.0)
    zoom_filter = PunchInPlanner.generate_zoom_filter(intervals, zoom_factor=1.14)

    editor = VideoEditorAgent(ffmpeg_bin=ffmpeg_bin, fonts_dir=fonts_dir)
    out_short = tmp_path / "polished_short.mp4"

    success = editor.render_short(
        source_video_path=test_vid,
        start_seconds=0.0,
        end_seconds=2.0,
        headline="PUNCH IN & EMOJIS",
        output_path=out_short,
        ass_subtitle_path=ass_file,
        punch_in_filter=zoom_filter,
        silence_trim=False,
        use_nvenc=True
    )

    assert success is True
    assert out_short.exists()

    # Verify properties with ffprobe
    cmd_probe = [str(ffmpeg_bin), "-i", str(out_short)]
    res = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert "1080x1920" in res.stderr
    assert "yuv420p" in res.stderr
    assert "Audio: aac" in res.stderr
