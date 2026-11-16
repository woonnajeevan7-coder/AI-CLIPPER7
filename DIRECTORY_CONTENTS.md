# 📂 AI Clipper Pro — Repository File & Directory Manifest

> Generated on **November 16, 2026** for workspace: `c:\Users\woonn\ai clipping`  
> Complete inventory of all available files, directories, autonomous agents, backend services, and frontend applications.

---

## 1. High-Level Architecture Overview

```
                                      AI CLIPPER PRO
               ┌─────────────────────────────┴─────────────────────────────┐
               ▼                                                           ▼
       [Streamlit Studio]                                         [Next.js 14 Web App]
         (app.py:8501)                                           (frontend/src/app:3000)
    Three.js 3D WebGL Viewport                                  Three.js 3D Canvas Hero
    Word Trimmer & Brand Kit                                   Interactive Transcript Editor
               │                                                           │
               └─────────────────────────────┬─────────────────────────────┘
                                             ▼
                             [ClipperOrchestratorAgent]
                                (agents/orchestrator.py)
                                             │
      ┌───────────────────┬──────────────────┼───────────────────┬───────────────────┐
      ▼                   ▼                  ▼                   ▼                   ▼
TranscriberAgent    ViralCuratorAgent    JudgeAgent       SmartFramingAgent   VideoEditorAgent
(Groq Whisper v3)   (Qwen 3.8-27b LLM) (4-Factor Rubric) (MediaPipe Dual-Mode) (1080x1920 60FPS)
      │                   │                  │                   │                   │
      └───────────────────┴──────────────────┼───────────────────┴───────────────────┘
                                             ▼
                                     [Platform Backend]
                                 FastAPI REST API (/api/v1)
                                Celery Worker · Redis Broker
                                SQLite / PostgreSQL · Cloudflare R2
```

---

## 2. Directory Tree Structure

```
c:\Users\woonn\ai clipping\
├── agents/                       # Specialized Autonomous AI Agents
│   ├── __init__.py               # Agent package exports
│   ├── boundary.py               # BoundarySnapper (sentence ends & pause snapping)
│   ├── curator.py                # ViralCuratorAgent (Groq Qwen 3.8-27b viral moment discovery)
│   ├── editor.py                 # VideoEditorAgent (1080x1920 60FPS NVENC, -14 LUFS 2-pass audio)
│   ├── feedback.py               # MoatFeedbackEngine (features, predicted vs actual retention ranker)
│   ├── framing.py                # SmartFramingAgent (MediaPipe face tracking, split-screen, deadband hysteresis)
│   ├── growth.py                 # MultiLanguageEngine & Official OAuth Publisher (Shorts/TikTok/Reels)
│   ├── judge.py                  # JudgeAgent (Pass-2 evaluator with 4-factor rubric & headline variants)
│   ├── orchestrator.py           # ClipperOrchestratorAgent (master pipeline coordinator & event stream)
│   ├── polish.py                 # KeywordEmojiTagger, PunchInPlanner, AudioPolisher
│   └── transcriber.py            # TranscriberAgent (Groq Whisper Large-v3 Turbo + 25MB auto-chunker)
├── backend/                      # Enterprise Platform Backend (FastAPI / Celery / SQLAlchemy)
│   ├── __init__.py               # Backend package initializer
│   ├── app.py                    # FastAPI application instance & middleware registration
│   ├── auth.py                   # JWT security, password hashing, OAuth & refresh token lifecycle
│   ├── config.py                 # Pydantic settings & environment configuration
│   ├── database.py               # SQLAlchemy database session & engine
│   ├── models.py                 # Relational database models (User, Project, Job, Clip, Plan, Usage)
│   ├── security.py               # SSRFGuard (domain allowlist, loopback/private IP blocking)
│   ├── sse.py                    # Server-Sent Events (SSE) live pipeline telemetry stream
│   ├── storage.py                # Cloudflare R2 / S3 presigned upload & download manager
│   ├── tasks.py                  # Celery idempotent background worker tasks
│   ├── telemetry.py              # Structured logging, request IDs, and Sentry hooks
│   └── routes/                   # FastAPI REST API Route Controllers (/api/v1)
│       ├── __init__.py           # Routes package export
│       ├── auth.py               # /api/v1/auth (register, login, refresh, me)
│       ├── clips.py              # /api/v1/clips (clip retrieval & streaming)
│       ├── jobs.py               # /api/v1/jobs (job progress & status)
│       ├── legal.py              # /api/v1/legal (DMCA takedown notice submission)
│       ├── projects.py           # /api/v1/projects (project ingestion & job creation)
│       └── usage.py              # /api/v1/usage (plans, tier quotas, and billing records)
├── frontend/                     # Modern Next.js 14 Production Web Application
│   ├── package.json              # Node.js dependencies (React 18, Next 14, Three.js, Tailwind)
│   ├── postcss.config.js         # PostCSS configuration for Tailwind CSS
│   ├── tailwind.config.js        # Tailwind styling & theme tokens
│   ├── tsconfig.json             # TypeScript compiler settings
│   └── src/app/                  # Next.js App Router
│       ├── layout.tsx            # Global HTML root layout & dark theme wrapper
│       ├── globals.css           # Global Tailwind directives & dark mode variables
│       ├── page.tsx              # Landing & Home dashboard with 3D WebGL hero
│       ├── components/
│       │   └── Hero3DCanvas.tsx  # Interactive Three.js 3D WebGL Phone Hologram with orbit controls
│       └── editor/
│           └── page.tsx          # Interactive transcript-based word trimmer & 9:16 preview
├── models/                       # Computer Vision Weights & Haar Cascades
│   ├── blaze_face_short_range.tflite # MediaPipe Face Detection model
│   └── haarcascade_frontalface_default.xml # OpenCV fallback frontal face cascade
├── tests/                        # Automated Pytest Suite (39/39 Passing Tests)
│   ├── test_phase1_captions_audio.py         # Word timestamps, ASS karaoke, -14 LUFS loudnorm, 60FPS NVENC
│   ├── test_phase2_smart_curation.py         # Boundary snapping, acoustic signals, judge rubric, score gating
│   ├── test_phase3_smart_framing.py          # MediaPipe face tracking, split screen, dual-mode smoothing
│   ├── test_phase4_motion_polish.py          # Punch-in zooms, keyword/emoji tagging, audio polisher
│   ├── test_phase5_platform_backend.py       # SSRF protection, JWT lifecycle, health & auth endpoints
│   ├── test_phase6_product_frontend.py       # Streamlit tabs, secure I/O, Next.js page structure
│   ├── test_phase7_growth_features.py        # Multi-language Indic support, official OAuth payloads
│   ├── test_phase8_feedback_loop.py          # Clip feature vectors, moat predicted vs actual ranker
│   └── test_phase9_production_hardening.py   # Cost tracking, request ID middleware, DMCA endpoints, CI
├── fonts/                        # TrueType Typography for Karaoke Captions
│   ├── KomikaAxis.ttf            # High-energy bold viral captions (Hormozi style)
│   ├── Montserrat-Bold.ttf       # Clean modern sans-serif captions
│   └── TheBoldFont.ttf           # Punchy headline typography
├── assets/                       # Static UI Icons & Assets
├── output_clips/                 # Rendered 1080x1920 60FPS Vertical Shorts (.mp4)
├── temp_media/                   # Temporary pipeline storage (downloaded audio/video segments)
├── .env                          # Local secrets (Active Groq API Key & configurations)
├── .env.example                  # Environment variable template
├── .gitignore                    # Git tracking ignore rules
├── ai_clipper.py                 # High-level Python programmatic CLI & API entry point
├── app.py                        # Streamlit Enterprise Studio with 3D WebGL & live telemetry
├── audio_signals.py              # Librosa acoustic signal analysis (laughter, energy peaks, speech rate)
├── captions.py                   # Subtitle generation (ASS karaoke highlight & collision avoidance)
├── docker-compose.yml            # Multi-container orchestration (api, worker, redis, postgres)
├── Dockerfile                    # Container definition with FFmpeg, Python 3.13, and GPU tools
├── ffmpeg.exe                    # Hardware-accelerated local FFmpeg binary
├── ffprobe.exe                   # Local FFprobe media stream analysis binary
├── PROGRESS.md                   # Comprehensive 9-phase progress log & benchmark gap reports
├── requirements.txt              # Production Python package dependencies
├── run_clipit.bat                # Windows batch launcher for Streamlit Studio
├── schema.py                     # Pydantic typed data contracts (WordTimestamp, CandidateClip, etc.)
└── verify_system.py              # Diagnostic validation script for system hardware & APIs
```

---

## 3. Detailed File Directory & Descriptions

### Root Scripts & Applications

| File | Purpose | Key Details |
|---|---|---|
| `app.py` | **Streamlit Web Studio** | The primary interactive GUI. Features an interactive **Three.js 3D WebGL Neural Engine Hero**, high-contrast white telemetry log cards, transcript word trimmer, brand kit customization, and billing tiers. |
| `ai_clipper.py` | **Unified Facade API** | High-level import interface wrapping `TranscriberAgent`, `ViralCuratorAgent`, and `VideoEditorAgent` for programmatic Python workflows. |
| `captions.py` | **ASS Karaoke Subtitle Engine** | Generates Advanced SubStation Alpha (`.ass`) subtitles with word-by-word karaoke highlights (`\k`), safe-area positioning ($Y \approx 1350\text{px}$), and 3 visual presets (`hormozi`, `cyber_cyan`, `emerald_box`). |
| `audio_signals.py` | **Multimodal Acoustic Analyzer** | Extracts audio energy peaks (RMS), laughter candidate segments, and speech rate tempo metrics using `librosa`. |
| `schema.py` | **Typed Domain Contracts** | Pydantic data schemas: `WordTimestamp`, `CandidateClip`, `RubricScore`, `HeadlineVariants`, `ClipMetadata`, and `AudioSignals`. |
| `verify_system.py` | **System Diagnostics** | Validates GPU acceleration (`h264_nvenc`), Groq LPU API connection, YouTube ingestion, and subtitle fonts. |
| `docker-compose.yml` | **Container Orchestration** | Defines services for `api` (FastAPI), `worker` (Celery), `redis` (task broker), and `postgres` (database). |
| `Dockerfile` | **Production Container** | Debian-based container with FFmpeg, Python dependencies, and font configuration. |
| `PROGRESS.md` | **Engineering Log** | Records build status, benchmark tables for 3 real videos, latency measurements, and known gaps. |
| `requirements.txt` | **Dependencies** | Python library requirements (`fastapi`, `celery`, `groq`, `mediapipe`, `librosa`, `opencv-python`, etc.). |
| `ffmpeg.exe` / `ffprobe.exe`| **Local Video Toolchain** | Pre-bundled Windows binaries for hardware-accelerated video compositing and stream probing. |

---

### Autonomous Agent Suite (`agents/`)

| File | Agent Name | Core Responsibility |
|---|---|---|
| `agents/orchestrator.py` | `ClipperOrchestratorAgent` | Central coordinator orchestrating stages 1–5; yields live telemetry events (`progress`, `status`, `result`). |
| `agents/transcriber.py` | `TranscriberAgent` | Ingests YouTube URLs or local video files, extracts audio, transcribes with **Groq Whisper Large-v3**, and automatically segments audio $> 25\text{MB}$ into 10-min chunks. |
| `agents/curator.py` | `ViralCuratorAgent` | Pass-1 discovery agent producing 10–15 candidate clips via **Groq Qwen 3.8-27b** LLM with acoustic signal fusion. |
| `agents/judge.py` | `JudgeAgent` | Pass-2 auditor re-ranking candidate clips on a 4-factor rubric (Hook, Self-Contained, Payoff, Zero Context) with explicit $\ge 75$ score gating and 3 headline variants. |
| `agents/boundary.py` | `BoundarySnapper` | Snaps rough start/end timestamps to nearest sentence boundaries (`.`, `!`, `?`) and silences, avoiding mid-word cuts. |
| `agents/framing.py` | `SmartFramingAgent` | Detects faces using **MediaPipe Tasks** with dual-mode smoothing (static median crop for stationary speakers, deadband hysteresis for moving speakers) and 2-speaker split-screen with 4px divider. |
| `agents/editor.py` | `VideoEditorAgent` | Renders vertical 1080x1920 60FPS video using **NVIDIA NVENC** (`h264_nvenc`) with two-pass EBU R128 audio normalization targeting $-14\text{ LUFS}$. |
| `agents/polish.py` | `KeywordEmojiTagger` / `PunchInPlanner` | Tags viral keywords/emojis for subtitle emphasis, plans 1.14x punch-in zooms, and ducks background music during speech. |
| `agents/growth.py` | `MultiLanguageEngine` / `OfficialPublisherAgent` | Multi-language Indic support (Hindi, Telugu, Tamil) and official OAuth publishing payloads for YouTube Shorts, TikTok, and Instagram Reels. |
| `agents/feedback.py` | `MoatFeedbackEngine` | Stores clip feature vectors, pulls live viewer metrics, and trains predicted vs. actual retention rankers. |

---

### Platform Backend (`backend/`)

| File | Purpose |
|---|---|
| `backend/app.py` | FastAPI application factory, CORS setup, request ID middleware, and exception handlers. |
| `backend/auth.py` | Password hashing with bcrypt, JWT access/refresh token generation, and user authentication dependencies. |
| `backend/config.py` | Pydantic settings loading from `.env` (JWT secrets, database URL, Redis URL, R2 credentials). |
| `backend/database.py` | SQLAlchemy database engine and `get_db` session provider. |
| `backend/models.py` | ORM entities: `User`, `Project`, `Job`, `Transcript`, `Clip`, `Plan`, `Usage`, `PublishTarget`, `ClipMetric`. |
| `backend/security.py` | `SSRFGuard` verifying ingest URLs against trusted domains and blocking private/loopback IP addresses. |
| `backend/sse.py` | SSE streaming endpoint broadcasting live pipeline events to connected clients. |
| `backend/storage.py` | Cloudflare R2 / S3 client generating presigned upload/download URLs. |
| `backend/tasks.py` | Idempotent Celery tasks with exponential-backoff retries for background video processing. |
| `backend/telemetry.py` | Sentry integration, request tracing, and structured cost accounting (tokens, transcription, render time). |
| `backend/routes/auth.py` | Endpoints for user registration, login, token refresh, and profile inspection. |
| `backend/routes/projects.py` | Project creation with quota checks, YouTube URL validation, and job dispatching. |
| `backend/routes/jobs.py` | Endpoint polling job status and stage progress. |
| `backend/routes/clips.py` | Endpoints for fetching rendered clips and downloading MP4 files. |
| `backend/routes/usage.py` | Endpoints listing tier plans (`free`, `pro`, `agency`) and current monthly quota usage. |
| `backend/routes/legal.py` | Endpoints for terms of service, privacy policy, and DMCA copyright infringement notice submission. |

---

### Next.js 14 Web Application (`frontend/`)

| File | Purpose |
|---|---|
| `frontend/src/app/page.tsx` | Main dashboard with URL ingest bar, viral clips gallery, and embedded 3D hero. |
| `frontend/src/app/layout.tsx` | Root layout with dark mode styles and SEO metadata. |
| `frontend/src/app/globals.css` | Tailwind CSS configuration and dark theme CSS variables. |
| `frontend/src/app/components/Hero3DCanvas.tsx` | Hardware-accelerated **Three.js WebGL 3D Canvas** with floating 9:16 smartphone, live face-tracking simulation, audio spectrum bars, and drag-to-orbit controls. |
| `frontend/src/app/editor/page.tsx` | **Transcript-Based Word Trimmer**: lets users click individual words to omit dead air, with live 9:16 preview and headline customizer. |

---

### Automated Test Suite (`tests/`)

All **39 tests** pass cleanly with zero deprecation warnings:

| Test File | Phase Covered | What is Verified |
|---|---|---|
| `test_phase1_captions_audio.py` | Phase 1 | Word grouping, ASS formatting, 60FPS NVENC, -14 LUFS audio, 25MB chunking |
| `test_phase2_smart_curation.py` | Phase 2 | Sentence/pause boundary snapping, audio signals, judge rubric, score gating ($\ge 75$) |
| `test_phase3_smart_framing.py` | Phase 3 | MediaPipe detection, single face EMA crop, dual-mode walking/stationary, 2-speaker split |
| `test_phase4_motion_polish.py` | Phase 4 | Keyword/emoji tagger, punch-in zooms, audio ducking, silence trimming |
| `test_phase5_platform_backend.py` | Phase 5 | SSRF guard (blocks loopback/private IPs), JWT lifecycle, FastAPI health & auth |
| `test_phase6_product_frontend.py` | Phase 6 | Streamlit tab configuration, safe file reading, Next.js page structure |
| `test_phase7_growth_features.py` | Phase 7 | Indic multi-language (Hindi/Telugu/Tamil), YouTube/TikTok/Reels publisher payloads |
| `test_phase8_feedback_loop.py` | Phase 8 | Clip feature extraction, retention sync, predicted vs actual correlation ranker |
| `test_phase9_production_hardening.py`| Phase 9 | Cost tracker, request ID middleware, DMCA takedown endpoints, CI configuration |

---

## 4. How to Run the Platform

### Option A: Streamlit Studio (Active on Port 8501)
```powershell
python -m streamlit run app.py --server.port 8501
```
Access at: [http://localhost:8501](http://localhost:8501)

### Option B: Next.js Web Frontend (Port 3000)
```powershell
cd frontend
npm run dev
```
Access at: [http://localhost:3000](http://localhost:3000)

### Option C: FastAPI REST API (Port 8000)
```powershell
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```
Interactive API docs at: [http://localhost:8000/docs](http://localhost:8000/docs)

### Option D: Run Full Test Suite
```powershell
pytest -v
```
