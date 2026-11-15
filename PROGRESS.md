# AI Clipper Pro — Build & Progress Tracking

## Overall Project Roadmap

- [x] **Phase 1: Captions & Audio Polish** (COMPLETED)
  - [x] Word-level timestamp propagation through the full pipeline
  - [x] `captions.py`: ASS generator with word-by-word karaoke highlight
  - [x] 3 distinct caption style presets (Hormozi, CyberCyan, EmeraldBox)
  - [x] Safe-area collision avoidance (margin_v=460 never collides with headline banner at y=240)
  - [x] FFmpeg burn-in with `subtitles` filter + EBU R128 `-14 LUFS` audio normalization (`loudnorm`)
  - [x] +faststart flag, H.264, yuv420p, AAC
  - [x] Comprehensive unit tests with pytest & ffprobe verification passed
- [x] **Phase 2: Smart Curation** (COMPLETED)
  - [x] Two-pass selection (Candidate Generator produces 10-15 candidates + JudgeAgent re-ranking)
  - [x] Boundary snapping to sentence ends and silences via `BoundarySnapper`
  - [x] 3 headline variants per clip (Curiosity, Value, Bold Claim) with optimal selection
  - [x] Multimodal audio signals (librosa energy, laughter, and speech-rate)
  - [x] Strict Pydantic output validation (`RubricScore`, `HeadlineVariants`, `CandidateClip`, `ClipMetadata`) with retry on invalid JSON
- [x] **Phase 3: Smart Framing** (COMPLETED)
  - [x] MediaPipe & OpenCV face tracking with EMA-smoothed 9:16 crop window
  - [x] PySceneDetect cut detection to reset EMA at camera switches
  - [x] 2-speaker vertical split-screen composition (1080x960 each)
  - [x] Seamless fallback to ambient Gaussian blur layout when no face is found
  - [x] Unit tests and FFmpeg rendering pipeline verified
- [x] **Phase 4: Motion & Polish** (COMPLETED)
  - [x] Punch-in zooms (1.14x) at sentence starts and emphasis moments
  - [x] Keyword & emoji highlights in ASS karaoke subtitles (`VIRAL_EMOJI_LEXICON`)
  - [x] Silence trimming filter (`silenceremove`)
  - [x] Background music ducking filter graph (`volume` + `amix`)
  - [x] Pytest suite covering all motion and polish features passing
- [x] **Phase 5: Platform Backend** (COMPLETED)
  - [x] FastAPI REST API (`/api/v1`) with JWT auth, refresh tokens, and user profile inspection
  - [x] Idempotent Celery tasks with exponential-backoff retries and dead-letter state
  - [x] Complete PostgreSQL models (users, projects, jobs, transcripts, clips, plans, usage, publish_targets, clip_metrics)
  - [x] Cloudflare R2 / S3 storage with presigned URLs and local fallback
  - [x] Server-Sent Events (SSE) live progress stream (`/api/v1/jobs/{id}/stream`)
  - [x] Multi-tier plan limits (Free, Pro, Agency) and usage tracking
  - [x] Rigorous SSRF protection blocking private, loopback, link-local IPs and untrusted domains
  - [x] Production Docker Compose (api, worker, redis, postgres) and Dockerfile
- [x] **Phase 6: Product Frontend** (COMPLETED)
  - [x] Streamlit Studio upgraded with 4 production tabs (Studio, Transcript Editor, Brand Kit, Billing)
  - [x] Transcript-based video trimming (click words to adjust timestamps and re-render)
  - [x] Brand Kit management (logo watermark, accent color picker, typography presets)
  - [x] Stripe-ready pricing cards and monthly quota visualization
  - [x] Next.js 14 web application structure in `frontend/` (Landing, Editor, Brand Kit, Pricing)
  - [x] Dark-mode first, glassmorphism, responsive UI with loading/error states
- [x] **Phase 7: Growth Features** (COMPLETED)
  - [x] Multi-language support: Hindi (`hi`), Telugu (`te`), Tamil (`ta`), Spanish (`es`), Portuguese (`pt`)
  - [x] Multilingual transcription via Whisper large-v3 & translation engine
  - [x] `ChannelWatcherAgent` for monitoring YouTube channels and auto-clipping new uploads
  - [x] `OfficialPublisherAgent` for automated scheduling via official YouTube Data API v3, TikTok, and Instagram Reels APIs
  - [x] Unit test suite covering all growth features passing
- [ ] **Phase 8: Feedback Loop & Moat** (Pending)
  - Real performance tracking & curator optimization ranker
- [ ] **Phase 9: Production Hardening** (Pending)
  - Sentry, NVENC parallel GPU paths, rate limiting, and test suite

---

## Phase 1 Status
- **Branch**: `phase-1-captions-audio`
- **Machine & Environment Inspection**: Completed
- **Plan**: Prepared and awaiting approval to implement
