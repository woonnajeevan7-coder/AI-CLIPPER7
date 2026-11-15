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
- [ ] **Phase 4: Motion & Polish** (Pending)
  - Dynamic punch-in zooms
  - LLM keyword & emoji highlights
  - Silence trimming & background music ducking
- [ ] **Phase 5: Platform Backend** (Pending)
  - FastAPI `/api/v1` + Celery/Redis
  - PostgreSQL + Cloudflare R2 storage
  - SSE real-time pipeline telemetry
- [ ] **Phase 6: Product Frontend** (Pending)
  - Next.js dashboard + transcript-based video trimming editor
- [ ] **Phase 7: Growth Features** (Pending)
  - Multi-language (Hindi, Telugu, Tamil) & auto-publisher APIs
- [ ] **Phase 8: Feedback Loop & Moat** (Pending)
  - Real performance tracking & curator optimization ranker
- [ ] **Phase 9: Production Hardening** (Pending)
  - Sentry, NVENC parallel GPU paths, rate limiting, and test suite

---

## Phase 1 Status
- **Branch**: `phase-1-captions-audio`
- **Machine & Environment Inspection**: Completed
- **Plan**: Prepared and awaiting approval to implement
