from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


@contextmanager
def launch_browser(headless: bool, slow_mo_ms: int, output_dir: str):
    output_path = Path(output_dir)
    video_dir = output_path / "video"
    traces_dir = output_path / "traces"
    screenshots_dir = output_path / "screenshots"
    for directory in [video_dir, traces_dir, screenshots_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Use project-local Playwright browser binaries for reproducible runs.
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo_ms)
        context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            record_video_dir=str(video_dir),
            record_video_size={"width": 1440, "height": 960},
        )
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        try:
            yield browser, context, page
        finally:
            trace_path = traces_dir / "trace.zip"
            context.tracing.stop(path=str(trace_path))
            context.close()
            browser.close()
