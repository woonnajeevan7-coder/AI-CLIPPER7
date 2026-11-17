# Live Clipper Architecture Specification (`docs/LIVE_ARCH.md`)

> **Document Status:** Planning & Architectural Blueprint  
> **Target Subsystem:** Live Stream Recording, Continuous Highlight Extraction & Real-Time 9:16 Shorts Rendering  
> **Compliance:** Strict adherence to *Live Clipper Rules* (FastAPI + Celery/Redis + SQLAlchemy; Next.js 14 + TS + Tailwind; Asyncio supervisor in `live/`; Fernet token encryption at rest; Mandatory `rights_confirmed=true`; No mock data; Full test verification).

---

## 1. Existing Modules Reusable for Live Clipping

The existing codebase contains a battle-tested, modular AI clipping squad and hardware-accelerated rendering pipeline. None of these core capabilities need to be reinvented; they will be reused directly:

| Module / Component | Path | Current Responsibility | Reuse Plan for Live Clipper |
| :--- | :--- | :--- | :--- |
| **`ViralCuratorAgent`** | `agents/curator.py` | Pass-1 viral candidate extraction via Groq LPU LLMs (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`) with multimodal audio signals & Pydantic validation. | Evaluates rolling live transcript windows (e.g. 120s sliding window) to detect viral spikes, punchlines, and narrative tension in live streams. |
| **`JudgeAgent`** | `agents/judge.py` | 4-pillar rubric evaluation (Hook, Engagement, Flow, Value), generating viral scores (0-100), headline variants, hook explanations, and rationales. | Acts as the quality gate on live candidate clips. Only candidates scoring above threshold (e.g., $\ge 80$) are queued for Celery 9:16 rendering. |
| **`BoundarySnapper`** | `agents/boundary.py` | Micro-timing boundary alignment snapping coarse timestamps to natural sentence beginnings, question pauses, and vocal silences ($\ge 0.35\text{s}$). | Prevents awkward mid-sentence cuts when live stream segment chunks are partitioned; snaps live highlight boundaries to coherent thoughts. |
| **`SmartFramingAgent`** | `agents/framing.py` | MediaPipe face detection, OpenCV Haar Cascade fallback, EMA-smoothed crop smoothing ($\alpha = 0.15$), PySceneDetect shot cuts, and Sports/Gaming Action-Crop. | Applied directly to cut highlight segments to generate optimal 9:16 vertical crop plans (face tracking or widescreen action crop). |
| **`captions.py`** | `captions.py` | Word-by-word karaoke ASS subtitle compiler with safe-area positioning (`margin_v: 460`) and visual presets (`hormozi`, `cyber_cyan`, `sports_gaming`). | Compiles animated subtitles with active word highlight tags (`\k`) for the generated live highlight clips. |
| **`VideoEditorAgent`** | `agents/editor.py` | Hardware-accelerated GPU export (NVIDIA NVENC, AMD AMF, Intel QSV), dynamic headline banners, punch-in zooms, audio ducking, and EBU R128 loudness normalization. | Executes the final composite render of the isolated highlight in Celery worker processes. |
| **`StorageManager`** | `backend/storage.py` | S3 / Cloudflare R2 client with local filesystem fallback (`temp_media/r2_local`) and presigned download URL generation. | Persists rendered live highlight MP4s and recorded segment media to object storage. |
| **`TranscriberAgent`** | `agents/transcriber.py` | Groq Whisper Large v3 Turbo speech-to-text with word-level timestamps and audio extraction via FFmpeg. | Transcribes incremental live audio chunks (`LiveSegment` audio) and accumulates timeline offsets ($t_{\text{offset}} = t_{\text{start}}$). |
| **`job_progress_sse_stream`** | `backend/sse.py` | Server-Sent Events (SSE) telemetry generator for real-time frontend status updates. | Extended to support live session telemetry (`live_session_sse_stream`) streaming recorder health, segment count, and newly ready highlight clips. |
| **`SSRFGuard`** | `backend/security.py` | URL scheme validation, DNS resolution, and blocking of private, loopback, and link-local IP addresses. | Validates inbound live stream ingest URLs before any network socket or recorder process is launched. |
| **`get_current_user`** | `backend/auth.py` | JWT authentication dependency verifying bearer tokens against active database users. | Enforces user identity and tenant ownership checks across all live capture and session management endpoints. |

---

## 2. Gap Analysis (What is Missing for Live Clipping)

While VOD processing is complete, live streaming introduces real-time streaming dynamics that require dedicated infrastructure:

```
+-------------------------------------------------------------------------------------------------------+
|                                          CURRENT ARCHITECTURE                                          |
|                                                                                                       |
|  [Static VOD / YouTube URL] ---> [FastAPI /projects] ---> [Celery process_pipeline_task]             |
|                                                                    |                                  |
|                                                        +-----------+-----------+                      |
|                                                        | One-shot batch pipeline|                      |
|                                                        +-----------------------+                      |
|                                                                                                       |
+-------------------------------------------------------------------------------------------------------+
                                                     |
                                                     v  (MISSING INFRASTRUCTURE)
+-------------------------------------------------------------------------------------------------------+
|                                           REQUIRED LIVE ARCHITECTURE                                  |
|                                                                                                       |
|  [Live Ingest: RTMP/HLS/YT]                                                                           |
|             |                                                                                         |
|             v                                                                                         |
|  [Asyncio Supervisor (live/)]  <--- Long-lived process (NOT Celery)                                   |
|             |                                                                                         |
|             +---> Rolling Chunks (LiveSegment: 60s TS/MP4)                                            |
|             |                                                                                         |
|             v                                                                                         |
|  [Celery Worker Pool]          <--- Dispatched per segment / rolling window                           |
|             |                                                                                         |
|             +---> Incremental Whisper Transcription (Cumulative Timestamps)                           |
|             +---> Sliding Window ViralCuratorAgent + JudgeAgent                                       |
|             +---> SmartFramingAgent + VideoEditorAgent (9:16 NVENC Render)                            |
|             +---> Storage Upload + Clip Persistence (source="highlight")                             |
|             |                                                                                         |
|             v                                                                                         |
|  [SSE Telemetry Stream]        ---> Next.js 14 Live Studio (Real-time clip alerts)                    |
+-------------------------------------------------------------------------------------------------------+
```

### Missing Components Detailed:
1. **Asyncio Stream Supervisor (`live/` directory)**:
   - Long-lived processes must not run inside Celery (violates Rule 3). Celery tasks have worker timeouts and are designed for finite, discrete jobs.
   - Missing: An asynchronous daemon supervisor that launches, monitors, and restarts FFmpeg / streamlink capture processes, managing rolling segment output (`-f segment -segment_time 60`).
2. **Database Entities for Live Sessions & Segments**:
   - The database only models static `Project`, `Job`, `Transcript`, and `Clip`.
   - Missing: `LiveSession` entity (mapped from Streams) and `LiveSegment` entity (mapped from StreamSegments).
   - Missing: `Clip.source` enum/string column (`"fixed"` vs `"highlight"`) to distinguish VOD manual/batch clips from automated live stream highlights.
3. **Sliding-Window Transcript Buffer**:
   - Current curation processes a static, finite transcript. Live streams generate a continuous, unbounded transcript stream.
   - Missing: A rolling buffer that aggregates consecutive `LiveSegment` words (e.g. current 60s segment + previous 60s segment = 120s window) to ensure moments spanning segment boundaries are not fragmented.
4. **Token Encryption at Rest (Fernet)**:
   - Rule 4 requires: `Secrets only from server env. Tokens encrypted at rest (Fernet)`.
   - `PublishTarget` currently stores third-party OAuth access/refresh tokens in raw plaintext.
   - Missing: A cryptographic helper in `backend/security.py` using Python's `cryptography.fernet.Fernet` with an environment-backed key (`FERNET_ENCRYPTION_KEY`).
5. **Mandatory Rights Confirmation Enforcement**:
   - Rule 5 requires: `require rights_confirmed=true when starting any capture`.
   - Missing: Request schema validation and database-level enforcement that rejects any capture where `rights_confirmed != True`.
6. **Live Studio UI in Next.js**:
   - `frontend/src/app/` has pages for static editing, billing, and project lists, but no live dashboard.
   - Missing: `frontend/src/app/live/page.tsx` with live stream preview, recorder controls, active segment counter, rights confirmation toggle, and dynamic SSE-fed highlight shorts grid.

---

## 3. Exact File, Model, and Endpoint Additions

The new live clipping capabilities will map onto the existing project structure without breaking any existing VOD workflows:

### A. Database Schema Modifications (`backend/models.py`)

#### 1. `LiveSession` (Mapped from Streams)
```python
class LiveSession(Base):
    __tablename__ = "live_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    stream_url = Column(Text, nullable=False)
    platform = Column(String(50), default="custom")  # 'youtube_live', 'twitch', 'custom_rtmp', 'hls'
    status = Column(String(50), default="initializing")  # 'initializing', 'recording', 'reconnecting', 'stopped', 'failed'
    rights_confirmed = Column(Boolean, default=False, nullable=False)
    target_framing = Column(String(50), default="sports_gaming")  # 'sports_gaming', 'single_face', 'split_screen'
    caption_style = Column(String(50), default="sports_gaming")
    output_resolution = Column(String(20), default="1080x1920")
    total_segments_recorded = Column(Integer, default=0)
    total_highlights_extracted = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="live_sessions")
    segments = relationship("LiveSegment", back_populates="session", cascade="all, delete-orphan", order_by="LiveSegment.segment_index")
    clips = relationship("Clip", back_populates="live_session", cascade="all, delete-orphan")
```

#### 2. `LiveSegment` (Mapped from StreamSegments)
```python
class LiveSegment(Base):
    __tablename__ = "live_segments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_index = Column(Integer, nullable=False, index=True)
    file_path = Column(Text, nullable=False)
    storage_key = Column(String(255), nullable=True)
    start_seconds = Column(Float, nullable=False)  # Session-relative timeline offset
    end_seconds = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    status = Column(String(50), default="recorded")  # 'recorded', 'transcribed', 'curated', 'failed'
    words_json = Column(JSON, nullable=True)  # List of WordTimestamp dicts
    created_at = Column(DateTime, default=utc_now, nullable=False)

    session = relationship("LiveSession", back_populates="segments")
```

#### 3. `Clip` Model Updates (`backend/models.py`)
```python
# Updated Clip entity:
class Clip(Base):
    __tablename__ = "clips"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    live_session_id = Column(String(36), ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Differentiates standard VOD cuts from live automated highlights
    source = Column(String(50), default="fixed", nullable=False)  # 'fixed' | 'highlight'
    
    title = Column(String(255), nullable=False)
    headline = Column(String(255), nullable=False)
    start_seconds = Column(Float, nullable=False)
    end_seconds = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    viral_score = Column(Integer, default=90)
    hook = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    layout = Column(String(50), default="single_face")
    rubric_json = Column(JSON, nullable=True)
    headline_variants_json = Column(JSON, nullable=True)
    video_url = Column(Text, nullable=True)
    r2_key = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    project = relationship("Project", back_populates="clips")
    live_session = relationship("LiveSession", back_populates="clips")
    metrics = relationship("ClipMetric", back_populates="clip", cascade="all, delete-orphan")
```

---

### B. New Asyncio Supervisor Engine (`live/`)

```
live/
├── __init__.py               # Package exports: LiveSupervisor, StreamRecorder
├── supervisor.py            # Asyncio process manager: session lifecycle, reconnect loops, signal handling
├── recorder.py              # Subprocess wrapper: FFmpeg segmentation engine (-f segment -segment_time 60)
└── buffer.py                # Sliding-window transcript & boundary cache manager
```

- **`live/supervisor.py`**:
  - Maintains in-memory registry `_active_recorders: Dict[str, asyncio.Task]`.
  - Runs in the FastAPI process event loop on startup (`@app.on_event("startup")` / lifespan context).
  - Handles reconnect backoff (exponential up to 30s) if a stream experiences network blips.
  - On new segment completion on disk, dispatches `process_live_segment_task.delay(segment_id)` to Celery.
- **`live/recorder.py`**:
  - Executes FFmpeg non-blocking:
    ```bash
    ffmpeg -re -i "<stream_url>" -c copy -f segment -segment_time 60 -reset_timestamps 1 -strftime 1 "temp_media/live/<session_id>/seg_%04d.mp4"
    ```
  - Parses stderr progress continuously to detect stream starvation or dropped frames.

---

### C. Token Encryption & Security Utilities (`backend/security.py`)

Add symmetric Fernet token encryption at rest:
```python
from cryptography.fernet import Fernet
import os

class TokenCipher:
    @classmethod
    def get_cipher(cls) -> Fernet:
        key = os.getenv("FERNET_ENCRYPTION_KEY")
        if not key:
            raise RuntimeError("CRITICAL: FERNET_ENCRYPTION_KEY must be set in environment.")
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)

    @classmethod
    def encrypt_token(cls, raw_token: str) -> str:
        if not raw_token:
            return ""
        return cls.get_cipher().encrypt(raw_token.encode("utf-8")).decode("utf-8")

    @classmethod
    def decrypt_token(cls, encrypted_token: str) -> str:
        if not encrypted_token:
            return ""
        return cls.get_cipher().decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
```

---

### D. New REST & SSE Endpoints (`backend/routes/live.py`)

All routes enforce `current_user: User = Depends(get_current_user)` and strict tenant ownership checks:

| Method | Endpoint | Description | Request Body / Parameters | Validation & Security Checks |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/live/sessions` | Start live stream recording & highlight extraction | `StartLiveSessionRequest`: `{ title, stream_url, platform, rights_confirmed, target_framing, caption_style }` | **1.** `rights_confirmed == True` (400 if False)<br>**2.** SSRF URL validation via `SSRFGuard`<br>**3.** User plan limit check<br>**4.** Spawns `LiveSupervisor` task |
| `GET` | `/api/v1/live/sessions` | List active & past live sessions for current user | None | Filters by `session.user_id == current_user.id` |
| `GET` | `/api/v1/live/sessions/{id}` | Get session details, status, duration & segment counts | Path `id: str` | Ownership check (403 if unauthorized) |
| `POST` | `/api/v1/live/sessions/{id}/stop` | Stop live recording and finalize session | Path `id: str` | Ownership check; sends graceful `SIGINT` to FFmpeg; updates status to `stopped` |
| `GET` | `/api/v1/live/sessions/{id}/stream` | SSE real-time stream of recorder telemetry & newly discovered highlights | Query/Header token | Authenticated via `get_current_user_sse`; yields events: `segment_recorded`, `highlight_found`, `render_completed` |
| `GET` | `/api/v1/live/sessions/{id}/clips` | List all highlight clips (`source="highlight"`) extracted from this session | Path `id: str` | Ownership check; returns list of `Clip` objects with presigned download URLs |

---

### E. Celery Live Pipeline Tasks (`backend/tasks.py`)

Add `process_live_segment_task`:
```python
@celery_app.task(bind=True, max_retries=2, autoretry_for=(Exception,), retry_backoff=True)
def process_live_segment_task(self, segment_id: str):
    """
    1. Transcribes segment audio via TranscriberAgent (Groq Whisper).
    2. Updates LiveSegment.words_json with absolute session timestamps.
    3. Queries recent rolling window words (previous + current segment).
    4. Evaluates window via ViralCuratorAgent & JudgeAgent.
    5. For each highlight with viral_score >= 80:
       - Snaps boundaries with BoundarySnapper.
       - Runs SmartFramingAgent for 9:16 crop plan.
       - Renders vertical MP4 via VideoEditorAgent with GPU NVENC.
       - Uploads to R2 via StorageManager.
       - Persists Clip with source="highlight", live_session_id=session.id.
       - Emits SSE highlight event to connected clients.
    """
```

---

### F. Frontend Live Studio Interface (`frontend/src/app/live/page.tsx`)

Build a dedicated, dark-themed Next.js page adhering to CSS variable tokens:
- **Stream Ingest Card**:
  - Live stream URL input (YouTube Live / Twitch / RTMP).
  - Mandatory **"I confirm I own the broadcast rights to this live stream"** checkbox (locks submit button until checked).
  - Framing preference selector (`Sports & Gaming Action Crop`, `Face Tracking`, `Split Screen`).
- **Live Session Telemetry HUD**:
  - Live indicator badge (pulsing green `RECORDING`, amber `RECONNECTING`, gray `STOPPED`).
  - Rolling metrics: Active duration clock, total segments processed, total clips found.
- **Real-Time Highlights Deck**:
  - Animated grid of 9:16 cards populated via SSE as Celery completes each highlight.
  - Direct video player preview, viral score pill, headline banner preview, and download button.
- **Styling**: `bg: #0B0B0F`, `surface: #14141B`, `surfaceElevated: #1A1A24`, `accent: #8B5CF6`, `border: #22222E`.

---

## 4. Known Bugs & Traps Blocking This Work

A comprehensive audit of the current repository identified the following issues that must be resolved or safely handled during implementation:

### 1. Mock Fallback Returns in Production Endpoints (Rule 6 Violation)
- **Location:** `backend/routes/clips.py` lines 31-45:
  ```python
  if clip_id.startswith("clip_"):
      return { "id": clip_id, "title": "Connecting the Dots Intro", ... }
  ```
- **Impact:** Hardcoded mock responses bypass database queries, bypass tenant authorization checks, and allow unauthenticated access to phantom clips.
- **Required Action:** Remove the mock return path entirely and enforce strict database lookups with `current_user` ownership verification.

### 2. Frontend Mock Fallback Desynchronization
- **Location:** `frontend/src/app/page.tsx` lines 144-159:
  ```python
  // Fallback for standalone demo when backend is offline
  const mockJobId = `job_${Date.now()}`;
  const mockProjectId = `proj_${Date.now()}`;
  ```
- **Impact:** If the FastAPI backend returns an error or is unreachable, the frontend silently disguises the failure by fabricating synthetic IDs and routing to a non-existent stepper page, leaving the user confused and making genuine API errors impossible to diagnose.
- **Required Action:** Replace silent mock fallbacks with explicit user-facing `ErrorAlert` notifications and retry triggers.

### 3. Missing `FERNET_ENCRYPTION_KEY` & Plaintext Token Storage (Rule 4 Violation)
- **Location:** `backend/config.py` and `backend/models.py`:
  - `Settings` does not declare `ENCRYPTION_KEY` or `FERNET_ENCRYPTION_KEY`.
  - `PublishTarget.access_token` and `refresh_token` are stored in raw unencrypted database text.
- **Impact:** Compromises third-party OAuth credentials if the database is inspected or dumped.
- **Required Action:** Add `FERNET_ENCRYPTION_KEY` to `Settings` and implement `TokenCipher` in `backend/security.py` using Fernet.

### 4. Rigid Domain Allowlists in `SSRFGuard` Rejecting Live Streams
- **Location:** `backend/security.py` lines 13-24:
  - `ALLOWED_MEDIA_DOMAINS` only includes `youtube.com`, `vimeo.com`, `tiktok.com`, `instagram.com`, etc.
  - Twitch (`twitch.tv`, `live.twitch.tv`), Kick (`kick.com`), and custom RTMP/HLS CDNs are not present.
  - `SSRFGuard.validate_ingest_url` strictly requires `http` or `https`, rejecting `rtmp://` and `rtmps://` protocols.
- **Impact:** Users attempting to ingest live Twitch streams or RTMP broadcast feeds will trigger immediate `SSRFValidationError` 400 rejections.
- **Required Action:** Extend `ALLOWED_MEDIA_DOMAINS` to include verified live platforms (`twitch.tv`, `ttvnw.net`, `kick.com`) and expand scheme validation to safely support `rtmp://` / `rtmps://` where appropriate.

### 5. Foreign Key Constraint on `Clip.project_id`
- **Location:** `backend/models.py` line 90:
  ```python
  project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
  ```
- **Impact:** If a live highlight clip is created under a `LiveSession` without a parent `Project`, database inserts will crash with an IntegrityError.
- **Required Action:** Modify `project_id` to be `nullable=True`, and add `live_session_id = Column(String(36), ForeignKey("live_sessions.id", ...), nullable=True)`.

### 6. File Naming Collisions in `TranscriberAgent` Under Concurrency
- **Location:** `agents/transcriber.py` line 135:
  ```python
  chunk_pattern = self.temp_dir / f"{audio_path.stem}_chunk_%03d.mp3"
  ```
- **Impact:** When multiple live segments are being transcribed concurrently in Celery worker processes, temporary audio chunk files sharing generic names (`audio.mp3`) will collide and overwrite each other, causing corrupted transcriptions.
- **Required Action:** Ensure all intermediate audio stems include UUIDs or unique segment IDs (`f"{segment_id}_{uuid.uuid4().hex[:8]}_chunk_%03d.mp3"`).

---

## 5. Execution Phasing & Verification Gates

Following Rule 7 (*"After each step: run pytest, show the result, then stop and wait"*), implementation will proceed in atomic steps:

- **Step 1: Security & Storage Foundation**
  - Implement `TokenCipher` in `backend/security.py` with Fernet encryption/decryption.
  - Add `FERNET_ENCRYPTION_KEY` to `backend/config.py`.
  - Extend `SSRFGuard` to support live stream domains.
  - *Gate:* Unit tests in `tests/test_live_security.py` verifying encryption at rest and SSRF validation.

- **Step 2: Database Schema & Models**
  - Add `LiveSession` and `LiveSegment` models to `backend/models.py`.
  - Update `Clip` model: add `source = "fixed" | "highlight"`, make `project_id` nullable, add `live_session_id`.
  - Update `init_db()` to create new tables and columns cleanly.
  - *Gate:* Schema integration test in `tests/test_live_models.py` verifying foreign keys, cascading deletes, and default values.

- **Step 3: Asyncio Supervisor & Recorder Core (`live/`)**
  - Implement `live/supervisor.py` and `live/recorder.py`.
  - Implement graceful start, segment tracking, and stop handling.
  - *Gate:* Automated subprocess test with synthetic video feed verifying 60s segment output.

- **Step 4: Celery Highlight Extraction Pipeline**
  - Implement `process_live_segment_task` in `backend/tasks.py`.
  - Integrate `TranscriberAgent`, sliding-window `ViralCuratorAgent`, `JudgeAgent`, and `BoundarySnapper`.
  - Persist clips with `source="highlight"`.
  - *Gate:* End-to-end task test with mock live segment verifying highlight extraction.

- **Step 5: FastAPI Live Routes & SSE Telemetry**
  - Implement `backend/routes/live.py` with full ownership checks and `rights_confirmed=true` enforcement.
  - Mount router on `/api/v1/live`.
  - Add live SSE stream generator.
  - *Gate:* API integration tests verifying authorization, rights confirmation, and SSE packet formats.

- **Step 6: Next.js Live Studio Frontend**
  - Implement `frontend/src/app/live/page.tsx` adhering to dark theme tokens and responsive layouts.
  - Add live SSE subscription, rights confirmation toggle, and dynamic highlight stream cards.
  - *Gate:* Frontend component render test and E2E route verification.
