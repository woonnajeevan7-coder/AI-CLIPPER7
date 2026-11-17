"""
Boundary Snapping Engine
Aligns clip boundaries to natural sentence starts, question pauses, and vocal silences.
Ensures zero mid-word cuts and complete narrative thoughts.
"""

from typing import List, Tuple, Optional
from schema import WordTimestamp


class BoundarySnapper:
    """Snaps coarse candidate timestamps to exact word boundaries, sentence starts, and silences."""

    @staticmethod
    def snap_boundaries(
        words: List[WordTimestamp],
        raw_start: float,
        raw_end: float,
        min_duration: float = 20.0,
        max_duration: float = 60.0
    ) -> Tuple[float, float]:
        """
        Snaps raw_start and raw_end to sentence starts and punctuation pauses.
        
        Returns:
            (snapped_start, snapped_end)
        """
        if not words:
            return round(raw_start, 2), round(raw_end, 2)

        # 1. Snap start timestamp
        # Find candidate words near raw_start (-3.0s to +3.0s)
        start_candidates = [
            (i, w) for i, w in enumerate(words)
            if abs(w.start - raw_start) <= 4.0 or (w.start <= raw_start <= w.end)
        ]

        best_start_idx = 0
        if start_candidates:
            # Score start points: prefer words after silence (>0.4s) or after punctuation in previous word
            best_score = -999.0
            for i, w in start_candidates:
                score = 0.0
                dist = abs(w.start - raw_start)
                score -= dist * 2.0  # distance penalty

                if i > 0:
                    prev_w = words[i - 1]
                    pause = w.start - prev_w.end
                    if pause >= 0.35:
                        score += 5.0
                    if any(prev_w.word.endswith(punct) for punct in [".", "!", "?", ":", "\n"]):
                        score += 8.0
                    elif any(prev_w.word.endswith(punct) for punct in [",", ";"]):
                        score += 3.0
                else:
                    score += 5.0

                if score > best_score:
                    best_score = score
                    best_start_idx = i
        else:
            # Nearest word
            best_start_idx = min(range(len(words)), key=lambda i: abs(words[i].start - raw_start))

        snapped_start = words[best_start_idx].start

        # 2. Snap end timestamp
        target_end = max(snapped_start + min_duration, min(raw_end, snapped_start + max_duration))
        end_candidates = [
            (i, w) for i, w in enumerate(words)
            if i >= best_start_idx and abs(w.end - target_end) <= 5.0
        ]

        best_end_idx = len(words) - 1
        if end_candidates:
            best_end_score = -999.0
            for i, w in end_candidates:
                score = 0.0
                dur = w.end - snapped_start
                if dur < min_duration:
                    score -= (min_duration - dur) * 10.0
                if dur > max_duration:
                    score -= (dur - max_duration) * 10.0

                dist = abs(w.end - target_end)
                score -= dist * 1.5

                # Reward sentence endings
                if any(w.word.endswith(punct) for punct in [".", "!", "?"]):
                    score += 10.0
                elif any(w.word.endswith(punct) for punct in [",", ";", "-"]):
                    score += 2.0

                if i + 1 < len(words):
                    pause_after = words[i + 1].start - w.end
                    if pause_after >= 0.4:
                        score += 6.0

                if score > best_end_score:
                    best_end_score = score
                    best_end_idx = i
        else:
            # Pick word closest to target_end
            eligible = [i for i in range(best_start_idx, len(words)) if words[i].end >= snapped_start + min_duration]
            if eligible:
                best_end_idx = min(eligible, key=lambda i: abs(words[i].end - target_end))
            else:
                best_end_idx = len(words) - 1

        snapped_end = words[best_end_idx].end
        # Guarantee minimum duration
        if snapped_end - snapped_start < min_duration and best_end_idx < len(words) - 1:
            for j in range(best_end_idx, len(words)):
                if words[j].end - snapped_start >= min_duration:
                    snapped_end = words[j].end
                    break

        return round(snapped_start, 3), round(snapped_end, 3)

    @classmethod
    def snap_to_silence(
        cls,
        raw_start: float,
        raw_end: float,
        silences: Optional[List[Tuple[float, float]]] = None,
        words: Optional[List[WordTimestamp]] = None,
        max_delta: float = 3.0,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        prev_clip_end: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Snaps raw_start and raw_end to the nearest silence pause within +/- max_delta (default 3s).
        Enforces:
        1. No overlap: snapped_start >= prev_clip_end
        2. Clamped duration: between (interval - max_delta) and (interval + max_delta)
        """
        interval = raw_end - raw_start
        min_dur = min_duration if min_duration is not None else max(1.0, interval - max_delta)
        max_dur = max_duration if max_duration is not None else (interval + max_delta)

        # Lower bound for start: must not overlap previous clip
        min_start_bound = prev_clip_end if prev_clip_end is not None else 0.0

        # Start snapping
        snapped_start = raw_start
        if silences:
            start_candidates = [
                (s, e) for (s, e) in silences
                if (s <= raw_start + max_delta and e >= raw_start - max_delta)
            ]
            valid_points = []
            for s, e in start_candidates:
                pt = round((s + e) / 2.0, 2)
                if pt >= min_start_bound:
                    valid_points.append(pt)
                elif e >= min_start_bound:
                    valid_points.append(round(e, 2))

            if valid_points:
                snapped_start = min(valid_points, key=lambda p: abs(p - raw_start))

        elif words:
            pauses = []
            for i in range(len(words) - 1):
                p_start = words[i].end
                p_end = words[i + 1].start
                if p_end - p_start >= 0.25 and (p_start <= raw_start + max_delta and p_end >= raw_start - max_delta):
                    pt = round((p_start + p_end) / 2.0, 2)
                    if pt >= min_start_bound:
                        pauses.append(pt)
            if pauses:
                snapped_start = min(pauses, key=lambda p: abs(p - raw_start))

        # Guarantee no overlap with previous clip
        if snapped_start < min_start_bound:
            snapped_start = min_start_bound

        # End snapping
        snapped_end = raw_end
        if silences:
            end_candidates = [
                (s, e) for (s, e) in silences
                if (s <= raw_end + max_delta and e >= raw_end - max_delta)
            ]
            valid_end_points = []
            for s, e in end_candidates:
                pt = round((s + e) / 2.0, 2)
                if pt > snapped_start:
                    valid_end_points.append(pt)
                elif s > snapped_start:
                    valid_end_points.append(round(s, 2))
            if valid_end_points:
                snapped_end = min(valid_end_points, key=lambda p: abs(p - raw_end))
        elif words:
            pauses = []
            for i in range(len(words) - 1):
                p_start = words[i].end
                p_end = words[i + 1].start
                if p_end - p_start >= 0.25 and (p_start <= raw_end + max_delta and p_end >= raw_end - max_delta):
                    pt = round((p_start + p_end) / 2.0, 2)
                    if pt > snapped_start:
                        pauses.append(pt)
            if pauses:
                snapped_end = min(pauses, key=lambda p: abs(p - raw_end))

        # Clamp duration to interval +/- max_delta
        current_dur = snapped_end - snapped_start
        if current_dur < min_dur:
            snapped_end = snapped_start + min_dur
        elif current_dur > max_dur:
            snapped_end = snapped_start + max_dur

        return round(snapped_start, 2), round(snapped_end, 2)
