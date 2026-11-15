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
- [ ] **Phase 2: Smart Curation** (Pending)
  - Two-pass selection (Candidate Generator + JudgeAgent re-ranking)
  - Boundary snapping to sentence ends and silences
  - 3 headline variants per clip
  - Multimodal audio signals (librosa energy/laughter)
  - Pydantic output validation
- [ ] **Phase 3: Smart Framing** (Pending)
  - MediaPipe face detection & active speaker tracking
  - Split-screen for 2 speakers
  - PySceneDetect cut transitions
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
