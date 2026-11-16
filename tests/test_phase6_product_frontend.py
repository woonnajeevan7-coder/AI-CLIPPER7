"""
Phase 6 Verification Tests: Product Frontend & Studio
Tests Streamlit multi-tab studio, brand kit state, transcript trimming logic, and web components.
"""

from pathlib import Path
import pytest


def test_app_py_contains_all_phase6_tabs():
    app_file = Path("app.py")
    assert app_file.exists()
    content = app_file.read_text(encoding="utf-8")
    
    # Check tabs
    assert "Clip Generation Studio" in content
    assert "Transcript-Based Editor" in content
    assert "Brand Kit" in content
    assert "Usage & Billing" in content
    
    # Check brand kit controls
    assert "brand_kit" in content
    assert "watermark_text" in content
    assert "font_family" in content

    # Check transcript word trimmer elements
    assert "word-pill" in content
    assert "Re-Render Short" in content


def test_app_security_and_safe_io():
    app_file = Path("app.py")
    content = app_file.read_text(encoding="utf-8")

    # Verify no hardcoded API keys exist and keys are not pre-filled into text_input
    assert "gsk_mock_redacted_security_key_000000000000000000000000" not in content
    assert 'value=DEFAULT_GROQ_KEY' not in content
    assert 'st.text_input(\n            "Groq API Key"' in content or 'Groq API Key' in content

    # Verify safe binary download reading without closed-file handle bug
    assert "c_path.read_bytes()" in content

    # Verify interactive word filter and dynamic plan management
    assert "multiselect" in content
    assert "active_plan" in content


def test_frontend_structure_and_pages():
    frontend_pkg = Path("frontend/package.json")
    assert frontend_pkg.exists()

    home_page = Path("frontend/src/app/page.tsx")
    assert home_page.exists()
    home_content = home_page.read_text(encoding="utf-8")
    assert "AI CLIPPER PRO" in home_content
    assert "Curated Viral Shorts" in home_content

    editor_page = Path("frontend/src/app/editor/page.tsx")
    assert editor_page.exists()
    editor_content = editor_page.read_text(encoding="utf-8")
    assert "Transcript-Based Video Editor" in editor_content
    assert "toggleWord" in editor_content


def test_html_escaping_in_app_py():
    from app import safe_html
    import html

    # Test malicious XSS payloads in transcript, title, and headline
    malicious_transcript = "<script>alert('xss')</script>"
    malicious_title = '"><img src=x onerror=alert(1)>'
    malicious_headline = "Top 10 Hacks & Tricks <script>evil()</script>"

    escaped_transcript = safe_html(malicious_transcript)
    escaped_title = safe_html(malicious_title)
    escaped_headline = safe_html(malicious_headline)

    assert "<script>" not in escaped_transcript
    assert "&lt;script&gt;" in escaped_transcript

    assert "<img" not in escaped_title
    assert "&quot;&gt;&lt;img" in escaped_title

    assert "<script>" not in escaped_headline
    assert "&amp;" in escaped_headline

    # Verify app.py source uses safe_html on words, titles, and headlines
    app_content = Path("app.py").read_text(encoding="utf-8")
    assert "w_escaped = safe_html(w)" in app_content
    assert "clip_title = safe_html(" in app_content
    assert "clip_headline = safe_html(" in app_content


def test_groq_key_not_prefilled_in_input():
    app_content = Path("app.py").read_text(encoding="utf-8")
    import re
    # Assert that Groq API Key input has value=""
    groq_input_match = re.search(r'st\.text_input\(\s*"Groq API Key"[^)]*value=""', app_content)
    assert groq_input_match is not None
    assert "DEFAULT_GROQ_KEY" not in app_content


def test_run_clipit_bat_binds_loopback():
    bat_file = Path("run_clipit.bat")
    assert bat_file.exists()
    bat_content = bat_file.read_text(encoding="utf-8")
    assert "--server.address 127.0.0.1" in bat_content

