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

from schema import CandidateClip, RubricScore, HeadlineVariants, ClipMetadata, AudioSignals


class JudgeAgent:
    """Pass-2 Judge Agent auditing viral candidate clips against strict retention rubrics."""

    def __init__(self, api_key: Optional[str] = None, provider: str = "groq", min_score_threshold: int = 75):
        self.api_key = api_key
        self.provider = provider
        self.min_score_threshold = min_score_threshold

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
                    return gated[:top_n]
            except Exception as e:
                print(f"[JudgeAgent] LLM evaluation error: {e}, using heuristic judge...")

        # Fallback to heuristic evaluation if offline or on error
        return self._heuristic_evaluate(candidates, audio_signals, top_n, min_score=threshold)

    def _llm_evaluate_groq(
        self,
        candidates: List[CandidateClip],
        transcript_context: str,
        audio_signals: Optional[AudioSignals]
    ) -> List[ClipMetadata]:
        from groq import Groq

        client = Groq(api_key=self.api_key)
        audio_info = audio_signals.summary_text if audio_signals else "No acoustic anomalies."

        candidates_payload = [
            {
                "candidate_id": c.candidate_id,
                "title": c.title,
                "start": c.start_seconds,
                "end": c.end_seconds,
                "duration": c.duration,
                "hook": c.hook,
                "initial_score": c.initial_score
            }
            for c in candidates
        ]

        prompt = f"""You are an elite YouTube Shorts / TikTok Content Judge and Algorithm Strategist.
Audit the following candidate video moments against our strict 4-factor Virality Rubric (Max 100 pts):

1. hook_strength (0-25): Does the first 3 seconds shock, question, or stop the scroll?
2. self_contained (0-25): Does it form a complete standalone story/idea without missing pronouns or context?
3. payoff (0-25): Is there an emotional climax, actionable takeaway, or mind-blowing reveal?
4. zero_context_needed (0-25): Can a stranger with zero knowledge immediately understand it?

MULTIMODAL SIGNALS:
{audio_info}

CANDIDATE CLIPS TO AUDIT:
{json.dumps(candidates_payload, indent=2)}

For EACH candidate:
- Grade all 4 rubric criteria (0-25) and compute total_score (sum 0-100).
- Provide a brief critique.
- Craft 3 viral headline variants (Curiosity, Value, Bold Claim; max 6 words each).
- Pick the best 'chosen' headline for the top banner.

OUTPUT REQUIREMENTS:
Respond ONLY with a valid JSON array of objects with this schema:
[
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
]"""

        # Call Groq with retry loop
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=[
                        {"role": "system", "content": "You are a master viral video judge. Output valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=800,
                    response_format={"type": "json_object"} if attempt == 0 else None
                )

                content = response.choices[0].message.content or ""
                # Parse JSON
                parsed_data = self._clean_and_parse_json(content)
                if not parsed_data:
                    continue

                if isinstance(parsed_data, dict):
                    # In case LLM wrapped list in {"clips": [...]} or similar
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

                results: List[ClipMetadata] = []
                cand_map = {c.candidate_id: c for c in candidates}

                for item in parsed_data:
                    if not isinstance(item, dict):
                        continue
                    cid = item.get("candidate_id")
                    if cid not in cand_map:
                        continue
                    cand = cand_map[cid]

                    rubric_dict = item.get("rubric", {})
                    # Calculate or validate total
                    total = sum([
                        int(rubric_dict.get("hook_strength", 20)),
                        int(rubric_dict.get("self_contained", 20)),
                        int(rubric_dict.get("payoff", 20)),
                        int(rubric_dict.get("zero_context_needed", 20))
                    ])
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
                    results.append(metadata)

                if results:
                    return results

            except Exception as e:
                print(f"[JudgeAgent] Attempt {attempt+1} failed: {e}")

        return []

    def _heuristic_evaluate(
        self,
        candidates: List[CandidateClip],
        audio_signals: Optional[AudioSignals],
        top_n: int,
        min_score: Optional[int] = None
    ) -> List[ClipMetadata]:
        """Deterministic rubric scoring, score gating, and headline generation for offline/fallback use."""
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
                critique="Heuristic judge verified hook density and acoustic climax."
            )

            clean_title = re.sub(r"[^A-Za-z0-9 ]", "", c.title).upper()
            variants = HeadlineVariants(
                curiosity=f"WHY {clean_title}?"[:30],
                value=f"HOW TO MASTER {clean_title}"[:30],
                bold_claim=f"THE TRUTH ABOUT {clean_title}"[:30],
                chosen=f"{clean_title}"[:30]
            )

            results.append(ClipMetadata(
                title=c.title,
                headline=variants.chosen,
                start_seconds=c.start_seconds,
                end_seconds=c.end_seconds,
                duration=c.duration,
                viral_score=total,
                hook=c.hook,
                reason=rubric.critique,
                headline_variants=variants,
                rubric=rubric
            ))

        results.sort(key=lambda x: x.viral_score, reverse=True)
        gated = [c for c in results if c.viral_score >= threshold]
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
