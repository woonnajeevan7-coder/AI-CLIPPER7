"""
Phase 3 Verification Tests: Smart Framing
Tests scene cut detection, face tracking, EMA crop calculation, split-screen layouts, and blur fallback.
"""

import subprocess
from pathlib import Path
import pytest
import numpy as np
import cv2

from schema import CropPlan
from agents.framing import SmartFramingAgent
from agents.editor import VideoEditorAgent


def test_blur_fallback_plan():
    agent = SmartFramingAgent()
    plan = agent._build_blur_fallback_plan(scene_cuts=[2.5])
    assert isinstance(plan, CropPlan)
    assert plan.layout == "blur_fallback"
    assert plan.face_count == 0
    assert "boxblur=25:5" in plan.filter_string
    assert "1080:1920" in plan.filter_string


def test_single_face_plan_ema_smoothing():
    agent = SmartFramingAgent(ema_alpha=0.2)
    # Simulate records with 1 face drifting from x=300 to x=500 in 1280x720 video
    records = [
        {"time_offset": 0.0, "faces": [{"cx": 300, "cy": 360, "w": 100, "h": 100}]},
        {"time_offset": 0.5, "faces": [{"cx": 400, "cy": 360, "w": 100, "h": 100}]},
        {"time_offset": 1.0, "faces": [{"cx": 500, "cy": 360, "w": 100, "h": 100}]},
    ]
    plan = agent._build_single_face_plan(records, width=1280, height=720, scene_cuts=[])
    assert plan.layout == "single_face"
    assert plan.face_count == 1
    assert plan.crop_h == 720
    assert plan.crop_w == int(720 * 9 / 16)  # 405
    assert plan.crop_x is not None
    assert 0 <= plan.crop_x <= (1280 - plan.crop_w)
    assert "crop=" in plan.filter_string
    assert "scale=1080:1920" in plan.filter_string


def test_split_screen_plan():
    agent = SmartFramingAgent()
    records = [
        {
            "time_offset": 0.0,
            "faces": [
                {"cx": 300, "cy": 360, "w": 100, "h": 100},  # Left speaker
                {"cx": 900, "cy": 360, "w": 100, "h": 100}   # Right speaker
            ]
        }
    ]
    plan = agent._build_split_screen_plan(records, width=1280, height=720, scene_cuts=[])
    assert plan.layout == "split_screen"
    assert plan.face_count == 2
    assert "vstack" in plan.filter_string
    assert "scale=1080:960" in plan.filter_string


def test_smart_framing_ffmpeg_render_pipeline(tmp_path: Path):
    ffmpeg_bin = Path("ffmpeg.exe").resolve()
    fonts_dir = Path("fonts").resolve()

    # Synthesize test video
    test_vid = tmp_path / "raw_cam.mp4"
    cmd_synth = [
        str(ffmpeg_bin),
        "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=500:sample_rate=48000",
        "-t", "1.5",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-y",
        str(test_vid)
    ]
    subprocess.run(cmd_synth, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    framing_agent = SmartFramingAgent()
    crop_plan = framing_agent.analyze_framing(test_vid, start_seconds=0.0, end_seconds=1.5)
    assert isinstance(crop_plan, CropPlan)

    # Render with editor using crop_plan
    editor = VideoEditorAgent(ffmpeg_bin=ffmpeg_bin, fonts_dir=fonts_dir)
    out_vid = tmp_path / "framed_short.mp4"
    success = editor.render_short(
        source_video_path=test_vid,
        start_seconds=0.0,
        end_seconds=1.5,
        headline="SMART FRAMING TEST",
        output_path=out_vid,
        crop_plan=crop_plan,
        use_nvenc=True
    )
    assert success is True
    assert out_vid.exists()

    # Probe output resolution & format
    cmd_probe = [str(ffmpeg_bin), "-i", str(out_vid)]
    res = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert "1080x1920" in res.stderr
    assert "yuv420p" in res.stderr
