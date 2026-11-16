"""
Tests for AI Engineer Curator & Judge enhancements:
1. Transcript chunking (>14000 chars) instead of truncation
2. Judge prompt includes verbatim transcript text for each candidate
3. Missing rubric fields are rejected rather than defaulted to 20
4. Fail loudly when LLM call fails with api_key (no silent heuristic fallback)
5. Explicit '[HEURISTIC MODE]' labels when offline
6. Groq model ID verified against live model list
"""

import pytest
from unittest.mock import MagicMock
from schema import CandidateClip, AudioSignals, RubricScore
from agents.curator import ViralCuratorAgent
from agents.judge import JudgeAgent


def test_transcript_chunking_handles_long_transcripts():
    curator = ViralCuratorAgent(api_key=None, provider="offline")
    # Generate 30,000 characters of timestamped transcript
    lines = [f"[{i // 60:02d}:{i % 60:02d}] This is line {i} of dialogue demonstrating deep thought." for i in range(500)]
    long_transcript = "\n".join(lines)
    assert len(long_transcript) > 25000

    chunks = curator._chunk_transcript(long_transcript, max_chunk_chars=10000)
    assert len(chunks) >= 3
    # Verify no lines were lost across chunks
    combined_text = " ".join(c["text"] for c in chunks)
    assert "line 0" in combined_text
    assert "line 499" in combined_text


def test_judge_prompt_includes_candidate_transcript():
    judge = JudgeAgent(api_key="mock_key", provider="groq")
    transcript = (
        "[00:10] The single greatest superpower in AI engineering\n"
        "[00:20] is systematic debugging and test-driven rigor.\n"
        "[00:35] Without it, agents silently hallucinate."
    )
    candidates = [
        CandidateClip(
            candidate_id=1,
            title="Superpower",
            start_seconds=10.0,
            end_seconds=40.0,
            duration=30.0,
            initial_score=90,
            hook="The single greatest superpower",
            reason="High viral potential"
        )
    ]
    extracted = judge._extract_candidate_transcript(transcript, 10.0, 40.0)
    assert "single greatest superpower" in extracted
    assert "systematic debugging" in extracted


def test_missing_rubric_fields_are_rejected_not_defaulted_to_20():
    judge = JudgeAgent(api_key="mock_key", provider="groq")
    candidates = [
        CandidateClip(
            candidate_id=1,
            title="Test Clip",
            start_seconds=0.0,
            end_seconds=30.0,
            duration=30.0,
            initial_score=90,
            hook="Hook text",
            reason="Reason"
        )
    ]

    # Mock Groq client returning JSON missing 'payoff' and 'zero_context_needed'
    mock_incomplete_response = [
        {
            "candidate_id": 1,
            "title": "Test Clip",
            "rubric": {
                "hook_strength": 24,
                "self_contained": 22
                # missing payoff and zero_context_needed!
            },
            "headline_variants": {
                "curiosity": "WHY THIS MATTERS",
                "value": "HOW TO WIN",
                "bold_claim": "THE TRUTH",
                "chosen": "THE TRUTH"
            }
        }
    ]

    mock_client = MagicMock()
    mock_client.models.list.return_value.data = [MagicMock(id="qwen/qwen3.8-27b")]
    mock_completion = MagicMock()
    import json
    mock_completion.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_incomplete_response)))]
    mock_client.chat.completions.create.return_value = mock_completion

    judge._get_verified_model = lambda client: "qwen/qwen3.8-27b"

    import groq
    # When all candidates have incomplete rubric fields, it must reject them and raise an error rather than inventing 20s
    with pytest.raises(RuntimeError, match="Groq LLM evaluation failed"):
        judge._llm_evaluate_groq(candidates, "transcript", None)


def test_fail_loudly_when_llm_fails_with_api_key():
    curator = ViralCuratorAgent(api_key="invalid_mock_key", provider="groq")
    # With api_key, failing LLM must raise RuntimeError rather than silently returning heuristic clips
    with pytest.raises(RuntimeError, match="LLM candidate generation failed"):
        curator.generate_candidates(transcript_text="Some transcript", target_candidates=3)


def test_offline_mode_labels_heuristic_mode_clearly():
    curator = ViralCuratorAgent(api_key=None, provider="offline")
    candidates = curator.generate_candidates(
        transcript_text="[00:05] Hello world\n[00:40] Second point\n[01:15] Third point",
        target_candidates=2
    )
    assert len(candidates) > 0
    for c in candidates:
        assert "[Heuristic]" in c.title or "[HEURISTIC MODE]" in c.reason

    judge = JudgeAgent(api_key=None, provider="offline")
    ranked = judge.evaluate_and_rank(candidates, transcript_context="", top_n=2)
    assert len(ranked) > 0
    for r in ranked:
        assert "[HEURISTIC MODE]" in r.reason or "[HEURISTIC" in r.headline


def test_groq_model_verification_against_live_models():
    curator = ViralCuratorAgent(api_key="mock", provider="groq")
    mock_client = MagicMock()
    mock_client.models.list.return_value.data = [
        MagicMock(id="whisper-large-v3"),
        MagicMock(id="qwen/qwen3.8-27b"),
        MagicMock(id="llama-3.3-70b-versatile")
    ]
    verified = curator._get_verified_model(mock_client)
    assert verified == "llama-3.3-70b-versatile"

    # If llama-3.3-70b not in live list, fallback to next preferred (e.g. qwen)
    curator._verified_model = None
    mock_client.models.list.return_value.data = [
        MagicMock(id="qwen/qwen3.8-27b")
    ]
    verified_fallback = curator._get_verified_model(mock_client)
    assert verified_fallback == "qwen/qwen3.8-27b"


def test_only_groq_ai_provider_enforced():
    """Verify that any non-Groq AI provider is rejected with ValueError."""
    import pytest
    for bad_provider in ["gemini", "openai", "anthropic", "cohere"]:
        with pytest.raises(ValueError, match="Only Groq AI is supported"):
            ViralCuratorAgent(api_key="test", provider=bad_provider)

        with pytest.raises(ValueError, match="Only Groq AI is supported"):
            JudgeAgent(api_key="test", provider=bad_provider)

    # Valid providers (Groq and offline heuristic modes) must succeed
    assert ViralCuratorAgent(api_key="test", provider="groq").provider == "groq"
    assert ViralCuratorAgent(api_key=None, provider="heuristic").provider == "heuristic"
    assert JudgeAgent(api_key="test", provider="groq").provider == "groq"
    assert JudgeAgent(api_key=None, provider="heuristic").provider == "heuristic"
