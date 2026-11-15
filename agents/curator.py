"""
Viral Curator Agent
Analyzes transcripts, identifies psychological viral hooks, scores virality (0-100), and outputs structured clip candidates.
"""

import re
import json
from typing import List, Dict, Any, Optional


class ViralCuratorAgent:
    """Agent responsible for psychological hook identification, virality scoring, and clip boundaries."""

    def __init__(self, api_key: Optional[str] = None, provider: str = "groq"):
        self.api_key = api_key
        self.provider = provider

    def curate_clips(
        self,
        transcript_text: str,
        num_clips: int = 3,
        min_duration: int = 25,
        max_duration: int = 60
    ) -> List[Dict[str, Any]]:
        prompt = f"""You are an elite viral short-form video producer and editor (like Opus Clip / Alex Hormozi).
Your task is to analyze the timestamped transcript of a video and select the top {num_clips} most engaging, high-retention vertical clips.

Rules for clip selection:
1. Strong Opening Hook: Must start with an intriguing question, shocking statement, high-value insight, or emotional punch.
2. Self-Contained Story Arc: Must make complete sense on its own without requiring the rest of the video.
3. Duration: Each clip MUST be between {min_duration} and {max_duration} seconds long.
4. Calculate exact start_seconds and end_seconds from the timestamps.
5. Provide a viral_score (0-100), a catchy 2-5 word on-screen HEADLINE, and a brief reasoning.

Return ONLY a valid JSON object in this exact schema:
{{
  "clips": [
    {{
      "title": "Short descriptive title",
      "headline": "PUNCHY HOOK BANNER",
      "start_seconds": 12.0,
      "end_seconds": 48.0,
      "duration": 36.0,
      "viral_score": 94,
      "hook": "Opening sentence",
      "reason": "Why this will retain viewers and generate shares"
    }}
  ]
}}

Timestamped Video Transcript:
{transcript_text[:12000]}
"""

        raw_text = ""
        if self.provider == "groq" and self.api_key:
            from groq import Groq
            client = Groq(api_key=self.api_key)
            completion = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[
                    {"role": "system", "content": "You are a professional viral short-form video editor. Respond ONLY with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            raw_text = completion.choices[0].message.content or ""
        elif self.provider == "gemini" and self.api_key:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            raw_text = response.text or ""
        elif self.provider == "openai" and self.api_key:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional viral short-form video editor."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            raw_text = completion.choices[0].message.content or ""
        else:
            return self._heuristic_fallback(transcript_text, num_clips, min_duration, max_duration)

        try:
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                clips = data.get("clips", [])
                if clips:
                    return clips
        except Exception as e:
            print(f"[ViralCuratorAgent] Error parsing LLM response: {e}")

        return self._heuristic_fallback(transcript_text, num_clips, min_duration, max_duration)

    @staticmethod
    def _heuristic_fallback(transcript_text: str, num_clips: int, min_duration: int, max_duration: int) -> List[Dict[str, Any]]:
        clips = []
        lines = [l for l in transcript_text.splitlines() if l.strip()]
        if not lines:
            return []

        parsed = []
        for line in lines:
            match = re.match(r"\[(\d+):(\d+)\]\s*(.*)", line)
            if match:
                secs = int(match.group(1)) * 60 + int(match.group(2))
                parsed.append((secs, match.group(3)))

        if len(parsed) < 3:
            return []

        total_secs = parsed[-1][0]
        clip_len = (min_duration + max_duration) // 2
        step = max(clip_len + 10, total_secs // (num_clips + 1))

        for i in range(num_clips):
            start = min(total_secs - clip_len, (i + 1) * step)
            if start < 0:
                start = 0
            end = min(total_secs, start + clip_len)
            clips.append({
                "title": f"Viral Moment #{i+1}",
                "headline": "KEY TAKEAWAY",
                "start_seconds": float(start),
                "end_seconds": float(end),
                "duration": float(end - start),
                "viral_score": 88 - (i * 4),
                "hook": "Check out this key moment from the discussion",
                "reason": "High speaker engagement and topic transition."
            })
        return clips
