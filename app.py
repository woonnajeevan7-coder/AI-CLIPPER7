"""
AI Clipper Agent Pro - Streamlit Web Studio
Autonomous Multi-Agent Video Repurposing Suite
Architecture: TranscriberAgent + ViralCuratorAgent + VideoEditorAgent + ClipperOrchestratorAgent
"""

import streamlit as st
import os
import sys
from pathlib import Path
import time

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from agents import ClipperOrchestratorAgent

# Page configuration
st.set_page_config(
    page_title="AI Clipper Agent Pro",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #f59e0b 0%, #ec4899 50%, #8b5cf6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .score-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%);
        color: white;
        font-weight: 700;
        font-size: 0.9rem;
    }
    .agent-log {
        background-color: #111827;
        border-left: 4px solid #8b5cf6;
        padding: 10px 14px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.9rem;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-title">🎬 AI Clipper Agent Pro</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Multi-Agent Video Repurposing System powered by Groq LPU, Whisper & FFmpeg.</div>', unsafe_allow_html=True)

# Default Key
DEFAULT_GROQ_KEY = os.getenv("GROQ_API_KEY", "gsk_mock_redacted_security_key_000000000000000000000000")

# Sidebar Configuration
with st.sidebar:
    st.header("⚡ Agent Configuration")
    
    provider = st.selectbox(
        "Agent LLM Brain",
        options=["Groq LPU (Ultra-Fast · Recommended)", "Google Gemini", "OpenAI", "Offline Mode (Heuristic)"],
        index=0
    )
    
    api_key = ""
    if "Groq" in provider:
        api_key = st.text_input(
            "Groq API Key",
            type="password",
            value=DEFAULT_GROQ_KEY,
            help="High-speed LPU inference powered by Groq"
        )
        engine_code = "groq"
    elif "Gemini" in provider:
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "")),
            help="Get a key from https://aistudio.google.com"
        )
        engine_code = "gemini"
    elif "OpenAI" in provider:
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            help="Get your key from platform.openai.com"
        )
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

    gpu_accel = st.checkbox("NVIDIA NVENC Hardware Acceleration", value=True, help="Leverage local RTX GPU for 5x faster 1080x1920 encoding")

    st.markdown("---")
    st.markdown("### 🤖 Active Agent Squad")
    st.markdown("""
    - **TranscriberAgent**: Ingestion & Speech-to-Text
    - **ViralCuratorAgent**: Retention & Hook Analysis
    - **VideoEditorAgent**: 9:16 FFmpeg Compositor
    - **OrchestratorAgent**: State & Pipeline Routing
    """)

# Main Input Section
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

st.markdown("---")

# Processing Button
if st.button("🚀 Run AI Clipper Squad", type="primary", use_container_width=True):
    if input_type == "YouTube Link" and not youtube_url.strip():
        st.error("Please enter a valid YouTube video URL.")
        st.stop()
    elif input_type != "YouTube Link" and not uploaded_file:
        st.error("Please select a video file to upload.")
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

        rendered_clips = []
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
                use_nvenc=gpu_accel
            )

            for event in generator:
                agent = event.get("agent", "Agent")
                status = event.get("status", "")
                progress = event.get("progress", 0)
                
                progress_bar.progress(progress)
                agent_log_area.markdown(f"<div class='agent-log'>🤖 <b>[{agent}]</b> {status}</div>", unsafe_allow_html=True)
                
                if "result" in event:
                    rendered_clips = event["result"]

            st.success("🎉 Multi-agent pipeline completed successfully! Your vertical shorts are ready below.")

        except Exception as e:
            st.error(f"Agent pipeline encountered an error: {e}")
            st.stop()

    # Results Gallery
    if rendered_clips:
        st.subheader("🔥 Curated Viral Shorts")
        num_cols = min(len(rendered_clips), 3)
        cols = st.columns(num_cols)
        
        for i, item in enumerate(rendered_clips):
            c_data = item["data"]
            c_path = item["path"]
            
            with cols[i % num_cols]:
                st.markdown(f"### {c_data.get('title', 'Clip')}")
                st.markdown(f"<span class='score-badge'>🔥 Viral Score: {c_data.get('viral_score', 92)}/100</span>", unsafe_allow_html=True)
                st.write(f"**Hook Banner:** `{c_data.get('headline', '')}`")
                st.caption(f"**Curator Rationale:** {c_data.get('reason', '')}")
                
                # Video preview
                st.video(str(c_path))
                
                # Download button
                with open(c_path, "rb") as vf:
                    st.download_button(
                        label=f"⬇️ Download Short #{i+1}",
                        data=vf,
                        file_name=c_path.name,
                        mime="video/mp4",
                        use_container_width=True
                    )
