"""
Video Editor Agent
Composites 9:16 vertical shorts using FFmpeg with smart face tracking, split-screen layouts,
punch-in zooms, viral headline banners, karaoke ASS subtitles with keyword emojis,
silence trimming, optional background music with ducking, and EBU R128 loudness normalization.
"""

import re
import subprocess
from pathlib import Path
from typing import Optional

from schema import CropPlan


class VideoEditorAgent:
    """Agent responsible for aspect-ratio transformation, typography, subtitle burn-in, motion, and rendering."""

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
        punch_in_filter: Optional[str] = None,
        silence_trim: bool = False,
        background_music_path: Optional[Path] = None,
        use_nvenc: bool = True
    ) -> bool:
        """
        Renders a vertical 9:16 short (1080x1920) conforming to TikTok/Reels/Shorts specs:
        - Layout: Smart single face crop, 2-speaker split-screen, or ambient blur fallback
        - Motion: Dynamic punch-in zoom scaling at emphasis intervals
        - Subtitles: Word-by-word karaoke ASS subtitles with highlighted keywords and emojis
        - Audio: Silence trimming, background music ducking, and EBU R128 (-14 LUFS) loudnorm
        - Hardware: NVENC RTX GPU acceleration with libx264 software fallback
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
            for part in crop_plan.filter_string.split(";"):
                part = part.strip()
                if part:
                    filter_chain.append(part)
        else:
            filter_chain.extend([
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg]",
                "[0:v]scale=1080:-2[fg]",
                "[bg][fg]overlay=(W-w)/2:(H-h)/2[merged]"
            ])

        last_v_tag = "[merged]"

        # Punch-in zooms
        if punch_in_filter:
            filter_chain.append(f"{last_v_tag}{punch_in_filter}[punched]")
            last_v_tag = "[punched]"

        # Headline banner
        filter_chain.append(
            f"{last_v_tag}drawtext={font_arg}text='{clean_headline}':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.75:boxborderw=14:x=(w-text_w)/2:y=240[with_headline]"
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

        # Audio filter construction
        audio_filters = []
        if silence_trim:
            audio_filters.append("silenceremove=stop_periods=-1:stop_duration=0.45:stop_threshold=-40dB")
        audio_filters.append("loudnorm=I=-14:LRA=11:TP=-1.5")
        audio_filter_str = ",".join(audio_filters)

        cmd = [
            str(self.ffmpeg_bin),
            "-ss", f"{start_seconds:.3f}",
            "-i", str(source_video_path),
            "-t", f"{duration:.3f}",
        ]

        # Background music input and mixing if provided
        has_bgm = background_music_path and Path(background_music_path).exists()
        if has_bgm:
            cmd.extend(["-stream_loop", "-1", "-i", str(background_music_path)])
            bgm_complex = f";[1:a]volume=0.10[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2,{audio_filter_str}[aout]"
            filter_complex_str += bgm_complex
            audio_map = "[aout]"
        else:
            audio_map = "0:a?"

        cmd.extend([
            "-filter_complex", filter_complex_str,
            "-map", last_v_tag,
            "-map", audio_map,
            *vcodec_args,
            "-pix_fmt", "yuv420p",
        ])

        if not has_bgm:
            cmd.extend(["-af", audio_filter_str])

        cmd.extend([
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-movflags", "+faststart",
            "-y",
            str(output_path)
        ])

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
                    punch_in_filter=punch_in_filter,
                    silence_trim=silence_trim,
                    background_music_path=background_music_path,
                    use_nvenc=False
                )
            print(f"[VideoEditorAgent] FFmpeg error: {e.stderr}")
            return False
