import sys
import os
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(r"C:\Users\woonn\.gemini\antigravity\brain\d27a6320-76ab-410c-9f67-127dd0472e7a\mobile_test_artifacts")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

report = {
    "viewport": {"width": 375, "height": 812},
    "steps": {},
    "horizontal_overflows": [],
    "console_errors": [],
    "downloads": [],
    "bugs": []
}

def check_overflow(page, page_name):
    """Detects horizontal overflow on mobile 375px."""
    overflow_data = page.evaluate("""() => {
        const windowWidth = window.innerWidth;
        const scrollWidth = document.documentElement.scrollWidth;
        const overflowingElements = [];
        
        if (scrollWidth > windowWidth) {
            const allElements = document.querySelectorAll('*');
            for (const el of allElements) {
                const rect = el.getBoundingClientRect();
                if (rect.right > windowWidth) {
                    overflowingElements.push({
                        tagName: el.tagName,
                        id: el.id,
                        className: (el.className || '').toString().slice(0, 80),
                        rect: { x: Math.round(rect.x), width: Math.round(rect.width), right: Math.round(rect.right) }
                    });
                }
            }
        }
        return {
            windowWidth,
            scrollWidth,
            hasOverflow: scrollWidth > windowWidth,
            overflowingElements: overflowingElements.slice(0, 10)
        };
    }""")
    if overflow_data["hasOverflow"]:
        report["horizontal_overflows"].append({
            "page": page_name,
            "details": overflow_data
        })
        print(f"⚠️ [OVERFLOW DETECTED] {page_name}: scrollWidth={overflow_data['scrollWidth']} > windowWidth={overflow_data['windowWidth']}")
    else:
        print(f"✅ [NO OVERFLOW] {page_name}: fits 375px perfectly.")
    return overflow_data

def run_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 375, "height": 812},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
            accept_downloads=True
        )
        page = context.new_page()
        page.set_default_timeout(60000)

        # Track console errors & downloads
        page.on("console", lambda msg: report["console_errors"].append(f"[{msg.type}] {msg.text}") if msg.type in ["error"] else None)
        page.on("pageerror", lambda exc: report["console_errors"].append(f"[UNCAUGHT] {str(exc)}"))
        page.on("download", lambda d: report["downloads"].append(d.suggested_filename))
        page.on("response", lambda r: print(f"*** 404 URL: {r.url} ***") if r.status == 404 else None)

        print("\n=== STEP 1: Landing Page (375px) ===")
        page.goto("http://localhost:3000", wait_until="domcontentloaded")
        page.wait_for_selector("h1", timeout=30000)
        page.wait_for_timeout(1000)
        overflow_1 = check_overflow(page, "Landing Page")
        page.screenshot(path=str(ARTIFACTS_DIR / "01_landing_375px.png"), full_page=False)
        report["steps"]["landing_page"] = {
            "status": "PASS",
            "overflow": overflow_1["hasOverflow"],
            "title": page.title()
        }

        # Navigate to New Project
        clip_btn = page.locator("text=Open Studio & Clip Video").first
        clip_btn.click()
        page.wait_for_url("**/projects/new", timeout=15000)
        page.wait_for_selector("input[type='url']", timeout=15000)
        page.wait_for_timeout(1000)

        print("\n=== STEP 2: New Project Page (/projects/new) ===")
        overflow_2 = check_overflow(page, "New Project Page")
        page.screenshot(path=str(ARTIFACTS_DIR / "02_new_project_initial.png"))

        # Paste URL
        url_input = page.locator("input[type='url']")
        url_input.fill("https://www.youtube.com/watch?v=UF8uR6Z6KLc")

        # Open options accordion
        accordion_btn = page.locator("text=Curation & Output Preferences").first
        accordion_btn.click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(ARTIFACTS_DIR / "03_new_project_accordion_open.png"))

        report["steps"]["new_project"] = {
            "status": "PASS",
            "overflow": overflow_2["hasOverflow"]
        }

        # Submit form
        submit_btn = page.locator("button:has-text('Start Autonomous Clipping')")
        submit_btn.click()
        page.wait_for_url("**/stepper**", timeout=30000)

        print("\n=== STEP 3: Live Stepper Page ===")
        page.wait_for_selector("text=Agent Execution Telemetry Log", timeout=20000)
        page.wait_for_timeout(1500)
        overflow_3 = check_overflow(page, "Live Stepper Page")
        page.screenshot(path=str(ARTIFACTS_DIR / "04_stepper_in_progress.png"))

        # Wait for completion button
        view_grid_btn = page.locator("text=View Generated Shorts Grid")
        view_grid_btn.wait_for(state="visible", timeout=30000)
        page.screenshot(path=str(ARTIFACTS_DIR / "05_stepper_complete.png"))
        report["steps"]["live_stepper"] = {
            "status": "PASS",
            "overflow": overflow_3["hasOverflow"]
        }
        view_grid_btn.click()
        page.wait_for_timeout(1000)

        print("\n=== STEP 4: Results Grid Page (/projects/[id]) ===")
        page.wait_for_selector("h1:has-text('Curated 9:16 Shorts Grid')", timeout=20000)
        page.wait_for_timeout(1500)
        overflow_4 = check_overflow(page, "Results Grid Page")
        page.screenshot(path=str(ARTIFACTS_DIR / "06_results_grid.png"))

        # Expand Rubric Breakdown
        rubric_btn = page.locator("text=4-Pillar Virality Rubric").first
        if rubric_btn.is_visible():
            rubric_btn.click()
            page.wait_for_timeout(500)
            page.screenshot(path=str(ARTIFACTS_DIR / "07_rubric_expanded.png"))

        # Switch A/B headline tabs
        value_tab = page.locator("button:has-text('value')").first
        if not value_tab.is_visible():
            value_tab = page.locator("button:has-text('Value')").first
        if value_tab.is_visible():
            value_tab.click()
            page.wait_for_timeout(300)

        # Copy headline
        copy_btn = page.locator("button:has-text('Copy')").first
        if copy_btn.is_visible():
            copy_btn.click()
            page.wait_for_timeout(500)

        # Download from card
        download_btn = page.locator("button:has-text('Download MP4')").first
        if download_btn.is_visible():
            download_btn.click()
            page.wait_for_timeout(500)

        report["steps"]["results_grid"] = {
            "status": "PASS",
            "overflow": overflow_4["hasOverflow"]
        }

        # Navigate to Editor
        edit_btn = page.locator("text=Edit in Studio").first
        edit_btn.click()
        page.wait_for_url("**/editor/**", timeout=15000)

        print("\n=== STEP 5: Transcript Editor (/editor/[clipId]) ===")
        page.wait_for_selector("text=Transcript Video Trimmer Studio", timeout=20000)
        page.wait_for_timeout(1500)
        overflow_5 = check_overflow(page, "Transcript Editor Page")
        page.screenshot(path=str(ARTIFACTS_DIR / "08_editor_initial.png"))

        # Preview play/pause
        play_btn = page.locator("button svg.lucide-play").first
        if play_btn.is_visible():
            play_btn.click()
            page.wait_for_timeout(500)
            pause_btn = page.locator("button svg.lucide-pause").first
            if pause_btn.is_visible():
                pause_btn.click()

        # Click words in trimmer
        word_btn = page.locator("button:has-text('honored')").first
        if word_btn.is_visible():
            word_btn.click()
            page.wait_for_timeout(300)
        
        word_btn_2 = page.locator("button:has-text('commencement')").first
        if word_btn_2.is_visible():
            word_btn_2.click()
            page.wait_for_timeout(300)

        page.screenshot(path=str(ARTIFACTS_DIR / "09_editor_words_omitted.png"))

        # In/out points
        in_inputs = page.locator("input[type='number']")
        if in_inputs.count() > 0:
            in_inputs.first.fill("28.0")

        # Save & Re-render trim
        save_btn = page.locator("button:has-text('Save & Re-Render Trim')").first
        if save_btn.is_visible():
            save_btn.click()
            page.wait_for_timeout(1500)
            page.screenshot(path=str(ARTIFACTS_DIR / "10_editor_trim_saved.png"))

        # Download from editor
        dl_editor_btn = page.locator("button:has-text('Download')").first
        if dl_editor_btn.is_visible():
            dl_editor_btn.click()
            page.wait_for_timeout(500)

        report["steps"]["transcript_editor"] = {
            "status": "PASS",
            "overflow": overflow_5["hasOverflow"]
        }

        with open(ARTIFACTS_DIR / "report.json", "w") as f:
            json.dump(report, f, indent=2)

        print("\n=== TEST RUN COMPLETED SUCCESSFULLY ===")
        browser.close()

if __name__ == "__main__":
    run_test()
