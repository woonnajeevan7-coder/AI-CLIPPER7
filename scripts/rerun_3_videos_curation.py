import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Ensure root workspace is in sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from agents.transcriber import TranscriberAgent
from agents.curator import ViralCuratorAgent
from audio_signals import AudioSignalAnalyzer
from schema import AudioSignals, WordTimestamp, ClipMetadata

def main():
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[ERROR] GROQ_API_KEY is not set.")
        sys.exit(1)

    ffmpeg_bin = str(root_dir / "ffmpeg.exe")
    temp_dir = root_dir / "temp_media"
    temp_dir.mkdir(exist_ok=True)

    transcriber = TranscriberAgent(ffmpeg_bin=ffmpeg_bin, temp_dir=temp_dir)
    curator = ViralCuratorAgent(api_key=api_key, provider="groq")

    test_videos = [
        temp_dir / "test_inputs" / "solo_speaker_full.mp4",
        temp_dir / "test_inputs" / "podcast_2speaker_full.mp4",
        temp_dir / "test_inputs" / "hindi_video_full.mp4"
    ]

    benchmark_results = {}

    for video_path in test_videos:
        video_name = video_path.name
        print(f"\n========================================================")
        print(f"BENCHMARK VIDEO: {video_name}")
        print(f"========================================================")

        if not video_path.exists():
            print(f"[ERROR] Video {video_path} not found.")
            continue

        audio_path = temp_dir / f"{video_path.stem}_bench_audio.mp3"
        print(f"[1/4] Extracting audio to {audio_path.name}...")
        extracted = transcriber.extract_audio(video_path, audio_path)
        if not extracted or not audio_path.exists():
            print(f"[ERROR] Failed to extract audio for {video_name}")
            continue

        print(f"[2/4] Transcribing audio with Groq Whisper Large v3...")
        words = transcriber.transcribe_with_groq_whisper(audio_path, api_key)
        transcript_text = transcriber.words_to_transcript_text(words)
        print(f"   -> Transcribed {len(words)} acoustic words ({len(transcript_text)} characters).")
        print(f"   -> Sample transcript: {transcript_text[:120]}...")

        print(f"[3/4] Analyzing acoustic signals (energy peaks, hook spikes, silence)...")
        audio_signals = AudioSignalAnalyzer.analyze_audio(audio_path=audio_path, words=words)
        print(f"   -> Summary: {audio_signals.summary_text}")

        print(f"[4/4] Curating & Judging clips with ViralCuratorAgent & JudgeAgent...", flush=True)
        t0 = time.time()
        clips = curator.curate_clips(
            transcript_text=transcript_text,
            words=words,
            audio_signals=audio_signals,
            num_clips=3,
            min_duration=20,
            max_duration=45
        )
        elapsed = time.time() - t0
        print(f"   -> Curation & Judging completed in {elapsed:.2f}s. Extracted {len(clips)} top clips.")

        video_summary = {
            "video_name": video_name,
            "word_count": len(words),
            "transcript_char_count": len(transcript_text),
            "audio_signals": {
                "energy_peak_count": len(audio_signals.energy_peaks),
                "laughter_spikes_count": len(audio_signals.laughter_spikes),
                "summary": audio_signals.summary_text
            },
            "clips_count": len(clips),
            "clips": []
        }

        for idx, raw_clip in enumerate(clips, 1):
            clip = ClipMetadata(**raw_clip) if isinstance(raw_clip, dict) else raw_clip
            print(f"\n   [Clip #{idx}] {clip.title}")
            print(f"       Window: {clip.start_seconds:.1f}s -> {clip.end_seconds:.1f}s ({clip.duration:.1f}s)")
            print(f"       Viral Score: {clip.viral_score}/100")
            print(f"       Hook: \"{clip.hook}\"")
            if clip.rubric:
                print(f"       Rubric: Hook={clip.rubric.hook_strength}, SelfContained={clip.rubric.self_contained}, Payoff={clip.rubric.payoff}, ZeroCtx={clip.rubric.zero_context_needed} (Total={clip.rubric.total_score})")
                print(f"       Critique: {clip.rubric.critique}")
            if clip.headline_variants:
                print(f"       Headline Chosen: {clip.headline_variants.chosen}")
                print(f"       Variants: Curiosity='{clip.headline_variants.curiosity}' | Value='{clip.headline_variants.value}' | Bold='{clip.headline_variants.bold_claim}'")

            clip_data = {
                "clip_id": idx,
                "title": clip.title,
                "start_seconds": clip.start_seconds,
                "end_seconds": clip.end_seconds,
                "duration": clip.duration,
                "viral_score": clip.viral_score,
                "hook": clip.hook,
                "headline_chosen": clip.headline_variants.chosen if clip.headline_variants else clip.headline,
                "headline_variants": {
                    "curiosity": clip.headline_variants.curiosity if clip.headline_variants else "",
                    "value": clip.headline_variants.value if clip.headline_variants else "",
                    "bold_claim": clip.headline_variants.bold_claim if clip.headline_variants else ""
                } if clip.headline_variants else None,
                "rubric": {
                    "hook_strength": clip.rubric.hook_strength,
                    "self_contained": clip.rubric.self_contained,
                    "payoff": clip.rubric.payoff,
                    "zero_context_needed": clip.rubric.zero_context_needed,
                    "total_score": clip.rubric.total_score,
                    "critique": clip.rubric.critique
                } if clip.rubric else None
            }
            video_summary["clips"].append(clip_data)

        benchmark_results[video_name] = video_summary

        # Clean up temporary audio file
        if audio_path.exists():
            try:
                audio_path.unlink()
            except Exception:
                pass

        time.sleep(2)

    results_file = temp_dir / "curation_3_videos_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_results, f, indent=2)

    print(f"\n========================================================")
    print(f"SUCCESS: Curation results saved to {results_file}")
    print(f"========================================================")

if __name__ == "__main__":
    main()
