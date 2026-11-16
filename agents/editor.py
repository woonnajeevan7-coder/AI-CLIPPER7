"""
Video Editor Agent
Composites 9:16 vertical shorts using FFmpeg with smart face tracking, split-screen layouts,
punch-in zooms, viral headline banners, karaoke ASS subtitles with keyword emojis,
silence trimming, optional background music with ducking, and EBU R128 loudness normalization.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Optional, Dict

from schema import CropPlan


class VideoEditorAgent:
    """Agent responsible for aspect-ratio transformation, typography, subtitle burn-in, motion, and rendering."""

    def __init__(self, ffmpeg_bin: Path, fonts_dir: Path):
        self.ffmpeg_bin = ffmpeg_bin
        self.fonts_dir = fonts_dir
        self._nvenc_available: Optional[bool] = None

    def check_nvenc_available(self) -> bool:
        """Probe and cache whether NVIDIA NVENC hardware acceleration is available."""
        if self._nvenc_available is not None:
            return self._nvenc_available

        try:
            cmd = [
                str(self.ffmpeg_bin),
                "-f", "lavfi",
                "-i", "color=c=black:s=256x256:d=0.04",
                "-c:v", "h264_nvenc",
                "-f", "null",
                "-"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self._nvenc_available = (res.returncode == 0)
        except Exception:
            self._nvenc_available = False

        return self._nvenc_available

    def probe_loudnorm(
        self,
        source_video_path: Path,
        start_seconds: float,
        duration: float
    ) -> Optional[Dict[str, str]]:
        """
        Pass 1: Fast pre-flight loudness probe on source segment.
        Parses JSON block from stderr for input_i, input_tp, input_lra, input_thresh, target_offset.
        """
        try:
            cmd = [
                str(self.ffmpeg_bin),
                "-ss", f"{start_seconds:.3f}",
                "-i", str(source_video_path),
                "-t", f"{duration:.3f}",
                "-vn",
                "-af", "loudnorm=I=-14:LRA=11:TP=-1.5:print_format=json",
                "-f", "null",
                "-"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = res.stderr

            match = re.search(r"\{\s*\"input_i\"[\s\S]*?\}", output)
            if match:
                data = json.loads(match.group(0))
                return {
                    "input_i": str(data.get("input_i", "-14.0")),
                    "input_tp": str(data.get("input_tp", "-1.5")),
                    "input_lra": str(data.get("input_lra", "11.0")),
                    "input_thresh": str(data.get("input_thresh", "-24.0")),
                    "target_offset": str(data.get("target_offset", "0.0")),
                }
        except Exception as e:
            print(f"[VideoEditorAgent] Loudness probe notice: {e}")

        return None

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
        has_subtitles = bool(ass_subtitle_path and Path(ass_subtitle_path).exists())
        headline_out_tag = "[with_headline]" if has_subtitles else "[v]"
        filter_chain.append(
            f"{last_v_tag}drawtext={font_arg}text='{clean_headline}':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.75:boxborderw=14:x=(w-text_w)/2:y=240{headline_out_tag}"
        )
        last_v_tag = headline_out_tag

        # Burn in ASS subtitles if provided
        if has_subtitles:
            escaped_ass = str(Path(ass_subtitle_path).resolve().as_posix()).replace(":", r"\:")
            escaped_fonts_dir = str(self.fonts_dir.resolve().as_posix()).replace(":", r"\:")
            filter_chain.append(
                f"{last_v_tag}subtitles='{escaped_ass}':fontsdir='{escaped_fonts_dir}'[v]"
            )
            last_v_tag = "[v]"

        filter_complex_str = ";".join(filter_chain)

        # Check NVENC hardware availability pre-flight
        if use_nvenc and not self.check_nvenc_available():
            use_nvenc = False

        # Video encoder selection (NVENC hardware acceleration with libx264 fallback)
        vcodec_args = (
            ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"]
            if use_nvenc
            else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]
        )

        # Audio filter construction with Two-Pass EBU R128 loudnorm
        audio_filters = []
        if silence_trim:
            audio_filters.append("silenceremove=stop_periods=-1:stop_duration=0.45:stop_threshold=-40dB")

        measured = self.probe_loudnorm(source_video_path, start_seconds, duration)
        if measured:
            audio_filters.append(
                f"loudnorm=I=-14:LRA=11:TP=-1.5:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:linear=true"
            )
        else:
            audio_filters.append("acompressor=threshold=-21dB:ratio=2.5:attack=15:release=120,loudnorm=I=-14:LRA=11:TP=-1.5")

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
            "-r", "60",
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
