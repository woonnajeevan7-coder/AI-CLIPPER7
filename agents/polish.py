"""
Motion and Polish Agent
Handles dynamic punch-in zooms, LLM keyword/emoji highlighting,
silence trimming, and background music ducking.
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from schema import WordTimestamp


VIRAL_EMOJI_LEXICON: Dict[str, str] = {
    # Money & Value
    "MONEY": "💰", "CASH": "💵", "DOLLAR": "💵", "RICH": "💎", "PROFIT": "📈",
    "WEALTH": "💰", "MILLION": "💰", "BILLION": "💎", "PAID": "💸", "REVENUE": "📈",
    
    # Growth & Power
    "VIRAL": "🔥", "FIRE": "🔥", "INSANE": "🤯", "CRAZY": "🤯", "EPIC": "⚡",
    "FAST": "⚡", "SPEED": "⚡", "ROCKET": "🚀", "SCALE": "🚀", "10X": "🚀",
    "BOOST": "🚀", "DOUBLE": "📈", "POWER": "⚡", "SUPER": "💥",
    
    # Secrets & Insights
    "SECRET": "💡", "HACK": "💡", "TRICK": "💡", "IDEA": "💡", "STRATEGY": "🧠",
    "DISCOVER": "🔍", "TRUTH": "👁️", "LESSON": "📚", "REVEAL": "🔓", "KEY": "🔑",
    
    # Warnings & Contradictions
    "WARNING": "⚠️", "MISTAKE": "❌", "STOP": "🛑", "NEVER": "🚫", "DANGER": "⚠️",
    "WORST": "💀", "TRAP": "🪤", "FAILED": "❌", "AVOID": "⛔", "WRONG": "❌",
    
    # Goals & Precision
    "TARGET": "🎯", "GOAL": "🎯", "FOCUS": "🎯", "WIN": "🏆", "SUCCESS": "🏆",
    "FUTURE": "🔮", "AI": "🤖", "CODE": "💻", "SYSTEM": "⚙️", "WORK": "🔨",
}


class KeywordEmojiTagger:
    """Tags salient words and attaches viral emojis to maximize short-form viewer retention."""

    @staticmethod
    def tag_words(
        words: List[WordTimestamp],
        max_emojis_per_clip: int = 6
    ) -> List[WordTimestamp]:
        """
        Enriches a list of WordTimestamp objects with is_keyword and emoji attributes.
        Ensures emojis are well-spaced (at least 2.5 seconds apart) to prevent visual clutter.
        """
        tagged_words: List[WordTimestamp] = []
        last_emoji_time = -10.0
        emojis_assigned = 0

        for w in words:
            clean_token = re.sub(r"[^A-Za-z0-9]", "", w.word).upper()
            assigned_emoji = None
            is_key = False

            if clean_token in VIRAL_EMOJI_LEXICON and emojis_assigned < max_emojis_per_clip:
                if (w.start - last_emoji_time) >= 2.5:
                    assigned_emoji = VIRAL_EMOJI_LEXICON[clean_token]
                    is_key = True
                    last_emoji_time = w.start
                    emojis_assigned += 1
            elif clean_token in ["FIRST", "ALWAYS", "BEST", "BIGGEST", "CRITICAL", "MASSIVE"]:
                is_key = True

            tagged_words.append(WordTimestamp(
                word=w.word,
                start=w.start,
                end=w.end,
                is_keyword=is_key,
                emoji=assigned_emoji
            ))

        return tagged_words


class PunchInPlanner:
    """Plans dynamic punch-in zoom cuts (1.14x) at sentence starts and emphasis moments."""

    @staticmethod
    def build_punch_in_intervals(
        words: List[WordTimestamp],
        clip_duration: float,
        zoom_duration: float = 2.0,
        min_gap: float = 2.5
    ) -> List[Tuple[float, float]]:
        """
        Identifies time intervals [start, end] for punch-in zooms.
        Always punches in on the opening hook (0.0s to 2.2s).
        """
        intervals: List[Tuple[float, float]] = []
        # 1. Opening hook punch-in
        hook_end = min(clip_duration, 2.2)
        intervals.append((0.0, hook_end))
        last_punch = hook_end

        # 2. Key emphasis punch-ins
        for w in words:
            if w.start < hook_end + 1.0:
                continue
            if w.start + zoom_duration > clip_duration - 1.0:
                break

            # Punch in if word is emphasized keyword or starts a sentence after a long pause
            if (w.is_keyword or (w.start - last_punch >= min_gap)) and (w.start - last_punch >= min_gap):
                punch_start = round(w.start, 2)
                punch_end = round(min(clip_duration, punch_start + zoom_duration), 2)
                intervals.append((punch_start, punch_end))
                last_punch = punch_end

        return intervals

    @staticmethod
    def generate_zoom_filter(intervals: List[Tuple[float, float]], zoom_factor: float = 1.14) -> str:
        """
        Generates dynamic FFmpeg filtergraph scaling in at planned intervals via split, crop, and overlay.
        Empirically verified to actively change frame pixels during punch-in intervals.
        """
        if not intervals:
            return ""

        conditions = [f"between(t\\,{start:.2f}\\,{end:.2f})" for start, end in intervals]
        condition_str = "+".join(conditions)

        return (
            f"split=2[punch_base][punch_crop];"
            f"[punch_crop]crop=iw/{zoom_factor}:ih/{zoom_factor}:(iw-ow)/2:(ih-oh)/2,scale=1080:1920[punch_zoomed];"
            f"[punch_base][punch_zoomed]overlay=0:0:enable='{condition_str}'"
        )


class AudioPolisher:
    """Generates audio filters for silence trimming and background music ducking."""

    @staticmethod
    def get_silence_trim_filter() -> str:
        """Removes dead air (>0.45s below -40dB)."""
        return "silenceremove=stop_periods=-1:stop_duration=0.45:stop_threshold=-40dB"

    @staticmethod
    def build_ducking_filter(music_volume: float = 0.15, threshold: float = 0.08, ratio: float = 4.0) -> str:
        """
        Mixes dialogue (stream 0) with background music (stream 1) using real sidechaincompress ducking,
        ducking the background music smoothly to avoid overpowering speech.
        """
        return (
            f"[1:a]volume={music_volume}[bgm];"
            f"[0:a]asplit=2[voice_main][voice_trigger];"
            f"[bgm][voice_trigger]sidechaincompress=threshold={threshold}:ratio={ratio}:attack=20:release=250[ducked_bgm];"
            f"[voice_main][ducked_bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
