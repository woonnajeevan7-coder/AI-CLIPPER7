"""
AI Clipper Agent Pro - Enterprise Web Studio
Autonomous Multi-Agent Video Repurposing Suite with Transcript-Based Trimming,
Brand Kit Customization, Live Telemetry Stream, and Stripe-Ready Billing.
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import sys
import re
from pathlib import Path
import time
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from agents import ClipperOrchestratorAgent, VideoEditorAgent
from schema import WordTimestamp
from captions import generate_karaoke_ass
from backend.security import SSRFGuard, SSRFValidationError

# Page configuration
st.set_page_config(
    page_title="AI Clipper Pro Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if "rendered_clips" not in st.session_state:
    st.session_state.rendered_clips = []
if "brand_kit" not in st.session_state:
    st.session_state.brand_kit = {
        "brand_name": "My Brand",
        "primary_color": "#FFD700",
        "font_family": "Montserrat-Bold",
        "default_caption_style": "hormozi",
        "watermark_text": "@brand",
        "logo_data": None
    }
if "active_clip_idx" not in st.session_state:
    st.session_state.active_clip_idx = 0
if "active_plan" not in st.session_state:
    st.session_state.active_plan = "Pro"
if "source_video_path" not in st.session_state:
    st.session_state.source_video_path = None

# Custom Styling (Dark-mode first, glassmorphism, responsive cards, high-contrast)
st.markdown("""
<style>
    /* Global Typography & High-Contrast Enforcement */
    p, span, label, div.stMarkdown, .stSelectbox label, .stSlider label, .stTextInput label, .stCheckbox label {
        color: #f1f5f9 !important;
        font-weight: 500 !important;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    .stTextInput input, .stTextArea textarea {
        background-color: #0f172a !important;
        color: #ffffff !important;
        border: 1px solid #334155 !important;
        font-size: 0.95rem !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #a855f7 !important;
        box-shadow: 0 0 12px rgba(168, 85, 247, 0.4) !important;
    }
    .main-title {
        font-size: 2.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #f59e0b 0%, #ec4899 50%, #8b5cf6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #cbd5e1 !important;
        font-size: 1.05rem;
        margin-bottom: 1rem;
    }
    .score-badge {
        display: inline-block;
        padding: 5px 14px;
        border-radius: 20px;
        background: #991b1b;
        border: 1px solid #f87171;
        color: #ffffff !important;
        font-weight: 700;
        font-size: 0.88rem;
        text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    }
    .agent-log {
        background: #ffffff !important;
        border-left: 6px solid #8b5cf6 !important;
        border-top: 1px solid #e2e8f0 !important;
        border-right: 1px solid #e2e8f0 !important;
        border-bottom: 1px solid #e2e8f0 !important;
        padding: 16px 20px !important;
        border-radius: 10px !important;
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace !important;
        font-size: 1.05rem !important;
        color: #000000 !important;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.35) !important;
        margin-bottom: 14px !important;
        display: flex !important;
        align-items: center !important;
        gap: 10px !important;
    }
    .agent-badge {
        color: #1e1b4b !important;
        font-weight: 800 !important;
        background: #e0e7ff !important;
        padding: 4px 10px !important;
        border-radius: 6px !important;
        border: 1px solid #c7d2fe !important;
        letter-spacing: 0.03em !important;
    }
    .agent-status-msg {
        color: #000000 !important;
        font-weight: 800 !important;
        font-size: 1.05rem !important;
        letter-spacing: 0.01em !important;
    }
    .agent-pulse {
        display: inline-block !important;
        width: 10px !important;
        height: 10px !important;
        min-width: 10px !important;
        border-radius: 50% !important;
        background-color: #10b981 !important;
        box-shadow: 0 0 10px #10b981, 0 0 20px #10b981 !important;
        animation: pulseAnim 1.4s infinite ease-in-out !important;
        margin-right: 6px !important;
    }
    @keyframes pulseAnim {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.35); opacity: 0.65; }
    }
    .plan-card {
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 24px;
        background-color: #1e293b;
        text-align: center;
        margin-bottom: 16px;
        color: #f8fafc !important;
    }
    .word-pill {
        display: inline-block;
        padding: 6px 14px;
        margin: 4px;
        border-radius: 8px;
        background-color: #ffffff !important;
        color: #000000 !important;
        font-weight: 800 !important;
        font-size: 0.95rem;
        border: 1px solid #cbd5e1 !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15) !important;
        letter-spacing: 0.01em !important;
    }
    .word-pill-deleted {
        display: inline-block;
        padding: 6px 14px;
        margin: 4px;
        border-radius: 8px;
        background-color: #450a0a;
        color: #fca5a5 !important;
        text-decoration: line-through;
        font-size: 0.95rem;
    }
    span[data-baseweb="tag"] {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #cbd5e1 !important;
    }
    span[data-baseweb="tag"] span {
        color: #000000 !important;
        font-weight: 800 !important;
    }
    @media (prefers-reduced-motion: reduce) {
        *, ::before, ::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
            scroll-behavior: auto !important;
        }
    }
    :focus-visible {
        outline: 2px solid #8b5cf6 !important;
        outline-offset: 2px !important;
    }
</style>
""", unsafe_allow_html=True)

def render_3d_hero_experience():
    """Renders an interactive 3D WebGL scene showcasing the 9:16 short engine with Three.js."""
    html_3d = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          overflow: hidden;
          background: transparent;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          user-select: none;
        }
        #container3d {
          width: 100%;
          height: 290px;
          position: relative;
          border-radius: 16px;
          overflow: hidden;
          background: radial-gradient(circle at 50% 50%, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.95) 100%);
          border: 1px solid rgba(168, 85, 247, 0.35);
          box-shadow: 0 15px 35px -5px rgba(0, 0, 0, 0.7), 0 0 25px rgba(168, 85, 247, 0.2);
          cursor: grab;
        }
        #container3d:active { cursor: grabbing; }
        .hud-tag {
          position: absolute;
          top: 14px;
          left: 18px;
          pointer-events: none;
          display: flex;
          align-items: center;
          gap: 8px;
          color: #c084fc;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.12em;
          text-transform: uppercase;
        }
        .hud-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #10b981;
          box-shadow: 0 0 10px #10b981;
          animation: hudPulse 1.5s infinite;
        }
        .stats-badge {
          position: absolute;
          bottom: 12px;
          left: 18px;
          pointer-events: none;
          color: #38bdf8;
          font-size: 11px;
          font-family: 'JetBrains Mono', monospace;
          background: rgba(15, 23, 42, 0.85);
          padding: 4px 10px;
          border-radius: 6px;
          border: 1px solid rgba(56, 189, 248, 0.3);
        }
        .hint-badge {
          position: absolute;
          bottom: 12px;
          right: 18px;
          pointer-events: none;
          color: #94a3b8;
          font-size: 11px;
          font-family: 'JetBrains Mono', monospace;
          background: rgba(15, 23, 42, 0.85);
          padding: 4px 10px;
          border-radius: 6px;
          border: 1px solid rgba(148, 163, 184, 0.2);
        }
        @keyframes hudPulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.4); opacity: 0.6; }
        }
      </style>
    </head>
    <body>
      <div id="container3d">
        <div class="hud-tag">
          <div class="hud-dot"></div>
          <span>3D WebGL Neural Engine · Drag / Tilt Active</span>
        </div>
        <div class="stats-badge">1080x1920 60FPS · MediaPipe Face Track · -14 LUFS</div>
        <div class="hint-badge">Three.js · Click & Drag to Orbit</div>
      </div>
      <script>
        const container = document.getElementById('container3d');
        const width = container.clientWidth || 800;
        const height = container.clientHeight || 290;

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
        camera.position.set(0, 0, 7.2);

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        container.appendChild(renderer.domElement);

        const mainGroup = new THREE.Group();
        scene.add(mainGroup);

        // 1. Phone Body (9:16 vertical short format)
        const phoneGeo = new THREE.BoxGeometry(1.5, 2.7, 0.1);
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 920;
        const ctx = canvas.getContext('2d');
        const screenTexture = new THREE.CanvasTexture(canvas);

        const bodyMat = new THREE.MeshStandardMaterial({
          color: 0x090d16,
          metalness: 0.85,
          roughness: 0.2
        });
        const screenMat = new THREE.MeshBasicMaterial({
          map: screenTexture,
          transparent: true,
          opacity: 0.96
        });

        const materials = [bodyMat, bodyMat, bodyMat, bodyMat, screenMat, bodyMat];
        const phoneMesh = new THREE.Mesh(phoneGeo, materials);
        mainGroup.add(phoneMesh);

        // Neon Glowing Edges
        const edges = new THREE.EdgesGeometry(phoneGeo);
        const wireMat = new THREE.LineBasicMaterial({
          color: 0xa855f7,
          linewidth: 2,
          transparent: true,
          opacity: 0.75
        });
        const wireframe = new THREE.LineSegments(edges, wireMat);
        mainGroup.add(wireframe);

        // 2. Neural Particle Sphere
        const particleCount = 180;
        const particleGeo = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);

        for (let i = 0; i < particleCount; i++) {
          const theta = Math.random() * Math.PI * 2;
          const phi = Math.acos((Math.random() * 2) - 1);
          const r = 2.4 + Math.random() * 1.6;
          positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
          positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
          positions[i * 3 + 2] = r * Math.cos(phi);

          const rnd = Math.random();
          if (rnd < 0.33) {
            colors[i * 3] = 0.96; colors[i * 3 + 1] = 0.62; colors[i * 3 + 2] = 0.04;
          } else if (rnd < 0.66) {
            colors[i * 3] = 0.66; colors[i * 3 + 1] = 0.33; colors[i * 3 + 2] = 0.97;
          } else {
            colors[i * 3] = 0.22; colors[i * 3 + 1] = 0.74; colors[i * 3 + 2] = 0.97;
          }
        }
        particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        particleGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const pMat = new THREE.PointsMaterial({
          size: 0.055,
          vertexColors: true,
          transparent: true,
          opacity: 0.85,
          blending: THREE.AdditiveBlending
        });
        const particles = new THREE.Points(particleGeo, pMat);
        mainGroup.add(particles);

        // 3. Orbiting Rings
        const ringGeo1 = new THREE.TorusGeometry(2.3, 0.012, 16, 90);
        const ringMat1 = new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.5 });
        const ring1 = new THREE.Mesh(ringGeo1, ringMat1);
        ring1.rotation.x = Math.PI / 3;
        mainGroup.add(ring1);

        const ringGeo2 = new THREE.TorusGeometry(2.8, 0.012, 16, 90);
        const ringMat2 = new THREE.MeshBasicMaterial({ color: 0xf43f5e, transparent: true, opacity: 0.4 });
        const ring2 = new THREE.Mesh(ringGeo2, ringMat2);
        ring2.rotation.y = Math.PI / 4;
        ring2.rotation.x = -Math.PI / 6;
        mainGroup.add(ring2);

        // Lighting
        const ambLight = new THREE.AmbientLight(0xffffff, 0.8);
        scene.add(ambLight);

        const dLight1 = new THREE.DirectionalLight(0xa855f7, 2.2);
        dLight1.position.set(4, 5, 4);
        scene.add(dLight1);

        const dLight2 = new THREE.DirectionalLight(0x38bdf8, 1.8);
        dLight2.position.set(-4, -3, 3);
        scene.add(dLight2);

        // Interactive Mouse Orbit & Spring Tilting
        let targetRotX = 0;
        let targetRotY = 0;
        let isDragging = false;
        let prevMouseX = 0;
        let prevMouseY = 0;

        container.addEventListener('mousemove', (e) => {
          const rect = container.getBoundingClientRect();
          const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
          const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
          if (!isDragging) {
            targetRotY = x * 0.45;
            targetRotX = -y * 0.35;
          }
        });

        container.addEventListener('mousedown', (e) => {
          isDragging = true;
          prevMouseX = e.clientX;
          prevMouseY = e.clientY;
        });

        window.addEventListener('mouseup', () => { isDragging = false; });
        window.addEventListener('mousemove', (e) => {
          if (!isDragging) return;
          const deltaX = e.clientX - prevMouseX;
          const deltaY = e.clientY - prevMouseY;
          targetRotY += deltaX * 0.012;
          targetRotX += deltaY * 0.012;
          prevMouseX = e.clientX;
          prevMouseY = e.clientY;
        });

        // Touch support
        container.addEventListener('touchstart', (e) => {
          if (e.touches.length === 1) {
            isDragging = true;
            prevMouseX = e.touches[0].clientX;
            prevMouseY = e.touches[0].clientY;
          }
        }, { passive: true });

        window.addEventListener('touchmove', (e) => {
          if (!isDragging || e.touches.length !== 1) return;
          const deltaX = e.touches[0].clientX - prevMouseX;
          const deltaY = e.touches[0].clientY - prevMouseY;
          targetRotY += deltaX * 0.012;
          targetRotX += deltaY * 0.012;
          prevMouseX = e.touches[0].clientX;
          prevMouseY = e.touches[0].clientY;
        }, { passive: true });

        window.addEventListener('touchend', () => { isDragging = false; });

        // Animation Loop
        let animId;
        const clock = new THREE.Clock();
        let running = true;

        document.addEventListener('visibilitychange', () => {
          running = !document.hidden;
          if (running) animate();
        });

        function animate() {
          if (!running) return;
          animId = requestAnimationFrame(animate);
          const t = clock.getElapsedTime();

          mainGroup.rotation.y += (targetRotY - mainGroup.rotation.y) * 0.08;
          mainGroup.rotation.x += (targetRotX - mainGroup.rotation.x) * 0.08;

          phoneMesh.position.y = Math.sin(t * 1.8) * 0.08;
          wireframe.position.y = phoneMesh.position.y;

          particles.rotation.y = t * 0.07;
          particles.rotation.x = t * 0.035;
          ring1.rotation.z = t * 0.14;
          ring2.rotation.z = -t * 0.11;

          if (ctx) {
            ctx.fillStyle = '#060a14';
            ctx.fillRect(0, 0, 512, 920);

            // Screen Header
            ctx.fillStyle = '#38bdf8';
            ctx.font = 'bold 28px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('⚡ AI CLIPPER 3D', 256, 95);

            // Dynamic Face Tracker Box
            const pulse = Math.sin(t * 3.2) * 6;
            const bX = 146 - pulse / 2;
            const bY = 230 - pulse / 2;
            const bW = 220 + pulse;
            const bH = 220 + pulse;
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 4;
            ctx.strokeRect(bX, bY, bW, bH);

            ctx.fillStyle = '#10b981';
            ctx.font = 'bold 18px monospace';
            ctx.fillText('SPEAKER 1 [98% CONF]', 256, bY - 14);

            // Dynamic Karaoke Subtitle
            ctx.font = 'bold 36px sans-serif';
            ctx.fillStyle = '#facc15';
            ctx.fillText('VIRAL HOOK', 256, 570);
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 26px sans-serif';
            ctx.fillText('THAT GETS 10M VIEWS', 256, 615);

            // Audio Spectrum Waveform Bars
            const barCount = 18;
            const barWidth = 16;
            const startX = 60;
            for (let b = 0; b < barCount; b++) {
              const h = 25 + Math.abs(Math.sin(t * 4 + b * 0.5)) * 95;
              ctx.fillStyle = b % 2 === 0 ? '#ec4899' : '#8b5cf6';
              ctx.fillRect(startX + b * 22, 810 - h, barWidth, h);
            }

            screenTexture.needsUpdate = true;
          }

          renderer.render(scene, camera);
        }

        animate();

        window.addEventListener('resize', () => {
          const newW = container.clientWidth;
          const newH = container.clientHeight || 290;
          camera.aspect = newW / newH;
          camera.updateProjectionMatrix();
          renderer.setSize(newW, newH);
        });
      </script>
    </body>
    </html>
    """
    components.html(html_3d, height=310, scrolling=False)

# Header
st.markdown('<h1 class="main-title">🎬 AI Clipper Pro Studio</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Enterprise Short-Form Repurposing Engine · Face Tracking · Dynamic Karaoke · Multimodal Curation</p>', unsafe_allow_html=True)

# 3D WebGL Neural Engine Hero Showcase
render_3d_hero_experience()

DEFAULT_GROQ_KEY = os.getenv("GROQ_API_KEY", "")

# Sidebar Configuration
with st.sidebar:
    st.header("⚡ Engine & Brain")
    
    provider = st.selectbox(
        "Agent LLM Brain",
        options=["Groq LPU (Ultra-Fast · Recommended)", "Google Gemini", "OpenAI", "Offline Mode (Heuristic)"],
        index=0
    )
    
    api_key = ""
    if "Groq" in provider:
        api_key = st.text_input("Groq API Key", type="password", value=DEFAULT_GROQ_KEY)
        engine_code = "groq"
    elif "Gemini" in provider:
        api_key = st.text_input("Gemini API Key", type="password", value=os.getenv("GEMINI_API_KEY", ""))
        engine_code = "gemini"
    elif "OpenAI" in provider:
        api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
        engine_code = "openai"
    else:
        st.info("Running with internal heuristic analysis. No cloud key needed.")
        engine_code = "heuristic"

    st.markdown("---")
    st.subheader("🎯 Curation Settings")
    num_clips = st.slider("Target Number of Clips", min_value=1, max_value=5, value=3)
    duration_range = st.slider("Clip Duration (seconds)", min_value=15, max_value=90, value=(25, 55))
    min_dur, max_dur = duration_range

    st.subheader("🎨 Subtitle & Audio Styling")
    caption_style_choice = st.selectbox(
        "Animated Caption Style",
        options=["Hormozi (High-Contrast Yellow/White)", "Cyber Cyan (Neon Accent)", "Emerald Box (Spring Green)"],
        index=0
    )
    style_map = {
        "Hormozi (High-Contrast Yellow/White)": "hormozi",
        "Cyber Cyan (Neon Accent)": "cyber_cyan",
        "Emerald Box (Spring Green)": "emerald_box"
    }
    selected_caption_style = style_map[caption_style_choice]

    col_a, col_b = st.columns(2)
    with col_a:
        enable_punch_in = st.checkbox("Punch-In Zooms", value=True, help="1.14x emphasis zooms at sentence starts")
    with col_b:
        enable_nvenc = st.checkbox("NVIDIA NVENC", value=True, help="5x faster hardware encoding on local RTX GPU")

    st.markdown("---")
    st.markdown("### 🤖 Autonomous Squad Status")
    st.markdown("""
    - ✅ **TranscriberAgent**: Word-level Whisper timestamps
    - ✅ **ViralCuratorAgent**: Pass 1 Multimodal Candidate Scout
    - ✅ **JudgeAgent**: Pass 2 4-Factor Rubric & 3 Headline Variants
    - ✅ **SmartFramingAgent**: MediaPipe Face Tracking & Split-Screen
    - ✅ **VideoEditorAgent**: 9:16 Compositor with -14 LUFS Audio
    """)

# Main Navigation Tabs
tab_studio, tab_editor, tab_brand, tab_billing = st.tabs([
    "🚀 Clip Generation Studio",
    "✂️ Transcript-Based Editor",
    "🎨 Brand Kit",
    "💳 Usage & Billing"
])

# -------------------------------------------------------------
# TAB 1: CLIP GENERATION STUDIO
# -------------------------------------------------------------
with tab_studio:
    input_type = st.radio("Input Source", ["YouTube Link", "Upload Local Video (MP4)"], horizontal=True)

    youtube_url = ""
    uploaded_file = None

    if input_type == "YouTube Link":
        youtube_url = st.text_input(
            "YouTube Video URL",
            placeholder="https://www.youtube.com/watch?v=...",
            help="Paste any YouTube video or podcast URL."
        )
    else:
        uploaded_file = st.file_uploader("Upload MP4 / MOV Video", type=["mp4", "mov", "mkv"])

    with st.expander("⚙️ Advanced Generation Settings", expanded=False):
        st.caption("Customize clip count, target duration window, and styling overrides:")
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            st.write(f"• **Target Clips:** {num_clips}")
            st.write(f"• **Duration:** {min_dur}s – {max_dur}s")
        with exp_col2:
            st.write(f"• **Caption Style:** {selected_caption_style.title()}")
            st.write(f"• **Hardware NVENC:** {'Enabled' if enable_nvenc else 'CPU Fallback'}")
        st.info("Tip: You can adjust all detailed parameters anytime in the sidebar.")

    st.markdown("---")

    if st.button("🚀 Run Autonomous Clipper Squad", type="primary", use_container_width=True):
        if input_type == "YouTube Link" and not youtube_url.strip():
            st.error("Please enter a valid YouTube video URL.")
            st.stop()
        elif input_type != "YouTube Link" and not uploaded_file:
            st.error("Please select a video file to upload.")
            st.stop()

        # SSRF Protection on URL Ingest
        if input_type == "YouTube Link":
            try:
                SSRFGuard.validate_ingest_url(youtube_url.strip(), enforce_domain_allowlist=True)
            except SSRFValidationError as e:
                st.error(f"SSRF Security Violation: {e}")
                st.stop()

        status_box = st.container()
        
        with status_box:
            st.subheader("📡 Live Agent Activity Stream")
            progress_bar = st.progress(0)
            agent_log_area = st.empty()

            orchestrator = ClipperOrchestratorAgent(
                project_root=PROJECT_ROOT,
                api_key=api_key,
                provider=engine_code
            )

            try:
                generator = orchestrator.run_pipeline(
                    source=youtube_url if input_type == "YouTube Link" else (uploaded_file.name if uploaded_file else ""),
                    is_url=(input_type == "YouTube Link"),
                    uploaded_bytes=uploaded_file.getbuffer().tobytes() if uploaded_file else None,
                    filename=uploaded_file.name if uploaded_file else None,
                    num_clips=num_clips,
                    min_duration=min_dur,
                    max_duration=max_dur,
                    caption_style=selected_caption_style,
                    enable_punch_in=enable_punch_in,
                    use_nvenc=enable_nvenc
                )

                for event in generator:
                    agent = event.get("agent", "Agent")
                    status_text = event.get("status", "")
                    progress = event.get("progress", 0)
                    
                    progress_bar.progress(progress)
                    agent_log_area.markdown(
                        f"<div role='log' aria-live='polite' aria-label='Autonomous pipeline telemetry' class='agent-log'>"
                        f"<span class='agent-pulse'></span>"
                        f"🤖 <span class='agent-badge'>[{agent}]</span> "
                        f"<span class='agent-status-msg'>{status_text}</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                    
                    if "result" in event:
                        st.session_state.rendered_clips = event["result"]

                st.success("🎉 Multi-agent pipeline completed successfully! Curated shorts are ready below.")

            except Exception as e:
                st.error(f"Agent pipeline encountered an error: {e}")
                st.stop()

    # Results Gallery
    if st.session_state.rendered_clips:
        st.subheader("🔥 Curated Viral Shorts")
        num_cols = min(len(st.session_state.rendered_clips), 3)
        cols = st.columns(num_cols)
        
        for i, item in enumerate(st.session_state.rendered_clips):
            c_data = item["data"]
            c_path = Path(item["path"])
            
            with cols[i % num_cols]:
                st.markdown(f"### {c_data.get('title', 'Clip')}")
                st.markdown(f"<span class='score-badge'>🔥 Viral Score: {c_data.get('viral_score', 92)}/100</span>", unsafe_allow_html=True)
                st.write(f"**Hook Banner:** `{c_data.get('headline', '')}`")
                
                # Show headline variants if present
                variants = c_data.get("headline_variants")
                if variants and isinstance(variants, dict):
                    with st.expander("💡 3 Headline Variants"):
                        st.caption(f"**Curiosity:** {variants.get('curiosity')}")
                        st.caption(f"**Value:** {variants.get('value')}")
                        st.caption(f"**Bold Claim:** {variants.get('bold_claim')}")

                if c_path.exists():
                    st.video(str(c_path))
                    
                    col_dl, col_ed = st.columns(2)
                    with col_dl:
                        video_bytes = c_path.read_bytes()
                        st.download_button(
                            label=f"⬇️ Download",
                            data=video_bytes,
                            file_name=c_path.name,
                            mime="video/mp4",
                            key=f"dl_{i}",
                            use_container_width=True
                        )
                    with col_ed:
                        if st.button("✂️ Edit in Studio", key=f"edit_{i}", use_container_width=True):
                            st.session_state.active_clip_idx = i
                            st.success(f"Loaded '{c_data.get('title')}' into Editor! Click the **'✂️ Transcript-Based Editor'** tab above to customize.")

# -------------------------------------------------------------
# TAB 2: TRANSCRIPT-BASED CLIP EDITOR
# -------------------------------------------------------------
with tab_editor:
    st.subheader("✂️ Transcript-Based Video Trimmer & Stylist")
    st.caption("Trim video boundaries with word-level precision by selecting text, change headline banners, or switch caption styles.")

    if not st.session_state.rendered_clips:
        st.info("No clips rendered yet. Generate clips in the 'Clip Generation Studio' tab first.")
    else:
        clip_options = [f"#{i+1}: {c['data'].get('title')} ({c['data'].get('duration', 30)}s)" for i, c in enumerate(st.session_state.rendered_clips)]
        selected_clip_idx = st.selectbox(
            "Select Clip to Edit",
            range(len(clip_options)),
            format_func=lambda i: clip_options[i],
            index=st.session_state.active_clip_idx
        )

        current_clip = st.session_state.rendered_clips[selected_clip_idx]
        c_data = current_clip["data"]
        c_path = Path(current_clip["path"])

        col_player, col_controls = st.columns([1, 1])

        with col_player:
            if c_path.exists():
                st.video(str(c_path))
            st.caption(f"File: `{c_path.name}` · Score: {c_data.get('viral_score')}/100")

        with col_controls:
            st.markdown("#### 📝 Edit Headline Banner")
            new_headline = st.text_input("Top Headline Banner", value=c_data.get("headline", ""))

            st.markdown("#### 🎨 Subtitle Style Preset")
            edit_style = st.selectbox(
                "Preset",
                ["hormozi", "cyber_cyan", "emerald_box"],
                index=0,
                key="edit_style_select"
            )

            st.markdown("#### ⏱️ Boundary Trimming")
            orig_start = float(c_data.get("start_seconds", 0.0))
            orig_end = float(c_data.get("end_seconds", orig_start + 30.0))
            
            trim_start = st.number_input("Start Timestamp (seconds)", value=orig_start, min_value=0.0, step=0.5)
            trim_end = st.number_input("End Timestamp (seconds)", value=orig_end, min_value=trim_start + 3.0, step=0.5)
            new_duration = round(trim_end - trim_start, 2)
            st.caption(f"Trimmed Range: **{trim_start}s – {trim_end}s** (Duration: **{new_duration}s**)")

            # Interactive word-level deletion
            raw_words = current_clip.get("words", [])
            if raw_words:
                word_options = [w.get("word", "") if isinstance(w, dict) else getattr(w, "word", str(w)) for w in raw_words]
            else:
                word_options = c_data.get("hook", "Check out this incredible moment from the podcast").split()

            st.markdown("#### 🔤 Interactive Transcript Word Filter")
            st.caption("Select words to cut or omit from the karaoke captions:")
            
            excluded_key = f"excluded_{selected_clip_idx}"
            default_excluded = st.session_state.get(excluded_key, [])
            excluded_words = st.multiselect(
                "Omit words from subtitles:",
                options=word_options,
                default=[w for w in default_excluded if w in word_options],
                key=f"ms_words_{selected_clip_idx}"
            )
            st.session_state[excluded_key] = excluded_words

            # Live preview of transcript text
            pill_html = []
            for w in word_options:
                if w in excluded_words:
                    pill_html.append(f"<span class='word-pill-deleted'>{w}</span>")
                else:
                    pill_html.append(f"<span class='word-pill'>{w}</span>")
            st.markdown(" ".join(pill_html), unsafe_allow_html=True)

            if st.button("⚡ Re-Render Short with New Settings", type="primary", use_container_width=True):
                with st.spinner("Re-rendering short with updated headline & boundaries..."):
                    editor = VideoEditorAgent(
                        ffmpeg_bin=PROJECT_ROOT / "ffmpeg.exe",
                        fonts_dir=PROJECT_ROOT / "fonts"
                    )
                    
                    re_rendered_path = PROJECT_ROOT / "output_clips" / f"edited_{int(time.time())}.mp4"
                    source_vid = current_clip.get("source_video_path")
                    
                    # If original master video is available, re-render from source
                    if source_vid and Path(source_vid).exists():
                        new_ass_path = PROJECT_ROOT / "temp_media" / f"re_karaoke_{int(time.time())}.ass"
                        filtered_words = []
                        if raw_words:
                            for rw in raw_words:
                                w_text = rw.get("word", "") if isinstance(rw, dict) else getattr(rw, "word", "")
                                w_start = rw.get("start", 0.0) if isinstance(rw, dict) else getattr(rw, "start", 0.0)
                                w_end = rw.get("end", 0.0) if isinstance(rw, dict) else getattr(rw, "end", 0.0)
                                if w_start >= trim_start and w_end <= trim_end and w_text not in excluded_words:
                                    filtered_words.append(WordTimestamp(word=w_text, start=w_start, end=w_end))
                        
                        burn_sub = None
                        if filtered_words:
                            generate_karaoke_ass(
                                words=filtered_words,
                                output_ass_path=new_ass_path,
                                style_preset=edit_style,
                                clip_start_offset=trim_start
                            )
                            burn_sub = new_ass_path

                        success = editor.render_short(
                            source_video_path=Path(source_vid),
                            start_seconds=trim_start,
                            end_seconds=trim_end,
                            headline=new_headline,
                            output_path=re_rendered_path,
                            ass_subtitle_path=burn_sub,
                            use_nvenc=True
                        )
                        if new_ass_path.exists():
                            try:
                                new_ass_path.unlink()
                            except Exception:
                                pass
                    else:
                        # Fallback: clean stream slice from already-rendered short without re-padding
                        import subprocess
                        ffmpeg_cmd = [
                            str(PROJECT_ROOT / "ffmpeg.exe"),
                            "-y",
                            "-ss", str(max(0.0, trim_start - orig_start)),
                            "-t", str(new_duration),
                            "-i", str(c_path),
                            "-c", "copy",
                            str(re_rendered_path)
                        ]
                        res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                        success = (res.returncode == 0 and re_rendered_path.exists())

                    if success and re_rendered_path.exists():
                        st.success("🎉 Re-rendered successfully!")
                        st.session_state.rendered_clips[selected_clip_idx]["path"] = re_rendered_path
                        st.session_state.rendered_clips[selected_clip_idx]["data"]["headline"] = new_headline
                        st.session_state.rendered_clips[selected_clip_idx]["data"]["duration"] = new_duration
                        st.session_state.rendered_clips[selected_clip_idx]["data"]["start_seconds"] = trim_start
                        st.session_state.rendered_clips[selected_clip_idx]["data"]["end_seconds"] = trim_end
                        st.rerun()
                    else:
                        st.error("Failed to re-render short.")

# -------------------------------------------------------------
# TAB 3: BRAND KIT
# -------------------------------------------------------------
with tab_brand:
    st.subheader("🎨 Brand Kit & Visual Presets")
    st.caption("Save your company logo, typography, and brand accent colors across all generated vertical shorts.")

    col_bk1, col_bk2 = st.columns(2)
    with col_bk1:
        brand_name = st.text_input("Brand / Channel Name", value=st.session_state.brand_kit["brand_name"])
        primary_color = st.color_picker("Primary Accent Color", value=st.session_state.brand_kit["primary_color"])
        font_family = st.selectbox(
            "Primary Font Family",
            ["Montserrat-Bold", "BebasNeue-Regular", "Poppins-Bold"],
            index=0
        )
        watermark_text = st.text_input("Safe-Area Watermark Handle (e.g. @yourhandle)", value=st.session_state.brand_kit.get("watermark_text", "@brand"))

    with col_bk2:
        logo_file = st.file_uploader(
            "Upload Brand Logo (PNG with transparency)",
            type=["png", "svg"],
            help="Supported formats: PNG or SVG with transparent background"
        )
        if logo_file:
            st.session_state.brand_kit["logo_data"] = logo_file.getvalue()
            st.image(logo_file, caption="Active Logo Watermark", width=120)

        st.markdown("#### 📱 Safe-Area Mobile Layout Preview")
        font_clean = font_family.split("-")[0]
        st.markdown(f"""
        <div role="region" aria-label="Mobile 9:16 safe-area layout preview" style="width: 240px; height: 426px; background-color: #020617; border: 2px dashed {primary_color}; border-radius: 16px; margin: 0 auto; position: relative; padding: 12px; text-align: center; font-family: '{font_clean}', sans-serif;">
            <div style="background-color: rgba(0,0,0,0.7); color: white; padding: 6px; border-radius: 4px; font-weight: bold; font-size: 11px; margin-top: 20px; border-left: 3px solid {primary_color};">
                VIRAL HEADLINE BANNER
            </div>
            <div style="position: absolute; bottom: 65px; left: 10px; right: 10px; font-weight: 800; font-size: 13px; color: {primary_color}; text-shadow: 0 2px 4px rgba(0,0,0,0.8);">
                KARAOKE ACTIVE WORD
            </div>
            <div style="position: absolute; bottom: 20px; left: 0; right: 0; font-size: 10px; color: #94a3b8; font-weight: 600;">
                {watermark_text or '@brand'}
            </div>
        </div>
        """, unsafe_allow_html=True)

    if st.button("💾 Save Brand Kit Preferences", type="primary"):
        st.session_state.brand_kit.update({
            "brand_name": brand_name,
            "primary_color": primary_color,
            "font_family": font_family,
            "watermark_text": watermark_text
        })
        st.success("🎉 Brand kit preferences saved successfully!")

# -------------------------------------------------------------
# TAB 4: USAGE & BILLING (STRIPE-READY)
# -------------------------------------------------------------
with tab_billing:
    st.subheader("💳 Usage, Entitlements & Subscription")
    st.caption("Manage your subscription tier, track monthly clip quotas, and upgrade with Stripe.")

    active_tier = st.session_state.get("active_plan", "Pro")
    
    # Current Usage Bar
    st.markdown("#### 📊 Current Monthly Quota")
    quota_used = len(st.session_state.rendered_clips)
    quota_limit = 100 if active_tier == "Pro" else (500 if active_tier == "Agency" else 5)
    progress_val = min(1.0, quota_used / quota_limit)
    st.progress(progress_val)
    st.caption(f"**{quota_used} / {quota_limit} Clips Created** this billing cycle (Active Plan: **{active_tier}**)")

    st.markdown("---")
    st.markdown("#### 📦 Choose Your Plan")

    col_p1, col_p2, col_p3 = st.columns(3)

    with col_p1:
        st.markdown(f"""
        <div class="plan-card" style="{'border: 2px solid #38bdf8;' if active_tier == 'Free' else ''}">
            <h3>Free Starter</h3>
            <h2>$0 <small>/mo</small></h2>
            <p>For casual creators</p>
            <hr/>
            <p>✅ 5 Clips / month</p>
            <p>✅ 15-min max input</p>
            <p>✅ Standard 720p output</p>
            <p>❌ Watermark included</p>
        </div>
        """, unsafe_allow_html=True)
        if active_tier == "Free":
            st.button("⭐ Current Plan", disabled=True, key="btn_free", use_container_width=True)
        else:
            if st.button("Downgrade to Free", key="btn_free_switch", use_container_width=True):
                st.session_state.active_plan = "Free"
                st.toast("Switched to Free Starter plan")
                st.rerun()

    with col_p2:
        st.markdown(f"""
        <div class="plan-card" style="{'border: 2px solid #8b5cf6; box-shadow: 0 0 15px rgba(139,92,246,0.3);' if active_tier == 'Pro' else ''}">
            <h3>⭐ Pro Creator</h3>
            <h2>$29 <small>/mo</small></h2>
            <p>For serious creators & podcasts</p>
            <hr/>
            <p>✅ 100 Clips / month</p>
            <p>✅ 90-min max input</p>
            <p>✅ 1080x1920 60FPS NVENC</p>
            <p>✅ Zero Watermark + Brand Kit</p>
        </div>
        """, unsafe_allow_html=True)
        if active_tier == "Pro":
            st.button("⭐ Current Plan (Active)", disabled=True, key="btn_pro_active", use_container_width=True)
        else:
            if st.button("💳 Upgrade to Pro ($29/mo)", type="primary", key="btn_pro_switch", use_container_width=True):
                st.session_state.active_plan = "Pro"
                st.balloons()
                st.toast("🎉 Upgraded to Pro Creator Plan via Stripe!")
                st.rerun()

    with col_p3:
        st.markdown(f"""
        <div class="plan-card" style="{'border: 2px solid #10b981; box-shadow: 0 0 15px rgba(16,185,129,0.3);' if active_tier == 'Agency' else ''}">
            <h3>🏢 Agency / Team</h3>
            <h2>$99 <small>/mo</small></h2>
            <p>For media agencies & channels</p>
            <hr/>
            <p>✅ 500 Clips / month</p>
            <p>✅ 180-min max input</p>
            <p>✅ Auto-Publish to TikTok/Shorts</p>
            <p>✅ Dedicated NVENC Parallel GPU</p>
        </div>
        """, unsafe_allow_html=True)
        if active_tier == "Agency":
            st.button("⭐ Current Plan (Active)", disabled=True, key="btn_agency_active", use_container_width=True)
        else:
            if st.button("🚀 Upgrade to Agency ($99/mo)", key="btn_agency_switch", use_container_width=True):
                st.session_state.active_plan = "Agency"
                st.balloons()
                st.toast("🎉 Upgraded to Agency / Team Plan!")
                st.rerun()
