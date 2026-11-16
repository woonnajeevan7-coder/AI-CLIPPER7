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
from typing import Optional, Dict, List, Tuple

from schema import CropPlan


class VideoEditorAgent:
    """Agent responsible for aspect-ratio transformation, typography, subtitle burn-in, motion, and rendering."""

    def __init__(self, ffmpeg_bin: Path, fonts_dir: Path):
        self.ffmpeg_bin = ffmpeg_bin
        self.fonts_dir = fonts_dir
        self._nvenc_available: Optional[bool] = None
        self.last_measured_loudness: Optional[Dict[str, float]] = None

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

    def detect_silence_intervals(
        self,
        source_video_path: Path,
        start_seconds: float,
        duration: float,
        noise_threshold: str = "-40dB",
        min_silence_duration: float = 0.45
    ) -> List[Tuple[float, float]]:
        """
        Detects silent intervals within the clip using FFmpeg silencedetect.
        Returns list of (rel_start, rel_end) tuples relative to start_seconds.
        """
        try:
            cmd = [
                str(self.ffmpeg_bin),
                "-ss", f"{start_seconds:.3f}",
                "-i", str(source_video_path),
                "-t", f"{duration:.3f}",
                "-vn",
                "-af", f"silencedetect=noise={noise_threshold}:d={min_silence_duration}",
                "-f", "null",
                "-"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = res.stderr

            intervals: List[Tuple[float, float]] = []
            cur_start = None
            for line in output.splitlines():
                if "silence_start:" in line:
                    m = re.search(r"silence_start:\s*([0-9.]+)", line)
                    if m:
                        cur_start = float(m.group(1))
                elif "silence_end:" in line and cur_start is not None:
                    m = re.search(r"silence_end:\s*([0-9.]+)", line)
                    if m:
                        end = float(m.group(1))
                        if end > cur_start:
                            intervals.append((round(cur_start, 3), round(end, 3)))
                    cur_start = None
            return intervals
        except Exception as e:
            print(f"[VideoEditorAgent] Silence detect notice: {e}")
            return []

    def adjust_ass_for_silence_cuts(
        self,
        ass_path: Path,
        intervals: List[Tuple[float, float]],
        out_ass_path: Path
    ) -> Path:
        """
        Adjusts ASS dialogue line timestamps backwards by preceding excised silence durations
        so captions remain frame-accurately synchronized with trimmed audio and video.
        """
        try:
            from captions import format_ass_timestamp
            lines = ass_path.read_text(encoding="utf-8").splitlines()
            out_lines = []

            def parse_t(ts_str: str) -> float:
                parts = ts_str.strip().split(":")
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

            def shift_t(t: float) -> float:
                shift = 0.0
                for s_start, s_end in intervals:
                    dur = s_end - s_start
                    if t >= s_end:
                        shift += dur
                    elif s_start <= t < s_end:
                        shift += (t - s_start)
                return max(0.0, t - shift)

            for line in lines:
                if line.startswith("Dialogue:"):
                    parts = line.split(",", 9)
                    if len(parts) == 10:
                        s_t = shift_t(parse_t(parts[1]))
                        e_t = shift_t(parse_t(parts[2]))
                        parts[1] = format_ass_timestamp(s_t)
                        parts[2] = format_ass_timestamp(e_t)
                        line = ",".join(parts)
                out_lines.append(line)

            out_ass_path.write_text("\n".join(out_lines), encoding="utf-8")
            return out_ass_path
        except Exception as e:
            print(f"[VideoEditorAgent] Error adjusting ASS for silence cuts: {e}")
            return ass_path

    def measure_loudness(self, media_path: Path) -> Dict[str, float]:
        """
        Measures integrated loudness (LUFS), True Peak (dBTP), and Loudness Range (LRA)
        of the rendered output media using FFmpeg EBU R128 analysis.
        """
        try:
            cmd = [
                str(self.ffmpeg_bin),
                "-i", str(media_path),
                "-vn",
                "-af", "ebur128=metadata=1",
                "-f", "null",
                "-"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = res.stderr

            i_match = re.search(r"Integrated loudness:\s*I:\s*([-\d.]+)\s*LUFS", output)
            if not i_match:
                i_match = re.search(r"I:\s*([-\d.]+)\s*LUFS", output)
            tp_match = re.search(r"True peak:\s*Peak:\s*([-\d.]+)\s*dBFS", output)
            if not tp_match:
                tp_match = re.search(r"Peak:\s*([-\d.]+)\s*dBFS", output)
            lra_match = re.search(r"Loudness range:\s*LRA:\s*([-\d.]+)\s*LU", output)
            if not lra_match:
                lra_match = re.search(r"LRA:\s*([-\d.]+)\s*LU", output)

            return {
                "integrated_lufs": float(i_match.group(1)) if i_match else -14.0,
                "true_peak_db": float(tp_match.group(1)) if tp_match else -1.5,
                "lra": float(lra_match.group(1)) if lra_match else 11.0,
            }
        except Exception as e:
            print(f"[VideoEditorAgent] Error measuring post-mix loudness: {e}")
            return {"integrated_lufs": -14.0, "true_peak_db": -1.5, "lra": 11.0}

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

        # Synchronized silence trimming across video, audio, and subtitles to prevent desync
        silence_intervals: List[Tuple[float, float]] = []
        effective_ass_path = ass_subtitle_path
        temp_adjusted_ass: Optional[Path] = None

        if silence_trim:
            silence_intervals = self.detect_silence_intervals(source_video_path, start_seconds, duration)
            if silence_intervals:
                v_cond = "+".join(f"between(t\\,{s:.2f}\\,{e:.2f})" for s, e in silence_intervals)
                filter_chain.append(f"{last_v_tag}select='not({v_cond})',setpts=N/FRAME_RATE/TB[v_synced]")
                last_v_tag = "[v_synced]"

                if ass_subtitle_path and Path(ass_subtitle_path).exists():
                    temp_adjusted_ass = Path(ass_subtitle_path).with_suffix(".synced.ass")
                    effective_ass_path = self.adjust_ass_for_silence_cuts(
                        Path(ass_subtitle_path), silence_intervals, temp_adjusted_ass
                    )

        # Punch-in zooms
        if punch_in_filter:
            filter_chain.append(f"{last_v_tag}{punch_in_filter}[punched]")
            last_v_tag = "[punched]"

        # Headline banner
        has_subtitles = bool(effective_ass_path and Path(effective_ass_path).exists())
        headline_out_tag = "[with_headline]" if has_subtitles else "[v]"
        filter_chain.append(
            f"{last_v_tag}drawtext={font_arg}text='{clean_headline}':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.75:boxborderw=14:x=(w-text_w)/2:y=240{headline_out_tag}"
        )
        last_v_tag = headline_out_tag

        # Burn in ASS subtitles if provided
        if has_subtitles:
            escaped_ass = str(Path(effective_ass_path).resolve().as_posix()).replace(":", r"\:")
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

        # Background music input with real sidechaincompress ducking
        has_bgm = background_music_path and Path(background_music_path).exists()

        if silence_intervals:
            a_cond = "+".join(f"between(t\\,{s:.2f}\\,{e:.2f})" for s, e in silence_intervals)
            sync_a_filter = f"[0:a]aselect='not({a_cond})',asetpts=N/SR/TB[voice_cut]"
            filter_complex_str += f";{sync_a_filter}"
            voice_source_tag = "[voice_cut]"
        else:
            voice_source_tag = "[0:a]"

        if has_bgm:
            cmd.extend(["-stream_loop", "-1", "-i", str(background_music_path)])
            bgm_complex = (
                f";[1:a]volume=0.25[bgm_in];"
                f"{voice_source_tag}asplit=2[voice_main][voice_trigger];"
                f"[bgm_in][voice_trigger]sidechaincompress=threshold=0.08:ratio=4:attack=20:release=250[ducked_bgm];"
                f"[voice_main][ducked_bgm]amix=inputs=2:duration=first:weights=1.0 0.8,{audio_filter_str}[aout]"
            )
            filter_complex_str += bgm_complex
            audio_map = "[aout]"
        elif silence_intervals:
            filter_complex_str += f";{voice_source_tag}{audio_filter_str}[aout]"
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

        if not has_bgm and not silence_intervals:
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
            if temp_adjusted_ass and temp_adjusted_ass.exists():
                try:
                    temp_adjusted_ass.unlink()
                except Exception:
                    pass
            # Measure loudness post-mixing
            self.last_measured_loudness = self.measure_loudness(output_path)
            return True
        except subprocess.CalledProcessError as e:
            if temp_adjusted_ass and temp_adjusted_ass.exists():
                try:
                    temp_adjusted_ass.unlink()
                except Exception:
                    pass
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
            print(f"[VideoEditorAgent] FFmpeg error: {e.stderr}")
            return False
