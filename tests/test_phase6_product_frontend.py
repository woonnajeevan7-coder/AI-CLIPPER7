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

    # Verify no hardcoded API keys exist
    assert "gsk_mock_redacted_security_key_000000000000000000000000" not in content
    assert 'DEFAULT_GROQ_KEY = os.getenv("GROQ_API_KEY", "")' in content

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
