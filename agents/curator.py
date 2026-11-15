"""
Viral Curator Agent (Pass 1 Candidate Generator)
Analyzes transcripts with multimodal audio signals (energy, laughter, rhythm)
to extract 10-15 high-potential viral candidates validated with Pydantic.
"""

import re
import json
from typing import List, Dict, Any, Optional
from pydantic import ValidationError

from schema import CandidateClip, AudioSignals, WordTimestamp, ClipMetadata
from .boundary import BoundarySnapper
from .judge import JudgeAgent


class ViralCuratorAgent:
    """Agent responsible for Pass-1 Candidate Generation and multimodal transcript analysis."""

    def __init__(self, api_key: Optional[str] = None, provider: str = "groq"):
        self.api_key = api_key
        self.provider = provider
        self.judge = JudgeAgent(api_key=api_key, provider=provider)

    def generate_candidates(
        self,
        transcript_text: str,
        audio_signals: Optional[AudioSignals] = None,
        target_candidates: int = 12,
        min_duration: int = 25,
        max_duration: int = 60
    ) -> List[CandidateClip]:
        """Pass 1: Generate 10-15 viral moment candidates with multimodal audio context."""
        audio_summary = audio_signals.summary_text if audio_signals else "Speech rhythm baseline."

        prompt = f"""You are an elite short-form video scout (Opus Clip / MrBeast level).
Generate {target_candidates} candidate short-form clips from the transcript below.

MULTIMODAL ACOUSTIC SIGNALS:
{audio_summary}

RULES:
1. Identify high-energy hooks, questions, contrarian views, and emotional climaxes.
2. Align candidate starts with detected vocal energy or hook spikes.
3. Each candidate duration MUST be between {min_duration} and {max_duration} seconds.
4. Output exactly {target_candidates} distinct candidates spanning the whole video.

OUTPUT JSON FORMAT ONLY:
{{
  "candidates": [
    {{
      "candidate_id": 1,
      "title": "Short title",
      "start_seconds": 12.0,
      "end_seconds": 45.0,
      "duration": 33.0,
      "initial_score": 92,
      "hook": "Opening hook line",
      "reason": "Why this candidate has high retention potential"
    }}
  ]
}}

Timestamped Video Transcript:
{transcript_text[:14000]}
"""

        raw_text = ""
        # Up to 3 attempts with retry on invalid JSON
        for attempt in range(3):
            try:
                if self.provider == "groq" and self.api_key:
                    from groq import Groq
                    client = Groq(api_key=self.api_key)
                    completion = client.chat.completions.create(
                        model="qwen/qwen-2.5-72b-instruct",
                        messages=[
                            {"role": "system", "content": "You are a viral video scout. Respond ONLY with valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3,
                        response_format={"type": "json_object"}
                    )
                    raw_text = completion.choices[0].message.content or ""
                elif self.provider == "gemini" and self.api_key:
                    from google import genai
                    client = genai.Client(api_key=self.api_key)
                    resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                    )
                    raw_text = resp.text or ""
                elif self.provider == "openai" and self.api_key:
                    import openai
                    client = openai.OpenAI(api_key=self.api_key)
                    completion = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a viral video scout."},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"}
                    )
                    raw_text = completion.choices[0].message.content or ""
                else:
                    return self._heuristic_candidates(transcript_text, target_candidates, min_duration, max_duration)

                data = self._clean_and_parse_json(raw_text)
                if data and "candidates" in data:
                    candidates = []
                    for item in data["candidates"]:
                        try:
                            c = CandidateClip(**item)
                            candidates.append(c)
                        except ValidationError:
                            continue
                    if len(candidates) >= 3:
                        return candidates

            except Exception as e:
                print(f"[ViralCuratorAgent] Candidate generation attempt {attempt+1} error: {e}")

        # Fallback if LLM failed
        return self._heuristic_candidates(transcript_text, target_candidates, min_duration, max_duration)

    def curate_clips(
        self,
        transcript_text: str,
        words: Optional[List[WordTimestamp]] = None,
        audio_signals: Optional[AudioSignals] = None,
        num_clips: int = 3,
        min_duration: int = 25,
        max_duration: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Full Two-Pass Smart Curation:
        Pass 1: Generate 10-15 candidates with multimodal signals
        Step 1.5: Snap boundaries to sentence ends and silences
        Pass 2: JudgeAgent audits against 4-factor rubric and creates 3 headline variants
        """
        # Pass 1: Generate candidate pool
        candidates = self.generate_candidates(
            transcript_text=transcript_text,
            audio_signals=audio_signals,
            target_candidates=max(10, num_clips * 3),
            min_duration=min_duration,
            max_duration=max_duration
        )

        # Step 1.5: Boundary snapping to complete sentences & pauses
        if words:
            snapped_candidates = []
            for c in candidates:
                s_start, s_end = BoundarySnapper.snap_boundaries(
                    words=words,
                    raw_start=c.start_seconds,
                    raw_end=c.end_seconds,
                    min_duration=min_duration,
                    max_duration=max_duration
                )
                snapped_candidates.append(CandidateClip(
                    candidate_id=c.candidate_id,
                    title=c.title,
                    start_seconds=s_start,
                    end_seconds=s_end,
                    duration=round(s_end - s_start, 2),
                    initial_score=c.initial_score,
                    hook=c.hook,
                    reason=c.reason
                ))
            candidates = snapped_candidates

        # Pass 2: JudgeAgent audit and re-ranking
        ranked_metadata = self.judge.evaluate_and_rank(
            candidates=candidates,
            transcript_context=transcript_text,
            audio_signals=audio_signals,
            top_n=num_clips
        )

        # Return dicts for pipeline compatibility
        return [meta.model_dump() for meta in ranked_metadata]

    def _heuristic_candidates(
        self,
        transcript_text: str,
        target_candidates: int,
        min_duration: int,
        max_duration: int
    ) -> List[CandidateClip]:
        """Heuristic candidate generator dividing transcript into balanced segments."""
        lines = [line.strip() for line in transcript_text.split("\n") if line.strip()]
        candidates: List[CandidateClip] = []

        time_entries = []
        for line in lines:
            m = re.match(r"\[(\d+):(\d+)\]\s*(.*)", line)
            if m:
                mins, secs, text = int(m.group(1)), int(m.group(2)), m.group(3)
                total_s = mins * 60 + secs
                time_entries.append((total_s, text))

        if not time_entries:
            time_entries = [(i * 30, f"Key highlight moment segment {i+1}") for i in range(12)]

        step = max(1, len(time_entries) // target_candidates)
        cid = 1
        for idx in range(0, len(time_entries), step):
            if cid > target_candidates:
                break
            start_s, hook_text = time_entries[idx]
            end_s = start_s + min_duration + (cid * 3) % (max_duration - min_duration)
            candidates.append(CandidateClip(
                candidate_id=cid,
                title=f"Viral Highlight {cid}",
                start_seconds=float(start_s),
                end_seconds=float(end_s),
                duration=float(end_s - start_s),
                initial_score=88 + (cid % 10),
                hook=hook_text[:60] if hook_text else "Check this out",
                reason="Heuristic candidate based on transcript timestamp cadence."
            ))
            cid += 1

        return candidates

    @staticmethod
    def _clean_and_parse_json(text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
        try:
            return json.loads(text)
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except Exception:
                    pass
        return None
