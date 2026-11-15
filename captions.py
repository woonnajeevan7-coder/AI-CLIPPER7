"""
Advanced Subtitle Engine
Generates ASS subtitles with word-by-word karaoke highlighting, safe-area bounds, and visual style presets.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from schema import WordTimestamp, CaptionSegment


STYLE_PRESETS: Dict[str, Dict[str, Any]] = {
    "hormozi": {
        "name": "Hormozi",
        "font": "Montserrat-Bold",
        "fontsize": 68,
        "primary_color": "&H00FFFFFF",      # Inactive: White (AABBGGRR)
        "highlight_color": "&H0000FFFF",    # Active: Bright Yellow (BGR: 00FFFF)
        "outline_color": "&H00000000",      # Outline: Pure Black
        "back_color": "&H80000000",         # Shadow: Translucent Black
        "bold": 1,
        "outline": 5.0,
        "shadow": 2.0,
        "alignment": 2,                     # Bottom Center
        "margin_v": 460,                    # Safe area above bottom bar (1080x1920)
    },
    "cyber_cyan": {
        "name": "CyberCyan",
        "font": "Montserrat-Bold",
        "fontsize": 66,
        "primary_color": "&H00FFFFFF",      # Inactive: White
        "highlight_color": "&H00FFFF00",    # Active: Neon Cyan (BGR: FFFF00)
        "outline_color": "&H00000000",      # Outline: Pure Black
        "back_color": "&HA0000000",
        "bold": 1,
        "outline": 4.5,
        "shadow": 3.0,
        "alignment": 2,
        "margin_v": 460,
    },
    "emerald_box": {
        "name": "EmeraldBox",
        "font": "Montserrat-Bold",
        "fontsize": 64,
        "primary_color": "&H00D0D0D0",      # Inactive: Silver Gray
        "highlight_color": "&H0000FF7F",    # Active: Spring Green (BGR: 7FFF00)
        "outline_color": "&H00101010",
        "back_color": "&HB0000000",
        "bold": 1,
        "outline": 4.0,
        "shadow": 1.5,
        "alignment": 2,
        "margin_v": 460,
    }
}


def format_ass_timestamp(seconds: float) -> str:
    """Format seconds to ASS timestamp format: H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def group_words_into_chunks(
    words: List[WordTimestamp],
    max_words_per_chunk: int = 4,
    max_pause_seconds: float = 0.5
) -> List[List[WordTimestamp]]:
    """Group continuous words into readable mobile-friendly subtitle screens (3-4 words max)."""
    if not words:
        return []

    chunks: List[List[WordTimestamp]] = []
    current_chunk: List[WordTimestamp] = []

    for word_obj in words:
        if not current_chunk:
            current_chunk.append(word_obj)
            continue

        pause = word_obj.start - current_chunk[-1].end
        if len(current_chunk) >= max_words_per_chunk or pause > max_pause_seconds:
            chunks.append(current_chunk)
            current_chunk = [word_obj]
        else:
            current_chunk.append(word_obj)

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def generate_karaoke_ass(
    words: List[WordTimestamp],
    output_ass_path: Path,
    style_preset: str = "hormozi",
    clip_start_offset: float = 0.0,
    font_file: Optional[Path] = None
) -> Path:
    """
    Generates an Advanced SubStation Alpha (.ass) file with active word-level karaoke highlights.
    
    Args:
        words: List of WordTimestamp objects
        output_ass_path: File destination for the .ass subtitle file
        style_preset: 'hormozi', 'cyber_cyan', or 'emerald_box'
        clip_start_offset: Seconds to subtract from timestamps if clipping a segment
        font_file: Optional path to TTF/OTF font
    """
    style = STYLE_PRESETS.get(style_preset.lower(), STYLE_PRESETS["hormozi"])
    font_name = "Montserrat" if not font_file else font_file.stem

    # Header section
    ass_content = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{style['fontsize']},{style['primary_color']},{style['highlight_color']},{style['outline_color']},{style['back_color']},{style['bold']},0,0,0,100,100,1,0,1,{style['outline']},{style['shadow']},{style['alignment']},60,60,{style['margin_v']},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    # Adjust words by offset if needed
    normalized_words = [
        WordTimestamp(
            word=w.word.strip().upper(),
            start=max(0.0, w.start - clip_start_offset),
            end=max(0.0, w.end - clip_start_offset)
        )
        for w in words
        if (w.end - clip_start_offset) > 0
    ]

    chunks = group_words_into_chunks(normalized_words, max_words_per_chunk=4)

    for chunk in chunks:
        for active_idx, active_word in enumerate(chunk):
            w_start = format_ass_timestamp(active_word.start)
            w_end = format_ass_timestamp(active_word.end)

            line_parts = []
            for idx, w in enumerate(chunk):
                if idx == active_idx:
                    # Highlight active word with highlight color
                    line_parts.append(f"{{\\c{style['highlight_color']}&}}{w.word}{{\\c{style['primary_color']}&}}")
                else:
                    line_parts.append(w.word)

            display_text = " ".join(line_parts)
            dialogue_line = f"Dialogue: 0,{w_start},{w_end},Default,,0,0,0,,{display_text}"
            ass_content.append(dialogue_line)

    output_ass_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ass_content) + "\n")

    return output_ass_path
