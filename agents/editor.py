"""
Video Editor Agent
Composites 9:16 vertical shorts using FFmpeg with smart face tracking, split-screen layouts,
ambient blur fallbacks, viral headline banners, karaoke ASS subtitles, and EBU R128 loudness normalization.
"""

import re
import subprocess
from pathlib import Path
from typing import Optional

from schema import CropPlan


class VideoEditorAgent:
    """Agent responsible for aspect-ratio transformation, typography, subtitle burn-in, and video rendering."""

    def __init__(self, ffmpeg_bin: Path, fonts_dir: Path):
        self.ffmpeg_bin = ffmpeg_bin
        self.fonts_dir = fonts_dir

    def render_short(
        self,
        source_video_path: Path,
        start_seconds: float,
        end_seconds: float,
        headline: str,
        output_path: Path,
        ass_subtitle_path: Optional[Path] = None,
        crop_plan: Optional[CropPlan] = None,
        use_nvenc: bool = True
    ) -> bool:
        """
        Renders a vertical 9:16 short (1080x1920) conforming to TikTok/Reels/Shorts specs:
        - Layout: Smart single face crop, 2-speaker split-screen, or ambient blur fallback
        - Resolution: 1080x1920
        - H.264 video with yuv420p pixel format
        - AAC audio at 192k normalized to -14 LUFS (EBU R128)
        - +faststart flag for instant streaming
        - Burned-in word-by-word karaoke ASS subtitles with collision-free safe margins
        """
        duration = end_seconds - start_seconds
        if duration <= 0:
            duration = 30.0

        clean_headline = re.sub(r"[^A-Za-z0-9 \-!?]", "", headline).upper()
        if not clean_headline:
            clean_headline = "VIRAL CLIP"

        # Escaped font path for drawtext (C\:/... on Windows)
        font_arg = ""
        font_file = (self.fonts_dir / "Montserrat-Bold.ttf").resolve()
        if font_file.exists():
            escaped_font = str(font_file.as_posix()).replace(":", r"\:")
            font_arg = f"fontfile='{escaped_font}':"

        # Build filtergraph
        filter_chain = []

        if crop_plan and crop_plan.filter_string:
            # Split-screen or smart single-face crop produces [merged]
            for part in crop_plan.filter_string.split(";"):
                part = part.strip()
                if part:
                    filter_chain.append(part)
        else:
            # Ambient blur background + centered video
            filter_chain.extend([
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg]",
                "[0:v]scale=1080:-2[fg]",
                "[bg][fg]overlay=(W-w)/2:(H-h)/2[merged]"
            ])

        # Headline banner
        filter_chain.append(
            f"[merged]drawtext={font_arg}text='{clean_headline}':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.75:boxborderw=14:x=(w-text_w)/2:y=240[with_headline]"
        )
        last_v_tag = "[with_headline]"

        # Burn in ASS subtitles if provided
        if ass_subtitle_path and Path(ass_subtitle_path).exists():
            escaped_ass = str(Path(ass_subtitle_path).resolve().as_posix()).replace(":", r"\:")
            escaped_fonts_dir = str(self.fonts_dir.resolve().as_posix()).replace(":", r"\:")
            filter_chain.append(
                f"{last_v_tag}subtitles='{escaped_ass}':fontsdir='{escaped_fonts_dir}'[v]"
            )
            last_v_tag = "[v]"
        else:
            filter_chain[-1] = filter_chain[-1].replace("[with_headline]", "[v]")
            last_v_tag = "[v]"

        filter_complex_str = ";".join(filter_chain)

        # Video encoder selection (NVENC hardware acceleration with libx264 fallback)
        vcodec_args = (
            ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"]
            if use_nvenc
            else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]
        )

        # Loudness normalization (-14 LUFS, LRA 11, TP -1.5)
        audio_filter = "loudnorm=I=-14:LRA=11:TP=-1.5"

        cmd = [
            str(self.ffmpeg_bin),
            "-ss", f"{start_seconds:.3f}",
            "-i", str(source_video_path),
            "-t", f"{duration:.3f}",
            "-filter_complex", filter_complex_str,
            "-map", last_v_tag,
            "-map", "0:a?",
            *vcodec_args,
            "-pix_fmt", "yuv420p",
            "-af", audio_filter,
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-movflags", "+faststart",
            "-y",
            str(output_path)
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            if use_nvenc:
                print(f"[VideoEditorAgent] NVENC failed ({e.stderr[-200:] if e.stderr else ''}), falling back to libx264...")
                return self.render_short(
                    source_video_path=source_video_path,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    headline=headline,
                    output_path=output_path,
                    ass_subtitle_path=ass_subtitle_path,
                    crop_plan=crop_plan,
                    use_nvenc=False
                )
            print(f"[VideoEditorAgent] FFmpeg error: {e.stderr}")
            return False
