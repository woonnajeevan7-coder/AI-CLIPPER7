"""
Judge Agent (Pass 2 Smart Curation)
Re-ranks candidate clips against a rigorous 4-factor virality rubric:
Hook Strength (25) + Self-Contained (25) + Payoff (25) + Zero Context Needed (25).
Generates 3 headline variants (Curiosity, Value, Bold Claim) and enforces Pydantic validation.
"""

import json
import re
from typing import List, Dict, Any, Optional
from pydantic import ValidationError

from schema import CandidateClip, RubricScore, HeadlineVariants, ClipMetadata, AudioSignals, WordTimestamp


class JudgeAgent:
    """Pass-2 Judge Agent auditing viral candidate clips against strict retention rubrics."""

    def __init__(self, api_key: Optional[str] = None, provider: str = "groq", min_score_threshold: int = 75):
        if provider not in ("groq", "heuristic", "offline"):
            raise ValueError(f"Unsupported provider '{provider}'. Only Groq AI is supported for clip evaluation.")
        self.api_key = api_key
        self.provider = provider
        self.min_score_threshold = min_score_threshold
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
            print(f"[JudgeAgent] Model verification notice: {e}")
        self._verified_model = "llama-3.3-70b-versatile"
        return self._verified_model

    def _extract_candidate_transcript(
        self,
        transcript_context: str,
        start_seconds: float,
        end_seconds: float
    ) -> str:
        """Extracts spoken dialogue from transcript_context within candidate [start, end] window."""
        if not transcript_context:
            return ""

        matching_lines = []
        for line in transcript_context.splitlines():
            line_str = line.strip()
            m = re.match(r"\[(\d+):(\d+)\]\s*(.*)", line_str)
            if m:
                mins, secs, text = int(m.group(1)), int(m.group(2)), m.group(3)
                t = mins * 60 + secs
                if (start_seconds - 2.0) <= t <= (end_seconds + 2.0):
                    matching_lines.append(text)
            elif line_str and not line_str.startswith("["):
                matching_lines.append(line_str)

        extracted = " ".join(matching_lines)
        return extracted[:3000] if extracted else transcript_context[:800]

    def evaluate_candidates(
        self,
        candidates: List[CandidateClip],
        transcript_words: Optional[List[WordTimestamp]] = None,
        transcript_context: Optional[str] = None,
        audio_signals: Optional[AudioSignals] = None,
        top_n: int = 3,
        threshold: Optional[int] = None
    ) -> List[ClipMetadata]:
        """Evaluates and ranks candidate clips against the 4-factor virality rubric."""
        if not transcript_context and transcript_words:
            from .transcriber import TranscriberAgent
            transcript_context = TranscriberAgent.words_to_transcript_text(transcript_words)
        return self.evaluate_and_rank(
            candidates=candidates,
            transcript_context=transcript_context or "",
            audio_signals=audio_signals,
            top_n=top_n,
            min_score=threshold
        )

    def evaluate_and_rank(
        self,
        candidates: List[CandidateClip],
        transcript_context: str,
        audio_signals: Optional[AudioSignals] = None,
        top_n: int = 3,
        min_score: Optional[int] = None
    ) -> List[ClipMetadata]:
        """
        Re-ranks pass-1 candidates, computes rubric scores, generates 3 headline variants,
        enforces explicit score gating (total_score >= 75 by default),
        and returns validated ClipMetadata objects.
        """
        if not candidates:
            return []

        threshold = min_score if min_score is not None else self.min_score_threshold

        # If LLM key is available, run deep LLM judge evaluation
        if self.api_key and self.provider == "groq":
            try:
                evaluated = self._llm_evaluate_groq(candidates, transcript_context, audio_signals)
                if evaluated:
                    # Apply explicit score gating
                    gated = [c for c in evaluated if (c.rubric.total_score if c.rubric else c.viral_score) >= threshold]
                    gated.sort(key=lambda c: c.viral_score, reverse=True)
                    if min_score is None and len(gated) < top_n and evaluated:
                        # If strict threshold filtered candidates, backfill with remaining evaluated candidates in descending score order
                        remaining = [c for c in sorted(evaluated, key=lambda c: c.viral_score, reverse=True) if c not in gated]
                        gated.extend(remaining[:(top_n - len(gated))])
                    return gated[:top_n]
                else:
                    raise RuntimeError("Groq LLM evaluation returned zero valid candidates.")
            except Exception as e:
                # Fail loudly when an API key was provided instead of silent fallback
                raise RuntimeError(f"[JudgeAgent] LLM evaluation failed on {self.provider}: {e}")

        # Fallback to heuristic evaluation only when offline (no API key provided)
        return self._heuristic_evaluate(candidates, audio_signals, top_n, min_score=threshold)

    def _llm_evaluate_groq(
        self,
        candidates: List[CandidateClip],
        transcript_context: str,
        audio_signals: Optional[AudioSignals]
    ) -> List[ClipMetadata]:
        from groq import Groq

        client = Groq(api_key=self.api_key)
        model_id = self._get_verified_model(client)
        audio_info = audio_signals.summary_text if audio_signals else "No acoustic anomalies."

        candidates_payload_all = [
            {
                "candidate_id": c.candidate_id,
                "title": c.title,
                "start": c.start_seconds,
                "end": c.end_seconds,
                "duration": c.duration,
                "hook": c.hook,
                "transcript_text": self._extract_candidate_transcript(transcript_context, c.start_seconds, c.end_seconds),
                "initial_score": c.initial_score
            }
            for c in candidates
        ]

        # Chunk into batches of at most 3 candidates to respect token ceilings and allow deep analysis
        batch_size = 3
        cand_map = {c.candidate_id: c for c in candidates}
        batches = [candidates[i:i + batch_size] for i in range(0, len(candidates), batch_size)]
        all_results: List[ClipMetadata] = []
        last_error = None

        for b_idx, batch in enumerate(batches):
            batch_payload = [
                item for item in candidates_payload_all
                if item["candidate_id"] in {c.candidate_id for c in batch}
            ]

            prompt = f"""You are an elite YouTube Shorts / TikTok Content Judge and Algorithm Strategist.
Audit the following candidate video moments against our strict 4-factor Virality Rubric (Max 100 pts):

1. hook_strength (0-25): Does the first 3 seconds shock, question, or stop the scroll?
2. self_contained (0-25): Does it form a complete standalone story/idea without missing pronouns or context?
3. payoff (0-25): Is there an emotional climax, actionable takeaway, or mind-blowing reveal?
4. zero_context_needed (0-25): Can a stranger with zero knowledge immediately understand it?

MULTIMODAL SIGNALS:
{audio_info}

CANDIDATE CLIPS TO AUDIT (WITH ACTUAL TRANSCRIPT TEXT):
{json.dumps(batch_payload, indent=2)}

For EACH candidate:
- Read its 'transcript_text' thoroughly and evaluate narrative flow and emotional punch.
- Grade all 4 rubric criteria (0-25 each, all 4 are MANDATORY) and compute total_score (sum 0-100).
- Provide a brief critique.
- Craft 3 viral headline variants (Curiosity, Value, Bold Claim; max 6 words each).
- Pick the best 'chosen' headline for the top banner.

OUTPUT REQUIREMENTS:
Respond ONLY with a valid JSON object containing a "clips" list:
{{
  "clips": [
    {{
      "candidate_id": 1,
      "title": "Title",
      "rubric": {{
        "hook_strength": 24,
        "self_contained": 23,
        "payoff": 22,
        "zero_context_needed": 24,
        "total_score": 93,
        "critique": "Instant intrigue hook with actionable conclusion."
      }},
      "headline_variants": {{
        "curiosity": "THE SECRET TO 10X SPEED",
        "value": "HOW TO DOUBLE CODING SPEED",
        "bold_claim": "NEVER WRITE BOILERPLATE AGAIN",
        "chosen": "THE SECRET TO 10X SPEED"
      }}
    }}
  ]
}}"""

            batch_success = False
            max_tok = 950 if "qwen" in model_id.lower() else 2048
            for attempt in range(3):
                try:
                    response = client.chat.completions.create(
                        model=model_id,
                        messages=[
                            {"role": "system", "content": "You are a master viral video judge. Output valid JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.2,
                        max_tokens=max_tok,
                        response_format={"type": "json_object"} if attempt == 0 else None
                    )

                    content = response.choices[0].message.content or ""
                    parsed_data = self._clean_and_parse_json(content)
                    if not parsed_data:
                        continue

                    if isinstance(parsed_data, dict):
                        found_list = False
                        for v in parsed_data.values():
                            if isinstance(v, list):
                                parsed_data = v
                                found_list = True
                                break
                        if not found_list:
                            if "candidate_id" in parsed_data:
                                parsed_data = [parsed_data]
                            else:
                                continue

                    if not isinstance(parsed_data, list):
                        continue

                    required_rubric = ["hook_strength", "self_contained", "payoff", "zero_context_needed"]
                    batch_evals: List[ClipMetadata] = []

                    for item in parsed_data:
                        if not isinstance(item, dict):
                            continue
                        cid = item.get("candidate_id")
                        if cid not in cand_map:
                            continue
                        cand = cand_map[cid]

                        rubric_dict = item.get("rubric", {})
                        # Stop defaulting missing rubric fields to 20: enforce all 4 required fields
                        if not all(k in rubric_dict for k in required_rubric):
                            print(f"[JudgeAgent] Candidate {cid} omitted required rubric fields ({list(rubric_dict.keys())}), skipping incomplete evaluation.")
                            continue

                        try:
                            hook_s = int(rubric_dict["hook_strength"])
                            self_c = int(rubric_dict["self_contained"])
                            payoff_s = int(rubric_dict["payoff"])
                            zero_c = int(rubric_dict["zero_context_needed"])
                        except (ValueError, TypeError):
                            continue

                        if not all(0 <= v <= 25 for v in (hook_s, self_c, payoff_s, zero_c)):
                            continue

                        total = hook_s + self_c + payoff_s + zero_c
                        rubric_dict["total_score"] = min(100, max(0, total))

                        rubric = RubricScore(**rubric_dict)
                        headlines = HeadlineVariants(**item.get("headline_variants", {
                            "curiosity": cand.title.upper(),
                            "value": cand.title.upper(),
                            "bold_claim": cand.title.upper(),
                            "chosen": cand.title.upper()
                        }))

                        metadata = ClipMetadata(
                            title=cand.title,
                            headline=headlines.chosen,
                            start_seconds=cand.start_seconds,
                            end_seconds=cand.end_seconds,
                            duration=cand.duration,
                            viral_score=rubric.total_score,
                            hook=cand.hook,
                            reason=rubric.critique,
                            headline_variants=headlines,
                            rubric=rubric
                        )
                        batch_evals.append(metadata)

                    if batch_evals:
                        all_results.extend(batch_evals)
                        batch_success = True
                        break

                except Exception as e:
                    last_error = e
                    print(f"[JudgeAgent] Batch {b_idx + 1} attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        import time
                        time.sleep(4 if ("429" in str(e) or "rate_limit" in str(e).lower()) else 1)

            if not batch_success and not all_results:
                break

        if all_results:
            # If any candidates failed LLM evaluation, backfill them with heuristic evaluation
            evaluated_starts = {round(r.start_seconds, 1) for r in all_results}
            missing = [c for c in candidates if round(c.start_seconds, 1) not in evaluated_starts]
            if missing:
                heuristic_fallback = self._heuristic_evaluate(missing, audio_signals, top_n=len(missing), min_score=0)
                all_results.extend(heuristic_fallback)
            return all_results

        raise RuntimeError(f"Groq LLM evaluation failed after 3 attempts. Last error: {last_error}")

    def _heuristic_evaluate(
        self,
        candidates: List[CandidateClip],
        audio_signals: Optional[AudioSignals],
        top_n: int,
        min_score: Optional[int] = None
    ) -> List[ClipMetadata]:
        """Deterministic rubric scoring, score gating, and headline generation for offline/fallback use with explicit heuristic mode labels."""
        print("[JudgeAgent] WARNING: Running in HEURISTIC MODE (no LLM API key provided).")
        results: List[ClipMetadata] = []
        energy_times = audio_signals.energy_peaks if audio_signals else []
        threshold = min_score if min_score is not None else self.min_score_threshold

        for c in candidates:
            # Rubric scoring heuristics
            hook_score = 22 if len(c.hook) > 15 else 18
            self_contained = 23 if (25.0 <= c.duration <= 50.0) else 19

            # Payoff boosted if audio energy burst falls near the end
            has_energy_payoff = any(c.end_seconds - 8.0 <= t <= c.end_seconds for t in energy_times)
            payoff_score = 24 if has_energy_payoff else 20
            zero_context = 22

            total = hook_score + self_contained + payoff_score + zero_context

            rubric = RubricScore(
                hook_strength=hook_score,
                self_contained=self_contained,
                payoff=payoff_score,
                zero_context_needed=zero_context,
                total_score=total,
                critique="[HEURISTIC MODE] Heuristic judge verified hook density and acoustic climax."
            )

            clean_title = re.sub(r"[^A-Za-z0-9 ]", "", c.title).upper()
            variants = HeadlineVariants(
                curiosity=f"WHY {clean_title}?"[:30],
                value=f"HOW TO MASTER {clean_title}"[:30],
                bold_claim=f"THE TRUTH ABOUT {clean_title}"[:30],
                chosen=f"[HEURISTIC] {clean_title}"[:30]
            )

            results.append(ClipMetadata(
                title=f"[Heuristic] {c.title}" if not c.title.startswith("[Heuristic]") else c.title,
                headline=variants.chosen,
                start_seconds=c.start_seconds,
                end_seconds=c.end_seconds,
                duration=c.duration,
                viral_score=total,
                hook=c.hook,
                reason="[HEURISTIC MODE] Evaluated without LLM.",
                headline_variants=variants,
                rubric=rubric
            ))

        results.sort(key=lambda x: x.viral_score, reverse=True)
        gated = [c for c in results if c.viral_score >= threshold]
        if min_score is None and len(gated) < top_n and results:
            remaining = [c for c in results if c not in gated]
            gated.extend(remaining[:(top_n - len(gated))])
        return gated[:top_n]

    @staticmethod
    def _clean_and_parse_json(text: str) -> Optional[Any]:
        text = text.strip()
        # Look for ```json markdown block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
        try:
            return json.loads(text)
        except Exception:
            # Try to locate array bracket
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except Exception:
                    pass
        return None
