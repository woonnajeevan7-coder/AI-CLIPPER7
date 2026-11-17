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
        if provider not in ("groq", "heuristic", "offline"):
            raise ValueError(f"Unsupported provider '{provider}'. Only Groq AI is supported for clip curation.")
        self.api_key = api_key
        self.provider = provider
        self.judge = JudgeAgent(api_key=api_key, provider=provider)
        self._verified_model: Optional[str] = None

    def _get_verified_model(self, client: Any) -> str:
        """Verifies and caches the optimal model ID against Groq's live model list."""
        if self._verified_model:
            return self._verified_model
        try:
            live_models = client.models.list().data
            live_ids = {m.id for m in live_models}
            # Priority preference list for Groq LPU models
            preferred = [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "qwen/qwen3.8-27b"
            ]
            for candidate in preferred:
                if candidate in live_ids:
                    self._verified_model = candidate
                    return candidate
            for m in live_models:
                if not m.id.startswith("whisper") and "guard" not in m.id:
                    self._verified_model = m.id
                    return m.id
        except Exception as e:
            print(f"[ViralCuratorAgent] Model verification notice: {e}")
        self._verified_model = "llama-3.3-70b-versatile"
        return self._verified_model

    def _chunk_transcript(
        self,
        transcript_text: str,
        max_chunk_chars: int = 12000,
        overlap_lines: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Chunks long transcripts into coherent segments respecting timestamp line boundaries
        instead of blindly truncating at 14000 characters.
        """
        if len(transcript_text) <= max_chunk_chars:
            return [{"chunk_index": 0, "text": transcript_text}]

        lines = [line for line in transcript_text.splitlines() if line.strip()]
        chunks: List[Dict[str, Any]] = []
        current_lines: List[str] = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1
            if current_len + line_len > max_chunk_chars and current_lines:
                chunks.append({
                    "chunk_index": len(chunks),
                    "text": "\n".join(current_lines)
                })
                # Preserve overlap from end of previous chunk
                overlap = current_lines[-overlap_lines:] if len(current_lines) >= overlap_lines else current_lines
                current_lines = list(overlap)
                current_len = sum(len(l) + 1 for l in current_lines)

            current_lines.append(line)
            current_len += line_len

        if current_lines:
            chunks.append({
                "chunk_index": len(chunks),
                "text": "\n".join(current_lines)
            })

        return chunks

    def propose_candidates(
        self,
        words: Optional[List[WordTimestamp]] = None,
        transcript_text: Optional[str] = None,
        audio_signals: Optional[AudioSignals] = None,
        top_n: int = 5,
        min_duration: int = 25,
        max_duration: int = 60
    ) -> List[CandidateClip]:
        """Proposes viral candidate clips from words or transcript text using multimodal audio signals."""
        if not transcript_text and words:
            from .transcriber import TranscriberAgent
            transcript_text = TranscriberAgent.words_to_transcript_text(words)
        return self.generate_candidates(
            transcript_text=transcript_text or "",
            audio_signals=audio_signals,
            target_candidates=top_n,
            min_duration=min_duration,
            max_duration=max_duration
        )

    def generate_candidates(
        self,
        transcript_text: str,
        audio_signals: Optional[AudioSignals] = None,
        target_candidates: int = 12,
        min_duration: int = 25,
        max_duration: int = 60
    ) -> List[CandidateClip]:
        """Pass 1: Generate 10-15 viral moment candidates with multimodal audio context across all transcript chunks."""
        if not self.api_key:
            return self._heuristic_candidates(transcript_text, target_candidates, min_duration, max_duration)

        audio_summary = audio_signals.summary_text if audio_signals else "Speech rhythm baseline."
        chunks = self._chunk_transcript(transcript_text, max_chunk_chars=12000)
        cands_per_chunk = max(3, (target_candidates // len(chunks)) + 2)

        collected_candidates: List[CandidateClip] = []
        last_error = None

        for chunk_info in chunks:
            chunk_text = chunk_info["text"]
            chunk_idx = chunk_info["chunk_index"]

            prompt = f"""You are an elite short-form video scout (Opus Clip / MrBeast level).
Generate {cands_per_chunk} candidate short-form clips from the transcript segment below.

MULTIMODAL ACOUSTIC SIGNALS:
{audio_summary}

RULES:
1. Identify high-energy hooks, questions, contrarian views, and emotional climaxes.
2. Align candidate starts with detected vocal energy or hook spikes.
3. Each candidate duration MUST be between {min_duration} and {max_duration} seconds.
4. Output distinct candidates spanning this transcript section.

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

Timestamped Video Transcript (Segment {chunk_idx + 1}/{len(chunks)}):
{chunk_text}
"""
            chunk_success = False
            for attempt in range(3):
                try:
                    if self.provider == "groq":
                        from groq import Groq
                        client = Groq(api_key=self.api_key)
                        model_id = self._get_verified_model(client)
                        max_tok = 950 if "qwen" in model_id.lower() else 2048
                        completion = client.chat.completions.create(
                            model=model_id,
                            messages=[
                                {"role": "system", "content": "You are a viral video scout. Respond ONLY with valid JSON."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.3,
                            max_tokens=max_tok,
                            response_format={"type": "json_object"}
                        )
                        raw_text = completion.choices[0].message.content or ""
                    else:
                        raise ValueError(f"Only Groq AI is supported for clip generation (got: '{self.provider}')")

                    data = self._clean_and_parse_json(raw_text)
                    if data and "candidates" in data:
                        for item in data["candidates"]:
                            try:
                                c = CandidateClip(**item)
                                collected_candidates.append(c)
                            except ValidationError:
                                continue
                        chunk_success = True
                        break

                except Exception as e:
                    last_error = e
                    print(f"[ViralCuratorAgent] Chunk {chunk_idx + 1} attempt {attempt + 1} error: {e}")
                    if attempt < 2:
                        import time
                        time.sleep(4 if ("429" in str(e) or "rate_limit" in str(e).lower()) else 1)

            if not chunk_success and not collected_candidates:
                # If chunk failed completely and no candidates collected so far, remember error
                pass

        # Deduplicate candidates across chunks by start timestamp proximity
        if collected_candidates:
            collected_candidates.sort(key=lambda c: c.initial_score, reverse=True)
            deduped: List[CandidateClip] = []
            for c in collected_candidates:
                # Check for overlap with already chosen candidates
                if not any(abs(c.start_seconds - chosen.start_seconds) < 6.0 for chosen in deduped):
                    deduped.append(c)
            # If deduplication dropped candidates below target_candidates, backfill with non-overlapping heuristic candidates
            if len(deduped) < target_candidates:
                h_cands = self._heuristic_candidates(transcript_text, target_candidates, min_duration, max_duration)
                for hc in h_cands:
                    if not any(abs(hc.start_seconds - chosen.start_seconds) < 6.0 for chosen in deduped):
                        deduped.append(hc)
                        if len(deduped) >= target_candidates:
                            break
            # Re-index candidate IDs
            for i, c in enumerate(deduped):
                c.candidate_id = i + 1
            if len(deduped) >= 3:
                return deduped[:target_candidates]

        # Fail loudly if LLM was requested with API key but failed
        raise RuntimeError(
            f"[ViralCuratorAgent] LLM candidate generation failed on provider '{self.provider}'. "
            f"Last error: {last_error}. No silent heuristic fallback allowed."
        )

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
        """Heuristic candidate generator dividing transcript into balanced segments with explicit heuristic mode labels."""
        print("[ViralCuratorAgent] WARNING: Running in HEURISTIC MODE (no LLM API key provided).")
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
            dur_range = max(1, max_duration - min_duration)
            end_s = start_s + min_duration + ((cid * 3) % dur_range)
            candidates.append(CandidateClip(
                candidate_id=cid,
                title=f"[Heuristic] Highlight {cid}",
                start_seconds=float(start_s),
                end_seconds=float(end_s),
                duration=float(end_s - start_s),
                initial_score=88 + (cid % 10),
                hook=hook_text[:60] if hook_text else "Check this out",
                reason="[HEURISTIC MODE] Candidate generated via transcript timestamp cadence."
            ))
            cid += 1

        # Guarantee candidate count reaches target_candidates by generating staggered sliding windows
        max_time = time_entries[-1][0] if time_entries else 180.0
        dur_range = max(1, max_duration - min_duration)
        while len(candidates) < target_candidates:
            offset = (cid - 1) * max(10.0, min_duration * 0.5)
            start_s = float(offset % max(45.0, max_time))
            end_s = start_s + min_duration + ((cid * 3) % dur_range)
            candidates.append(CandidateClip(
                candidate_id=cid,
                title=f"[Heuristic] Highlight {cid}",
                start_seconds=float(start_s),
                end_seconds=float(end_s),
                duration=float(end_s - start_s),
                initial_score=88 + (cid % 10),
                hook=f"Candidate highlight moment #{cid}",
                reason="[HEURISTIC MODE] Staggered window cadence."
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
